"""Deterministic repository intelligence for Reverend."""

from __future__ import annotations

import sqlite3
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from reverend.development import (
    TaskNotFoundError,
    get_task,
    inspect_repository,
)


DEFAULT_MAX_FILES = 50_000
DEFAULT_HISTORY_LIMIT = 20


class RepositoryIntelligenceError(RuntimeError):
    """Base repository-intelligence error."""


class RepositoryTooLargeError(
    RepositoryIntelligenceError
):
    """Raised instead of silently truncating a repository scan."""


class RepositoryGitError(
    RepositoryIntelligenceError
):
    """Raised when deterministic Git inspection fails."""


@dataclass(frozen=True)
class RepositoryFile:
    path: str
    size_bytes: int
    language: str | None
    is_test: bool
    is_symlink: bool


@dataclass(frozen=True)
class GitCommit:
    commit: str
    subject: str


@dataclass(frozen=True)
class RepositoryProfile:
    root: Path
    head_commit: str
    current_branch: str | None
    default_branch: str | None
    origin_url: str | None
    is_dirty: bool
    files: tuple[RepositoryFile, ...]
    languages: tuple[tuple[str, int], ...]
    build_systems: tuple[str, ...]
    test_files: tuple[str, ...]
    changed_files: tuple[str, ...]
    recent_commits: tuple[GitCommit, ...]

    @property
    def file_count(self) -> int:
        return len(self.files)

    @property
    def test_count(self) -> int:
        return len(self.test_files)


_EXTENSION_LANGUAGES = {
    ".py": "Python",
    ".pyi": "Python",
    ".c": "C",
    ".h": "C/C++ Header",
    ".cc": "C++",
    ".cpp": "C++",
    ".cxx": "C++",
    ".hh": "C/C++ Header",
    ".hpp": "C/C++ Header",
    ".hxx": "C/C++ Header",
    ".cu": "CUDA",
    ".cuh": "CUDA",
    ".rs": "Rust",
    ".go": "Go",
    ".java": "Java",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".cs": "C#",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".scala": "Scala",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".ps1": "PowerShell",
    ".sql": "SQL",
    ".md": "Markdown",
    ".rst": "reStructuredText",
    ".json": "JSON",
    ".toml": "TOML",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".cmake": "CMake",
}


_SPECIAL_LANGUAGES = {
    "CMakeLists.txt": "CMake",
    "Makefile": "Make",
    "GNUmakefile": "Make",
    "Dockerfile": "Dockerfile",
}


def _git(
    root: Path,
    *args: str,
    timeout: float = 20.0,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                *args,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except (
        OSError,
        subprocess.TimeoutExpired,
    ) as exc:
        raise RepositoryGitError(
            f"Unable to run Git for {root}: {exc}"
        ) from exc

    if check and result.returncode != 0:
        stderr = result.stderr.decode(
            "utf-8",
            errors="replace",
        ).strip()

        stdout = result.stdout.decode(
            "utf-8",
            errors="replace",
        ).strip()

        detail = (
            stderr
            or stdout
            or f"exit code {result.returncode}"
        )

        raise RepositoryGitError(
            f"Git inspection failed: {detail}"
        )

    return result


def _nul_paths(
    raw: bytes,
) -> list[str]:
    if not raw:
        return []

    return [
        item.decode(
            "utf-8",
            errors="surrogateescape",
        )
        for item in raw.split(b"\0")
        if item
    ]


def _language_for(
    relative_path: str,
) -> str | None:
    path = Path(relative_path)

    if path.name in _SPECIAL_LANGUAGES:
        return _SPECIAL_LANGUAGES[
            path.name
        ]

    return _EXTENSION_LANGUAGES.get(
        path.suffix.lower()
    )


def _is_test_path(
    relative_path: str,
) -> bool:
    path = Path(relative_path)

    parts = {
        part.lower()
        for part in path.parts
    }

    if parts & {
        "test",
        "tests",
        "__tests__",
        "spec",
        "specs",
    }:
        return True

    name = path.name.lower()

    patterns = (
        "test_",
        "_test.py",
        "_test.cpp",
        "_test.cc",
        "_test.cxx",
        "_test.c",
        ".test.js",
        ".test.jsx",
        ".test.ts",
        ".test.tsx",
        ".spec.js",
        ".spec.jsx",
        ".spec.ts",
        ".spec.tsx",
    )

    return (
        name.startswith("test_")
        or any(
            name.endswith(pattern)
            for pattern in patterns[1:]
        )
    )


def _detect_build_systems(
    paths: set[str],
) -> tuple[str, ...]:
    names = {
        Path(path).name
        for path in paths
    }

    systems: set[str] = set()

    if names & {
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
    }:
        systems.add("python")

    if "CMakeLists.txt" in names:
        systems.add("cmake")

    if names & {
        "Makefile",
        "GNUmakefile",
    }:
        systems.add("make")

    if "package.json" in names:
        systems.add("node")

    if "Cargo.toml" in names:
        systems.add("cargo")

    if "go.mod" in names:
        systems.add("go")

    if names & {
        "build.gradle",
        "build.gradle.kts",
    }:
        systems.add("gradle")

    if "pom.xml" in names:
        systems.add("maven")

    if "meson.build" in names:
        systems.add("meson")

    return tuple(
        sorted(systems)
    )


def _changed_files(
    root: Path,
) -> tuple[str, ...]:
    paths: set[str] = set()

    for args in (
        (
            "diff",
            "--name-only",
            "-z",
        ),
        (
            "diff",
            "--cached",
            "--name-only",
            "-z",
        ),
        (
            "ls-files",
            "--others",
            "--exclude-standard",
            "-z",
        ),
    ):
        result = _git(
            root,
            *args,
        )

        paths.update(
            _nul_paths(
                result.stdout
            )
        )

    return tuple(
        sorted(paths)
    )


def _recent_commits(
    root: Path,
    limit: int,
) -> tuple[GitCommit, ...]:
    result = _git(
        root,
        "log",
        f"-n{limit}",
        "--format=%H%x1f%s%x1e",
    )

    text = result.stdout.decode(
        "utf-8",
        errors="replace",
    )

    commits: list[GitCommit] = []

    for record in text.split("\x1e"):
        record = record.strip()

        if not record:
            continue

        commit, separator, subject = (
            record.partition("\x1f")
        )

        if not separator:
            continue

        commits.append(
            GitCommit(
                commit=commit.strip(),
                subject=subject.strip(),
            )
        )

    return tuple(commits)


def scan_repository(
    path: str | Path,
    *,
    max_files: int = DEFAULT_MAX_FILES,
    history_limit: int = DEFAULT_HISTORY_LIMIT,
) -> RepositoryProfile:
    """Build a deterministic read-only profile of a Git repository."""

    if max_files < 1:
        raise ValueError(
            "max_files must be positive"
        )

    if history_limit < 0:
        raise ValueError(
            "history_limit cannot be negative"
        )

    snapshot = inspect_repository(
        path
    )

    root = snapshot.real_root

    result = _git(
        root,
        "ls-files",
        "-z",
        "--cached",
        "--others",
        "--exclude-standard",
    )

    relative_paths = sorted(
        set(
            _nul_paths(
                result.stdout
            )
        )
    )

    relative_paths = [p for p in relative_paths if not p.startswith('.reverend-build/')]

    if len(relative_paths) > max_files:
        raise RepositoryTooLargeError(
            f"Repository contains "
            f"{len(relative_paths)} files; "
            f"configured maximum is {max_files}."
        )

    files: list[RepositoryFile] = []
    language_counts: Counter[str] = Counter()
    test_files: list[str] = []

    for relative_path in relative_paths:
        absolute = (
            root
            / relative_path
        )

        try:
            stat = absolute.lstat()
        except FileNotFoundError:
            continue

        language = _language_for(
            relative_path
        )

        is_test = _is_test_path(
            relative_path
        )

        item = RepositoryFile(
            path=relative_path,
            size_bytes=stat.st_size,
            language=language,
            is_test=is_test,
            is_symlink=absolute.is_symlink(),
        )

        files.append(item)

        if language is not None:
            language_counts[
                language
            ] += 1

        if is_test:
            test_files.append(
                relative_path
            )

    languages = tuple(
        sorted(
            language_counts.items(),
            key=lambda item: (
                -item[1],
                item[0],
            ),
        )
    )

    paths = {
        item.path
        for item in files
    }

    commits = (
        _recent_commits(
            root,
            history_limit,
        )
        if history_limit
        else ()
    )

    return RepositoryProfile(
        root=root,
        head_commit=snapshot.head_commit,
        current_branch=(
            snapshot.current_branch
        ),
        default_branch=(
            snapshot.default_branch
        ),
        origin_url=snapshot.origin_url,
        is_dirty=snapshot.is_dirty,
        files=tuple(files),
        languages=languages,
        build_systems=(
            _detect_build_systems(
                paths
            )
        ),
        test_files=tuple(
            sorted(test_files)
        ),
        changed_files=_changed_files(
            root
        ),
        recent_commits=commits,
    )


def scan_task_repository(
    connection: sqlite3.Connection,
    task_id: str,
    *,
    max_files: int = DEFAULT_MAX_FILES,
    history_limit: int = DEFAULT_HISTORY_LIMIT,
) -> RepositoryProfile:
    """Profile a task's isolated worktree."""

    task = get_task(
        connection,
        task_id,
    )

    if task is None:
        raise TaskNotFoundError(
            f"Unknown task: {task_id}"
        )

    if not task.worktree_path:
        raise RepositoryIntelligenceError(
            "Task has no isolated worktree."
        )

    return scan_repository(
        task.worktree_path,
        max_files=max_files,
        history_limit=history_limit,
    )
