from __future__ import annotations

import subprocess

import pytest

from reverend.codeintel import (
    CodeRetrievalError,
    search_code,
    search_task_code,
    tokenize_query,
)
from reverend.development import (
    TaskState,
    create_task,
    create_task_worktree,
    database,
    register_project,
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
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    files = {
        "pyproject.toml": (
            "[project]\n"
            'name = "example"\n'
        ),
        "src/example/models.py": """
from enum import Enum


class TaskState(Enum):
    PENDING = "pending"
    RUNNING = "running"
""".lstrip(),
        "src/example/tasks.py": """
from .models import TaskState


def transition_task(task, target):
    if task.state == target:
        return task

    task.state = target
    return task


def create_task():
    return TaskState.PENDING
""".lstrip(),
        "src/example/database.py": """
def connect_database():
    return None
""".lstrip(),
        "tests/test_tasks.py": """
from src.example.models import TaskState
from src.example.tasks import transition_task


def test_task_state_transition():
    task = type("Task", (), {"state": TaskState.PENDING})()
    transition_task(task, TaskState.RUNNING)
    assert task.state == TaskState.RUNNING
""".lstrip(),
        "README.md": (
            "# Example\n\n"
            "Task state transitions are validated "
            "before execution.\n"
        ),
    }

    for relative, content in files.items():
        path = repo / relative

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        path.write_text(
            content,
            encoding="utf-8",
        )

    git(repo, "add", ".")

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


def test_tokenizer_handles_snake_and_camel_case():
    tokens = tokenize_query(
        "TaskState transition_task validation"
    )

    assert tokens == (
        "task",
        "state",
        "transition",
        "validation",
    )


def test_structural_query_ranks_task_implementation(
    tmp_path,
):
    repo = make_repo(tmp_path)

    result = search_code(
        repo,
        "task state transition",
    )

    assert (
        result.hits[0].path
        == "src/example/tasks.py"
    )

    assert (
        "transition_task"
        in result.hits[0].symbols
    )


def test_state_definition_is_retrieved(
    tmp_path,
):
    repo = make_repo(tmp_path)

    result = search_code(
        repo,
        "TaskState",
    )

    paths = result.paths[:3]

    assert (
        "src/example/models.py"
        in paths
    )


def test_related_test_is_retrieved(
    tmp_path,
):
    repo = make_repo(tmp_path)

    result = search_code(
        repo,
        "test task state transition",
    )

    paths = result.paths[:3]

    assert (
        "tests/test_tasks.py"
        in paths
    )

    test_hit = next(
        hit
        for hit in result.hits
        if hit.path
        == "tests/test_tasks.py"
    )

    assert test_hit.is_test


def test_results_include_matching_lines(
    tmp_path,
):
    repo = make_repo(tmp_path)

    result = search_code(
        repo,
        "transition task",
    )

    hit = next(
        item
        for item in result.hits
        if item.path
        == "src/example/tasks.py"
    )

    assert hit.line_numbers


def test_search_is_deterministic(
    tmp_path,
):
    repo = make_repo(tmp_path)

    first = search_code(
        repo,
        "task state transition",
    )

    second = search_code(
        repo,
        "task state transition",
    )

    assert first == second


def test_empty_query_is_rejected(
    tmp_path,
):
    repo = make_repo(tmp_path)

    with pytest.raises(
        CodeRetrievalError
    ):
        search_code(
            repo,
            "   ",
        )


def test_task_worktree_can_be_searched(
    tmp_path,
):
    repo = make_repo(tmp_path)

    with database(
        tmp_path
        / "development.db"
    ) as connection:
        project = register_project(
            connection,
            repo,
        )

        task = create_task(
            connection,
            project.id,
            title="Retrieve task code",
            request="Find task transitions",
        )

        task = transition_task(
            connection,
            task.id,
            TaskState.PREPARING,
        )

        create_task_worktree(
            connection,
            task.id,
            root=(
                tmp_path
                / "worktrees"
            ),
        )

        result = search_task_code(
            connection,
            task.id,
            "task state transition",
        )

        assert (
            result.hits[0].path
            == "src/example/tasks.py"
        )
