"""Isolated Git worktrees for Reverend development tasks."""

from __future__ import annotations

import re
import shutil
import sqlite3
import subprocess
from dataclasses import dataclass
from pathlib import Path

from reverend.config import DATA_ROOT

from .database import transaction
from .models import TaskState
from .projects import (
    get_project,
    inspect_repository,
)
from .tasks import (
    TaskNotFoundError,
    TaskServiceError,
    get_task,
)


DEFAULT_WORKTREE_ROOT = (
    DATA_ROOT / "worktrees"
)


class WorktreeError(RuntimeError):
    """Base Reverend worktree error."""


class WorktreeStateError(WorktreeError):
    """Raised when task state forbids a worktree operation."""


class WorktreeCollisionError(WorktreeError):
    """Raised when a path or Git branch is already occupied."""


class WorktreeGitError(WorktreeError):
    """Raised when a Git worktree command fails."""


@dataclass(frozen=True)
class WorktreeRecord:
    task_id: str
    project_id: str
    branch_name: str
    path: Path
    base_commit: str
    head_commit: str


def _git(
    repo: Path,
    *args: str,
    check: bool = True,
    timeout: float = 60.0,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                *args,
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
        )
    except (
        OSError,
        subprocess.TimeoutExpired,
    ) as exc:
        raise WorktreeGitError(
            f"Unable to run Git: {exc}"
        ) from exc

    if check and result.returncode != 0:
        detail = (
            result.stderr.strip()
            or result.stdout.strip()
            or f"exit code {result.returncode}"
        )

        raise WorktreeGitError(
            f"Git worktree operation failed: {detail}"
        )

    return result


def _slug(value: str) -> str:
    value = value.strip().lower()

    value = re.sub(
        r"[^a-z0-9]+",
        "-",
        value,
    )

    value = value.strip("-")

    if not value:
        return "task"

    return value[:48].rstrip("-")


def branch_name_for_task(
    task_id: str,
    title: str,
) -> str:
    short_id = (
        task_id
        .replace("-", "")[:8]
    )

    return (
        f"reverend/task-{short_id}-"
        f"{_slug(title)}"
    )


def worktree_path_for_task(
    project_id: str,
    task_id: str,
    *,
    root: str | Path | None = None,
) -> Path:
    base = (
        Path(root)
        if root is not None
        else DEFAULT_WORKTREE_ROOT
    )

    return (
        base
        / project_id
        / task_id
    )


def _branch_exists(
    repo: Path,
    branch_name: str,
) -> bool:
    result = _git(
        repo,
        "show-ref",
        "--verify",
        "--quiet",
        f"refs/heads/{branch_name}",
        check=False,
    )

    return result.returncode == 0


def _head_commit(
    repo: Path,
) -> str:
    result = _git(
        repo,
        "rev-parse",
        "HEAD",
    )

    return result.stdout.strip()


def inspect_task_worktree(
    connection: sqlite3.Connection,
    task_id: str,
) -> WorktreeRecord | None:
    task = get_task(
        connection,
        task_id,
    )

    if task is None:
        raise TaskNotFoundError(
            f"Unknown task: {task_id}"
        )

    if (
        task.worktree_path is None
        or task.branch_name is None
        or task.base_commit is None
    ):
        return None

    path = Path(
        task.worktree_path
    )

    if not path.exists():
        raise WorktreeStateError(
            "Task records a worktree that "
            f"does not exist: {path}"
        )

    snapshot = inspect_repository(
        path
    )

    if snapshot.real_root != path.resolve():
        raise WorktreeStateError(
            "Recorded task worktree does not "
            "resolve to its own Git worktree root."
        )

    if snapshot.current_branch != (
        task.branch_name
    ):
        raise WorktreeStateError(
            "Task worktree branch mismatch: "
            f"expected {task.branch_name!r}, "
            f"found {snapshot.current_branch!r}"
        )

    return WorktreeRecord(
        task_id=task.id,
        project_id=task.project_id,
        branch_name=task.branch_name,
        path=path,
        base_commit=task.base_commit,
        head_commit=snapshot.head_commit,
    )


def create_task_worktree(
    connection: sqlite3.Connection,
    task_id: str,
    *,
    root: str | Path | None = None,
) -> WorktreeRecord:
    """Create one isolated branch/worktree from the pinned task commit."""

    task = get_task(
        connection,
        task_id,
    )

    if task is None:
        raise TaskNotFoundError(
            f"Unknown task: {task_id}"
        )

    if task.state != TaskState.PREPARING:
        raise WorktreeStateError(
            "Task must be in PREPARING state "
            "before creating its worktree."
        )

    if task.base_commit is None:
        raise WorktreeStateError(
            "Task has no pinned base commit."
        )

    existing = inspect_task_worktree(
        connection,
        task_id,
    )

    if existing is not None:
        return existing

    project = get_project(
        connection,
        task.project_id,
    )

    if project is None:
        raise TaskServiceError(
            f"Task project disappeared: "
            f"{task.project_id}"
        )

    repo = Path(
        project.repo_real_path
    )

    branch_name = branch_name_for_task(
        task.id,
        task.title,
    )

    path = worktree_path_for_task(
        task.project_id,
        task.id,
        root=root,
    )

    if path.exists():
        if any(path.iterdir()):
            raise WorktreeCollisionError(
                f"Worktree path already exists "
                f"and is not empty: {path}"
            )

        path.rmdir()

    if _branch_exists(
        repo,
        branch_name,
    ):
        raise WorktreeCollisionError(
            f"Task branch already exists but "
            f"is not registered: {branch_name}"
        )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        _git(
            repo,
            "worktree",
            "add",
            "-b",
            branch_name,
            str(path),
            task.base_commit,
            timeout=120.0,
        )
    except BaseException:
        if (
            path.exists()
            and not any(path.iterdir())
        ):
            path.rmdir()

        raise

    try:
        observed_head = _head_commit(
            path
        )

        if observed_head != task.base_commit:
            raise WorktreeStateError(
                "New worktree did not start "
                "from the pinned task commit."
            )

        with transaction(connection):
            connection.execute(
                """
                UPDATE tasks
                SET
                    branch_name = ?,
                    worktree_path = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    branch_name,
                    str(path),
                    task.id,
                ),
            )

    except BaseException:
        _git(
            repo,
            "worktree",
            "remove",
            "--force",
            str(path),
            check=False,
        )

        _git(
            repo,
            "branch",
            "-D",
            branch_name,
            check=False,
        )

        raise

    return WorktreeRecord(
        task_id=task.id,
        project_id=task.project_id,
        branch_name=branch_name,
        path=path,
        base_commit=task.base_commit,
        head_commit=observed_head,
    )


def remove_task_worktree(
    connection: sqlite3.Connection,
    task_id: str,
    *,
    force: bool = False,
    delete_branch: bool = False,
) -> None:
    """Remove a task worktree while preserving its branch by default."""

    task = get_task(
        connection,
        task_id,
    )

    if task is None:
        raise TaskNotFoundError(
            f"Unknown task: {task_id}"
        )

    if (
        task.worktree_path is None
        and task.branch_name is None
    ):
        return

    project = get_project(
        connection,
        task.project_id,
    )

    if project is None:
        raise TaskServiceError(
            f"Task project disappeared: "
            f"{task.project_id}"
        )

    repo = Path(
        project.repo_real_path
    )

    path = (
        Path(task.worktree_path)
        if task.worktree_path
        else None
    )

    if path is not None and path.exists():
        args = [
            "worktree",
            "remove",
        ]

        if force:
            args.append(
                "--force"
            )

        args.append(
            str(path)
        )

        _git(
            repo,
            *args,
            timeout=120.0,
        )

    _git(
        repo,
        "worktree",
        "prune",
        check=False,
    )

    if (
        delete_branch
        and task.branch_name
        and _branch_exists(
            repo,
            task.branch_name,
        )
    ):
        flag = (
            "-D"
            if force
            else "-d"
        )

        _git(
            repo,
            "branch",
            flag,
            task.branch_name,
        )

    with transaction(connection):
        connection.execute(
            """
            UPDATE tasks
            SET
                worktree_path = NULL,
                branch_name = CASE
                    WHEN ? THEN NULL
                    ELSE branch_name
                END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                1 if delete_branch else 0,
                task.id,
            ),
        )

    if (
        path is not None
        and path.exists()
        and force
    ):
        shutil.rmtree(
            path,
            ignore_errors=True,
        )
