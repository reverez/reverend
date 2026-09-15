"""Single-command M11 worker-orchestration validation.

Portable validation uses deterministic fixture-controlled model responses while
exercising the real isolated development engine. Live validation swaps only the
scheduler for Reverend's configured local models, so both gates traverse the
same worktree, edit, deterministic verification and Critic / Verifier path.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from reverend.benchmarks.evaluator import evaluate_expectations
from reverend.benchmarks.workers import (
    DevelopmentWorkerExecutor,
    WorkerOrchestrationExecutor,
    worker_cases,
)


def _pytest_summary(output: str) -> dict:
    passed = re.findall(r"(\d+) passed", output)
    failed = re.findall(r"(\d+) failed", output)
    return {
        "passed": int(passed[-1]) if passed else None,
        "failed": int(failed[-1]) if failed else 0,
    }


def _case_report(case, observation) -> dict:
    assertions = evaluate_expectations(
        case,
        observation,
    )
    return {
        "case_id": case.case_id,
        "passed": bool(assertions)
        and all(assertion.passed for assertion in assertions),
        "assertions": [
            {
                "name": assertion.name,
                "passed": assertion.passed,
                "detail": assertion.detail,
            }
            for assertion in assertions
        ],
        "metadata": dict(observation.metadata),
    }


def _live_ok(metadata: dict) -> bool:
    return bool(
        metadata.get("status") == "pass"
        and metadata.get("stop_reason") == "complete"
        and metadata.get("workers_used") == 3
        and metadata.get("worker_steps") == 3
        and metadata.get("tool_calls") == 0
        and metadata.get("model_calls") == 3
        and metadata.get("primary_checkout_unchanged") is True
        and metadata.get("worktree_changed") is True
        and metadata.get("coder_verified_by") == "coder:verify"
    )


def run_validation(
    *,
    report_root: Path,
    skip_tests: bool = False,
    skip_live_model: bool = False,
) -> tuple[int, dict]:
    report_root = Path(report_root)
    report_root.mkdir(
        parents=True,
        exist_ok=True,
    )
    created_at = datetime.now(timezone.utc)
    stamp = created_at.strftime("%Y%m%dT%H%M%SZ")

    try:
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        revision = None

    summary = {
        "schema_version": 1,
        "created_at": created_at.isoformat(),
        "code_revision": revision,
        "tests": {
            "skipped": skip_tests,
            "returncode": None,
            "passed": None,
            "failed": None,
        },
        "portable_workers": {
            "cases": [],
            "passed": 0,
            "failed": 0,
        },
        "live_development": {
            "skipped": skip_live_model,
        },
        "portable_ok": False,
        "overall_ok": False,
    }

    if not skip_tests:
        completed = subprocess.run(
            [str(Path(__import__("sys").executable)), "-m", "pytest", "-q"],
            text=True,
            capture_output=True,
            check=False,
        )
        output = (
            (completed.stdout or "")
            + (completed.stderr or "")
        )
        counts = _pytest_summary(output)
        summary["tests"].update(
            returncode=completed.returncode,
            passed=counts["passed"],
            failed=counts["failed"],
        )
        if completed.returncode:
            summary["tests"]["tail"] = output[-4000:]

    portable_reports = []
    portable_executor = WorkerOrchestrationExecutor()
    for case in worker_cases():
        try:
            observation = portable_executor(case)
            report = _case_report(
                case,
                observation,
            )
        except Exception as exc:
            report = {
                "case_id": case.case_id,
                "passed": False,
                "error": (
                    f"{type(exc).__name__}: {exc}"
                ),
            }
        portable_reports.append(report)

    portable_passed = sum(
        bool(report.get("passed"))
        for report in portable_reports
    )
    summary["portable_workers"] = {
        "cases": portable_reports,
        "passed": portable_passed,
        "failed": (
            len(portable_reports)
            - portable_passed
        ),
    }

    if not skip_live_model:
        integration_case = next(
            case
            for case in worker_cases()
            if case.case_id
            == "m11-development-engine-workers"
        )
        try:
            from reverend.development.coder import create_local_scheduler

            live_observation = DevelopmentWorkerExecutor(
                scheduler_factory=create_local_scheduler,
            )(integration_case)
            live_metadata = dict(
                live_observation.metadata
            )
            summary["live_development"] = {
                "skipped": False,
                "passed": _live_ok(live_metadata),
                "response": live_observation.response,
                "metadata": live_metadata,
            }
        except Exception as exc:
            summary["live_development"] = {
                "skipped": False,
                "passed": False,
                "error": (
                    f"{type(exc).__name__}: {exc}"
                ),
            }

    tests_ok = (
        skip_tests
        or summary["tests"]["returncode"] == 0
    )
    workers_ok = (
        summary["portable_workers"]["failed"] == 0
        and summary["portable_workers"]["passed"]
        == len(worker_cases())
    )
    summary["portable_ok"] = bool(
        tests_ok
        and workers_ok
    )

    live_ok = bool(
        not skip_live_model
        and summary["live_development"].get("passed")
    )
    summary["overall_ok"] = bool(
        summary["portable_ok"]
        and live_ok
    )

    summary_path = (
        report_root
        / f"validation-{stamp}.json"
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
    if skip_live_model and summary["portable_ok"]:
        return 2, summary
    return 1, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--report-root",
        type=Path,
        default=Path(
            "benchmarks/results/vnext/m11/live-validation"
        ),
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help=(
            "Skip pytest when a green complete suite "
            "has already been recorded."
        ),
    )
    parser.add_argument(
        "--skip-live-model",
        action="store_true",
        help=(
            "Run only portable gates. This cannot mark "
            "M11 fully accepted."
        ),
    )
    args = parser.parse_args(argv)

    code, summary = run_validation(
        report_root=args.report_root,
        skip_tests=args.skip_tests,
        skip_live_model=args.skip_live_model,
    )
    print(
        json.dumps(
            summary,
            indent=2,
        )
    )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
