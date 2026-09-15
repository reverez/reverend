"""Single-command M12 Code Intelligence v2 validation.

Portable validation keeps localization deterministic and model-free. Live validation
adds exactly one configured local STRONG_CODE planning call over the same bounded,
isolated task-context path used by Reverend's Code Localizer.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from reverend.benchmarks.codeintel import (
    CodeIntelligenceExecutor,
    codeintel_cases,
)
from reverend.benchmarks.evaluator import (
    evaluate_expectations,
)


def _pytest_summary(output: str) -> dict:
    passed = re.findall(r"(\d+) passed", output)
    failed = re.findall(r"(\d+) failed", output)

    return {
        "passed": (
            int(passed[-1])
            if passed
            else None
        ),
        "failed": (
            int(failed[-1])
            if failed
            else 0
        ),
    }


def _case_report(
    case,
    observation,
) -> dict:
    assertions = evaluate_expectations(
        case,
        observation,
    )

    return {
        "case_id": case.case_id,
        "passed": bool(assertions)
        and all(
            assertion.passed
            for assertion in assertions
        ),
        "assertions": [
            {
                "name": assertion.name,
                "passed": assertion.passed,
                "detail": assertion.detail,
            }
            for assertion in assertions
        ],
        "metadata": dict(
            observation.metadata
        ),
    }


def _live_ok(
    metadata: dict,
) -> bool:
    return bool(
        metadata.get(
            "context_dependency_focused"
        )
        is True
        and metadata.get(
            "context_test_focused"
        )
        is True
        and metadata.get(
            "needs_more_context"
        )
        is False
        and metadata.get(
            "model_calls"
        )
        == 1
        and metadata.get(
            "plan_grounded"
        )
        is True
        and metadata.get(
            "relevant_plan_path"
        )
        is True
        and isinstance(
            metadata.get("model"),
            str,
        )
        and bool(
            metadata.get(
                "model",
                "",
            ).strip()
        )
        and isinstance(
            metadata.get(
                "prompt_estimated_tokens"
            ),
            int,
        )
        and (
            0
            < metadata[
                "prompt_estimated_tokens"
            ]
            <= 12_000
        )
    )


def _write_fixture(
    repository: Path,
) -> None:
    files = {
        "src/example/__init__.py": "",
        "src/example/models.py": (
            "class TaskState:\n"
            "    PENDING = 'pending'\n"
            "    RUNNING = 'running'\n"
        ),
        "src/example/guard.py": (
            "".join(
                f"# bounded fixture filler {index}\n"
                for index in range(
                    1,
                    101,
                )
            )
            + "\n"
            + "def enforce(value):\n"
            + "    return value\n"
        ),
        "src/example/tasks.py": (
            "from .guard import enforce\n"
            "from .models import TaskState\n\n"
            "def transition_task(task, target):\n"
            "    task.state = enforce(target)\n"
            "    return task\n"
        ),
        "tests/test_tasks.py": (
            "from src.example.tasks import transition_task\n\n"
            "def test_transition():\n"
            "    task = type('Task', (), {'state': 'pending'})()\n"
            "    transition_task(task, 'running')\n"
            "    assert task.state == 'running'\n"
        ),
        "README.md": (
            "# Example\n\n"
            "Small local validation fixture.\n"
        ),
    }

    for relative, content in files.items():
        target = (
            repository
            / relative
        )
        target.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        target.write_text(
            content,
            encoding="utf-8",
        )


def _run_live_localizer(
    scheduler_factory,
) -> dict:
    from reverend.development import (
        TaskState,
        create_task,
        create_task_worktree,
        database,
        register_project,
        transition_task,
    )
    from reverend.development.coder import (
        generate_coding_plan,
    )

    with TemporaryDirectory(
        prefix="reverend-m12-localizer-"
    ) as temporary:
        root = Path(temporary)
        repository = root / "repo"
        repository.mkdir()

        subprocess.run(
            [
                "git",
                "init",
                "-b",
                "main",
                str(repository),
            ],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        _write_fixture(
            repository
        )

        subprocess.run(
            [
                "git",
                "-C",
                str(repository),
                "add",
                ".",
            ],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(repository),
                "-c",
                "user.name=Reverend Validation",
                "-c",
                "user.email=reverend@example.invalid",
                "commit",
                "-m",
                "M12 validation fixture",
            ],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        with database(
            root
            / "development.db"
        ) as connection:
            project = register_project(
                connection,
                repository,
            )
            task = create_task(
                connection,
                project.id,
                title=(
                    "Tighten task "
                    "transition behavior"
                ),
                request=(
                    "Change task transition behavior "
                    "so state changes are checked by "
                    "the existing helper and add "
                    "coverage for rejected changes. "
                    "Use the current structure rather "
                    "than introducing a new subsystem."
                ),
                acceptance_criteria=(
                    "Rejected changes fail "
                    "deterministically; ordinary "
                    "changes continue to pass."
                ),
            )
            task = transition_task(
                connection,
                task.id,
                TaskState.PREPARING,
            )
            worktree = (
                create_task_worktree(
                    connection,
                    task.id,
                    root=(
                        root
                        / "worktrees"
                    ),
                )
            )

            scheduler = (
                scheduler_factory()
            )
            run = generate_coding_plan(
                connection,
                task.id,
                scheduler,
            )

            model_calls = int(
                connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM model_runs
                    WHERE task_id = ?
                    """,
                    (
                        task.id,
                    ),
                ).fetchone()[0]
            )

            sections = {
                section.path: section
                for section
                in run.context.sections
                if section.path
            }

            guard = sections.get(
                "src/example/guard.py"
            )
            test = sections.get(
                "tests/test_tasks.py"
            )

            dependency_focused = bool(
                guard
                and "def enforce"
                in guard.content
                and (
                    "graph:imports:"
                    "src/example/tasks.py"
                    in guard.content
                )
                and (
                    "call:transition_task"
                    "->enforce"
                    in guard.content
                )
            )
            test_focused = bool(
                test
                and (
                    "graph:imported_by:"
                    "src/example/tasks.py"
                    in test.content
                )
                and (
                    "call:test_transition"
                    "->transition_task"
                    in test.content
                )
            )

            context_paths = set(
                sections
            )
            planned_paths = [
                {
                    "path": item.path,
                    "action": item.action,
                }
                for item in run.plan.files
            ]

            grounded = all(
                (
                    item.action
                    in {
                        "none",
                        "create",
                    }
                )
                or (
                    item.path
                    in context_paths
                )
                for item
                in run.plan.files
            )
            create_paths_valid = all(
                not (
                    Path(
                        worktree.path
                    )
                    / item.path
                ).exists()
                for item
                in run.plan.files
                if item.action == "create"
            )
            grounded = bool(
                grounded
                and create_paths_valid
            )

            relevant = bool(
                {
                    item.path
                    for item
                    in run.plan.files
                    if item.action
                    != "none"
                }
                & {
                    "src/example/tasks.py",
                    "src/example/guard.py",
                    "tests/test_tasks.py",
                }
            )

            return {
                "context_dependency_focused": (
                    dependency_focused
                ),
                "context_test_focused": (
                    test_focused
                ),
                "needs_more_context": (
                    run.plan
                    .needs_more_context
                ),
                "model_calls": model_calls,
                "plan_grounded": grounded,
                "relevant_plan_path": (
                    relevant
                ),
                "model": run.model,
                "digest": run.digest,
                "prompt_estimated_tokens": (
                    run
                    .prompt_estimated_tokens
                ),
                "context_chars": (
                    run.context.char_count
                ),
                "context_estimated_tokens": (
                    run.context
                    .estimated_tokens
                ),
                "context_paths": sorted(
                    context_paths
                ),
                "planned_paths": (
                    planned_paths
                ),
            }


def run_validation(
    *,
    report_root: Path,
    skip_tests: bool = False,
    skip_live_model: bool = False,
    scheduler_factory=None,
) -> tuple[int, dict]:
    report_root = Path(
        report_root
    )
    report_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    created_at = datetime.now(
        timezone.utc
    )
    stamp = created_at.strftime(
        "%Y%m%dT%H%M%SZ"
    )

    try:
        revision = (
            subprocess.check_output(
                [
                    "git",
                    "rev-parse",
                    "HEAD",
                ],
                text=True,
            ).strip()
        )
    except (
        OSError,
        subprocess.CalledProcessError,
    ):
        revision = None

    summary = {
        "schema_version": 1,
        "created_at": (
            created_at.isoformat()
        ),
        "code_revision": revision,
        "tests": {
            "skipped": skip_tests,
            "returncode": None,
            "passed": None,
            "failed": None,
        },
        "portable_codeintel": {
            "cases": [],
            "passed": 0,
            "failed": 0,
        },
        "live_localizer": {
            "skipped": (
                skip_live_model
            ),
        },
        "portable_ok": False,
        "overall_ok": False,
    }

    if not skip_tests:
        completed = subprocess.run(
            [
                str(
                    Path(
                        sys.executable
                    )
                ),
                "-m",
                "pytest",
                "-q",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        output = (
            (completed.stdout or "")
            + (completed.stderr or "")
        )
        counts = _pytest_summary(
            output
        )
        summary["tests"].update(
            returncode=(
                completed.returncode
            ),
            passed=counts["passed"],
            failed=counts["failed"],
        )

        if completed.returncode:
            summary["tests"][
                "tail"
            ] = output[-4000:]

    reports = []
    executor = (
        CodeIntelligenceExecutor()
    )

    for case in codeintel_cases():
        try:
            observation = executor(
                case
            )
            report = _case_report(
                case,
                observation,
            )
        except Exception as exc:
            report = {
                "case_id": (
                    case.case_id
                ),
                "passed": False,
                "error": (
                    f"{type(exc).__name__}: "
                    f"{exc}"
                ),
            }

        reports.append(
            report
        )

    portable_passed = sum(
        bool(
            report.get(
                "passed"
            )
        )
        for report in reports
    )
    summary[
        "portable_codeintel"
    ] = {
        "cases": reports,
        "passed": portable_passed,
        "failed": (
            len(reports)
            - portable_passed
        ),
    }

    if not skip_live_model:
        try:
            if (
                scheduler_factory
                is None
            ):
                from reverend.development.coder import (
                    create_local_scheduler,
                )

                scheduler_factory = (
                    create_local_scheduler
                )

            metadata = (
                _run_live_localizer(
                    scheduler_factory
                )
            )
            summary[
                "live_localizer"
            ] = {
                "skipped": False,
                "passed": (
                    _live_ok(
                        metadata
                    )
                ),
                "metadata": metadata,
            }
        except Exception as exc:
            summary[
                "live_localizer"
            ] = {
                "skipped": False,
                "passed": False,
                "error": (
                    f"{type(exc).__name__}: "
                    f"{exc}"
                ),
            }

    tests_ok = bool(
        skip_tests
        or summary["tests"][
            "returncode"
        ]
        == 0
    )
    portable_cases_ok = bool(
        summary[
            "portable_codeintel"
        ]["failed"]
        == 0
        and summary[
            "portable_codeintel"
        ]["passed"]
        == len(
            codeintel_cases()
        )
    )
    summary["portable_ok"] = bool(
        tests_ok
        and portable_cases_ok
    )

    live_ok = bool(
        not skip_live_model
        and summary[
            "live_localizer"
        ].get(
            "passed"
        )
    )
    summary["overall_ok"] = bool(
        summary["portable_ok"]
        and live_ok
    )

    summary_path = (
        report_root
        / (
            "validation-"
            f"{stamp}.json"
        )
    )
    summary["summary_path"] = str(
        summary_path
    )
    summary_path.write_text(
        json.dumps(
            summary,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    if summary["overall_ok"]:
        return 0, summary

    if (
        skip_live_model
        and summary["portable_ok"]
    ):
        return 2, summary

    return 1, summary


def main(
    argv: list[str] | None = None,
) -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--report-root",
        type=Path,
        default=Path(
            "benchmarks/results/vnext/"
            "m12/live-validation"
        ),
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help=(
            "Skip pytest when a green full "
            "suite has already been recorded."
        ),
    )
    parser.add_argument(
        "--skip-live-model",
        action="store_true",
        help=(
            "Run only portable gates. This "
            "cannot mark M12 fully accepted."
        ),
    )

    args = parser.parse_args(
        argv
    )

    code, summary = (
        run_validation(
            report_root=(
                args.report_root
            ),
            skip_tests=(
                args.skip_tests
            ),
            skip_live_model=(
                args.skip_live_model
            ),
        )
    )

    print(
        json.dumps(
            summary,
            indent=2,
        )
    )

    return code


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
