"""Typed vNext contracts. Classification cannot grant execution permissions."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from reverend.runtime import ModelRole


class Intent(str,Enum):
    CONVERSATION='conversation'
    TRANSFORM='transform'
    FACT='open_domain_fact'
    RESEARCH='research'
    CODE='code_question'
    DEVELOP='development'
    REASON='reasoning'
    PERSONAL='personal_knowledge'
    CLARIFY='clarification'


class EvidenceClass(str,Enum):
    PERSONAL='PERSONAL'
    PROJECT='PROJECT'
    REFERENCE='REFERENCE'
    FRESH='FRESH'


class NetworkPolicy(str,Enum):
    OFF='OFF'
    ASK='ASK'
    AUTO='AUTO'


@dataclass(frozen=True)
class Understanding:
    intent: Intent
    entities: tuple[str,...]=()
    domain: str='general'
    complexity: str='low'
    freshness: str='stable'
    evidence_need: str='none'
    execution_intent: str='none'
    risk: str='low'
    ambiguities: tuple[str,...]=()
    confidence: float=1.0
    method: str='deterministic'

    def __post_init__(self):
        if not isinstance(self.intent,Intent):raise ValueError('Invalid intent')
        if self.complexity not in {'low','medium','high'}:raise ValueError('Invalid complexity')
        if self.freshness not in {'stable','current'}:raise ValueError('Invalid freshness')
        if self.evidence_need not in {'none','personal','project','reference','fresh'}:raise ValueError('Invalid evidence need')
        if self.execution_intent not in {'none','develop'}:raise ValueError('Invalid execution intent')
        if self.risk not in {'low','elevated'}:raise ValueError('Invalid risk')
        if not 0<=self.confidence<=1:raise ValueError('Invalid confidence')
        if len(self.domain)>64 or len(self.entities)>8 or len(self.ambiguities)>8:raise ValueError('Understanding exceeds budget')
        if any(not isinstance(v,str) or len(v)>200 for v in (*self.entities,*self.ambiguities)):raise ValueError('Invalid entity/ambiguity')

    @classmethod
    def from_model(cls,value: dict):
        if not isinstance(value,dict):raise ValueError('Expected understanding object')
        allowed={'intent','entities','domain','complexity','freshness','evidence_need','risk','ambiguities','confidence'}
        if set(value)-allowed:raise ValueError('Unexpected understanding fields')
        for key in ('entities','ambiguities'):
            if key in value and not isinstance(value[key],(list,tuple)):raise ValueError('Expected entity/ambiguity list')
        # Never accept execution directives, tool names or permissions from a model.
        return cls(intent=Intent(value['intent']),entities=tuple(value.get('entities',())),
            domain=value.get('domain','general'),complexity=value.get('complexity','low'),
            freshness=value.get('freshness','stable'),evidence_need=value.get('evidence_need','reference'),
            risk=value.get('risk','low'),ambiguities=tuple(value.get('ambiguities',())),
            confidence=value.get('confidence',0.0),method='local_router')


@dataclass(frozen=True)
class RequestBudget:
    max_model_calls: int=2
    max_retrieval_rounds: int=2
    # Hard per-call ceiling. Routing chooses the actual budget below it.
    output_tokens: int=4096

    def __post_init__(self):
        if any(not isinstance(value,int) or isinstance(value,bool) for value in (self.max_model_calls,self.max_retrieval_rounds,self.output_tokens)):
            raise ValueError('Request budgets must be integers')
        if not 0<=self.max_model_calls<=8:raise ValueError('Model call budget must be 0–8')
        if not 0<=self.max_retrieval_rounds<=4:raise ValueError('Retrieval budget must be 0–4')
        if not 128<=self.output_tokens<=4096:raise ValueError('Output budget must be 128–4096')


@dataclass(frozen=True)
class ExecutionPlan:
    model_role: ModelRole
    corpora: tuple[EvidenceClass,...]
    workers: tuple[str,...]
    tools: tuple[str,...]
    network_required: bool
    network_allowed: bool
    network_approval_required: bool
    critic_required: bool
    max_model_calls: int
    max_retrieval_rounds: int
    output_tokens: int
    rationale: str
    capability_limited: bool=False


@dataclass(frozen=True)
class Escalation:
    action: str
    model_role: ModelRole | None
    reason: str
