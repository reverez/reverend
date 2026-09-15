from __future__ import annotations

import json
import re
from types import SimpleNamespace

import pytest

from reverend.autonomy import StageOutput, run_software_autonomy
from reverend.benchmarks.m_vnext_07_validation import run_live_failure_investigator
from reverend.controlplane import ControlPlaneStore, WorkflowStatus
from reverend.controlplane.view import control_plane_snapshot
from reverend.intelligence.failure_investigator import (
    FailureCase,
    FailureEvidence,
    RootCauseFinding,
    build_failure_investigation_pack,
    collect_failure_case,
    failure_investigator_spec,
    investigate_workflow_failure,
    run_failure_investigation,
)
from reverend.runtime import ModelRole


def _executors(*, security_block: bool = False):
    def research(_ctx):
        return StageOutput("evidence_pack", {"supported": True}, "RESEARCH_BACKED")

    def architecture(_ctx):
        return StageOutput("architecture_decision", {"decision": "extend"}, "GENERATED")

    def development(_ctx):
        return StageOutput(
            "implementation_patch",
            {"diff": "SECRET_IMPLEMENTATION_PAYLOAD"},
            "GENERATED",
        )

    def verification(_ctx):
        return StageOutput(
            "verification_result",
            {"accepted": True},
            "OBSERVED",
            verification_accepted=True,
        )

    def security(_ctx):
        return StageOutput(
            "security_assessment",
            {"blocked": security_block},
            "GENERATED",
            promotion_blocked=security_block,
        )

    def integration(_ctx):
        return StageOutput(
            "integration_decision",
            {"accepted": True},
            "OBSERVED",
            integration_accepted=True,
        )

    return {
        "research": research,
        "architecture": architecture,
        "development": development,
        "verification": verification,
        "security": security,
        "integration": integration,
    }


def test_failure_investigator_has_diagnosis_only_authority():
    spec = failure_investigator_spec()
    assert spec.model_role is ModelRole.DEEP_REASON
    assert spec.authority_profile == "diagnosis_only"
    assert spec.output_artifact_types == ("failure_investigation",)
    assert spec.metadata["may_repair"] is False
    assert spec.metadata["may_execute"] is False
    assert spec.metadata["may_promote"] is False
    assert all("write" not in capability for capability in spec.required_capabilities)


def test_autonomy_block_records_payload_minimized_failure_evidence(tmp_path):
    store = ControlPlaneStore(tmp_path / "control-plane.db")
    result = run_software_autonomy(
        store,
        "Add guarded feature",
        acceptance_criteria=("tests pass",),
        executors=_executors(security_block=True),
    )
    assert result.status == "blocked"
    case = collect_failure_case(store, result.workflow_id)

    serialized = json.dumps(
        [
            {
                "id": item.evidence_id,
                "summary": item.summary,
                "metadata": dict(item.metadata),
            }
            for item in case.evidence
        ],
        sort_keys=True,
    )
    assert "SECRET_IMPLEMENTATION_PAYLOAD" not in serialized
    assert any(
        item.kind == "control_event"
        and "AutonomyPromotionBlocked" in item.summary
        for item in case.evidence
    )
    assert any("security_blocked" in item.summary for item in case.evidence)


def test_stage_exception_records_failure_event_for_investigation(tmp_path):
    store = ControlPlaneStore(tmp_path / "control-plane.db")
    callbacks = _executors()

    def explode(_ctx):
        raise RuntimeError("private message should not be persisted")

    callbacks["architecture"] = explode
    result = run_software_autonomy(
        store,
        "Fail safely",
        acceptance_criteria=("tests pass",),
        executors=callbacks,
    )
    assert result.status == "failed"
    case = collect_failure_case(store, result.workflow_id)
    event_rows = [
        item for item in case.evidence
        if item.kind == "control_event"
        and "AutonomyStageFailed" in item.summary
    ]
    assert event_rows
    assert "RuntimeError" in event_rows[0].summary
    assert "private message should not be persisted" not in event_rows[0].summary


def test_model_diagnosis_must_reference_observed_evidence():
    case = FailureCase(
        workflow_id="workflow-1",
        objective="Diagnose failure",
        workflow_status="failed",
        evidence=(
            FailureEvidence(
                "job:1",
                "job",
                "development job status=failed error_code=TestFailure",
            ),
        ),
        failed_job_ids=("1",),
    )
    payload = {
        "summary": "A deterministic test failure stopped development.",
        "primary_category": "verification",
        "findings": [
            {
                "finding_id": "FAIL-1",
                "category": "verification",
                "certainty": "confirmed",
                "statement": "The observed job failed its required test gate.",
                "evidence_refs": ["job:1"],
            }
        ],
        "contributing_factors": [],
        "recommended_actions": ["Inspect the failing deterministic test."],
        "regression_case": {
            "should_add": True,
            "title": "Preserve deterministic failure gate",
            "trigger": "Required verification fails",
            "expected_invariant": "The workflow cannot report success.",
        },
        "reproduction_requirements": ["Run the required verification command."],
        "unresolved_questions": [],
    }

    class Scheduler:
        def generate(self, role, prompt, **kwargs):
            assert role is ModelRole.DEEP_REASON
            assert "ALLOWED EVIDENCE IDS" in prompt
            assert '"job:1"' in prompt
            evidence_schema = (
                kwargs["response_format"]["properties"]["findings"]["items"]
                ["properties"]["evidence_refs"]["items"]
            )
            assert evidence_schema["enum"] == ["job:1"]
            return SimpleNamespace(
                response={"response": json.dumps(payload)},
                model="deep-reason",
                digest="digest",
            )

    report = run_failure_investigation(Scheduler(), case=case)
    assert report.primary_category == "verification"
    assert report.findings[0].evidence_refs == ("job:1",)
    assert report.regression_case["should_add"] is True


def test_unknown_model_evidence_reference_is_rejected():
    case = FailureCase(
        workflow_id="workflow-1",
        objective="Diagnose failure",
        workflow_status="failed",
        evidence=(FailureEvidence("event:1", "control_event", "stage failed"),),
    )
    with pytest.raises(ValueError, match="unknown evidence"):
        build_failure_investigation_pack(
            case=case,
            summary="Diagnosis",
            primary_category="runtime",
            findings=(
                RootCauseFinding(
                    "FAIL-1",
                    "runtime",
                    "possible",
                    "Unsupported cause",
                    ("event:missing",),
                ),
            ),
        )


def test_investigation_uses_separate_workflow_and_never_mutates_source(tmp_path):
    store = ControlPlaneStore(tmp_path / "control-plane.db")
    source = store.create_workflow("Broken workflow")
    store.transition_workflow(source.id, WorkflowStatus.ACTIVE)
    store.transition_workflow(source.id, WorkflowStatus.FAILED)
    source_before = store.workflow(source.id)

    def runner(_scheduler, *, case):
        return build_failure_investigation_pack(
            case=case,
            summary="The source workflow is observed failed; no deeper cause is established.",
            primary_category="unknown",
            findings=(
                RootCauseFinding(
                    "FAIL-1",
                    "unknown",
                    "possible",
                    "Only the terminal workflow state is currently observed.",
                    (f"workflow:{source.id}",),
                ),
            ),
            recommended_actions=("Collect a failed job or trace span.",),
            regression_case={
                "should_add": False,
                "title": "",
                "trigger": "",
                "expected_invariant": "",
            },
            unresolved_questions=("Which stage produced the failure?",),
        )

    diagnostic_id, report, artifact_id = investigate_workflow_failure(
        store,
        object(),
        source.id,
        runner=runner,
    )

    assert store.workflow(source.id) == source_before
    assert store.workflow(diagnostic_id).status is WorkflowStatus.COMPLETE
    artifact = store.artifact(artifact_id)
    assert artifact.artifact_type == "failure_investigation"
    assert artifact.validation_state.value == "unvalidated"
    assert artifact.promotion_state.value == "unpromoted"
    assert report.source_workflow_id == source.id
    event = store.events(event_type="FailureInvestigationCompleted")[-1]
    assert source.id in event.subject_ids
    assert diagnostic_id in event.subject_ids


class _Spec:
    model = "model"
    context = 4096
    think = False
    keep_alive = "5m"
    exclusive_memory = False
    description = "test"


class _Registry:
    def roles(self):
        return (ModelRole.FAST_GENERAL,)

    def spec(self, _role):
        return _Spec()


class _Provider:
    def loaded_models(self):
        return []


class _SchedulerView:
    registry = _Registry()
    provider = _Provider()


def test_control_plane_discovers_failure_investigator(tmp_path):
    store = ControlPlaneStore(tmp_path / "control-plane.db")
    snapshot = control_plane_snapshot(store, _SchedulerView())
    by_name = {item["name"]: item for item in snapshot["specialists"]}
    investigator = by_name["Failure Investigator"]
    assert investigator["authority_profile"] == "diagnosis_only"
    assert investigator["model_role"] == "deep_reason"


def test_live_harness_contract_with_fake_local_scheduler():
    class Scheduler:
        def generate(self, role, prompt, **_kwargs):
            assert role is ModelRole.DEEP_REASON
            match = re.search(r'"evidence_id":\s*"(event:[^"]+)"', prompt)
            assert match is not None
            event_ref = match.group(1)
            payload = {
                "summary": "Promotion was blocked by the observed security gate.",
                "primary_category": "security",
                "findings": [
                    {
                        "finding_id": "FAIL-SEC-1",
                        "category": "security",
                        "certainty": "confirmed",
                        "statement": "The security gate explicitly blocked promotion.",
                        "evidence_refs": [event_ref],
                    }
                ],
                "contributing_factors": [],
                "recommended_actions": [
                    "Review the blocking security finding before any retry."
                ],
                "regression_case": {
                    "should_add": True,
                    "title": "Security block prevents promotion",
                    "trigger": "Security gate reports blocked",
                    "expected_invariant": "Implementation remains unpromoted.",
                },
                "reproduction_requirements": [
                    "Create a workflow with a blocking security decision."
                ],
                "unresolved_questions": [],
            }
            return SimpleNamespace(
                response={"response": json.dumps(payload)},
                model="fake-deep-reason",
                digest="fake",
            )

    report = run_live_failure_investigator(scheduler=Scheduler())
    assert report["passed"] is True
    assert report["result"]["security_identified"] is True
    assert report["result"]["event_cited"] is True
    assert report["result"]["source_unchanged"] is True
    assert report["result"]["artifact_unpromoted"] is True
