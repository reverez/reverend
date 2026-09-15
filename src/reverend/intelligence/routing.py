"""Bounded capability ladder independent of model names and source content."""
from __future__ import annotations
from reverend.runtime import ModelRole
from .contracts import EvidenceClass,Escalation,ExecutionPlan,Intent,NetworkPolicy,RequestBudget,Understanding


class RoutingError(ValueError):
    pass


def _adaptive_output_tokens(
    request: Understanding,
    role: ModelRole,
    mode: str,
) -> int:
    """Choose a bounded task-sensitive generation budget."""

    if role is ModelRole.ROUTER:
        return 512

    if role in {
        ModelRole.DEEP_REASON,
        ModelRole.STRONG_CODE,
    }:
        return 4096

    if role is ModelRole.FAST_CODE:
        return (
            3072
            if request.complexity == 'high'
            else 2048
        )

    if (
        mode == 'research'
        or request.intent is Intent.RESEARCH
        or request.complexity == 'high'
    ):
        return 3072

    if request.complexity == 'medium':
        return 2048

    return 1536


def plan_request(request: Understanding,*,budget=RequestBudget(),mode='auto',
                 network=NetworkPolicy.OFF,available_roles=None,calls_used=0) -> ExecutionPlan:
    if mode not in {'auto','ask','reason','research','develop'}:raise RoutingError('Unknown workflow override')
    if not isinstance(network,NetworkPolicy):raise RoutingError('Invalid network policy')
    if calls_used<0 or calls_used>=budget.max_model_calls:raise RoutingError('No model calls remain')
    role=ModelRole.FAST_GENERAL;reason='Fast local model is sufficient'
    if request.intent==Intent.DEVELOP:
        role=ModelRole.STRONG_CODE;reason='Structured development requires the established coding engine'
    elif mode=='reason' or request.intent==Intent.REASON and request.complexity=='high':
        role=ModelRole.DEEP_REASON;reason='Complex reasoning benefits from the reasoning role'
    elif request.intent==Intent.CODE:
        role=ModelRole.STRONG_CODE if request.complexity=='high' else ModelRole.FAST_CODE
        reason='Code capability selected from task complexity'
    if mode=='ask':role=ModelRole.FAST_GENERAL;reason='Explicit Ask override'
    available=set(available_roles) if available_roles is not None else set(ModelRole)
    limited=False
    if role not in available:
        # Never silently downgrade a development task's required engine capability.
        if request.intent==Intent.DEVELOP or mode=='reason':raise RoutingError('Required local model role is unavailable')
        fallback=ModelRole.FAST_CODE if request.intent==Intent.CODE else ModelRole.FAST_GENERAL
        if fallback not in available:raise RoutingError('No sufficient local model role is available')
        role=fallback;limited=True;reason+='; preferred role unavailable, result needs additional review'
    classes={'personal':EvidenceClass.PERSONAL,'project':EvidenceClass.PROJECT,'reference':EvidenceClass.REFERENCE,'fresh':EvidenceClass.FRESH}
    corpora=(classes[request.evidence_need],) if request.evidence_need in classes else ()
    if request.evidence_need=='fresh':corpora=(EvidenceClass.REFERENCE,EvidenceClass.FRESH)
    wants_network=request.freshness=='current' or request.evidence_need=='fresh'
    development=request.intent==Intent.DEVELOP and request.execution_intent=='develop'
    if request.intent==Intent.DEVELOP and not development:raise RoutingError('Classification cannot authorize development')
    remaining=budget.max_model_calls-calls_used
    if development and remaining<3:raise RoutingError('Development needs at least plan, implementation and verifier calls')
    output_tokens=min(
        budget.output_tokens,
        _adaptive_output_tokens(
            request,
            role,
            mode,
        ),
    )
    reason+=f'; output budget {output_tokens} tokens'
    return ExecutionPlan(role,corpora,('coder','verifier') if development else (),
        ('isolated_development',) if development else (),wants_network,wants_network and network==NetworkPolicy.AUTO,
        wants_network and network==NetworkPolicy.ASK,development or request.risk=='elevated',
        remaining,budget.max_retrieval_rounds if corpora else 0,output_tokens,reason,limited)


def escalation(plan: ExecutionPlan,*,reason: str,model_calls: int,retrieval_rounds: int=0) -> Escalation:
    if model_calls<0 or retrieval_rounds<0:raise RoutingError('Usage counts cannot be negative')
    if reason in {'missing_evidence','irrelevant_evidence','conflicting_evidence'}:
        action='retrieve' if retrieval_rounds<plan.max_retrieval_rounds else 'abstain'
        return Escalation(action,None,reason)
    if reason=='ambiguous_request':return Escalation('clarify',None,reason)
    if reason not in {'reasoning_failure','verification_failure','output_limit'}:raise RoutingError('Unknown escalation reason')
    if model_calls>=plan.max_model_calls:return Escalation('stop',None,'Model budget exhausted')
    higher={ModelRole.FAST_GENERAL:ModelRole.DEEP_REASON,ModelRole.FAST_CODE:ModelRole.STRONG_CODE}.get(plan.model_role)
    return Escalation('model' if higher else 'stop',higher,reason)
