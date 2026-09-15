"""Adapters from accepted WorkerRole/WorkerPolicy into SpecialistSpec."""
from __future__ import annotations
from reverend.workers import WorkerRole,worker_policy
from .models import ContextPolicy,SpecialistSpec

_CAPABILITY_MAP={
    "repository_read":"repo.read",
    "propose_edits":"repo.propose_edit",
    "execute_tools":"tool.execute",
    "propose_memory":"memory.propose",
    "verify":"verify.run",
}
_METHODS={
    WorkerRole.RESEARCH_SCOUT:"research.discovery_v1",
    WorkerRole.SOURCE_ANALYST:"research.evidence_analysis_v1",
    WorkerRole.CODE_LOCALIZER:"development.localization_v1",
    WorkerRole.CODER:"development.implementation_v1",
    WorkerRole.REASONER:"reasoning.deliberate_v1",
    WorkerRole.MEMORY_CURATOR:"memory.curation_v1",
    WorkerRole.CRITIC_VERIFIER:"verification.independent_v1",
}
_OUTPUTS={
    WorkerRole.RESEARCH_SCOUT:("research_findings",),
    WorkerRole.SOURCE_ANALYST:("evidence_pack",),
    WorkerRole.CODE_LOCALIZER:("repository_localization",),
    WorkerRole.CODER:("implementation_patch",),
    WorkerRole.REASONER:("reasoning_result",),
    WorkerRole.MEMORY_CURATOR:("memory_proposal",),
    WorkerRole.CRITIC_VERIFIER:("verification_result",),
}
_INPUTS={
    WorkerRole.CODER:("repository_localization","architecture_decision"),
    WorkerRole.CRITIC_VERIFIER:("implementation_patch",),
}

def specialist_from_worker(role:WorkerRole,*,version:int=1,context_tokens:int|None=None)->SpecialistSpec:
    policy=worker_policy(role)
    capabilities=tuple(value for attr,value in _CAPABILITY_MAP.items() if getattr(policy,attr))
    budget=context_tokens or (16384 if policy.model_role.value in {"strong_code","fast_code"} else 8192)
    context_policy=ContextPolicy(
        max_input_tokens=budget,
        max_item_tokens=min(4096,budget),
        allowed_layers=("system","authoritative_task","current_request","checkpoint","evidence","project","memory","history","summary"),
    )
    return SpecialistSpec(
        id=role.value,
        version=version,
        name=role.value.replace("_"," ").title(),
        model_role=policy.model_role,
        methodology_binding=_METHODS[role],
        context_policy=context_policy,
        tool_policy=tuple(capabilities),
        required_capabilities=capabilities,
        input_artifact_types=_INPUTS.get(role,()),
        output_artifact_types=_OUTPUTS[role],
        authority_profile="verifier" if role is WorkerRole.CRITIC_VERIFIER else "worker_policy",
        independent_verifier=role is WorkerRole.CRITIC_VERIFIER,
        metadata={"legacy_worker_role":role.value},
    )
