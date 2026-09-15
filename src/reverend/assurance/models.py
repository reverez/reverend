"""Shared assurance contracts for deterministic + independent verification."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

class CheckAuthority(str,Enum):
    DETERMINISTIC="deterministic"
    SEMANTIC="semantic"
class CheckStatus(str,Enum):
    PASS="pass"; FAIL="fail"; UNCHECKED="unchecked"
class VerificationOutcome(str,Enum):
    PASS="pass"; FAIL="fail"; UNVERIFIED="unverified"
class RepairStopReason(str,Enum):
    REPAIRED="repaired"; ATTEMPT_BUDGET_EXHAUSTED="attempt_budget_exhausted"; BLOCKED="blocked"; CANCELLED="cancelled"
@dataclass(frozen=True)
class VerificationCheck:
    name:str; status:CheckStatus; authority:CheckAuthority; required:bool=True; evidence:str=""
    def __post_init__(self):
        if not self.name:raise ValueError("Verification check name is required")
@dataclass(frozen=True)
class VerificationResult:
    producer_id:str; verifier_id:str; outcome:VerificationOutcome; checks:tuple[VerificationCheck,...]; summary:str
    @property
    def accepted(self)->bool:return self.outcome is VerificationOutcome.PASS
@dataclass(frozen=True)
class RepairBudget:
    max_attempts:int=2
    def __post_init__(self):
        if not isinstance(self.max_attempts,int) or isinstance(self.max_attempts,bool) or not 0<=self.max_attempts<=8:raise ValueError("Repair attempt budget must be 0-8")
@dataclass(frozen=True)
class RepairState:
    attempts_used:int; budget:RepairBudget; stop_reason:RepairStopReason|None=None
    @property
    def can_retry(self)->bool:return self.stop_reason is None and self.attempts_used<self.budget.max_attempts
@dataclass(frozen=True)
class MilestoneGate:
    milestone:str; portable_ok:bool; live_required:bool=False; live_ok:bool=False; evidence_ref:str|None=None
@dataclass(frozen=True)
class Wave1Acceptance:
    milestones:tuple[MilestoneGate,...]; portable_ok:bool; live_ok:bool; overall_ok:bool; remaining_gates:tuple[str,...]
