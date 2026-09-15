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
from reverend.development.verification import (
    VerificationCheck,
    VerificationStateError,
    discover_verification_plan,
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

    (
        repo
        / "pyproject.toml"
    ).write_text(
        (
            "[project]\n"
            'name = "example"\n'
        ),
        encoding="utf-8",
    )

    tests = (
        repo
        / "tests"
        / "test_example.py"
    )

    tests.parent.mkdir(
        parents=True
    )

    tests.write_text(
        (
            "def test_example():\n"
            "    assert True\n"
        ),
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
        title="Verify task",
        request="Verify repository",
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


def test_discovery_finds_git_and_pytest(
    tmp_path,
):
    repo = make_repo(tmp_path)

    checks = (
        discover_verification_plan(
            repo,
            python_executable=(
                sys.executable
            ),
        )
    )

    names = [
        check.name
        for check in checks
    ]

    assert names == [
        "git-diff-check",
        "pytest",
    ]


def test_discovery_finds_explicit_node_test_script(
    tmp_path,
):
    repo = tmp_path / "node-repo"
    repo.mkdir()

    subprocess.run(
        ["git", "init", "-b", "main", str(repo)],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    (repo / "package.json").write_text(
        (
            '{"name":"calculator","private":true,'
            '"scripts":{"test":"node --test"}}\n'
        ),
        encoding="utf-8",
    )
    (repo / "calculator.js").write_text(
        "export function add(a,b){return a+b;}\n",
        encoding="utf-8",
    )
    tests = repo / "tests" / "calculator.test.js"
    tests.parent.mkdir()
    tests.write_text(
        (
            "import test from 'node:test';\n"
            "import assert from 'node:assert/strict';\n"
            "test('addition',()=>assert.equal(2+2,4));\n"
        ),
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
        "Initial node repository",
    )

    checks = discover_verification_plan(
        repo
    )
    names = [check.name for check in checks]

    assert names == [
        "git-diff-check",
        "npm-test",
    ]

    node = checks[1]
    assert node.argv == (
        "npm",
        "--silent",
        "test",
    )
    assert dict(node.environment) == {
        "CI":"1",
        "NODE_ENV":"test",
    }


def test_node_placeholder_test_script_is_not_accepted(
    tmp_path,
):
    repo = tmp_path / "node-placeholder"
    repo.mkdir()

    subprocess.run(
        ["git", "init", "-b", "main", str(repo)],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    (repo / "package.json").write_text(
        (
            '{"name":"calculator",'
            '"scripts":{"test":"echo \\"Error: no test specified\\" && exit 1"}}\n'
        ),
        encoding="utf-8",
    )
    tests = repo / "tests" / "calculator.test.js"
    tests.parent.mkdir()
    tests.write_text(
        "console.log('placeholder');\n",
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
        "Initial node repository",
    )

    checks = discover_verification_plan(
        repo
    )

    assert [
        check.name
        for check in checks
    ] == [
        "git-diff-check",
    ]


def test_passing_check_is_recorded(
    tmp_path,
):
    (
        context,
        connection,
        task,
        _,
    ) = setup_task(tmp_path)

    try:
        report = (
            run_verification_plan(
                connection,
                task.id,
                [
                    VerificationCheck(
                        name="pass",
                        kind="test",
                        argv=(
                            sys.executable,
                            "-c",
                            "print('ok')",
                        ),
                    )
                ],
            )
        )

        assert report.passed
        assert len(
            report.checks
        ) == 1

        assert (
            report.checks[0].status
            == "passed"
        )

        row = connection.execute(
            """
            SELECT *
            FROM verifications
            WHERE task_id = ?
            """,
            (
                task.id,
            ),
        ).fetchone()

        assert row is not None
        assert (
            row["status"]
            == "passed"
        )
        assert row["summary"]=="pass: passed | ok"

    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_failure_is_recorded(
    tmp_path,
):
    (
        context,
        connection,
        task,
        _,
    ) = setup_task(tmp_path)

    try:
        report = (
            run_verification_plan(
                connection,
                task.id,
                [
                    VerificationCheck(
                        name="fail",
                        kind="test",
                        argv=(
                            sys.executable,
                            "-c",
                            "raise SystemExit(7)",
                        ),
                    )
                ],
            )
        )

        assert not report.passed

        check = (
            report.checks[0]
        )

        assert not check.passed
        assert (
            check.exit_code
            == 7
        )

    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_fail_fast_stops_after_required_failure(
    tmp_path,
):
    (
        context,
        connection,
        task,
        _,
    ) = setup_task(tmp_path)

    try:
        report = (
            run_verification_plan(
                connection,
                task.id,
                [
                    VerificationCheck(
                        name="first",
                        kind="test",
                        argv=(
                            sys.executable,
                            "-c",
                            "raise SystemExit(1)",
                        ),
                    ),
                    VerificationCheck(
                        name="second",
                        kind="test",
                        argv=(
                            sys.executable,
                            "-c",
                            "print('never')",
                        ),
                    ),
                ],
                fail_fast=True,
            )
        )

        assert len(
            report.checks
        ) == 1

        assert (
            report.checks[0].name
            == "first"
        )

    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_non_fail_fast_runs_all_checks(
    tmp_path,
):
    (
        context,
        connection,
        task,
        _,
    ) = setup_task(tmp_path)

    try:
        report = (
            run_verification_plan(
                connection,
                task.id,
                [
                    VerificationCheck(
                        name="first",
                        kind="test",
                        argv=(
                            sys.executable,
                            "-c",
                            "raise SystemExit(1)",
                        ),
                    ),
                    VerificationCheck(
                        name="second",
                        kind="test",
                        argv=(
                            sys.executable,
                            "-c",
                            "print('runs')",
                        ),
                    ),
                ],
                fail_fast=False,
            )
        )

        assert len(
            report.checks
        ) == 2

        assert not (
            report.checks[0]
            .passed
        )

        assert (
            report.checks[1]
            .passed
        )

    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_optional_failure_does_not_fail_report(
    tmp_path,
):
    (
        context,
        connection,
        task,
        _,
    ) = setup_task(tmp_path)

    try:
        report = (
            run_verification_plan(
                connection,
                task.id,
                [
                    VerificationCheck(
                        name="optional",
                        kind="diagnostic",
                        required=False,
                        argv=(
                            sys.executable,
                            "-c",
                            "raise SystemExit(1)",
                        ),
                    )
                ],
            )
        )

        assert report.passed

    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_artifacts_are_linked_to_verification(
    tmp_path,
):
    (
        context,
        connection,
        task,
        _,
    ) = setup_task(tmp_path)

    try:
        report = (
            run_verification_plan(
                connection,
                task.id,
                [
                    VerificationCheck(
                        name="output",
                        kind="test",
                        argv=(
                            sys.executable,
                            "-c",
                            (
                                "import sys; "
                                "print('out'); "
                                "print('err', file=sys.stderr)"
                            ),
                        ),
                    )
                ],
            )
        )

        assert report.passed

        count = connection.execute(
            """
            SELECT COUNT(*)
            FROM artifacts
            WHERE task_id = ?
            """,
            (
                task.id,
            ),
        ).fetchone()[0]

        assert count == 2

        details = connection.execute(
            """
            SELECT details_json
            FROM verifications
            WHERE task_id = ?
            """,
            (
                task.id,
            ),
        ).fetchone()[
            "details_json"
        ]

        assert (
            "stdout_artifact"
            in details
        )

        assert (
            "stderr_artifact"
            in details
        )

    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_wrong_task_state_is_rejected(
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
            title="Pending",
            request="Remain pending",
        )

        with pytest.raises(
            VerificationStateError
        ):
            run_verification_plan(
                connection,
                task.id,
                [
                    VerificationCheck(
                        name="check",
                        kind="test",
                        argv=(
                            sys.executable,
                            "-c",
                            "print('no')",
                        ),
                    )
                ],
            )



def test_discovery_runs_targeted_pytest_before_full_suite(tmp_path):
    repo = make_repo(tmp_path)
    checks = discover_verification_plan(
        repo,
        python_executable=sys.executable,
        affected_tests=("tests/test_example.py", "not-a-test.py"),
    )

    assert [check.name for check in checks] == [
        "git-diff-check",
        "pytest-targeted",
        "pytest",
    ]
    assert checks[1].argv == (
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "tests/test_example.py",
    )
    assert checks[2].argv == (
        sys.executable,
        "-m",
        "pytest",
        "-q",
    )
