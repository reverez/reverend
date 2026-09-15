"""CLI-facing operations for ReverendBench."""

from __future__ import annotations

import json
from collections.abc import Sequence

from reverend.benchmarks.models import BenchmarkCase


def case_payload(case: BenchmarkCase) -> dict:
    return {
        "case_id": case.case_id,
        "name": case.name,
        "category": case.category.value,
        "tags": list(case.tags),
        "budget": {
            "timeout_seconds": case.budget.timeout_seconds,
            "max_model_calls": case.budget.max_model_calls,
            "max_retrieval_rounds": (
                case.budget.max_retrieval_rounds
            ),
        },
    }


def command_benchmark_list(
    cases: Sequence[BenchmarkCase],
) -> int:
    payload = {
        "count": len(cases),
        "cases": [
            case_payload(case)
            for case in cases
        ],
    }

    print(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        )
    )

    return 0


def command_benchmark_run_unavailable() -> int:
    """Fail explicitly until executable M6 cases are registered."""

    payload = {
        "ok": False,
        "error": (
            "No executable ReverendBench suite is registered yet. "
            "M6.3 will add the first product regression cases."
        ),
    }

    print(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        )
    )

    return 2


def command_benchmark_run(
    cases,
    *,
    data_root,
    case_ids=None,
    workstation_factory=None,
    executor_factory=None,
    report_root=None,
) -> int:
    """Execute ReverendBench against an isolated Workstation."""

    from dataclasses import asdict
    import hashlib
    import platform
    import subprocess
    from datetime import datetime, timezone
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from uuid import uuid4

    from reverend.benchmarks.evaluator import evaluate_expectations
    from reverend.benchmarks.reporting import BenchmarkRun, save_run
    from reverend.benchmarks.runner import BenchmarkRunner
    from reverend.benchmarks.workstation import WorkstationChatExecutor

    selected_ids = set(case_ids or ())
    selected = tuple(
        case
        for case in cases
        if not selected_ids or case.case_id in selected_ids
    )

    missing = selected_ids - {
        case.case_id for case in cases
    }

    if missing:
        print(json.dumps({
            "ok": False,
            "error": "Unknown benchmark case(s)",
            "case_ids": sorted(missing),
        }, indent=2))
        return 2

    if not selected:
        print(json.dumps({
            "ok": False,
            "error": "No benchmark cases selected",
        }, indent=2))
        return 2

    data_root = Path(data_root)
    code_root = Path(__file__).resolve().parents[3]
    try:
        revision = subprocess.run(['git','-C',str(code_root),'rev-parse','HEAD'],
            capture_output=True,text=True,check=True,timeout=5).stdout.strip()
    except (OSError,subprocess.SubprocessError):
        revision = None
    definitions = [asdict(case) for case in selected]
    case_digest = hashlib.sha256(json.dumps(definitions,sort_keys=True).encode()).hexdigest()
    started = datetime.now(timezone.utc)
    run_id = (
        started.strftime("%Y%m%dT%H%M%S%fZ")
        + "-"
        + uuid4().hex[:8]
    )

    if workstation_factory is None:
        from reverend.workstation.service import Workstation
        workstation_factory = Workstation

    with TemporaryDirectory(
        prefix="reverend-bench-"
    ) as temporary:
        workstation = workstation_factory(
            root=Path(temporary),
            knowledge_db_path=data_root / "platform.db",
        )

        try:
            executor = (
                executor_factory(workstation)
                if executor_factory is not None
                else WorkstationChatExecutor(workstation)
            )

            results = BenchmarkRunner(
                executor=executor,
                evaluator=evaluate_expectations,
            ).run(selected)
        finally:
            workstation.close()

    completed = datetime.now(timezone.utc)

    run = BenchmarkRun(
        run_id=run_id,
        started_at=started.isoformat(),
        completed_at=completed.isoformat(),
        results=results,
        metadata={
            "case_count": len(selected),
            "state_isolated": True,
            "code_revision": revision,
            "python_version": platform.python_version(),
            "case_definitions": definitions,
            "case_sha256": case_digest,
            "knowledge_database": str(data_root/'platform.db'),
        },
    )

    destination = save_run(
        run,
        root=Path(report_root) if report_root is not None else data_root,
    )

    payload = run.to_dict()
    payload["report_path"] = str(destination)

    print(json.dumps(
        payload,
        indent=2,
        ensure_ascii=False,
    ))

    return 0 if run.summary.failed == 0 \
        and run.summary.errors == 0 \
        and run.summary.timeouts == 0 else 1
