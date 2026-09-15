"""Wave-2 Development Intelligence handoff over the mature development engine."""
from __future__ import annotations
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any,Mapping

from reverend.runtime import ModelRole
from reverend.specialists import ContextPolicy,SpecialistSpec

@dataclass(frozen=True)
class DevelopmentResultPack:
    task_id:str
    producer_status:str
    plan_available:bool
    implementation_available:bool
    edit_batch_available:bool
    repair_used:bool
    verifier_observed:bool
    message:str
    provenance_class:str="GENERATED"
    methodology_version:str="development.implementation_v1"
    metadata:Mapping[str,Any]=MappingProxyType({})
    def __post_init__(self):
        if not self.task_id: raise ValueError("Development task id is required")
        if self.producer_status not in {"READY_FOR_VERIFICATION","BLOCKED","FAILED"}: raise ValueError("Invalid development producer status")
        if self.provenance_class!="GENERATED": raise ValueError("Development output remains GENERATED")
        object.__setattr__(self,"metadata",MappingProxyType(dict(self.metadata)))
    @property
    def approved(self)->bool:
        return False

def development_specialist_spec()->SpecialistSpec:
    return SpecialistSpec(
        id="development_intelligence",
        version=1,
        name="Development Intelligence",
        model_role=ModelRole.STRONG_CODE,
        methodology_binding="development.implementation_v1",
        context_policy=ContextPolicy(
            max_input_tokens=16384,
            max_item_tokens=4096,
            allowed_layers=("system","authoritative_task","current_request","evidence","project","history","summary"),
        ),
        tool_policy=("repo.read","repo.propose_edit"),
        required_capabilities=("repo.read","repo.propose_edit"),
        input_artifact_types=("architecture_decision","acceptance_contract","repository_localization"),
        output_artifact_types=("implementation_patch","development_result"),
        authority_profile="implementation_only",
        metadata={"terminal_state":"READY_FOR_VERIFICATION","self_approval":False},
    )

def development_handoff(task_id:str,result:Any)->DevelopmentResultPack:
    status=str(getattr(result,"status","")).casefold()
    implementation=getattr(result,"implementation",None)
    initial_edits=getattr(result,"initial_edits",None)
    repair=getattr(result,"repair",None)
    if implementation is not None and status not in {"fail","failed","blocked"}:
        producer_status="READY_FOR_VERIFICATION"
    elif status in {"blocked","unverified"}:
        producer_status="BLOCKED"
    else:
        producer_status="FAILED"
    return DevelopmentResultPack(
        task_id=str(task_id),
        producer_status=producer_status,
        plan_available=getattr(result,"plan",None) is not None,
        implementation_available=implementation is not None,
        edit_batch_available=initial_edits is not None,
        repair_used=repair is not None,
        verifier_observed=getattr(result,"verifier",None) is not None,
        message=str(getattr(result,"message",""))[:4000],
        metadata={
            "engine_status":status,
            "semantic_repairs_used":int(getattr(result,"semantic_repairs_used",0) or 0),
            "total_repairs_used":int(getattr(result,"total_repairs_used",0) or 0),
        },
    )


def run_development_intelligence(connection,task_id:str,scheduler,*,engine=None,**engine_options)->DevelopmentResultPack:
    """Run the mature Development Agent and return the Wave-2 producer handoff."""
    if engine is None:
        from reverend.development.engine import run_development_task
        engine=run_development_task
    result=engine(connection,task_id,scheduler,**engine_options)
    return development_handoff(task_id,result)
