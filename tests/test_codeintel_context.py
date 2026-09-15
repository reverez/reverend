from __future__ import annotations

import subprocess

import pytest

from reverend.codeintel import (
    ContextCompilerError,
    compile_repository_context,
    compile_task_context,
    estimate_tokens,
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

    if target not in {TaskState.PENDING, TaskState.RUNNING}:
        raise ValueError("invalid transition")

    task.state = target
    return task


def unrelated_helper():
    return "not important"
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
            "Task state transitions are validated.\n"
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


def test_token_estimate_is_conservative():
    text = "x" * 300

    assert estimate_tokens(
        text
    ) == 100


def test_repository_context_contains_repository_state(
    tmp_path,
):
    repo = make_repo(tmp_path)

    context = compile_repository_context(
        repo,
        "task state transition",
    )

    assert (
        "## Repository state"
        in context.text
    )

    assert (
        "branch: main"
        in context.text
    )


def test_context_contains_ranked_implementation(
    tmp_path,
):
    repo = make_repo(tmp_path)

    context = compile_repository_context(
        repo,
        "task state transition",
    )

    assert (
        "src/example/tasks.py"
        in context.text
    )

    assert (
        "def transition_task"
        in context.text
    )


def test_context_includes_related_tests(
    tmp_path,
):
    repo = make_repo(tmp_path)

    context = compile_repository_context(
        repo,
        "test task state transition",
    )

    assert (
        "tests/test_tasks.py"
        in context.text
    )

    assert (
        "test_task_state_transition"
        in context.text
    )


def test_context_respects_hard_budget(
    tmp_path,
):
    repo = make_repo(tmp_path)

    context = compile_repository_context(
        repo,
        "task state transition",
        max_chars=1500,
    )

    assert context.char_count <= 1500
    assert context.truncated


def test_compilation_is_deterministic(
    tmp_path,
):
    repo = make_repo(tmp_path)

    first = compile_repository_context(
        repo,
        "task state transition",
    )

    second = compile_repository_context(
        repo,
        "task state transition",
    )

    assert first.text == second.text
    assert (
        first.estimated_tokens
        == second.estimated_tokens
    )


def test_empty_query_is_rejected(
    tmp_path,
):
    repo = make_repo(tmp_path)

    with pytest.raises(
        ContextCompilerError
    ):
        compile_repository_context(
            repo,
            "   ",
        )


def test_task_context_contains_task_contract(
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
            title="Fix task transitions",
            request=(
                "Reject illegal task "
                "state transitions."
            ),
            acceptance_criteria=(
                "Valid transitions pass; "
                "invalid transitions fail."
            ),
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

        context = compile_task_context(
            connection,
            task.id,
        )

        assert "## Task" in context.text

        assert (
            "Fix task transitions"
            in context.text
        )

        assert (
            "Reject illegal task"
            in context.text
        )

        assert (
            "Valid transitions pass"
            in context.text
        )

        assert (
            task.base_commit
            in context.text
        )


def test_task_context_uses_worktree_contents(
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
            title="Fix task transitions",
            request="Change transition behavior.",
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

        path = (
            worktree.path
            / "src/example/tasks.py"
        )

        path.write_text(
            path.read_text(
                encoding="utf-8"
            )
            + "\n# WORKTREE_ONLY_MARKER\n",
            encoding="utf-8",
        )

        context = compile_task_context(
            connection,
            task.id,
        )

        assert (
            "WORKTREE_ONLY_MARKER"
            in context.text
        )


def test_task_context_uses_call_graph_for_deep_related_symbol(
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
            title="Change task transition",
            request=(
                "Update transition task behavior "
                "without changing unrelated code."
            ),
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

        guard = (
            worktree.path
            / "src/example/guard.py"
        )
        guard.write_text(
            "".join(
                f"# filler {index}\n"
                for index in range(1, 101)
            )
            + "\n"
            + "def enforce(value):\n"
            + "    return value\n",
            encoding="utf-8",
        )

        tasks = (
            worktree.path
            / "src/example/tasks.py"
        )
        tasks.write_text(
            (
                "from .models import TaskState\n"
                "from .guard import enforce\n\n"
                "def transition_task(task, target):\n"
                "    if task.state == target:\n"
                "        return task\n\n"
                "    task.state = target\n"
                "    return enforce(task)\n"
            ),
            encoding="utf-8",
        )

        context = compile_task_context(
            connection,
            task.id,
        )

        guard_section = next(
            section
            for section in context.sections
            if section.path
            == "src/example/guard.py"
        )
        test_section = next(
            section
            for section in context.sections
            if section.path
            == "tests/test_tasks.py"
        )

        assert "def enforce" in guard_section.content
        assert (
            "call:transition_task->enforce"
            in guard_section.content
        )
        assert (
            "graph:imported_by:"
            "src/example/tasks.py"
            in test_section.content
        )
        assert (
            "call:test_task_state_transition"
            "->transition_task"
            in test_section.content
        )
