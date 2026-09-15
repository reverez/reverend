from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

from reverend.development.command import (
    execute_dev_implement,
)


def git(
    repo,
    *args,
):
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


def make_repo(
    tmp_path,
):
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

    (
        repo
        / "value.py"
    ).write_text(
        "VALUE = 1\n",
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
        "Initial",
    )

    return repo


def fake_engine(
    connection,
    task_id,
    scheduler,
    **kwargs,
):
    row = connection.execute(
        """
        SELECT worktree_path
        FROM tasks
        WHERE id = ?
        """,
        (
            task_id,
        ),
    ).fetchone()

    root = Path(
        row["worktree_path"]
    )

    (
        root
        / "value.py"
    ).write_text(
        "VALUE = 2\n",
        encoding="utf-8",
    )

    return SimpleNamespace(
        status="pass",
        message=(
            "Fake autonomous implementation passed."
        ),
        plan=SimpleNamespace(
            plan=SimpleNamespace(
                summary=(
                    "Change VALUE to two."
                )
            )
        ),
        repair=SimpleNamespace(
            repairs_used=0,
        ),
        verifier=SimpleNamespace(
            verdict="pass",
            summary=(
                "Change independently verified."
            ),
        ),
    )


def test_execute_dev_implement_creates_isolated_result(
    tmp_path,
):
    repo = make_repo(
        tmp_path
    )

    original_head = git(repo, "rev-parse", "HEAD").stdout.strip()

    result = execute_dev_implement(
        repo,
        "Change VALUE to two.",
        acceptance="VALUE equals 2.",
        max_repairs=2,
        database_path=(
            tmp_path
            / "development.db"
        ),
        scheduler_factory=(
            lambda: object()
        ),
        engine=fake_engine,
    )

    assert result.passed
    assert result.worker_stop_reason is None
    assert result.workers_used == 0
    assert result.worker_steps == 0
    assert result.worker_tool_calls == 0

    assert (
        result.status
        == "pass"
    )

    assert (
        result.changed_paths
        == ("value.py",)
    )

    assert (
        Path(
            result.worktree
        ).exists()
    )

    assert (
        result.branch.startswith(
            "reverend/task-"
        )
    )

    assert git(repo, "status", "--porcelain").stdout == ""
    assert git(repo, "rev-parse", "HEAD").stdout.strip() == original_head
    assert Path(result.worktree).resolve() != repo.resolve()
    assert (Path(result.worktree) / "value.py").read_text() == "VALUE = 2\n"
    assert "value.py" in git(Path(result.worktree), "diff", "--name-only").stdout

    # Primary checkout remains untouched.
    assert (
        (
            repo
            / "value.py"
        ).read_text(
            encoding="utf-8"
        )
        == "VALUE = 1\n"
    )


def test_result_is_not_auto_merged(
    tmp_path,
):
    repo = make_repo(
        tmp_path
    )

    original_head = (
        git(
            repo,
            "rev-parse",
            "HEAD",
        ).stdout.strip()
    )

    result = execute_dev_implement(
        repo,
        "Change VALUE to two.",
        database_path=(
            tmp_path
            / "development.db"
        ),
        scheduler_factory=(
            lambda: object()
        ),
        engine=fake_engine,
    )

    final_head = (
        git(
            repo,
            "rev-parse",
            "HEAD",
        ).stdout.strip()
    )

    assert result.passed

    assert (
        final_head
        == original_head
    )


def test_repairs_are_forwarded(
    tmp_path,
):
    repo = make_repo(
        tmp_path
    )

    observed = {}

    def engine(
        connection,
        task_id,
        scheduler,
        **kwargs,
    ):
        observed.update(
            kwargs
        )

        return SimpleNamespace(
            status="blocked",
            message="Blocked.",
            plan=SimpleNamespace(
                plan=SimpleNamespace(
                    summary="Blocked plan."
                )
            ),
            repair=None,
            verifier=None,
        )

    result = execute_dev_implement(
        repo,
        "Perform task.",
        max_repairs=4,
        database_path=(
            tmp_path
            / "development.db"
        ),
        scheduler_factory=(
            lambda: object()
        ),
        engine=engine,
    )

    assert (
        result.status
        == "blocked"
    )

    assert (
        observed[
            "max_repairs"
        ]
        == 4
    )
