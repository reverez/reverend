"""Single-command M14 Intelligence & Runtime Optimisation validation.

Portable gates cover the deterministic optimisation contracts and retain the accepted M13
privacy/security invariants. Live acceptance measures the configured local Workstation
without using a model as an evaluator.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from reverend.benchmarks.evaluator import (
    evaluate_expectations,
)
from reverend.benchmarks.m13_validation import (
    _portable_security,
)
from reverend.benchmarks.runtime import (
    RuntimeInventoryExecutor,
    runtime_cases,
)


def _pytest_summary(
    output: str,
) -> dict:
    passed = re.findall(
        r"(\d+) passed",
        output,
    )
    failed = re.findall(
        r"(\d+) failed",
        output,
    )

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


def _runtime_report() -> dict:
    executor = (
        RuntimeInventoryExecutor()
    )
    reports = []

    for case in runtime_cases():
        try:
            observation = executor(
                case
            )
            assertions = (
                evaluate_expectations(
                    case,
                    observation,
                )
            )
            passed = bool(
                assertions
            ) and all(
                assertion.passed
                for assertion
                in assertions
            )
            report = {
                "case_id": (
                    case.case_id
                ),
                "passed": passed,
                "assertions": [
                    {
                        "name": (
                            assertion.name
                        ),
                        "passed": (
                            assertion.passed
                        ),
                        "detail": (
                            assertion.detail
                        ),
                    }
                    for assertion
                    in assertions
                ],
                "metadata": dict(
                    observation.metadata
                ),
            }
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

    passed = sum(
        bool(
            report.get(
                "passed"
            )
        )
        for report in reports
    )

    return {
        "cases": reports,
        "passed": passed,
        "failed": (
            len(reports)
            - passed
        ),
    }


def _wait_job(
    workstation,
    identity: str,
    *,
    timeout: float = 180.0,
) -> dict:
    deadline = (
        time.monotonic()
        + timeout
    )

    while (
        time.monotonic()
        < deadline
    ):
        job = (
            workstation.store.job(
                identity
            )
        )

        if job[
            "status"
        ] not in {
            "queued",
            "running",
            "stopping",
        }:
            return job

        time.sleep(
            0.05
        )

    try:
        workstation.cancel(
            identity
        )
    except Exception:
        pass

    raise TimeoutError(
        "M14 live Workstation job timed out."
    )


def _clear_fact_ok(
    job: dict,
    *,
    wall_seconds: float,
) -> bool:
    details = dict(
        job.get(
            "details"
        )
        or {}
    )
    understanding = dict(
        details.get(
            "understanding"
        )
        or {}
    )
    routing = dict(
        details.get(
            "routing"
        )
        or {}
    )
    model_runs = list(
        details.get(
            "model_runs"
        )
        or []
    )
    response = str(
        job.get(
            "response"
        )
        or ""
    ).lower()

    return bool(
        job.get(
            "status"
        )
        == "complete"
        and (
            "ada"
            in response
            or "lovelace"
            in response
        )
        and understanding.get(
            "method"
        )
        == "deterministic"
        and routing.get(
            "model_role"
        )
        == "fast_general"
        and details.get(
            "model_calls"
        )
        == 1
        and details.get(
            "generation_calls"
        )
        == 1
        and details.get(
            "embedding_calls"
        )
        == 0
        and details.get(
            "inventory_provider_reads"
        )
        <= 1
        and details.get(
            "inventory_cache_hits",
            0,
        )
        >= 1
        and details.get(
            "total_prompt_tokens",
            0,
        )
        > 0
        and (
            0
            < details.get(
                "total_generated_tokens",
                0,
            )
            <= routing.get(
                "output_tokens",
                1536,
            )
        )
        and details.get(
            "total_provider_seconds",
            0.0,
        )
        > 0
        and details.get(
            "total_queue_wait_seconds",
            -1.0,
        )
        >= 0
        and details.get(
            "total_setup_seconds",
            -1.0,
        )
        >= 0
        and len(
            model_runs
        )
        == 1
        and model_runs[0].get(
            "role"
        )
        == "fast_general"
        and wall_seconds
        > 0
    )


def _ambiguous_guard_ok(
    job: dict,
) -> bool:
    details = dict(
        job.get(
            "details"
        )
        or {}
    )
    understanding = dict(
        details.get(
            "understanding"
        )
        or {}
    )
    model_runs = list(
        details.get(
            "model_runs"
        )
        or []
    )

    router_invoked = any(
        run.get(
            "role"
        )
        == "router"
        for run
        in model_runs
    )
    ambiguity_handled = bool(
        understanding.get(
            "method"
        )
        == "local_router"
        or details.get(
            "clarification_required"
        )
        is True
    )

    return bool(
        job.get(
            "status"
        )
        == "complete"
        and router_invoked
        and ambiguity_handled
        and details.get(
            "model_calls",
            0,
        )
        >= 1
        and details.get(
            "model_calls",
            0,
        )
        <= 2
    )


def _run_live_workstation() -> dict:
    from reverend.development.coder import (
        create_local_scheduler,
    )
    from reverend.workstation.service import (
        Workstation,
    )

    with TemporaryDirectory(
        prefix="reverend-m14-live-"
    ) as temporary:
        root = Path(
            temporary
        )
        workstation = Workstation(
            root,
            scheduler_factory=(
                create_local_scheduler
            ),
        )

        try:
            clear_started = (
                time.monotonic()
            )
            submitted = (
                workstation.chat(
                    "Who is Ada Lovelace?",
                    max_model_calls=1,
                    privacy_mode=(
                        "ephemeral"
                    ),
                )
            )
            clear_job = _wait_job(
                workstation,
                submitted[
                    "job_id"
                ],
            )
            clear_wall = round(
                time.monotonic()
                - clear_started,
                6,
            )

            guard_started = (
                time.monotonic()
            )
            guard_submitted = (
                workstation.chat(
                    "Who is he?",
                    max_model_calls=2,
                    privacy_mode=(
                        "ephemeral"
                    ),
                )
            )
            guard_job = _wait_job(
                workstation,
                guard_submitted[
                    "job_id"
                ],
            )
            guard_wall = round(
                time.monotonic()
                - guard_started,
                6,
            )

            scheduler = (
                workstation
                .scheduler_factory()
            )
            try:
                loaded_models = (
                    scheduler.provider
                    .loaded_models()
                )
            except Exception:
                loaded_models = []

            clear_details = dict(
                clear_job.get(
                    "details"
                )
                or {}
            )
            guard_details = dict(
                guard_job.get(
                    "details"
                )
                or {}
            )

            clear_passed = (
                _clear_fact_ok(
                    clear_job,
                    wall_seconds=(
                        clear_wall
                    ),
                )
            )
            guard_passed = (
                _ambiguous_guard_ok(
                    guard_job
                )
            )

            return {
                "passed": bool(
                    clear_passed
                    and guard_passed
                ),
                "clear_fact": {
                    "passed": (
                        clear_passed
                    ),
                    "wall_seconds": (
                        clear_wall
                    ),
                    "response": (
                        clear_job.get(
                            "response",
                            "",
                        )
                    ),
                    "understanding": (
                        clear_details.get(
                            "understanding"
                        )
                    ),
                    "routing": (
                        clear_details.get(
                            "routing"
                        )
                    ),
                    "model_calls": (
                        clear_details.get(
                            "model_calls"
                        )
                    ),
                    "generation_calls": (
                        clear_details.get(
                            "generation_calls"
                        )
                    ),
                    "embedding_calls": (
                        clear_details.get(
                            "embedding_calls"
                        )
                    ),
                    "prompt_tokens": (
                        clear_details.get(
                            "total_prompt_tokens"
                        )
                    ),
                    "generated_tokens": (
                        clear_details.get(
                            "total_generated_tokens"
                        )
                    ),
                    "queue_wait_seconds": (
                        clear_details.get(
                            "total_queue_wait_seconds"
                        )
                    ),
                    "setup_seconds": (
                        clear_details.get(
                            "total_setup_seconds"
                        )
                    ),
                    "provider_seconds": (
                        clear_details.get(
                            "total_provider_seconds"
                        )
                    ),
                    "inventory_provider_reads": (
                        clear_details.get(
                            "inventory_provider_reads"
                        )
                    ),
                    "inventory_cache_hits": (
                        clear_details.get(
                            "inventory_cache_hits"
                        )
                    ),
                    "model_runs": (
                        clear_details.get(
                            "model_runs"
                        )
                    ),
                },
                "ambiguous_guard": {
                    "passed": (
                        guard_passed
                    ),
                    "wall_seconds": (
                        guard_wall
                    ),
                    "response": (
                        guard_job.get(
                            "response",
                            "",
                        )
                    ),
                    "understanding": (
                        guard_details.get(
                            "understanding"
                        )
                    ),
                    "routing": (
                        guard_details.get(
                            "routing"
                        )
                    ),
                    "model_calls": (
                        guard_details.get(
                            "model_calls"
                        )
                    ),
                    "prompt_tokens": (
                        guard_details.get(
                            "total_prompt_tokens"
                        )
                    ),
                    "generated_tokens": (
                        guard_details.get(
                            "total_generated_tokens"
                        )
                    ),
                    "inventory_provider_reads": (
                        guard_details.get(
                            "inventory_provider_reads"
                        )
                    ),
                    "inventory_cache_hits": (
                        guard_details.get(
                            "inventory_cache_hits"
                        )
                    ),
                    "model_runs": (
                        guard_details.get(
                            "model_runs"
                        )
                    ),
                },
                "loaded_models": (
                    loaded_models
                ),
            }
        finally:
            workstation.close()


def run_validation(
    *,
    report_root: Path,
    skip_tests: bool = False,
    skip_live_workstation: bool = False,
    live_runner=None,
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
    stamp = (
        created_at.strftime(
            "%Y%m%dT%H%M%SZ"
        )
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
            "skipped": (
                skip_tests
            ),
            "returncode": None,
            "passed": None,
            "failed": None,
        },
        "portable_runtime": {},
        "portable_security": {},
        "live_workstation": {
            "skipped": (
                skip_live_workstation
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
            (
                completed.stdout
                or ""
            )
            + (
                completed.stderr
                or ""
            )
        )
        counts = _pytest_summary(
            output
        )
        summary[
            "tests"
        ].update(
            returncode=(
                completed.returncode
            ),
            passed=(
                counts["passed"]
            ),
            failed=(
                counts["failed"]
            ),
        )

        if (
            completed.returncode
        ):
            summary[
                "tests"
            ]["tail"] = (
                output[-4000:]
            )

    try:
        summary[
            "portable_runtime"
        ] = _runtime_report()
    except Exception as exc:
        summary[
            "portable_runtime"
        ] = {
            "passed": False,
            "error": (
                f"{type(exc).__name__}: "
                f"{exc}"
            ),
        }

    try:
        security = (
            _portable_security()
        )
        summary[
            "portable_security"
        ] = security
    except Exception as exc:
        summary[
            "portable_security"
        ] = {
            "passed": False,
            "error": (
                f"{type(exc).__name__}: "
                f"{exc}"
            ),
        }

    if not skip_live_workstation:
        try:
            runner = (
                _run_live_workstation
                if live_runner
                is None
                else live_runner
            )
            summary[
                "live_workstation"
            ] = {
                "skipped": False,
                **runner(),
            }
        except Exception as exc:
            summary[
                "live_workstation"
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
        or summary[
            "tests"
        ][
            "returncode"
        ]
        == 0
    )
    runtime_ok = bool(
        summary[
            "portable_runtime"
        ].get(
            "failed"
        )
        == 0
        and summary[
            "portable_runtime"
        ].get(
            "passed"
        )
        == len(
            runtime_cases()
        )
    )
    security_ok = bool(
        summary[
            "portable_security"
        ].get(
            "passed"
        )
        is True
    )

    summary[
        "portable_ok"
    ] = bool(
        tests_ok
        and runtime_ok
        and security_ok
    )

    live_ok = bool(
        not skip_live_workstation
        and summary[
            "live_workstation"
        ].get(
            "passed"
        )
        is True
    )

    summary[
        "overall_ok"
    ] = bool(
        summary[
            "portable_ok"
        ]
        and live_ok
    )

    summary_path = (
        report_root
        / (
            "validation-"
            f"{stamp}.json"
        )
    )
    summary[
        "summary_path"
    ] = str(
        summary_path
    )
    summary_path.write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    if summary[
        "overall_ok"
    ]:
        return 0, summary

    if (
        skip_live_workstation
        and summary[
            "portable_ok"
        ]
    ):
        return 2, summary

    return 1, summary


def main(
    argv: list[str] | None = None,
) -> int:
    parser = (
        argparse.ArgumentParser()
    )
    parser.add_argument(
        "--report-root",
        type=Path,
        default=Path(
            "benchmarks/results/"
            "vnext/m14/live-validation"
        ),
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help=(
            "Skip pytest when a green "
            "full suite has already been "
            "recorded."
        ),
    )
    parser.add_argument(
        "--skip-live-workstation",
        action="store_true",
        help=(
            "Run portable gates only. "
            "This cannot mark M14 accepted."
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
            skip_live_workstation=(
                args.skip_live_workstation
            ),
        )
    )

    print(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
    )

    return code


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
