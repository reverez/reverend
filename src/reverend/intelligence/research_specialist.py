"""Wave-2 Research Intelligence: typed evidence-pack assembly over existing research quality."""
from __future__ import annotations
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any,Callable,Mapping,Sequence

from reverend.research.quality import evaluate_evidence
from reverend.runtime import ModelRole
from reverend.specialists import ContextPolicy,SpecialistSpec

@dataclass(frozen=True)
class EvidencePack:
    query:str
    status:str
    overall_confidence:str
    claims:tuple[Mapping[str,Any],...]
    source_count:int
    provenance_class:str="RESEARCH_BACKED"
    methodology_version:str="research.evidence_pack_v1"
    def __post_init__(self):
        if not self.query.strip(): raise ValueError("Research query is required")
        if self.status not in {"supported","conflicting","insufficient"}: raise ValueError("Invalid evidence-pack status")
        if self.provenance_class!="RESEARCH_BACKED": raise ValueError("Research output provenance must remain RESEARCH_BACKED")
        object.__setattr__(self,"claims",tuple(MappingProxyType(dict(row)) for row in self.claims))
    def metadata(self)->dict[str,Any]:
        return {
            "artifact_type":"evidence_pack",
            "query":self.query,
            "status":self.status,
            "overall_confidence":self.overall_confidence,
            "claim_count":len(self.claims),
            "source_count":self.source_count,
            "provenance_class":self.provenance_class,
            "methodology_version":self.methodology_version,
        }

def research_specialist_spec()->SpecialistSpec:
    return SpecialistSpec(
        id="research_intelligence",
        version=1,
        name="Research Intelligence",
        model_role=ModelRole.DEEP_REASON,
        methodology_binding="research.evidence_pack_v1",
        context_policy=ContextPolicy(
            max_input_tokens=8192,
            max_item_tokens=4096,
            allowed_layers=("system","authoritative_task","current_request","evidence","project","history","summary"),
        ),
        tool_policy=("network.public_read","repo.read"),
        required_capabilities=("network.public_read",),
        input_artifact_types=("research_question",),
        output_artifact_types=("evidence_pack",),
        authority_profile="evidence_synthesis_only",
        metadata={"provenance_output":"RESEARCH_BACKED"},
    )

def build_evidence_pack(
    query:str,
    sources:Sequence[dict[str,Any]],
    *,
    evaluator:Callable[[str,Sequence[dict[str,Any]]],dict[str,Any]]=evaluate_evidence,
)->EvidencePack:
    if not isinstance(query,str) or not query.strip(): raise ValueError("Research query is required")
    report=evaluator(query,tuple(sources))
    overall=str(report.get("overall_confidence") or report.get("overall") or "insufficient_evidence")
    if "conflict" in overall:
        status="conflicting"
    elif "insufficient" in overall or bool(report.get("abstain")):
        status="insufficient"
    else:
        status="supported"
    claims=tuple(report.get("claims") or ())
    return EvidencePack(
        query=query.strip(),
        status=status,
        overall_confidence=overall,
        claims=claims,
        source_count=len(tuple(sources)),
    )
