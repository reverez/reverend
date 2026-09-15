from __future__ import annotations

import subprocess

from reverend.codeintel import (
    related_python_files,
    scan_python_dependency_graph,
    search_code,
)


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )


def make_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    subprocess.run(
        ["git", "init", "-b", "main", str(repo)],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    files = {
        "src/example/__init__.py": "",
        "src/example/models.py": (
            "class TaskState:\n"
            "    PENDING = 'pending'\n"
        ),
        "src/example/guard.py": (
            "def enforce(value):\n"
            "    return value\n"
        ),
        "src/example/tasks.py": (
            "from .models import TaskState\n"
            "from .guard import enforce\n\n"
            "def transition_task(task):\n"
            "    return enforce(TaskState.PENDING)\n"
        ),
        "tests/test_tasks.py": (
            "from src.example.tasks import transition_task\n\n"
            "def test_transition():\n"
            "    assert transition_task(object()) == 'pending'\n"
        ),
    }

    for relative, content in files.items():
        target = repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    git(repo, "add", ".")
    git(
        repo,
        "-c",
        "user.name=Reverend Test",
        "-c",
        "user.email=reverend@example.invalid",
        "commit",
        "-m",
        "Initial",
    )
    return repo


def test_dependency_graph_resolves_relative_and_absolute_imports(tmp_path):
    repo = make_repo(tmp_path)
    graph = scan_python_dependency_graph(repo)

    assert graph.imports_from("src/example/tasks.py") == (
        "src/example/guard.py",
        "src/example/models.py",
    )
    assert graph.imported_by("src/example/tasks.py") == (
        "tests/test_tasks.py",
    )


def test_related_files_are_bounded_and_bidirectional(tmp_path):
    repo = make_repo(tmp_path)
    graph = scan_python_dependency_graph(repo)

    related = related_python_files(
        graph,
        ["src/example/tasks.py"],
        max_hops=1,
        limit=8,
    )

    by_path = {
        item.path: item
        for item in related
    }

    assert by_path["src/example/models.py"].relation == "imports"
    assert by_path["src/example/guard.py"].relation == "imports"
    assert by_path["tests/test_tasks.py"].relation == "imported_by"
    assert all(item.distance == 1 for item in related)


def test_related_files_do_not_escape_configured_limit(tmp_path):
    repo = make_repo(tmp_path)
    graph = scan_python_dependency_graph(repo)

    related = related_python_files(
        graph,
        ["src/example/tasks.py"],
        max_hops=2,
        limit=2,
    )

    assert len(related) == 2


def test_retrieval_expands_to_structurally_related_file(tmp_path):
    repo = make_repo(tmp_path)

    result = search_code(
        repo,
        "transition task",
        limit=10,
    )

    guard = next(
        hit
        for hit in result.hits
        if hit.path == "src/example/guard.py"
    )

    assert any(
        reason.startswith(
            "graph:imports:src/example/tasks.py"
        )
        for reason in guard.reasons
    )


def test_symbol_calls_resolve_across_internal_imports(tmp_path):
    repo = make_repo(tmp_path)
    graph = scan_python_dependency_graph(repo)

    edges = {
        (
            call.source_path,
            call.source_symbol,
            call.target_path,
            call.target_symbol,
        )
        for call in graph.symbol_calls
    }

    assert (
        "src/example/tasks.py",
        "transition_task",
        "src/example/guard.py",
        "enforce",
    ) in edges
    assert (
        "tests/test_tasks.py",
        "test_transition",
        "src/example/tasks.py",
        "transition_task",
    ) in edges


def test_retrieval_uses_symbol_call_to_focus_related_context(tmp_path):
    repo = make_repo(tmp_path)

    result = search_code(
        repo,
        "transition task",
        limit=10,
    )

    guard = next(
        hit
        for hit in result.hits
        if hit.path == "src/example/guard.py"
    )
    test = next(
        hit
        for hit in result.hits
        if hit.path == "tests/test_tasks.py"
    )

    assert "enforce" in guard.symbols
    assert any(
        reason
        == "call:transition_task->enforce"
        for reason in guard.reasons
    )
    assert "test_transition" in test.symbols
    assert test.line_numbers
