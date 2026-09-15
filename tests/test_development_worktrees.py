from __future__ import annotations

import subprocess

import pytest

from reverend.development import (
    TaskState,
    WorktreeCollisionError,
    WorktreeStateError,
    branch_name_for_task,
    create_task,
    create_task_worktree,
    database,
    inspect_task_worktree,
    register_project,
    remove_task_worktree,
    transition_task,
)


def git(repo, *args):
    return subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            *args,
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )


def make_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    subprocess.run(
        [
            "git",
            "init",
            "-b",
            "main",
            str(repo),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    (repo / "README.md").write_text(
        "# Repository\n",
        encoding="utf-8",
    )

    git(
        repo,
        "add",
        "README.md",
    )

    git(
        repo,
        "-c",
        "user.name=Reverend Test",
        "-c",
        "user.email=reverend@example.invalid",
        "commit",
        "-m",
        "Initial commit",
    )

    return repo


def setup_task(tmp_path):
    repo = make_repo(
        tmp_path
    )

    context = database(
        tmp_path / "development.db"
    )
    connection = context.__enter__()

    project = register_project(
        connection,
        repo,
    )

    task = create_task(
        connection,
        project.id,
        title="Implement example feature",
        request="Implement feature",
    )

    task = transition_task(
        connection,
        task.id,
        TaskState.PREPARING,
    )

    return (
        repo,
        context,
        connection,
        task,
    )


def test_branch_name_is_deterministic():
    name = branch_name_for_task(
        "12345678-aaaa-bbbb-cccc-dddddddddddd",
        "Add Safe Worktrees!",
    )

    assert name == (
        "reverend/task-12345678-"
        "add-safe-worktrees"
    )


def test_create_worktree_uses_pinned_commit(
    tmp_path,
):
    (
        repo,
        context,
        connection,
        task,
    ) = setup_task(tmp_path)

    try:
        worktree = create_task_worktree(
            connection,
            task.id,
            root=tmp_path / "worktrees",
        )

        assert worktree.path.exists()
        assert (
            worktree.head_commit
            == task.base_commit
        )

        observed = git(
            worktree.path,
            "branch",
            "--show-current",
        ).stdout.strip()

        assert observed == (
            worktree.branch_name
        )

        main_head = git(
            repo,
            "rev-parse",
            "HEAD",
        ).stdout.strip()

        assert main_head == (
            task.base_commit
        )

    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_create_worktree_is_idempotent(
    tmp_path,
):
    (
        _,
        context,
        connection,
        task,
    ) = setup_task(tmp_path)

    try:
        first = create_task_worktree(
            connection,
            task.id,
            root=tmp_path / "worktrees",
        )

        second = create_task_worktree(
            connection,
            task.id,
            root=tmp_path / "worktrees",
        )

        assert first == second

    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_inspect_task_worktree(
    tmp_path,
):
    (
        _,
        context,
        connection,
        task,
    ) = setup_task(tmp_path)

    try:
        created = create_task_worktree(
            connection,
            task.id,
            root=tmp_path / "worktrees",
        )

        observed = inspect_task_worktree(
            connection,
            task.id,
        )

        assert observed == created

    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_worktree_requires_preparing_state(
    tmp_path,
):
    repo = make_repo(
        tmp_path
    )

    with database(
        tmp_path / "development.db"
    ) as connection:
        project = register_project(
            connection,
            repo,
        )

        task = create_task(
            connection,
            project.id,
            title="Wrong state",
            request="Wrong state",
        )

        with pytest.raises(
            WorktreeStateError
        ):
            create_task_worktree(
                connection,
                task.id,
                root=tmp_path / "worktrees",
            )


def test_existing_unregistered_branch_is_rejected(
    tmp_path,
):
    (
        repo,
        context,
        connection,
        task,
    ) = setup_task(tmp_path)

    try:
        branch = branch_name_for_task(
            task.id,
            task.title,
        )

        git(
            repo,
            "branch",
            branch,
            task.base_commit,
        )

        with pytest.raises(
            WorktreeCollisionError
        ):
            create_task_worktree(
                connection,
                task.id,
                root=tmp_path / "worktrees",
            )

    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_remove_worktree_preserves_branch_by_default(
    tmp_path,
):
    (
        repo,
        context,
        connection,
        task,
    ) = setup_task(tmp_path)

    try:
        worktree = create_task_worktree(
            connection,
            task.id,
            root=tmp_path / "worktrees",
        )

        remove_task_worktree(
            connection,
            task.id,
        )

        assert not worktree.path.exists()

        branches = git(
            repo,
            "branch",
            "--list",
            worktree.branch_name,
        ).stdout

        assert worktree.branch_name in branches

    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_remove_worktree_can_delete_branch(
    tmp_path,
):
    (
        repo,
        context,
        connection,
        task,
    ) = setup_task(tmp_path)

    try:
        worktree = create_task_worktree(
            connection,
            task.id,
            root=tmp_path / "worktrees",
        )

        remove_task_worktree(
            connection,
            task.id,
            force=True,
            delete_branch=True,
        )

        branches = git(
            repo,
            "branch",
            "--list",
            worktree.branch_name,
        ).stdout.strip()

        assert branches == ""

    finally:
        context.__exit__(
            None,
            None,
            None,
        )
