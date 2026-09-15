"""Wave-2 Stakeholder Intelligence + Product Strategy MVP."""
from __future__ import annotations
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any,Mapping,Sequence

from reverend.runtime import ModelRole
from reverend.specialists import ContextPolicy,SpecialistSpec

@dataclass(frozen=True)
class StakeholderFinding:
    finding_id:str
    stakeholder:str
    need:str
    concern:str
    rationale:str
    evidence_refs:tuple[str,...]=()
    provenance_class:str="SIMULATED"
    def __post_init__(self):
        if not self.finding_id or not self.stakeholder or not self.need: raise ValueError("Stakeholder finding identity/stakeholder/need are required")
        if self.provenance_class!="SIMULATED": raise ValueError("Synthetic stakeholder findings must remain SIMULATED")

@dataclass(frozen=True)
class ProductDecisionPack:
    objective:str
    requirements:tuple[str,...]
    non_goals:tuple[str,...]
    scope:tuple[str,...]
    priorities:tuple[str,...]
    tradeoffs:tuple[str,...]
    success_criteria:tuple[str,...]
    validation_plan:tuple[str,...]
    evidence_refs:tuple[str,...]
    stakeholder_finding_ids:tuple[str,...]
    provenance_class:str="GENERATED"
    methodology_version:str="product.strategy_v1"
    metadata:Mapping[str,Any]=MappingProxyType({})
    def __post_init__(self):
        if not self.objective.strip(): raise ValueError("Product objective is required")
        if not self.requirements: raise ValueError("Product pack requires explicit requirements")
        if not self.success_criteria: raise ValueError("Product pack requires success criteria")
        if not self.validation_plan: raise ValueError("Product pack requires a validation plan")
        if self.provenance_class!="GENERATED": raise ValueError("Product decisions remain GENERATED")
        object.__setattr__(self,"metadata",MappingProxyType(dict(self.metadata)))

def stakeholder_specialist_spec()->SpecialistSpec:
    return SpecialistSpec(
        id="stakeholder_intelligence",
        version=1,
        name="Stakeholder Intelligence",
        model_role=ModelRole.FAST_GENERAL,
        methodology_binding="stakeholder.simulation_v1",
        context_policy=ContextPolicy(
            max_input_tokens=8192,max_item_tokens=4096,
            allowed_layers=("system","authoritative_task","current_request","evidence","project","summary"),
        ),
        tool_policy=(),
        required_capabilities=(),
        input_artifact_types=("evidence_pack","project_constraints"),
        output_artifact_types=("stakeholder_findings",),
        authority_profile="simulation_only",
        metadata={"provenance_output":"SIMULATED","cannot_create_evidence":True},
    )

def product_specialist_spec()->SpecialistSpec:
    return SpecialistSpec(
        id="product_strategist",
        version=1,
        name="Product Strategist",
        model_role=ModelRole.DEEP_REASON,
        methodology_binding="product.strategy_v1",
        context_policy=ContextPolicy(
            max_input_tokens=8192,max_item_tokens=4096,
            allowed_layers=("system","authoritative_task","current_request","evidence","project","summary"),
        ),
        tool_policy=(),
        required_capabilities=(),
        input_artifact_types=("evidence_pack","stakeholder_findings","project_constraints"),
        output_artifact_types=("product_decision",),
        authority_profile="product_scope_proposal",
        metadata={"stakeholder_input_is_not_evidence":True},
    )

def stakeholder_methodology()->tuple[str,...]:
    return ("resolve_relevant_stakeholders","simulate_needs","expert_review","evidence_audit","simplify","detect_conflicts")

def product_methodology()->tuple[str,...]:
    return ("combine_evidence_constraints_and_simulations","separate_requirements_from_non_goals","prioritize","record_tradeoffs","define_success_criteria","define_validation_plan")

def detect_stakeholder_conflicts(findings:Sequence[StakeholderFinding])->tuple[tuple[str,str],...]:
    conflicts=[]
    for i,left in enumerate(findings):
        for right in findings[i+1:]:
            if left.need.casefold()==right.concern.casefold() or right.need.casefold()==left.concern.casefold():
                conflicts.append((left.finding_id,right.finding_id))
    return tuple(conflicts)

def build_product_decision_pack(*,objective:str,requirements:Sequence[str],non_goals:Sequence[str],scope:Sequence[str],priorities:Sequence[str],tradeoffs:Sequence[str],success_criteria:Sequence[str],validation_plan:Sequence[str],evidence_refs:Sequence[str],stakeholder_findings:Sequence[StakeholderFinding]=(),metadata:Mapping[str,Any]|None=None)->ProductDecisionPack:
    clean=lambda values:tuple(str(v).strip() for v in values if str(v).strip())
    return ProductDecisionPack(
        objective=objective.strip(),requirements=clean(requirements),non_goals=clean(non_goals),
        scope=clean(scope),priorities=clean(priorities),tradeoffs=clean(tradeoffs),
        success_criteria=clean(success_criteria),validation_plan=clean(validation_plan),
        evidence_refs=clean(evidence_refs),
        stakeholder_finding_ids=tuple(f.finding_id for f in stakeholder_findings),
        metadata=metadata or {},
    )


def run_product_strategy(scheduler,*,objective:str,evidence_summary:str,stakeholder_findings:Sequence[StakeholderFinding],project_constraints:Sequence[str],evidence_refs:Sequence[str])->ProductDecisionPack:
    """Synthesize product scope while keeping simulated stakeholders separate from evidence."""
    import json
    from reverend.development.repair_model import _extract_json,RepairModelResponseError
    schema={"requirements":["requirement"],"non_goals":["non-goal"],"scope":["scope"],"priorities":["priority"],"tradeoffs":["trade-off"],"success_criteria":["criterion"],"validation_plan":["validation"]}
    simulated=[{"id":f.finding_id,"stakeholder":f.stakeholder,"need":f.need,"concern":f.concern,"provenance":"SIMULATED"} for f in stakeholder_findings[:24]]
    prompt=(
        "You are Reverend's Product Strategist. Treat evidence and simulated stakeholders differently. "
        "SIMULATED stakeholder findings are hypotheses, never evidence. Produce requirements/non-goals/scope/priorities/trade-offs/success criteria/validation plan. "
        "Return exactly one JSON object matching the schema and no private reasoning.\n"
        +json.dumps(schema)+"\nOBJECTIVE:\n"+objective[:3000]
        +"\nEVIDENCE SUMMARY (evidence-backed data):\n"+evidence_summary[:8000]
        +"\nSIMULATED STAKEHOLDERS (not evidence):\n"+json.dumps(simulated)
        +"\nPROJECT CONSTRAINTS:\n"+json.dumps(list(project_constraints)[:32])
    )
    result=scheduler.generate(ModelRole.DEEP_REASON,prompt,context=8192,predict=2048,temperature=0.0,think=False,response_format="json")
    try:value=_extract_json(str(result.response.get("response","")))
    except RepairModelResponseError as exc:raise ValueError("Product strategist returned invalid structured JSON") from exc
    if not isinstance(value,dict) or set(value)!=set(schema):raise ValueError("Product response fields do not match contract")
    return build_product_decision_pack(
        objective=objective,requirements=value["requirements"],non_goals=value["non_goals"],
        scope=value["scope"],priorities=value["priorities"],tradeoffs=value["tradeoffs"],
        success_criteria=value["success_criteria"],validation_plan=value["validation_plan"],
        evidence_refs=evidence_refs,stakeholder_findings=stakeholder_findings,
        metadata={"model":getattr(result,"model",None),"digest":getattr(result,"digest",None)},
    )
