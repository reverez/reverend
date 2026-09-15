from __future__ import annotations

import subprocess

import pytest

from reverend.development import (
    DirtyRepositoryError,
    InvalidRunTransitionError,
    InvalidTaskTransitionError,
    RunStatus,
    StepStatus,
    TaskState,
    database,
    create_step,
    create_task,
    list_tasks,
    register_project,
    start_run,
    transition_run,
    transition_step,
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
        "# Test\n",
        encoding="utf-8",
    )

    git(repo, "add", "README.md")

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


def setup_project(tmp_path):
    repo = make_repo(tmp_path)

    connection_context = database(
        tmp_path / "development.db"
    )

    connection = (
        connection_context.__enter__()
    )

    project = register_project(
        connection,
        repo,
    )

    return (
        repo,
        connection_context,
        connection,
        project,
    )


def test_create_task_pins_head_commit(
    tmp_path,
):
    (
        repo,
        context,
        connection,
        project,
    ) = setup_project(tmp_path)

    try:
        expected = git(
            repo,
            "rev-parse",
            "HEAD",
        ).stdout.strip()

        task = create_task(
            connection,
            project.id,
            title="Example",
            request="Implement example",
        )

        assert task.state == (
            TaskState.PENDING
        )
        assert task.base_commit == expected
        assert task.attempt_budget == 3
    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_dirty_repository_is_rejected(
    tmp_path,
):
    (
        repo,
        context,
        connection,
        project,
    ) = setup_project(tmp_path)

    try:
        (repo / "dirty.txt").write_text(
            "dirty\n",
            encoding="utf-8",
        )

        with pytest.raises(
            DirtyRepositoryError
        ):
            create_task(
                connection,
                project.id,
                title="Unsafe",
                request="Do something",
            )
    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_invalid_task_transition_is_rejected(
    tmp_path,
):
    (
        _,
        context,
        connection,
        project,
    ) = setup_project(tmp_path)

    try:
        task = create_task(
            connection,
            project.id,
            title="Example",
            request="Example",
        )

        with pytest.raises(
            InvalidTaskTransitionError
        ):
            transition_task(
                connection,
                task.id,
                TaskState.COMPLETE,
            )
    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_task_can_complete_normal_lifecycle(
    tmp_path,
):
    (
        _,
        context,
        connection,
        project,
    ) = setup_project(tmp_path)

    try:
        task = create_task(
            connection,
            project.id,
            title="Lifecycle",
            request="Exercise lifecycle",
        )

        task = transition_task(
            connection,
            task.id,
            TaskState.PREPARING,
        )

        task = transition_task(
            connection,
            task.id,
            TaskState.RUNNING,
        )

        assert task.started_at is not None

        task = transition_task(
            connection,
            task.id,
            TaskState.VERIFYING,
        )

        task = transition_task(
            connection,
            task.id,
            TaskState.COMPLETE,
        )

        assert task.state == (
            TaskState.COMPLETE
        )
        assert task.completed_at is not None
    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_blocked_task_can_resume(
    tmp_path,
):
    (
        _,
        context,
        connection,
        project,
    ) = setup_project(tmp_path)

    try:
        task = create_task(
            connection,
            project.id,
            title="Resume",
            request="Resume later",
        )

        task = transition_task(
            connection,
            task.id,
            TaskState.PREPARING,
        )

        task = transition_task(
            connection,
            task.id,
            TaskState.BLOCKED,
            error_message="Waiting",
        )

        task = transition_task(
            connection,
            task.id,
            TaskState.PREPARING,
        )

        assert task.state == (
            TaskState.PREPARING
        )
    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_runs_increment_per_task(
    tmp_path,
):
    (
        _,
        context,
        connection,
        project,
    ) = setup_project(tmp_path)

    try:
        task = create_task(
            connection,
            project.id,
            title="Runs",
            request="Test runs",
        )

        transition_task(
            connection,
            task.id,
            TaskState.PREPARING,
        )

        transition_task(
            connection,
            task.id,
            TaskState.RUNNING,
        )

        first = start_run(
            connection,
            task.id,
            model_role="strong_code",
        )

        transition_run(
            connection,
            first.id,
            RunStatus.COMPLETE,
        )

        second = start_run(
            connection,
            task.id,
            model_role="strong_code",
        )

        assert first.run_number == 1
        assert second.run_number == 2
    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_run_requires_running_task(
    tmp_path,
):
    (
        _,
        context,
        connection,
        project,
    ) = setup_project(tmp_path)

    try:
        task = create_task(
            connection,
            project.id,
            title="Run guard",
            request="Guard runs",
        )

        with pytest.raises(
            InvalidRunTransitionError
        ):
            start_run(
                connection,
                task.id,
            )
    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_steps_are_ordered_and_transition(
    tmp_path,
):
    (
        _,
        context,
        connection,
        project,
    ) = setup_project(tmp_path)

    try:
        task = create_task(
            connection,
            project.id,
            title="Steps",
            request="Exercise steps",
        )

        transition_task(
            connection,
            task.id,
            TaskState.PREPARING,
        )

        transition_task(
            connection,
            task.id,
            TaskState.RUNNING,
        )

        run = start_run(
            connection,
            task.id,
        )

        first = create_step(
            connection,
            run.id,
            kind="inspect",
        )

        second = create_step(
            connection,
            run.id,
            kind="test",
        )

        assert first.sequence == 1
        assert second.sequence == 2

        first = transition_step(
            connection,
            first.id,
            StepStatus.RUNNING,
        )

        first = transition_step(
            connection,
            first.id,
            StepStatus.COMPLETE,
            output_summary="done",
        )

        assert first.status == (
            StepStatus.COMPLETE
        )
        assert first.started_at is not None
        assert first.finished_at is not None
    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_list_tasks_can_filter_state(
    tmp_path,
):
    (
        _,
        context,
        connection,
        project,
    ) = setup_project(tmp_path)

    try:
        first = create_task(
            connection,
            project.id,
            title="First",
            request="First",
        )

        create_task(
            connection,
            project.id,
            title="Second",
            request="Second",
        )

        transition_task(
            connection,
            first.id,
            TaskState.PREPARING,
        )

        pending = list_tasks(
            connection,
            project_id=project.id,
            state=TaskState.PENDING,
        )

        assert len(pending) == 1
        assert pending[0].title == "Second"
    finally:
        context.__exit__(
            None,
            None,
            None,
        )
