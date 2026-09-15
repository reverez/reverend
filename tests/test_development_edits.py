from __future__ import annotations

import subprocess

import pytest

import reverend.development.edits as edits_module
from reverend.development import (
    TaskState,
    create_task,
    create_task_worktree,
    database,
    register_project,
    transition_task,
)
from reverend.development.edits import (
    EditApplyError,
    EditConflictError,
    EditLimitError,
    EditPathError,
    EditProposal,
    apply_edits,
    hash_file,
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
    repo = (
        tmp_path
        / "repo"
    )
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
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    path = (
        repo
        / "src"
        / "example.py"
    )

    path.parent.mkdir(
        parents=True
    )

    path.write_text(
        "value = 1\n",
        encoding="utf-8",
    )

    git(
        repo,
        "add",
        ".",
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
        tmp_path
        / "development.db"
    )

    connection = (
        context.__enter__()
    )

    project = register_project(
        connection,
        repo,
    )

    task = create_task(
        connection,
        project.id,
        title="Edit task",
        request="Safely edit repository",
    )

    task = transition_task(
        connection,
        task.id,
        TaskState.PREPARING,
    )

    worktree = create_task_worktree(
        connection,
        task.id,
        root=(
            tmp_path
            / "worktrees"
        ),
    )

    task = transition_task(
        connection,
        task.id,
        TaskState.RUNNING,
    )

    return (
        context,
        connection,
        task,
        worktree,
    )


def test_create_file(
    tmp_path,
):
    (
        context,
        connection,
        task,
        worktree,
    ) = setup_task(tmp_path)

    try:
        result = apply_edits(
            connection,
            task.id,
            [
                EditProposal(
                    path="src/new.py",
                    action="create",
                    content="answer = 42\n",
                )
            ],
        )

        assert (
            worktree.path
            / "src/new.py"
        ).read_text(
            encoding="utf-8"
        ) == "answer = 42\n"

        assert (
            "src/new.py"
            in result.diff
        )

    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_replace_requires_matching_hash(
    tmp_path,
):
    (
        context,
        connection,
        task,
        worktree,
    ) = setup_task(tmp_path)

    try:
        path = (
            worktree.path
            / "src/example.py"
        )

        before = hash_file(
            path
        )

        result = apply_edits(
            connection,
            task.id,
            [
                EditProposal(
                    path="src/example.py",
                    action="replace",
                    expected_sha256=before,
                    content="value = 2\n",
                )
            ],
        )

        assert (
            path.read_text(
                encoding="utf-8"
            )
            == "value = 2\n"
        )

        assert (
            result.edits[0]
            .before_sha256
            == before
        )

        assert (
            result.edits[0]
            .after_sha256
            == hash_file(path)
        )

    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_stale_hash_rejected_without_mutation(
    tmp_path,
):
    (
        context,
        connection,
        task,
        worktree,
    ) = setup_task(tmp_path)

    try:
        path = (
            worktree.path
            / "src/example.py"
        )

        original = (
            path.read_text(
                encoding="utf-8"
            )
        )

        with pytest.raises(
            EditConflictError
        ):
            apply_edits(
                connection,
                task.id,
                [
                    EditProposal(
                        path="src/example.py",
                        action="replace",
                        expected_sha256=(
                            "0" * 64
                        ),
                        content="value = 9\n",
                    )
                ],
            )

        assert (
            path.read_text(
                encoding="utf-8"
            )
            == original
        )

    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_delete_requires_matching_hash(
    tmp_path,
):
    (
        context,
        connection,
        task,
        worktree,
    ) = setup_task(tmp_path)

    try:
        path = (
            worktree.path
            / "src/example.py"
        )

        digest = hash_file(
            path
        )

        result = apply_edits(
            connection,
            task.id,
            [
                EditProposal(
                    path="src/example.py",
                    action="delete",
                    expected_sha256=digest,
                )
            ],
        )

        assert not path.exists()

        assert (
            result.edits[0]
            .after_sha256
            is None
        )

    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_parent_traversal_is_rejected(
    tmp_path,
):
    (
        context,
        connection,
        task,
        _,
    ) = setup_task(tmp_path)

    try:
        with pytest.raises(
            EditPathError
        ):
            apply_edits(
                connection,
                task.id,
                [
                    EditProposal(
                        path="../outside.py",
                        action="create",
                        content="bad\n",
                    )
                ],
            )

    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_git_directory_is_rejected(
    tmp_path,
):
    (
        context,
        connection,
        task,
        _,
    ) = setup_task(tmp_path)

    try:
        with pytest.raises(
            EditPathError
        ):
            apply_edits(
                connection,
                task.id,
                [
                    EditProposal(
                        path=".git/config",
                        action="create",
                        content="bad\n",
                    )
                ],
            )

    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_symlink_parent_is_rejected(
    tmp_path,
):
    (
        context,
        connection,
        task,
        worktree,
    ) = setup_task(tmp_path)

    try:
        outside = (
            tmp_path
            / "outside"
        )
        outside.mkdir()

        link = (
            worktree.path
            / "linked"
        )

        link.symlink_to(
            outside,
            target_is_directory=True,
        )

        with pytest.raises(
            EditPathError
        ):
            apply_edits(
                connection,
                task.id,
                [
                    EditProposal(
                        path="linked/escape.py",
                        action="create",
                        content="bad\n",
                    )
                ],
            )

        assert not (
            outside
            / "escape.py"
        ).exists()

    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_all_edits_validate_before_any_mutation(
    tmp_path,
):
    (
        context,
        connection,
        task,
        worktree,
    ) = setup_task(tmp_path)

    try:
        original = (
            worktree.path
            / "src/example.py"
        )

        text = original.read_text(
            encoding="utf-8"
        )

        with pytest.raises(
            EditConflictError
        ):
            apply_edits(
                connection,
                task.id,
                [
                    EditProposal(
                        path="src/new.py",
                        action="create",
                        content="created = True\n",
                    ),
                    EditProposal(
                        path="src/example.py",
                        action="replace",
                        expected_sha256=(
                            "f" * 64
                        ),
                        content="value = 3\n",
                    ),
                ],
            )

        assert not (
            worktree.path
            / "src/new.py"
        ).exists()

        assert (
            original.read_text(
                encoding="utf-8"
            )
            == text
        )

    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_total_write_limit_is_enforced(
    tmp_path,
):
    (
        context,
        connection,
        task,
        _,
    ) = setup_task(tmp_path)

    try:
        with pytest.raises(
            EditLimitError
        ):
            apply_edits(
                connection,
                task.id,
                [
                    EditProposal(
                        path="large.txt",
                        action="create",
                        content="x" * 100,
                    )
                ],
                max_total_bytes=32,
            )

    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_diff_limit_is_enforced_before_mutation(
    tmp_path,
):
    (
        context,
        connection,
        task,
        worktree,
    ) = setup_task(tmp_path)

    try:
        with pytest.raises(
            EditLimitError
        ):
            apply_edits(
                connection,
                task.id,
                [
                    EditProposal(
                        path="large.txt",
                        action="create",
                        content=(
                            "line\n"
                            * 100
                        ),
                    )
                ],
                max_diff_chars=40,
            )

        assert not (
            worktree.path
            / "large.txt"
        ).exists()

    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_failure_rolls_back_entire_batch(
    tmp_path,
    monkeypatch,
):
    (
        context,
        connection,
        task,
        worktree,
    ) = setup_task(tmp_path)

    try:
        path = (
            worktree.path
            / "src/example.py"
        )

        original = (
            path.read_text(
                encoding="utf-8"
            )
        )

        digest = hash_file(
            path
        )

        def fail_check(root):
            raise EditApplyError(
                "forced validation failure"
            )

        monkeypatch.setattr(
            edits_module,
            "_git_diff_check",
            fail_check,
        )

        with pytest.raises(
            EditApplyError
        ):
            apply_edits(
                connection,
                task.id,
                [
                    EditProposal(
                        path="src/example.py",
                        action="replace",
                        expected_sha256=digest,
                        content="value = 99\n",
                    ),
                    EditProposal(
                        path="src/new.py",
                        action="create",
                        content="new = True\n",
                    ),
                ],
            )

        assert (
            path.read_text(
                encoding="utf-8"
            )
            == original
        )

        assert not (
            worktree.path
            / "src/new.py"
        ).exists()

    finally:
        context.__exit__(
            None,
            None,
            None,
        )
