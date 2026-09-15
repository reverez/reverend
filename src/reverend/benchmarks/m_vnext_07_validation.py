"""Live M-VNEXT-07 Failure Investigator acceptance."""
from __future__ import annotations

import argparse
import json
import tempfile
import time
from pathlib import Path
from typing import Any

from reverend.controlplane import ControlPlaneStore, WorkflowStatus
from reverend.intelligence.failure_investigator import investigate_workflow_failure


def run_live_failure_investigator(*, scheduler=None) -> dict[str, Any]:
    if scheduler is None:
        from reverend.development.coder import create_local_scheduler
        scheduler = create_local_scheduler()

    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="reverend-failure-live-") as temp:
        store = ControlPlaneStore(Path(temp) / "control-plane.db")
        source = store.create_workflow("Ship a feature with independent security review")
        store.transition_workflow(source.id, WorkflowStatus.ACTIVE)
        store.transition_workflow(source.id, WorkflowStatus.FAILED)
        store.append_event(
            "AutonomyPromotionBlocked",
            actor="executive_orchestrator",
            subject_ids=(source.id,),
            trace_context={"workflow_id": source.id},
            payload={
                "verification_accepted": True,
                "security_blocked": True,
                "integration_accepted": True,
                "reasons": ["security blocked promotion"],
            },
        )
        source_before = store.workflow(source.id)
        try:
            diagnostic_id, report, artifact_id = investigate_workflow_failure(
                store,
                scheduler,
                source.id,
            )
            source_unchanged = store.workflow(source.id) == source_before
            diagnostic_complete = (
                store.workflow(diagnostic_id).status is WorkflowStatus.COMPLETE
            )
            artifact = store.artifact(artifact_id)
            artifact_unpromoted = artifact.promotion_state.value == "unpromoted"
            cited = {
                ref
                for finding in report.findings
                for ref in finding.evidence_refs
            }
            event_cited = any(ref.startswith("event:") for ref in cited)
            security_identified = (
                report.primary_category == "security"
                or any(finding.category == "security" for finding in report.findings)
            )
            passed = all(
                (
                    source_unchanged,
                    diagnostic_complete,
                    artifact_unpromoted,
                    event_cited,
                    security_identified,
                )
            )
            error = None
            result = {
                "source_workflow_id": source.id,
                "diagnostic_workflow_id": diagnostic_id,
                "artifact_id": artifact_id,
                "primary_category": report.primary_category,
                "summary": report.summary,
                "finding_count": len(report.findings),
                "event_cited": event_cited,
                "security_identified": security_identified,
                "source_unchanged": source_unchanged,
                "diagnostic_complete": diagnostic_complete,
                "artifact_unpromoted": artifact_unpromoted,
            }
        except Exception as exc:
            passed = False
            error = {
                "type": type(exc).__name__,
                "message": str(exc)[:1000],
            }
            result = {}

    return {
        "schema_version": 1,
        "suite": "M-VNEXT-07 live Failure Investigator acceptance",
        "passed": passed,
        "elapsed_seconds": round(time.monotonic() - started, 4),
        "result": result,
        "error": error,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = run_live_failure_investigator()
    text = json.dumps(report, indent=2, sort_keys=True, default=str) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
