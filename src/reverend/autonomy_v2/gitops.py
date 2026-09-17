from __future__ import annotations

import difflib
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


class DiffTooLarge(RuntimeError):
    pass


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

    def worktree_head(self, worktree_path: str | Path) -> str:
        path = Path(worktree_path).resolve()
        value = self._git(["rev-parse", "HEAD"], cwd=path)
        if not re.fullmatch(r"[0-9a-f]{40}", value):
            raise GitCommandError(["git", "rev-parse", "HEAD"], 0, "unexpected commit id")
        return value

    def worktree_status(self, worktree_path: str | Path) -> str:
        return self._git(["status", "--porcelain"], cwd=Path(worktree_path).resolve())

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

    def delete_branch(self, branch_name: str, *, force: bool = False) -> None:
        self._validate_ref(branch_name, label="branch_name")
        self._git(["branch", "-D" if force else "-d", branch_name])

    def has_meaningful_diff(self, worktree_path: str | Path, base_ref: str) -> bool:
        return bool(self.changed_files(worktree_path, base_ref))

    def changed_files(self, worktree_path: str | Path, base_ref: str) -> tuple[str, ...]:
        path = Path(worktree_path).resolve()
        self._validate_ref(base_ref, label="base_ref")
        tracked = self._git(["diff", "--name-only", base_ref, "--"], cwd=path).splitlines()
        untracked = self._git(["ls-files", "--others", "--exclude-standard"], cwd=path).splitlines()
        return tuple(dict.fromkeys(item for item in [*tracked, *untracked] if item))

    def diff_text(
        self,
        worktree_path: str | Path,
        base_ref: str,
        *,
        max_chars: int = 120_000,
        max_untracked_file_bytes: int = 256_000,
    ) -> str:
        path = Path(worktree_path).resolve()
        self._validate_ref(base_ref, label="base_ref")
        diff = self._git(
            ["diff", "--no-ext-diff", "--unified=40", base_ref, "--"], cwd=path
        )
        chunks = [diff] if diff else []

        untracked = self._git(
            ["ls-files", "--others", "--exclude-standard"], cwd=path
        ).splitlines()
        for relative in untracked:
            file_path = (path / relative).resolve()
            try:
                file_path.relative_to(path)
            except ValueError as exc:
                raise RuntimeError(f"untracked path escaped worktree: {relative}") from exc
            if file_path.stat().st_size > max_untracked_file_bytes:
                chunks.append(
                    f"diff --git a/{relative} b/{relative}\n"
                    f"[untracked file omitted: {file_path.stat().st_size} bytes]\n"
                )
                continue
            try:
                text = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                chunks.append(
                    f"diff --git a/{relative} b/{relative}\n[untracked binary file omitted]\n"
                )
                continue
            chunks.append(
                "".join(
                    difflib.unified_diff(
                        [],
                        text.splitlines(keepends=True),
                        fromfile="/dev/null",
                        tofile=f"b/{relative}",
                        n=40,
                    )
                )
            )

        combined = "\n".join(chunk for chunk in chunks if chunk)
        if len(combined) > max_chars:
            raise DiffTooLarge(
                f"review diff is {len(combined)} characters; limit is {max_chars}"
            )
        return combined

    def commit_changes(
        self,
        worktree_path: str | Path,
        *,
        message: str,
        base_ref: str | None = None,
        author_name: str = "Reverend Autonomy",
        author_email: str = "autonomy@reverend.local",
    ) -> str:
        path = Path(worktree_path).resolve()
        if not message.strip():
            raise ValueError("commit message must not be empty")

        status = self.worktree_status(path)
        if not status:
            head = self.worktree_head(path)
            if base_ref is not None:
                self._validate_ref(base_ref, label="base_ref")
                base = self._git(["rev-parse", "--verify", f"{base_ref}^{{commit}}"], cwd=path)
                if head != base:
                    return head
            raise RuntimeError("no controller-owned changes are available to commit")

        self._git(["add", "-A"], cwd=path)
        self._git(
            [
                "-c",
                f"user.name={author_name}",
                "-c",
                f"user.email={author_email}",
                "commit",
                "-m",
                message,
            ],
            cwd=path,
        )
        return self.worktree_head(path)

    def fast_forward_merge(
        self,
        integration_worktree: str | Path,
        branch_name: str,
    ) -> str:
        self._validate_ref(branch_name, label="branch_name")
        path = Path(integration_worktree).resolve()
        if self.worktree_status(path):
            raise RuntimeError("integration worktree is dirty")
        self._git(["merge", "--ff-only", branch_name], cwd=path)
        return self.worktree_head(path)
