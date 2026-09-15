"""Bounded Wave-2 software autonomy orchestration over the authoritative control plane."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any,Callable,Mapping

from reverend.controlplane import ControlPlaneStore,TaskStatus,WorkflowStatus

@dataclass(frozen=True)
class SoftwareWorkflow:
    workflow_id:str
    task_ids:Mapping[str,str]
    include_product:bool
    def __post_init__(self):
        object.__setattr__(self,"task_ids",dict(self.task_ids))

def build_software_workflow(
    store:ControlPlaneStore,
    objective:str,
    *,
    acceptance_criteria:tuple[str,...],
    include_product:bool=False,
)->SoftwareWorkflow:
    """Create the canonical Wave-2 DAG without executing specialist work."""
    workflow=store.create_workflow(objective)
    store.transition_workflow(workflow.id,WorkflowStatus.ACTIVE)

    research=store.create_task(
        workflow.id,kind="research",objective="Build evidence for: "+objective,
        acceptance_criteria=("Evidence provenance remains explicit.",),
    )
    task_ids={"research":research.id}
    prior=research.id

    if include_product:
        product=store.create_task(
            workflow.id,kind="product",objective="Define product scope for: "+objective,
            dependencies=(prior,),
            acceptance_criteria=("Requirements, non-goals and success criteria are explicit.",),
        )
        task_ids["product"]=product.id;prior=product.id

    architect=store.create_task(
        workflow.id,kind="architecture",objective="Produce architecture decision for: "+objective,
        dependencies=(prior,),
        acceptance_criteria=("State ownership, failure semantics and migration are explicit.",),
    )
    task_ids["architecture"]=architect.id

    development=store.create_task(
        workflow.id,kind="development",objective="Implement approved architecture for: "+objective,
        dependencies=(architect.id,),acceptance_criteria=acceptance_criteria,
    )
    task_ids["development"]=development.id

    verification=store.create_task(
        workflow.id,kind="verification",objective="Independently verify implementation for: "+objective,
        dependencies=(development.id,),acceptance_criteria=acceptance_criteria,
    )
    task_ids["verification"]=verification.id

    security=store.create_task(
        workflow.id,kind="security",objective="Review trust boundaries and capabilities for: "+objective,
        dependencies=(development.id,),
        acceptance_criteria=("Critical security findings block promotion.",),
    )
    task_ids["security"]=security.id

    integration=store.create_task(
        workflow.id,kind="integration",objective="Check global Reverend compatibility for: "+objective,
        dependencies=(verification.id,security.id),
        acceptance_criteria=("All global compatibility domains are checked.",),
    )
    task_ids["integration"]=integration.id

    store.transition_task(research.id,TaskStatus.READY)
    return SoftwareWorkflow(workflow.id,task_ids,include_product)

def next_ready_tasks(store:ControlPlaneStore,workflow:SoftwareWorkflow)->tuple[str,...]:
    """Return dependency-satisfied pending tasks without mutating them."""
    ready=[]
    for _kind,task_id in workflow.task_ids.items():
        task=store.task(task_id)
        if task.status is not TaskStatus.PENDING:
            continue
        dependencies=[store.task(dep) for dep in task.dependencies]
        if all(dep.status is TaskStatus.COMPLETE for dep in dependencies):
            ready.append(task_id)
    return tuple(ready)

def advance_ready_tasks(store:ControlPlaneStore,workflow:SoftwareWorkflow)->tuple[str,...]:
    ids=next_ready_tasks(store,workflow)
    for task_id in ids:store.transition_task(task_id,TaskStatus.READY)
    return ids


from dataclasses import asdict, is_dataclass
import json
from types import MappingProxyType
from reverend.controlplane import JobStatus, PromotionState

@dataclass(frozen=True)
class StageContext:
    workflow_id:str
    task_id:str
    kind:str
    objective:str
    parent_artifact_ids:tuple[str,...]
    parent_artifacts:tuple[Any,...]

@dataclass(frozen=True)
class StageOutput:
    artifact_type:str
    payload:Any
    provenance_class:str
    verification_accepted:bool|None=None
    promotion_blocked:bool=False
    integration_accepted:bool|None=None
    metadata:Mapping[str,Any]=MappingProxyType({})
    def __post_init__(self):
        if not self.artifact_type or not self.provenance_class:
            raise ValueError("Stage output requires artifact type and provenance class")
        object.__setattr__(self,"metadata",MappingProxyType(dict(self.metadata)))

@dataclass(frozen=True)
class AutonomyResult:
    workflow_id:str
    status:str
    artifacts:Mapping[str,str]
    implementation_artifact_id:str|None
    promoted:bool
    reason:str
    def __post_init__(self):
        object.__setattr__(self,"artifacts",MappingProxyType(dict(self.artifacts)))

StageExecutor=Callable[[StageContext],StageOutput]

def _serialize_stage_payload(payload:Any)->str:
    if is_dataclass(payload):
        value=asdict(payload)
    elif isinstance(payload,Mapping):
        value=dict(payload)
    elif isinstance(payload,(list,tuple,str,int,float,bool)) or payload is None:
        value=payload
    elif hasattr(payload,"metadata") and callable(payload.metadata):
        value=payload.metadata()
    else:
        raise ValueError("Stage payload must be a dataclass, mapping, scalar or metadata-bearing object")
    text=json.dumps(value,sort_keys=True,ensure_ascii=False,default=str)
    if len(text.encode("utf-8"))>60*1024:
        raise ValueError("Stage payload exceeds inline artifact budget")
    return text

def run_software_autonomy(
    store:ControlPlaneStore,
    objective:str,
    *,
    acceptance_criteria:tuple[str,...],
    executors:Mapping[str,StageExecutor],
    include_product:bool=False,
)->AutonomyResult:
    """Execute the canonical Wave-2 DAG with typed artifact lineage.

    This coordinator never invents specialist authority. Each stage is an
    injected executor. Verification validates the implementation; Security can
    block promotion; Integration must independently accept global compatibility.
    """
    required={"research","architecture","development","verification","security","integration"}
    if include_product:required.add("product")
    missing=sorted(required-set(executors))
    if missing:raise ValueError("Missing autonomy stage executors: "+", ".join(missing))

    workflow=build_software_workflow(
        store,objective,acceptance_criteria=acceptance_criteria,
        include_product=include_product,
    )
    artifacts:dict[str,str]={}
    implementation_artifact_id=None
    verification_ok=False
    security_blocked=False
    integration_ok=False

    order=("research","product","architecture","development","verification","security","integration")
    for kind in order:
        if kind=="product" and not include_product:continue
        task_id=workflow.task_ids[kind]
        task=store.task(task_id)
        if task.status is TaskStatus.PENDING:
            advance_ready_tasks(store,workflow)
            task=store.task(task_id)
        if task.status is not TaskStatus.READY:
            raise RuntimeError(f"Autonomy task is not ready: {kind}")

        store.transition_task(task_id,TaskStatus.RUNNING)
        job=store.create_job(
            task_id,executor=kind,
            trace_context={"workflow_id":workflow.workflow_id},
        )
        store.transition_job(job.id,JobStatus.RUNNING)

        parent_ids=tuple(
            artifacts[parent_kind]
            for parent_kind,parent_task_id in workflow.task_ids.items()
            if parent_task_id in task.dependencies and parent_kind in artifacts
        )
        context=StageContext(
            workflow_id=workflow.workflow_id,task_id=task_id,kind=kind,
            objective=task.objective,parent_artifact_ids=parent_ids,
            parent_artifacts=tuple(store.artifact(identity) for identity in parent_ids),
        )
        try:
            output=executors[kind](context)
            if not isinstance(output,StageOutput):
                raise ValueError(f"{kind} executor must return StageOutput")
            artifact=store.create_artifact(
                output.artifact_type,
                inline_content=_serialize_stage_payload(output.payload),
                producer_job_id=job.id,
                parent_ids=parent_ids,
                provenance={
                    "class":output.provenance_class,
                    "stage":kind,
                    "workflow_id":workflow.workflow_id,
                    **dict(output.metadata),
                },
            )
            artifacts[kind]=artifact.id
            if kind=="development":
                implementation_artifact_id=artifact.id
            elif kind=="verification":
                if output.verification_accepted is None:
                    raise ValueError("Verification stage must declare verification_accepted")
                verification_ok=bool(output.verification_accepted)
                if implementation_artifact_id is None:
                    raise RuntimeError("Verification has no implementation artifact")
                store.validate_artifact(
                    implementation_artifact_id,
                    accepted=verification_ok,
                )
            elif kind=="security":
                security_blocked=bool(output.promotion_blocked)
            elif kind=="integration":
                if output.integration_accepted is None:
                    raise ValueError("Integration stage must declare integration_accepted")
                integration_ok=bool(output.integration_accepted)

            store.transition_job(job.id,JobStatus.SUCCEEDED,result_ref=artifact.id)
            store.transition_task(task_id,TaskStatus.COMPLETE)
            store.append_event(
                "AutonomyStageCompleted",actor=kind,
                subject_ids=(workflow.workflow_id,task_id,job.id,artifact.id),
                trace_context={"workflow_id":workflow.workflow_id},
                payload={"stage":kind,"artifact_type":output.artifact_type},
            )
        except Exception as exc:
            store.transition_job(job.id,JobStatus.FAILED,error_code=type(exc).__name__)
            store.transition_task(task_id,TaskStatus.FAILED)
            store.transition_workflow(workflow.workflow_id,WorkflowStatus.FAILED)
            store.append_event(
                "AutonomyStageFailed",actor=kind,
                subject_ids=(workflow.workflow_id,task_id,job.id),
                trace_context={"workflow_id":workflow.workflow_id},
                payload={"stage":kind,"error_type":type(exc).__name__},
            )
            return AutonomyResult(
                workflow.workflow_id,"failed",artifacts,implementation_artifact_id,
                False,f"{kind} failed: {type(exc).__name__}",
            )

    accepted=bool(verification_ok and not security_blocked and integration_ok)
    promoted=False
    if accepted and implementation_artifact_id is not None:
        promoted_artifact=store.promote_artifact(implementation_artifact_id)
        promoted=promoted_artifact.promotion_state is PromotionState.PROMOTED
        store.transition_workflow(workflow.workflow_id,WorkflowStatus.COMPLETE)
        reason="verification, security and integration accepted"
        status="complete"
    else:
        store.transition_workflow(workflow.workflow_id,WorkflowStatus.FAILED)
        reasons=[]
        if not verification_ok:reasons.append("verification rejected")
        if security_blocked:reasons.append("security blocked promotion")
        if not integration_ok:reasons.append("integration did not accept")
        reason=", ".join(reasons) or "promotion conditions were not met"
        store.append_event(
            "AutonomyPromotionBlocked",actor="executive_orchestrator",
            subject_ids=(
                (workflow.workflow_id,)
                if implementation_artifact_id is None
                else (workflow.workflow_id,implementation_artifact_id)
            ),
            trace_context={"workflow_id":workflow.workflow_id},
            payload={
                "verification_accepted":verification_ok,
                "security_blocked":security_blocked,
                "integration_accepted":integration_ok,
                "reasons":reasons,
            },
        )
        status="blocked"
    return AutonomyResult(
        workflow.workflow_id,status,artifacts,implementation_artifact_id,promoted,reason,
    )
