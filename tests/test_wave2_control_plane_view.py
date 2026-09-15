from reverend.controlplane import ControlPlaneStore,JobStatus,TaskStatus,WorkflowStatus
from reverend.controlplane.view import control_plane_snapshot
from reverend.runtime import ModelRole

class Spec:
    model="model"
    context=4096
    think=False
    keep_alive="5m"
    exclusive_memory=False
    description="test"
class Registry:
    def roles(self):return (ModelRole.FAST_GENERAL,)
    def spec(self,role):return Spec()
class Provider:
    def loaded_models(self):return []
class Scheduler:
    registry=Registry();provider=Provider()

def test_control_plane_snapshot_is_read_only_and_correlated(tmp_path):
    store=ControlPlaneStore(tmp_path/"control-plane.db")
    workflow=store.create_workflow("Build feature");store.transition_workflow(workflow.id,WorkflowStatus.ACTIVE)
    task=store.create_task(workflow.id,kind="development",objective="Implement");store.transition_task(task.id,TaskStatus.READY);store.transition_task(task.id,TaskStatus.RUNNING)
    job=store.create_job(task.id,executor="development_intelligence");store.transition_job(job.id,JobStatus.RUNNING)
    artifact=store.create_artifact("implementation_patch",inline_content="diff",producer_job_id=job.id,provenance={"class":"GENERATED"})
    snapshot=control_plane_snapshot(store,Scheduler())
    assert snapshot["read_only"] is True
    assert snapshot["workflows"][0]["id"]==workflow.id
    assert snapshot["tasks"][0]["workflow_id"]==workflow.id
    assert snapshot["jobs"][0]["task_id"]==task.id
    assert snapshot["artifacts"][0]["id"]==artifact.id
    assert snapshot["models"][0]["role"]=="fast_general"
    assert snapshot["specialists"]
