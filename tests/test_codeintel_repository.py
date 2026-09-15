from __future__ import annotations

import subprocess

import pytest

from reverend.codeintel import (
    RepositoryTooLargeError,
    scan_repository,
    scan_task_repository,
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
        "CMakeLists.txt": (
            "cmake_minimum_required(VERSION 3.24)\n"
        ),
        "src/app.py": (
            "def answer():\n"
            "    return 42\n"
        ),
        "src/kernel.cu": (
            "__global__ void kernel() {}\n"
        ),
        "tests/test_app.py": (
            "def test_answer():\n"
            "    assert True\n"
        ),
        "README.md": "# Example\n",
        ".gitignore": ".cache/\n",
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
        / ".cache"
        / "ignored.py"
    )

    ignored.parent.mkdir(
        parents=True
    )

    ignored.write_text(
        "ignored = True\n",
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
        "Initial repository",
    )

    return repo


def test_scan_detects_languages(
    tmp_path,
):
    repo = make_repo(tmp_path)

    profile = scan_repository(
        repo
    )

    languages = dict(
        profile.languages
    )

    assert languages["Python"] == 2
    assert languages["CUDA"] == 1
    assert languages["CMake"] == 1
    assert languages["TOML"] == 1


def test_scan_detects_build_systems(
    tmp_path,
):
    repo = make_repo(tmp_path)

    profile = scan_repository(
        repo
    )

    assert profile.build_systems == (
        "cmake",
        "python",
    )


def test_scan_discovers_tests(
    tmp_path,
):
    repo = make_repo(tmp_path)

    profile = scan_repository(
        repo
    )

    assert (
        "tests/test_app.py"
        in profile.test_files
    )

    assert profile.test_count == 1


def test_ignored_files_are_excluded(
    tmp_path,
):
    repo = make_repo(tmp_path)

    profile = scan_repository(
        repo
    )

    paths = {
        item.path
        for item in profile.files
    }

    assert (
        ".cache/ignored.py"
        not in paths
    )


def test_changed_files_include_modified_and_untracked(
    tmp_path,
):
    repo = make_repo(tmp_path)

    (
        repo
        / "src"
        / "app.py"
    ).write_text(
        "def answer():\n"
        "    return 43\n",
        encoding="utf-8",
    )

    (
        repo
        / "notes.txt"
    ).write_text(
        "new\n",
        encoding="utf-8",
    )

    profile = scan_repository(
        repo
    )

    assert "src/app.py" in (
        profile.changed_files
    )

    assert "notes.txt" in (
        profile.changed_files
    )

    assert profile.is_dirty


def test_recent_history_is_captured(
    tmp_path,
):
    repo = make_repo(tmp_path)

    (
        repo
        / "second.txt"
    ).write_text(
        "second\n",
        encoding="utf-8",
    )

    git(
        repo,
        "add",
        "second.txt",
    )

    git(
        repo,
        "-c",
        "user.name=Reverend Test",
        "-c",
        "user.email=reverend@example.invalid",
        "commit",
        "-m",
        "Second commit",
    )

    profile = scan_repository(
        repo,
        history_limit=2,
    )

    assert len(
        profile.recent_commits
    ) == 2

    assert (
        profile.recent_commits[0].subject
        == "Second commit"
    )


def test_repository_limit_is_explicit(
    tmp_path,
):
    repo = make_repo(tmp_path)

    with pytest.raises(
        RepositoryTooLargeError
    ):
        scan_repository(
            repo,
            max_files=2,
        )


def test_task_worktree_can_be_profiled(
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
            title="Profile task",
            request="Inspect repository",
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

        profile = scan_task_repository(
            connection,
            task.id,
        )

        assert (
            profile.head_commit
            == task.base_commit
        )

        assert (
            profile.current_branch
            is not None
        )

        assert (
            profile.current_branch
            .startswith(
                "reverend/task-"
            )
        )
