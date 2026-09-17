from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence


_BRANCH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")


class GitCommandError(RuntimeError):
    def __init__(self, command: Sequence[str], returncode: int, stderr: str) -> None:
        self.command = tuple(command)
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(
            f"git command failed ({returncode}): {' '.join(command)}\n{stderr.strip()}"
        )


@dataclass(frozen=True)
class WorktreeInfo:
    issue_number: int
    path: Path
    branch_name: str
    base_ref: str


Runner = Callable[..., subprocess.CompletedProcess[str]]


class WorktreeManager:
    """Deterministic Git operations owned by the controller, never by an LLM."""

    def __init__(
        self,
        repository_root: str | Path,
        *,
        runtime_root: str | Path | None = None,
        runner: Runner = subprocess.run,
    ) -> None:
        self.repository_root = Path(repository_root).resolve()
        if not (self.repository_root / ".git").exists():
            raise ValueError(f"not a git repository: {self.repository_root}")
        self.runtime_root = (
            Path(runtime_root).resolve()
            if runtime_root is not None
            else self.repository_root / ".autonomy" / "worktrees"
        )
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        self.runner = runner

    def _git(self, args: Sequence[str], *, cwd: Path | None = None) -> str:
        command = ["git", *args]
        completed = self.runner(
            command,
            cwd=str(cwd or self.repository_root),
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            raise GitCommandError(command, completed.returncode, completed.stderr)
        return completed.stdout.strip()

    @staticmethod
    def _validate_ref(value: str, *, label: str) -> str:
        if not value or not _BRANCH_RE.fullmatch(value):
            raise ValueError(f"unsafe {label}: {value!r}")
        if value.startswith("-") or ".." in value or value.endswith("/"):
            raise ValueError(f"unsafe {label}: {value!r}")
        return value

    def head_commit(self, ref: str = "HEAD") -> str:
        self._validate_ref(ref, label="ref")
        value = self._git(["rev-parse", "--verify", f"{ref}^{{commit}}"])
        if not re.fullmatch(r"[0-9a-f]{40}", value):
            raise GitCommandError(["git", "rev-parse", ref], 0, "unexpected commit id")
        return value

    def assert_clean(self) -> None:
        if self._git(["status", "--porcelain"]):
            raise RuntimeError("repository working tree is not clean")

    def create_issue_worktree(
        self,
        *,
        issue_number: int,
        base_ref: str,
        branch_name: str,
    ) -> WorktreeInfo:
        if issue_number <= 0:
            raise ValueError("issue_number must be positive")
        self._validate_ref(base_ref, label="base_ref")
        self._validate_ref(branch_name, label="branch_name")
        base_commit = self.head_commit(base_ref)
        path = (self.runtime_root / f"issue-{issue_number}").resolve()
        try:
            path.relative_to(self.runtime_root.resolve())
        except ValueError as exc:
            raise ValueError("worktree escaped runtime root") from exc
        if path.exists():
            raise FileExistsError(path)

        self._git(
            ["worktree", "add", "--no-track", "-b", branch_name, str(path), base_commit]
        )
        return WorktreeInfo(
            issue_number=issue_number,
            path=path,
            branch_name=branch_name,
            base_ref=base_commit,
        )

    def remove_worktree(self, worktree: WorktreeInfo, *, force: bool = False) -> None:
        args = ["worktree", "remove"]
        if force:
            args.append("--force")
        args.append(str(worktree.path))
        self._git(args)
        self._git(["worktree", "prune"])

    def has_meaningful_diff(self, worktree_path: str | Path, base_ref: str) -> bool:
        path = Path(worktree_path).resolve()
        self._validate_ref(base_ref, label="base_ref")
        tracked = self._git(["diff", "--name-only", base_ref, "--"], cwd=path)
        untracked = self._git(["ls-files", "--others", "--exclude-standard"], cwd=path)
        return bool(tracked.strip() or untracked.strip())

    def changed_files(self, worktree_path: str | Path, base_ref: str) -> tuple[str, ...]:
        path = Path(worktree_path).resolve()
        self._validate_ref(base_ref, label="base_ref")
        tracked = self._git(["diff", "--name-only", base_ref, "--"], cwd=path).splitlines()
        untracked = self._git(["ls-files", "--others", "--exclude-standard"], cwd=path).splitlines()
        return tuple(dict.fromkeys(item for item in [*tracked, *untracked] if item))
