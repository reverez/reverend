"""Single-command live M10 validation for the local WSL workstation."""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def quality_decision(report: dict) -> dict:
    baseline = report["baseline"]
    reranked = report["reranked"]
    metrics = ("hit_at_1", "hit_at_k", "mrr_at_k")
    non_regression = all(
        float(reranked[name]) >= float(baseline[name])
        for name in metrics
    )
    improved = any(
        float(reranked[name]) > float(baseline[name])
        for name in metrics
    )
    return {
        "quality_non_regression": non_regression,
        "quality_improved": improved,
        "recommended_default": non_regression and improved,
    }


def _pytest_summary(output: str) -> dict:
    passed = re.findall(r"(\d+) passed", output)
    failed = re.findall(r"(\d+) failed", output)
    return {
        "passed": int(passed[-1]) if passed else None,
        "failed": int(failed[-1]) if failed else 0,
    }


def run_validation(
    *,
    report_root: Path,
    skip_tests: bool = False,
) -> tuple[int, dict]:
    from reverend.benchmarks.catalog import builtin_cases
    from reverend.benchmarks.command import command_benchmark_run
    from reverend.benchmarks.reference_fabric import (
        load_cases,
        run_reference_fabric_benchmark,
    )
    from reverend.config import DATA_ROOT
    from reverend.development.coder import create_local_scheduler
    from reverend.knowledge import KnowledgeFabric
    from reverend.reference import configured_reference

    report_root = Path(report_root)
    report_root.mkdir(parents=True, exist_ok=True)
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
        "canonical_m9_regression": {},
        "reference_fabric": {},
        "overall_ok": False,
    }

    if not skip_tests:
        result = subprocess.run(
            [str(Path(__import__("sys").executable)), "-m", "pytest", "-q"],
            text=True,
            capture_output=True,
            check=False,
        )
        output = (result.stdout or "") + (result.stderr or "")
        counts = _pytest_summary(output)
        summary["tests"].update(
            returncode=result.returncode,
            passed=counts["passed"],
            failed=counts["failed"],
        )
        if result.returncode:
            summary["tests"]["tail"] = output[-4000:]

    canonical_root = report_root / "m9-regression"
    canonical_buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(canonical_buffer):
            canonical_code = command_benchmark_run(
                builtin_cases(),
                data_root=DATA_ROOT,
                report_root=canonical_root,
            )
        canonical_payload = json.loads(canonical_buffer.getvalue())
        failed_cases = [
            {
                "case_id": result.get("case_id"),
                "status": result.get("status"),
                "failed_assertions": [
                    {
                        "name": assertion.get("name"),
                        "detail": assertion.get("detail"),
                    }
                    for assertion in result.get("assertions", [])
                    if not assertion.get("passed")
                ],
            }
            for result in canonical_payload.get("results", [])
            if result.get("status") != "pass"
        ]
        summary["canonical_m9_regression"] = {
            "returncode": canonical_code,
            "summary": canonical_payload.get("summary"),
            "failed_cases": failed_cases,
            "report_path": canonical_payload.get("report_path"),
        }
    except Exception as exc:
        summary["canonical_m9_regression"] = {
            "returncode": 1,
            "error": f"{type(exc).__name__}: {exc}",
        }

    provider = None
    try:
        provider = configured_reference(DATA_ROOT)
        if provider is None:
            raise RuntimeError("No configured REFERENCE provider is available")

        with tempfile.TemporaryDirectory(
            prefix="reverend-m10-live-",
            dir=DATA_ROOT,
        ) as temporary:
            fabric = KnowledgeFabric(Path(temporary) / "cache.db")
            reference_report = run_reference_fabric_benchmark(
                provider,
                fabric,
                create_local_scheduler(),
                load_cases(Path("benchmarks/reference-fabric-queries.json")),
                limit=5,
            )

        reference_report["created_at"] = datetime.now(timezone.utc).isoformat()
        reference_root = report_root / "reference-fabric"
        reference_root.mkdir(parents=True, exist_ok=True)
        reference_path = reference_root / f"{stamp}.json"
        reference_path.write_text(
            json.dumps(reference_report, indent=2) + "\n",
            encoding="utf-8",
        )
        summary["reference_fabric"] = {
            "returncode": 0,
            "baseline": reference_report["baseline"],
            "reranked": reference_report["reranked"],
            "quality_delta": reference_report["quality_delta"],
            "quality_decision": quality_decision(reference_report),
            "latency": reference_report["latency"],
            "cache": reference_report["cache"],
            "report_path": str(reference_path),
        }
    except Exception as exc:
        summary["reference_fabric"] = {
            "returncode": 1,
            "error": f"{type(exc).__name__}: {exc}",
        }

    tests_ok = (
        skip_tests
        or summary["tests"]["returncode"] == 0
    )
    canonical = summary["canonical_m9_regression"]
    canonical_summary = canonical.get("summary") or {}
    canonical_ok = (
        canonical.get("returncode") == 0
        and canonical_summary.get("passed") == 3
        and canonical_summary.get("failed") == 0
        and canonical_summary.get("errors") == 0
        and canonical_summary.get("timeouts") == 0
    )
    reference_ok = summary["reference_fabric"].get("returncode") == 0

    summary["overall_ok"] = bool(
        tests_ok
        and canonical_ok
        and reference_ok
    )

    summary_path = report_root / f"validation-{stamp}.json"
    summary["summary_path"] = str(summary_path)
    summary_path.write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )
    return (0 if summary["overall_ok"] else 1), summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--report-root",
        type=Path,
        default=Path("benchmarks/results/vnext/m10/live-validation"),
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip pytest when a green full suite has already been recorded.",
    )
    args = parser.parse_args(argv)

    code, summary = run_validation(
        report_root=args.report_root,
        skip_tests=args.skip_tests,
    )
    print(json.dumps(summary, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
