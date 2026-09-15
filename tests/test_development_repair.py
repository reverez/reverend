from __future__ import annotations

import subprocess
import sys

import pytest

from reverend.development import (
    TaskState,
    create_task,
    create_task_worktree,
    database,
    register_project,
    transition_task,
)
from reverend.development.edits import (
    EditProposal,
    hash_file,
)
from reverend.development.repair import (
    RepairBudgetError,
    RepairStrategyError,
    collect_failure_diagnostics,
    run_repair_loop,
)
from reverend.development.verification import (
    VerificationCheck,
    run_verification_plan,
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

    target = repo / "value.txt"

    target.write_text(
        "broken\n",
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


def setup_task(tmp_path):
    repo = make_repo(tmp_path)

    context = database(
        tmp_path
        / "development.db"
    )

    connection = context.__enter__()

    project = register_project(
        connection,
        repo,
    )

    task = create_task(
        connection,
        project.id,
        title="Repair value",
        request=(
            "Make value.txt contain fixed."
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
        root=tmp_path / "worktrees",
    )

    task = transition_task(
        connection,
        task.id,
        TaskState.RUNNING,
    )

    check = VerificationCheck(
        name="value-check",
        kind="test",
        argv=(
            sys.executable,
            "-c",
            (
                "from pathlib import Path; "
                "raise SystemExit("
                "0 if Path('value.txt').read_text() "
                "== 'fixed\\n' else 1)"
            ),
        ),
    )

    return (
        context,
        connection,
        task,
        worktree,
        check,
    )


def test_no_repair_when_initial_verification_passes(
    tmp_path,
):
    (
        context,
        connection,
        task,
        worktree,
        check,
    ) = setup_task(tmp_path)

    try:
        (
            worktree.path
            / "value.txt"
        ).write_text(
            "fixed\n",
            encoding="utf-8",
        )

        called = False

        def strategy(request):
            nonlocal called
            called = True
            return []

        result = run_repair_loop(
            connection,
            task.id,
            [check],
            strategy,
        )

        assert result.passed
        assert result.repairs_used == 0
        assert not called

    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_single_repair_can_fix_failure(
    tmp_path,
):
    (
        context,
        connection,
        task,
        worktree,
        check,
    ) = setup_task(tmp_path)

    try:
        target = (
            worktree.path
            / "value.txt"
        )

        def strategy(request):
            return [
                EditProposal(
                    path="value.txt",
                    action="replace",
                    expected_sha256=(
                        hash_file(target)
                    ),
                    content="fixed\n",
                )
            ]

        result = run_repair_loop(
            connection,
            task.id,
            [check],
            strategy,
        )

        assert result.passed
        assert result.repairs_used == 1

        assert (
            target.read_text(
                encoding="utf-8"
            )
            == "fixed\n"
        )

    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_loop_stops_at_repair_budget(
    tmp_path,
):
    (
        context,
        connection,
        task,
        worktree,
        check,
    ) = setup_task(tmp_path)

    try:
        target = (
            worktree.path
            / "value.txt"
        )

        calls = 0

        def strategy(request):
            nonlocal calls
            calls += 1

            return [
                EditProposal(
                    path="value.txt",
                    action="replace",
                    expected_sha256=(
                        hash_file(target)
                    ),
                    content=(
                        f"still-broken-{calls}\n"
                    ),
                )
            ]

        result = run_repair_loop(
            connection,
            task.id,
            [check],
            strategy,
            max_repairs=2,
        )

        assert not result.passed
        assert result.repairs_used == 2
        assert calls == 2

    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_diagnostics_capture_failure_output(
    tmp_path,
):
    (
        context,
        connection,
        task,
        _,
        _,
    ) = setup_task(tmp_path)

    try:
        check = VerificationCheck(
            name="diagnostic",
            kind="test",
            argv=(
                sys.executable,
                "-c",
                (
                    "import sys; "
                    "print('useful stdout'); "
                    "print('useful stderr', file=sys.stderr); "
                    "raise SystemExit(2)"
                ),
            ),
        )

        report = run_verification_plan(
            connection,
            task.id,
            [check],
        )

        diagnostics = (
            collect_failure_diagnostics(
                connection,
                report,
                attempt=1,
            )
        )

        assert (
            "useful stdout"
            in diagnostics.text
        )

        assert (
            "useful stderr"
            in diagnostics.text
        )

        assert (
            diagnostics.failed_checks
            == ("diagnostic",)
        )

    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_diagnostics_are_bounded(
    tmp_path,
):
    (
        context,
        connection,
        task,
        _,
        _,
    ) = setup_task(tmp_path)

    try:
        check = VerificationCheck(
            name="large-output",
            kind="test",
            argv=(
                sys.executable,
                "-c",
                (
                    "print('x' * 10000); "
                    "raise SystemExit(1)"
                ),
            ),
        )

        report = run_verification_plan(
            connection,
            task.id,
            [check],
        )

        diagnostics = (
            collect_failure_diagnostics(
                connection,
                report,
                attempt=1,
                max_chars=1000,
            )
        )

        assert (
            len(diagnostics.text)
            <= 1100
        )

        assert "clipped" in (
            diagnostics.text
        )

    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_empty_repair_is_rejected(
    tmp_path,
):
    (
        context,
        connection,
        task,
        _,
        check,
    ) = setup_task(tmp_path)

    try:
        with pytest.raises(
            RepairStrategyError
        ):
            run_repair_loop(
                connection,
                task.id,
                [check],
                lambda request: [],
            )

    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_invalid_budget_is_rejected(
    tmp_path,
):
    (
        context,
        connection,
        task,
        _,
        check,
    ) = setup_task(tmp_path)

    try:
        with pytest.raises(
            RepairBudgetError
        ):
            run_repair_loop(
                connection,
                task.id,
                [check],
                lambda request: [],
                max_repairs=-1,
            )

        with pytest.raises(
            RepairBudgetError
        ):
            run_repair_loop(
                connection,
                task.id,
                [check],
                lambda request: [],
                max_repairs=11,
            )

    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_repair_attempts_are_persisted(
    tmp_path,
):
    (
        context,
        connection,
        task,
        worktree,
        check,
    ) = setup_task(tmp_path)

    try:
        target = (
            worktree.path
            / "value.txt"
        )

        result = run_repair_loop(
            connection,
            task.id,
            [check],
            lambda request: [
                EditProposal(
                    path="value.txt",
                    action="replace",
                    expected_sha256=(
                        hash_file(target)
                    ),
                    content="fixed\n",
                )
            ],
        )

        assert result.passed

        row = connection.execute(
            """
            SELECT
                name,
                status,
                metadata_json
            FROM experiments
            WHERE task_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (
                task.id,
            ),
        ).fetchone()

        assert row is not None

        assert (
            row["name"]
            == "repair-attempt-1"
        )

        assert (
            row["status"]
            == "complete"
        )

        assert (
            '"verification_passed": true'
            in row["metadata_json"]
        )

    finally:
        context.__exit__(
            None,
            None,
            None,
        )



def test_diagnostics_classify_test_failure_and_capture_delta(tmp_path):
    context, connection, task, worktree, _ = setup_task(tmp_path)
    try:
        connection.execute(
            "UPDATE tasks SET acceptance_criteria = ? WHERE id = ?",
            ("value.txt must contain exactly 'fixed'.", task.id),
        )
        (worktree.path / "value.txt").write_text("changed\n", encoding="utf-8")
        check = VerificationCheck(
            name="pytest-like",
            kind="test",
            argv=(
                sys.executable,
                "-c",
                (
                    "print('FAILED tests/test_value.py::test_value - AssertionError'); "
                    "raise SystemExit(1)"
                ),
            ),
        )
        report = run_verification_plan(connection, task.id, [check])
        diagnostics = collect_failure_diagnostics(
            connection,
            report,
            attempt=1,
            task_id=task.id,
        )

        assert diagnostics.failure_kind == "test_assertion"
        assert diagnostics.failing_tests == ("tests/test_value.py::test_value",)
        assert diagnostics.changed_paths == ("value.txt",)
        assert diagnostics.acceptance_criteria[0].startswith("AC-01:")
        assert "FAILURE_KIND: test_assertion" in diagnostics.text
        assert "CHANGED_PATHS: value.txt" in diagnostics.text
    finally:
        context.__exit__(None, None, None)
