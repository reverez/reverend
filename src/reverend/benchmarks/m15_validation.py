"""Final M15 Reverend 0.4.0 release-readiness validation."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from reverend import __version__
from reverend.benchmarks.m13_sandbox_validation import (
    run_live_probe,
)
from reverend.benchmarks.m13_validation import (
    _portable_security,
)
from reverend.benchmarks.m14_validation import (
    _runtime_report,
)
from reverend.benchmarks.release import (
    run_release_smoke,
)


def _pytest_summary(
    output: str,
) -> dict:
    import re

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


def _release_contract(
    repository: Path,
) -> dict:
    readme = (
        repository
        / "README.md"
    ).read_text(
        encoding="utf-8"
    )
    guide = (
        repository
        / "docs"
        / "release-0.4.0.md"
    )
    roadmap = (
        repository
        / "docs"
        / "roadmap.md"
    ).read_text(
        encoding="utf-8"
    )
    env_example = (
        repository
        / ".env.example"
    ).read_text(
        encoding="utf-8"
    )

    assertions = {
        "version_is_0_4_0": (
            __version__
            == "0.4.0"
        ),
        "readme_names_reverend": (
            "# Reverend"
            in readme
        ),
        "readme_names_release": (
            "Reverend 0.4.0"
            in readme
        ),
        "upgrade_guide_present": (
            guide.is_file()
        ),
        "roadmap_tracks_m15": (
            "M15"
            in roadmap
            and "0.4.0"
            in roadmap
        ),
        "environment_example_portable": (
            "192.168."
            not in env_example
            and "/home/you/"
            in env_example
        ),
        "no_example_api_key": (
            "QDRANT_API_KEY="
            not in env_example
        ),
    }

    return {
        "passed": all(
            assertions.values()
        ),
        "assertions": assertions,
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
        job = workstation.store.job(
            identity
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
        "M15 live inference timed out."
    )


def _run_live_inference() -> dict:
    from reverend.development.coder import (
        create_local_scheduler,
    )
    from reverend.workstation.service import (
        Workstation,
    )

    with TemporaryDirectory(
        prefix="reverend-m15-live-"
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
            started = (
                time.monotonic()
            )
            submitted = workstation.chat(
                (
                    "Reply with one short sentence confirming "
                    "that Reverend local inference is running."
                ),
                mode="ask",
                max_model_calls=1,
                privacy_mode="ephemeral",
            )
            job = _wait_job(
                workstation,
                submitted[
                    "job_id"
                ],
            )
            wall = round(
                time.monotonic()
                - started,
                6,
            )
            details = dict(
                job.get(
                    "details"
                )
                or {}
            )
            runs = list(
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
            ).strip()

            passed = bool(
                job.get(
                    "status"
                )
                == "complete"
                and response
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
                    "total_prompt_tokens",
                    0,
                )
                > 0
                and details.get(
                    "total_generated_tokens",
                    0,
                )
                > 0
                and details.get(
                    "total_provider_seconds",
                    0.0,
                )
                > 0
                and len(
                    runs
                )
                == 1
                and runs[0].get(
                    "role"
                )
                == "fast_general"
                and runs[0].get(
                    "model"
                )
                == "qwen3.5:4b"
                and wall
                > 0
            )

            return {
                "passed": passed,
                "version": (
                    __version__
                ),
                "wall_seconds": (
                    wall
                ),
                "response": response,
                "model_calls": (
                    details.get(
                        "model_calls"
                    )
                ),
                "generation_calls": (
                    details.get(
                        "generation_calls"
                    )
                ),
                "embedding_calls": (
                    details.get(
                        "embedding_calls"
                    )
                ),
                "prompt_tokens": (
                    details.get(
                        "total_prompt_tokens"
                    )
                ),
                "generated_tokens": (
                    details.get(
                        "total_generated_tokens"
                    )
                ),
                "provider_seconds": (
                    details.get(
                        "total_provider_seconds"
                    )
                ),
                "inventory_provider_reads": (
                    details.get(
                        "inventory_provider_reads"
                    )
                ),
                "inventory_cache_hits": (
                    details.get(
                        "inventory_cache_hits"
                    )
                ),
                "model_runs": runs,
            }
        finally:
            workstation.close()


def run_validation(
    *,
    repository: Path,
    report_root: Path,
    skip_tests: bool = False,
    skip_live: bool = False,
    release_runner=None,
    sandbox_runner=None,
    inference_runner=None,
) -> tuple[int, dict]:
    repository = Path(
        repository
    ).resolve()
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
        revision = subprocess.check_output(
            [
                "git",
                "-C",
                str(
                    repository
                ),
                "rev-parse",
                "HEAD",
            ],
            text=True,
        ).strip()
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
        "version": (
            __version__
        ),
        "tests": {
            "skipped": (
                skip_tests
            ),
            "returncode": None,
            "passed": None,
            "failed": None,
        },
        "release_contract": {},
        "release_smoke": {},
        "portable_runtime": {},
        "portable_security": {},
        "live_sandbox": {
            "skipped": (
                skip_live
            ),
        },
        "live_inference": {
            "skipped": (
                skip_live
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
            cwd=repository,
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
                counts[
                    "passed"
                ]
            ),
            failed=(
                counts[
                    "failed"
                ]
            ),
        )

        if completed.returncode:
            summary[
                "tests"
            ][
                "tail"
            ] = output[-4000:]

    try:
        summary[
            "release_contract"
        ] = _release_contract(
            repository
        )
    except Exception as exc:
        summary[
            "release_contract"
        ] = {
            "passed": False,
            "error": (
                f"{type(exc).__name__}: "
                f"{exc}"
            ),
        }

    try:
        runner = (
            run_release_smoke
            if release_runner
            is None
            else release_runner
        )
        summary[
            "release_smoke"
        ] = runner(
            repository
        )
    except Exception as exc:
        summary[
            "release_smoke"
        ] = {
            "passed": False,
            "error": (
                f"{type(exc).__name__}: "
                f"{exc}"
            ),
        }

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
        summary[
            "portable_security"
        ] = _portable_security()
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

    if not skip_live:
        try:
            runner = (
                run_live_probe
                if sandbox_runner
                is None
                else sandbox_runner
            )
            summary[
                "live_sandbox"
            ] = {
                "skipped": False,
                **runner(),
            }
        except Exception as exc:
            summary[
                "live_sandbox"
            ] = {
                "skipped": False,
                "passed": False,
                "error": (
                    f"{type(exc).__name__}: "
                    f"{exc}"
                ),
            }

        try:
            runner = (
                _run_live_inference
                if inference_runner
                is None
                else inference_runner
            )
            summary[
                "live_inference"
            ] = {
                "skipped": False,
                **runner(),
            }
        except Exception as exc:
            summary[
                "live_inference"
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
    release_contract_ok = bool(
        summary[
            "release_contract"
        ].get(
            "passed"
        )
        is True
    )
    release_smoke_ok = bool(
        summary[
            "release_smoke"
        ].get(
            "passed"
        )
        is True
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
        == 3
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
        and release_contract_ok
        and release_smoke_ok
        and runtime_ok
        and security_ok
    )

    live_ok = bool(
        not skip_live
        and summary[
            "live_sandbox"
        ].get(
            "passed"
        )
        is True
        and summary[
            "live_inference"
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
            + stamp
            + ".json"
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
        skip_live
        and summary[
            "portable_ok"
        ]
    ):
        return 2, summary

    return 1, summary


def main(
    argv: list[str] | None = None,
) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repository",
        type=Path,
        default=Path(
            "."
        ),
    )
    parser.add_argument(
        "--report-root",
        type=Path,
        default=Path(
            "benchmarks/results/"
            "vnext/m15/live-validation"
        ),
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
    )
    parser.add_argument(
        "--skip-live",
        action="store_true",
        help=(
            "Run portable release gates only. "
            "This cannot mark M15 accepted."
        ),
    )
    args = parser.parse_args(
        argv
    )

    code, summary = run_validation(
        repository=(
            args.repository
        ),
        report_root=(
            args.report_root
        ),
        skip_tests=(
            args.skip_tests
        ),
        skip_live=(
            args.skip_live
        ),
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
