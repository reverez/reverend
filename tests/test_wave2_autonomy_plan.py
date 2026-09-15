from reverend.autonomy import advance_ready_tasks,build_software_workflow,next_ready_tasks
from reverend.controlplane import ControlPlaneStore,TaskStatus

def test_standard_software_dag_orders_research_architecture_development_assurance(tmp_path):
    store=ControlPlaneStore(tmp_path/"control-plane.db")
    workflow=build_software_workflow(store,"Add feature",acceptance_criteria=("tests pass",),include_product=False)
    ids=workflow.task_ids
    assert store.task(ids["research"]).status is TaskStatus.READY
    assert store.task(ids["architecture"]).dependencies==(ids["research"],)
    assert store.task(ids["development"]).dependencies==(ids["architecture"],)
    assert store.task(ids["verification"]).dependencies==(ids["development"],)
    assert store.task(ids["security"]).dependencies==(ids["development"],)
    assert set(store.task(ids["integration"]).dependencies)=={ids["verification"],ids["security"]}

def test_product_is_optional_but_when_enabled_sits_between_research_and_architecture(tmp_path):
    store=ControlPlaneStore(tmp_path/"control-plane.db")
    workflow=build_software_workflow(store,"MVP",acceptance_criteria=("works",),include_product=True)
    ids=workflow.task_ids
    assert store.task(ids["product"]).dependencies==(ids["research"],)
    assert store.task(ids["architecture"]).dependencies==(ids["product"],)

def test_ready_advancement_follows_completed_dependencies(tmp_path):
    store=ControlPlaneStore(tmp_path/"control-plane.db")
    workflow=build_software_workflow(store,"Feature",acceptance_criteria=("tests pass",))
    research=workflow.task_ids["research"]
    store.transition_task(research,TaskStatus.RUNNING);store.transition_task(research,TaskStatus.COMPLETE)
    ready=advance_ready_tasks(store,workflow)
    assert ready==(workflow.task_ids["architecture"],)
    assert store.task(workflow.task_ids["architecture"]).status is TaskStatus.READY
