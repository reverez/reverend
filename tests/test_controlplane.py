from __future__ import annotations
import hashlib,sqlite3
from types import SimpleNamespace
import pytest
from reverend.controlplane import ArtifactStateError,ControlPlaneStore,DependencyCycleError,JobStatus,PromotionState,StateTransitionError,TaskStatus,ValidationState,WorkflowStatus,default_control_plane_path,development_job_snapshot,development_task_snapshot,workstation_task_snapshot

def store(tmp_path):return ControlPlaneStore(tmp_path/"control-plane.db")
def test_default_path_uses_authoritative_data_root(tmp_path):assert default_control_plane_path(tmp_path)==tmp_path/"control-plane.db"
def test_workflow_dag_rejects_cycles_and_blocks_readiness(tmp_path):
    db=store(tmp_path);w=db.create_workflow("Build a verified feature");a=db.create_task(w.id,kind="research",objective="Research");b=db.create_task(w.id,kind="implement",objective="Implement",dependencies=(a.id,))
    with pytest.raises(StateTransitionError,match="dependency"):db.transition_task(b.id,TaskStatus.READY)
    with pytest.raises(DependencyCycleError):db.add_dependency(a.id,b.id)
    db.transition_workflow(w.id,WorkflowStatus.ACTIVE);db.transition_task(a.id,TaskStatus.READY);db.transition_task(a.id,TaskStatus.RUNNING);db.transition_task(a.id,TaskStatus.COMPLETE)
    assert db.transition_task(b.id,TaskStatus.READY).status is TaskStatus.READY
def test_retries_create_distinct_jobs_and_preserve_history(tmp_path):
    db=store(tmp_path);w=db.create_workflow("Retry safely");t=db.create_task(w.id,kind="implement",objective="Implement");first=db.create_job(t.id,executor="developer");db.transition_job(first.id,JobStatus.RUNNING);db.transition_job(first.id,JobStatus.FAILED,error_code="tests_failed");second=db.create_job(t.id,executor="developer")
    assert second.id!=first.id and second.attempt_number==2
    jobs=db.jobs_for_task(t.id);assert [j.attempt_number for j in jobs]==[1,2];assert jobs[0].status is JobStatus.FAILED and jobs[0].error_code=="tests_failed"
def test_job_lifecycle_is_bounded(tmp_path):
    db=store(tmp_path);w=db.create_workflow("Lifecycle");t=db.create_task(w.id,kind="verify",objective="Verify");j=db.create_job(t.id,executor="verifier");j=db.transition_job(j.id,JobStatus.ACQUIRING_RESOURCES);j=db.transition_job(j.id,JobStatus.RUNNING);j=db.transition_job(j.id,JobStatus.VERIFYING);j=db.transition_job(j.id,JobStatus.SUCCEEDED,result_ref="artifact:result")
    assert j.started_at and j.finished_at
    with pytest.raises(StateTransitionError):db.transition_job(j.id,JobStatus.RUNNING)
def test_events_are_append_only_at_database_boundary(tmp_path):
    db=store(tmp_path);e=db.append_event("JobStarted",actor="runtime",subject_ids=("job-1",),payload={"bounded":True});assert db.events()[0]==e
    with db.connection() as c:
        with pytest.raises(sqlite3.IntegrityError,match="immutable"):c.execute("UPDATE events SET actor='changed' WHERE id=?",(e.id,))
        with pytest.raises(sqlite3.IntegrityError,match="immutable"):c.execute("DELETE FROM events WHERE id=?",(e.id,))
def test_artifact_hash_lineage_validation_and_promotion_are_separate(tmp_path):
    db=store(tmp_path);w=db.create_workflow("Artifacts");t=db.create_task(w.id,kind="implement",objective="Produce");j=db.create_job(t.id,executor="developer")
    p=db.create_artifact("research_report",inline_content="evidence-backed input",producer_job_id=j.id,provenance={"class":"RESEARCH_BACKED"});c=db.create_artifact("patch",inline_content="diff payload",producer_job_id=j.id,parent_ids=(p.id,),provenance={"class":"GENERATED"})
    assert c.content_hash==hashlib.sha256(b"diff payload").hexdigest() and c.parent_ids==(p.id,) and c.validation_state is ValidationState.UNVALIDATED and c.promotion_state is PromotionState.UNPROMOTED
    with pytest.raises(ArtifactStateError):db.promote_artifact(c.id)
    c=db.validate_artifact(c.id,accepted=True);assert c.validation_state is ValidationState.VALIDATED and c.promotion_state is PromotionState.UNPROMOTED
    assert db.promote_artifact(c.id).promotion_state is PromotionState.PROMOTED
def test_rejected_artifact_cannot_be_promoted_or_redecided(tmp_path):
    db=store(tmp_path);a=db.create_artifact("report",inline_content="bad");assert db.validate_artifact(a.id,accepted=False).validation_state is ValidationState.REJECTED
    with pytest.raises(ArtifactStateError):db.promote_artifact(a.id)
    with pytest.raises(ArtifactStateError):db.validate_artifact(a.id,accepted=True)
def test_referenced_artifact_requires_integrity_hash(tmp_path):
    db=store(tmp_path)
    with pytest.raises(ValueError,match="content_hash"):db.create_artifact("file",content_ref="artifacts/file.bin")
def test_existing_state_adapters_are_read_only_semantic_views():
    ws=SimpleNamespace(id="task-ws",conversation_id="conversation",kind="research",state=SimpleNamespace(value="active"),objective="Research objective",acceptance_criteria=("cite sources",),specification_hash="abc",specification_version=2);assert workstation_task_snapshot(ws)["status"]=="running"
    dev=SimpleNamespace(id="task-dev",project_id="project",title="Implement",request="Do it",acceptance_criteria="tests pass",state=SimpleNamespace(value="verifying"),base_commit="deadbeef");s=development_task_snapshot(dev);assert s["status"]=="running" and s["provenance"]["base_commit"]=="deadbeef"
    run=SimpleNamespace(id="run",task_id="task-dev",run_number=3,status=SimpleNamespace(value="failed"),model_role="strong_code",model_name="qwen",base_commit="deadbeef");assert development_job_snapshot(run)["attempt_number"]==3
