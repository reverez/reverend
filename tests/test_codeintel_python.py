from __future__ import annotations

import subprocess

from reverend.codeintel import (
    module_name_for_path,
    scan_python_file,
    scan_python_repository,
    scan_task_python_repository,
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
        "src/demo/__init__.py": "",
        "src/demo/service.py": """
import sqlite3
import json as js
from pathlib import Path
from .helpers import helper as renamed


class Service:
    def run(self):
        def nested():
            return 1
        return nested()

    async def async_run(self):
        return 2


def top_level():
    return Service()
""".lstrip(),
        "src/demo/helpers.py": """
def helper():
    return 42
""".lstrip(),
        "tests/test_service.py": """
from src.demo.service import Service


def test_service():
    assert Service()
""".lstrip(),
        ".gitignore": ".ignored/\n",
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

    ignored = (
        repo
        / ".ignored"
        / "ignored.py"
    )

    ignored.parent.mkdir(
        parents=True
    )

    ignored.write_text(
        "def ignored(): pass\n",
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


def test_module_name_conversion():
    assert (
        module_name_for_path(
            "src/demo/service.py"
        )
        == "src.demo.service"
    )

    assert (
        module_name_for_path(
            "src/demo/__init__.py"
        )
        == "src.demo"
    )


def test_symbols_include_classes_functions_and_methods(
    tmp_path,
):
    repo = make_repo(tmp_path)

    profile = scan_python_file(
        repo,
        "src/demo/service.py",
    )

    symbols = {
        (
            symbol.qualified_name,
            symbol.kind,
        )
        for symbol in profile.symbols
    }

    assert (
        "Service",
        "class",
    ) in symbols

    assert (
        "Service.run",
        "method",
    ) in symbols

    assert (
        "Service.run.nested",
        "function",
    ) in symbols

    assert (
        "top_level",
        "function",
    ) in symbols


def test_async_symbol_is_recorded(
    tmp_path,
):
    repo = make_repo(tmp_path)

    profile = scan_python_file(
        repo,
        "src/demo/service.py",
    )

    symbol = next(
        item
        for item in profile.symbols
        if item.qualified_name
        == "Service.async_run"
    )

    assert symbol.kind == "method"
    assert symbol.is_async


def test_imports_are_structured(
    tmp_path,
):
    repo = make_repo(tmp_path)

    profile = scan_python_file(
        repo,
        "src/demo/service.py",
    )

    imports = {
        (
            item.imported_module,
            item.imported_name,
            item.alias,
            item.level,
        )
        for item in profile.imports
    }

    assert (
        "sqlite3",
        None,
        None,
        0,
    ) in imports

    assert (
        "json",
        None,
        "js",
        0,
    ) in imports

    assert (
        "pathlib",
        "Path",
        None,
        0,
    ) in imports

    assert (
        "helpers",
        "helper",
        "renamed",
        1,
    ) in imports


def test_symbol_line_ranges_are_recorded(
    tmp_path,
):
    repo = make_repo(tmp_path)

    profile = scan_python_file(
        repo,
        "src/demo/service.py",
    )

    service = next(
        item
        for item in profile.symbols
        if item.qualified_name
        == "Service"
    )

    assert service.line_start > 0
    assert (
        service.line_end
        >= service.line_start
    )


def test_syntax_errors_do_not_crash_repository_scan(
    tmp_path,
):
    repo = make_repo(tmp_path)

    broken = (
        repo
        / "src"
        / "broken.py"
    )

    broken.write_text(
        "def broken(:\n",
        encoding="utf-8",
    )

    profile = scan_python_repository(
        repo
    )

    errors = {
        file.path
        for file in profile.parse_errors
    }

    assert "src/broken.py" in errors


def test_ignored_python_files_are_not_parsed(
    tmp_path,
):
    repo = make_repo(tmp_path)

    profile = scan_python_repository(
        repo
    )

    paths = {
        file.path
        for file in profile.files
    }

    assert (
        ".ignored/ignored.py"
        not in paths
    )


def test_task_worktree_python_can_be_scanned(
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
            title="Python scan",
            request="Inspect Python structure",
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

        profile = (
            scan_task_python_repository(
                connection,
                task.id,
            )
        )

        names = {
            symbol.qualified_name
            for symbol in profile.symbols
        }

        assert "Service" in names
        assert "Service.run" in names
        assert "top_level" in names
