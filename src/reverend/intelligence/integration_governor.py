"""Wave-2 Integration Governor: global compatibility acceptance after task verification."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Sequence

class IntegrationCheckStatus(str,Enum):
    PASS="pass"; FAIL="fail"; UNCHECKED="unchecked"

@dataclass(frozen=True)
class IntegrationCheck:
    name:str
    status:IntegrationCheckStatus
    evidence:str
    blocking:bool=True
    def __post_init__(self):
        if not self.name or not self.evidence:raise ValueError("Integration checks require name and evidence")

@dataclass(frozen=True)
class IntegrationDecision:
    outcome:str
    checks:tuple[IntegrationCheck,...]
    summary:str
    methodology_version:str="integration.governor_v1"
    def __post_init__(self):
        if self.outcome not in {"accept","block","unverified"}:raise ValueError("Invalid integration outcome")
    @property
    def accepted(self)->bool:return self.outcome=="accept"

_REQUIRED_DOMAINS=(
    "schemas","configuration","dependencies","duplicate_implementations",
    "migrations","backwards_compatibility","cross_subsystem_contracts","whole_system_tests",
)

def integration_governor_methodology()->tuple[str,...]:
    return _REQUIRED_DOMAINS

def compose_integration_decision(checks:Sequence[IntegrationCheck])->IntegrationDecision:
    checks=tuple(checks)
    by_name={check.name:check for check in checks}
    missing=tuple(name for name in _REQUIRED_DOMAINS if name not in by_name)
    failed=tuple(check for check in checks if check.blocking and check.status is IntegrationCheckStatus.FAIL)
    unchecked=tuple(
        name for name in _REQUIRED_DOMAINS
        if name not in by_name or by_name[name].status is IntegrationCheckStatus.UNCHECKED
    )
    if failed:
        outcome="block";summary="Blocking global compatibility checks failed: "+", ".join(check.name for check in failed)
    elif missing or unchecked:
        outcome="unverified";summary="Global compatibility evidence is incomplete: "+", ".join(dict.fromkeys((*missing,*unchecked)))
    else:
        outcome="accept";summary="All required global compatibility domains passed."
    return IntegrationDecision(outcome,checks,summary)
