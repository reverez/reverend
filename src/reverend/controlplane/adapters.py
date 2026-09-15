"""Read-only compatibility adapters for accepted task/run state."""
from __future__ import annotations
from typing import Any
_WORKSTATION_STATE={"active":"running","blocked":"blocked","complete":"complete","failed":"failed","cancelled":"cancelled"}
_DEVELOPMENT_STATE={"pending":"pending","preparing":"ready","running":"running","verifying":"running","blocked":"blocked","complete":"complete","failed":"failed","cancelled":"cancelled"}
def _value(value:Any)->str:return str(getattr(value,"value",value))
def workstation_task_snapshot(task:Any)->dict[str,Any]:
    state=_value(getattr(task,"state","active"))
    return {"external_id":str(task.id),"source":"workstation_authoritative_task","kind":str(task.kind),"objective":str(task.objective),"status":_WORKSTATION_STATE.get(state,state),"acceptance_criteria":tuple(task.acceptance_criteria),"provenance":{"conversation_id":str(task.conversation_id),"specification_hash":str(task.specification_hash),"specification_version":int(task.specification_version)}}
def development_task_snapshot(task:Any)->dict[str,Any]:
    state=_value(getattr(task,"state","pending"));criteria=getattr(task,"acceptance_criteria",None)
    return {"external_id":str(task.id),"source":"development_task","kind":"development","objective":str(getattr(task,"title","") or getattr(task,"request","")),"status":_DEVELOPMENT_STATE.get(state,state),"acceptance_criteria":(str(criteria),) if criteria else (),"provenance":{"project_id":str(task.project_id),"base_commit":getattr(task,"base_commit",None)}}
def development_job_snapshot(run:Any)->dict[str,Any]:
    return {"external_id":str(run.id),"source":"development_task_run","task_id":str(run.task_id),"attempt_number":int(run.run_number),"status":_value(run.status),"executor":getattr(run,"model_role",None),"result_ref":None,"provenance":{"model_name":getattr(run,"model_name",None),"base_commit":getattr(run,"base_commit",None)}}
