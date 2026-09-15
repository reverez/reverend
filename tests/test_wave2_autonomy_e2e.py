from __future__ import annotations
import json
from reverend.autonomy import StageOutput,run_software_autonomy
from reverend.controlplane import ControlPlaneStore,PromotionState,WorkflowStatus

def executors(*,verify=True,security_block=False,integrate=True):
    def research(ctx):
        return StageOutput("evidence_pack",{"status":"supported"},"RESEARCH_BACKED")
    def architecture(ctx):
        assert ctx.parent_artifacts
        return StageOutput("architecture_decision",{"decision":"extend"},"GENERATED")
    def development(ctx):
        return StageOutput("implementation_patch",{"diff":"change"},"GENERATED")
    def verification(ctx):
        return StageOutput("verification_result",{"accepted":verify},"OBSERVED",verification_accepted=verify)
    def security(ctx):
        return StageOutput("security_assessment",{"blocked":security_block},"GENERATED",promotion_blocked=security_block)
    def integration(ctx):
        return StageOutput("integration_decision",{"accepted":integrate},"OBSERVED",integration_accepted=integrate)
    return {
        "research":research,"architecture":architecture,"development":development,
        "verification":verification,"security":security,"integration":integration,
    }

def test_e2e_autonomy_promotes_only_after_all_assurance_gates_accept(tmp_path):
    store=ControlPlaneStore(tmp_path/"control-plane.db")
    result=run_software_autonomy(
        store,"Add safe feature",acceptance_criteria=("tests pass",),
        executors=executors(),
    )
    assert result.status=="complete" and result.promoted is True
    implementation=store.artifact(result.implementation_artifact_id)
    assert implementation.validation_state.value=="validated"
    assert implementation.promotion_state is PromotionState.PROMOTED
    assert store.workflow(result.workflow_id).status is WorkflowStatus.COMPLETE
    events=store.events(event_type="AutonomyStageCompleted")
    assert [event.payload["stage"] for event in events]==[
        "research","architecture","development","verification","security","integration"
    ]
    integration_artifact=store.artifact(result.artifacts["integration"])
    assert set(integration_artifact.parent_ids)=={
        result.artifacts["verification"],result.artifacts["security"]
    }

def test_security_block_overrides_positive_integration(tmp_path):
    store=ControlPlaneStore(tmp_path/"control-plane.db")
    result=run_software_autonomy(
        store,"Feature",acceptance_criteria=("tests pass",),
        executors=executors(security_block=True,integrate=True),
    )
    assert result.status=="blocked"
    assert result.promoted is False
    assert "security blocked" in result.reason
    assert store.artifact(result.implementation_artifact_id).promotion_state.value=="unpromoted"

def test_verification_rejection_prevents_promotion(tmp_path):
    store=ControlPlaneStore(tmp_path/"control-plane.db")
    result=run_software_autonomy(
        store,"Feature",acceptance_criteria=("tests pass",),
        executors=executors(verify=False,integrate=True),
    )
    assert result.status=="blocked" and result.promoted is False
    implementation=store.artifact(result.implementation_artifact_id)
    assert implementation.validation_state.value=="rejected"

def test_missing_stage_executor_fails_before_workflow_creation(tmp_path):
    store=ControlPlaneStore(tmp_path/"control-plane.db")
    callbacks=executors();callbacks.pop("security")
    try:
        run_software_autonomy(store,"Feature",acceptance_criteria=("tests pass",),executors=callbacks)
    except ValueError as exc:
        assert "security" in str(exc)
    else:
        raise AssertionError("missing stage should fail")
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM workflows").fetchone()[0]==0
