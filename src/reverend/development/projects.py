"""Git repository discovery and persistent project registration."""

from __future__ import annotations

import sqlite3
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

from .database import transaction
from .models import TrustMode


class ProjectRegistryError(RuntimeError):
    """Base project-registry error."""


class RepositoryNotFoundError(ProjectRegistryError):
    """Raised when a requested repository path does not exist."""


class NotGitRepositoryError(ProjectRegistryError):
    """Raised when a path is not inside a usable Git repository."""


class GitInspectionError(ProjectRegistryError):
    """Raised when Git repository inspection fails."""


@dataclass(frozen=True)
class RepositorySnapshot:
    """Live repository state observed from Git."""

    root: Path
    real_root: Path
    name: str
    current_branch: str | None
    head_commit: str
    default_branch: str | None
    origin_url: str | None
    is_dirty: bool


@dataclass(frozen=True)
class ProjectRecord:
    """Persistent Reverend project registration."""

    id: str
    name: str
    repo_path: str
    repo_real_path: str
    default_branch: str | None
    trust_mode: TrustMode
    created_at: str
    updated_at: str


def _git(
    path: Path,
    *args: str,
    check: bool = True,
    timeout: float = 10.0,
) -> subprocess.CompletedProcess[str]:
    """Run Git without invoking a shell."""

    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(path),
                *args,
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except (
        OSError,
        subprocess.TimeoutExpired,
    ) as exc:
        raise GitInspectionError(
            f"Unable to run Git for {path}: {exc}"
        ) from exc

    if check and result.returncode != 0:
        detail = (
            result.stderr.strip()
            or result.stdout.strip()
            or f"exit code {result.returncode}"
        )

        raise GitInspectionError(
            f"Git inspection failed for {path}: {detail}"
        )

    return result


def _optional_git(
    path: Path,
    *args: str,
) -> str | None:
    result = _git(
        path,
        *args,
        check=False,
    )

    if result.returncode != 0:
        return None

    value = result.stdout.strip()

    return value or None


def _default_branch(
    root: Path,
    current_branch: str | None,
) -> str | None:
    """Resolve the repository's default branch conservatively."""

    origin_head = _optional_git(
        root,
        "symbolic-ref",
        "--quiet",
        "--short",
        "refs/remotes/origin/HEAD",
    )

    if origin_head:
        prefix = "origin/"

        if origin_head.startswith(prefix):
            return origin_head[
                len(prefix):
            ]

        return origin_head

    for candidate in (
        "main",
        "master",
    ):
        result = _git(
            root,
            "show-ref",
            "--verify",
            "--quiet",
            f"refs/heads/{candidate}",
            check=False,
        )

        if result.returncode == 0:
            return candidate

    return current_branch


def inspect_repository(
    path: str | Path,
) -> RepositorySnapshot:
    """Inspect and canonicalize a working Git repository."""

    requested = Path(path).expanduser()

    if not requested.exists():
        raise RepositoryNotFoundError(
            f"Repository path does not exist: {requested}"
        )

    if not requested.is_dir():
        raise RepositoryNotFoundError(
            f"Repository path is not a directory: {requested}"
        )

    inside = _git(
        requested,
        "rev-parse",
        "--is-inside-work-tree",
        check=False,
    )

    if (
        inside.returncode != 0
        or inside.stdout.strip() != "true"
    ):
        raise NotGitRepositoryError(
            f"Not a Git working tree: {requested}"
        )

    bare = _optional_git(
        requested,
        "rev-parse",
        "--is-bare-repository",
    )

    if bare == "true":
        raise NotGitRepositoryError(
            f"Bare repositories are not supported: {requested}"
        )

    root_text = _optional_git(
        requested,
        "rev-parse",
        "--show-toplevel",
    )

    if not root_text:
        raise GitInspectionError(
            f"Git did not report a repository root for {requested}"
        )

    root = Path(root_text)
    real_root = root.resolve()

    head_commit = _optional_git(
        root,
        "rev-parse",
        "HEAD",
    )

    if not head_commit:
        raise GitInspectionError(
            "Repository has no HEAD commit. "
            "Reverend currently requires at least one commit."
        )

    current_branch = _optional_git(
        root,
        "symbolic-ref",
        "--quiet",
        "--short",
        "HEAD",
    )

    origin_url = _optional_git(
        root,
        "remote",
        "get-url",
        "origin",
    )

    status = _git(
        root,
        "status",
        "--porcelain",
        "--untracked-files=normal",
    )

    return RepositorySnapshot(
        root=root,
        real_root=real_root,
        name=root.name,
        current_branch=current_branch,
        head_commit=head_commit,
        default_branch=_default_branch(
            root,
            current_branch,
        ),
        origin_url=origin_url,
        is_dirty=bool(
            status.stdout.strip()
        ),
    )


def project_id_for_path(
    real_root: str | Path,
) -> str:
    """Return a deterministic ID for one canonical local repository."""

    canonical = str(
        Path(real_root).resolve()
    )

    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"reverend-project:{canonical}",
        )
    )


def _row_to_project(
    row: sqlite3.Row,
) -> ProjectRecord:
    return ProjectRecord(
        id=row["id"],
        name=row["name"],
        repo_path=row["repo_path"],
        repo_real_path=row[
            "repo_real_path"
        ],
        default_branch=row[
            "default_branch"
        ],
        trust_mode=TrustMode(
            row["trust_mode"]
        ),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def register_project(
    connection: sqlite3.Connection,
    path: str | Path,
    *,
    name: str | None = None,
    trust_mode: TrustMode = (
        TrustMode.TRUSTED_REPO
    ),
) -> ProjectRecord:
    """Register or refresh one Git repository."""

    snapshot = inspect_repository(
        path
    )

    project_id = project_id_for_path(
        snapshot.real_root
    )

    project_name = (
        name.strip()
        if name is not None
        else snapshot.name
    )

    if not project_name:
        raise ProjectRegistryError(
            "Project name cannot be empty."
        )

    existing = connection.execute(
        """
        SELECT trust_mode
        FROM projects
        WHERE id = ?
        """,
        (project_id,),
    ).fetchone()

    if (
        existing is not None
        and TrustMode(existing["trust_mode"])
        is not trust_mode
    ):
        raise ProjectRegistryError(
            "Project trust mode cannot change during registration. "
            "Use an explicit trust-management action."
        )

    with transaction(connection):
        connection.execute(
            """
            INSERT INTO projects (
                id,
                name,
                repo_path,
                repo_real_path,
                default_branch,
                trust_mode
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id)
            DO UPDATE SET
                name = excluded.name,
                repo_path = excluded.repo_path,
                repo_real_path = excluded.repo_real_path,
                default_branch = excluded.default_branch,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                project_id,
                project_name,
                str(snapshot.root),
                str(snapshot.real_root),
                snapshot.default_branch,
                trust_mode.value,
            ),
        )

    project = get_project(
        connection,
        project_id,
    )

    if project is None:
        raise ProjectRegistryError(
            "Project registration succeeded "
            "but the project could not be read back."
        )

    return project


def get_project(
    connection: sqlite3.Connection,
    project_id: str,
) -> ProjectRecord | None:
    row = connection.execute(
        """
        SELECT
            id,
            name,
            repo_path,
            repo_real_path,
            default_branch,
            trust_mode,
            created_at,
            updated_at
        FROM projects
        WHERE id = ?
        """,
        (
            project_id,
        ),
    ).fetchone()

    if row is None:
        return None

    return _row_to_project(row)


def get_project_by_path(
    connection: sqlite3.Connection,
    path: str | Path,
) -> ProjectRecord | None:
    snapshot = inspect_repository(
        path
    )

    row = connection.execute(
        """
        SELECT
            id,
            name,
            repo_path,
            repo_real_path,
            default_branch,
            trust_mode,
            created_at,
            updated_at
        FROM projects
        WHERE repo_real_path = ?
        """,
        (
            str(snapshot.real_root),
        ),
    ).fetchone()

    if row is None:
        return None

    return _row_to_project(row)


def list_projects(
    connection: sqlite3.Connection,
) -> list[ProjectRecord]:
    rows = connection.execute(
        """
        SELECT
            id,
            name,
            repo_path,
            repo_real_path,
            default_branch,
            trust_mode,
            created_at,
            updated_at
        FROM projects
        ORDER BY name COLLATE NOCASE, id
        """
    ).fetchall()

    return [
        _row_to_project(row)
        for row in rows
    ]
