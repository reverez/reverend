"""Read-only control-plane projection for the local GUI."""
from __future__ import annotations
from dataclasses import asdict
from typing import Any

from reverend.controlplane import ControlPlaneStore
from reverend.workers import WorkerRole
from reverend.specialists import specialist_from_worker

def _rows(store:ControlPlaneStore,sql:str,params=())->list[dict[str,Any]]:
    with store.connection() as db:
        return [dict(row) for row in db.execute(sql,params).fetchall()]

def _optional_wave2_specialists():
    result=[]
    candidates=(
        ("reverend.intelligence.research_specialist","research_specialist_spec"),
        ("reverend.intelligence.architecture_specialist","architect_specialist_spec"),
        ("reverend.intelligence.development_specialist","development_specialist_spec"),
        ("reverend.intelligence.security_specialist","security_specialist_spec"),
        ("reverend.intelligence.product_specialist","stakeholder_specialist_spec"),
        ("reverend.intelligence.product_specialist","product_specialist_spec"),
        ("reverend.intelligence.failure_investigator","failure_investigator_spec"),
    )
    for module_name,function_name in candidates:
        try:
            module=__import__(module_name,fromlist=[function_name])
            spec=getattr(module,function_name)()
        except (ImportError,AttributeError,ValueError):
            continue
        result.append(spec)
    return tuple(result)

def control_plane_snapshot(store:ControlPlaneStore,scheduler)->dict[str,Any]:
    workflows=_rows(store,"SELECT id,objective,status,trace_id,created_at,updated_at FROM workflows ORDER BY created_at DESC LIMIT 50")
    tasks=_rows(store,"SELECT id,workflow_id,kind,objective,status,created_at,updated_at FROM tasks ORDER BY created_at DESC LIMIT 100")
    jobs=_rows(store,"SELECT id,task_id,attempt_number,status,executor,started_at,finished_at,error_code,result_ref FROM jobs ORDER BY rowid DESC LIMIT 100")
    artifacts=_rows(store,"SELECT id,artifact_type,schema_version,content_hash,producer_job_id,validation_state,promotion_state,created_at FROM artifacts ORDER BY created_at DESC LIMIT 100")
    events=_rows(store,"SELECT id,event_type,occurred_at,actor,subject_json,schema_version FROM events ORDER BY sequence DESC LIMIT 100")
    specialist_specs=[]
    seen=set()
    for role in WorkerRole:
        try:spec=specialist_from_worker(role)
        except Exception:continue
        key=(spec.id,spec.version)
        if key not in seen:
            seen.add(key);specialist_specs.append(spec)
    for spec in _optional_wave2_specialists():
        key=(spec.id,spec.version)
        if key not in seen:
            seen.add(key);specialist_specs.append(spec)
    specialists=[
        {
            "id":spec.id,"version":spec.version,"name":spec.name,
            "model_role":spec.model_role.value,
            "methodology":spec.methodology_binding,
            "authority_profile":spec.authority_profile,
            "inputs":list(spec.input_artifact_types),
            "outputs":list(spec.output_artifact_types),
            "capabilities":list(spec.required_capabilities),
            "independent_verifier":spec.independent_verifier,
        }
        for spec in specialist_specs
    ]
    models=[]
    for role in scheduler.registry.roles():
        spec=scheduler.registry.spec(role)
        try:row=asdict(spec)
        except TypeError:row={key:value for key,value in vars(spec).items() if not key.startswith("_")}
        row["role"]=role.value
        models.append(row)
    try:loaded=scheduler.provider.loaded_models()
    except Exception:loaded=[]
    verification_events=[
        event for event in events
        if "verification" in str(event.get("event_type","")).casefold()
        or "verify" in str(event.get("event_type","")).casefold()
    ]
    resource_events=[
        event for event in events
        if "resource" in str(event.get("event_type","")).casefold()
        or "lease" in str(event.get("event_type","")).casefold()
        or "model" in str(event.get("event_type","")).casefold()
    ]
    return {
        "read_only":True,
        "workflows":workflows,
        "tasks":tasks,
        "jobs":jobs,
        "specialists":specialists,
        "models":models,
        "loaded_models":loaded,
        "resources":{"events":resource_events[:30],"loaded_models":loaded},
        "artifacts":artifacts,
        "verification":{"events":verification_events[:30]},
        "counts":{
            "workflows":len(workflows),"tasks":len(tasks),"jobs":len(jobs),
            "specialists":len(specialists),"models":len(models),"artifacts":len(artifacts),
        },
    }
