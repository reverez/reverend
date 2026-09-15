"""Assurance composition: deterministic truth outranks model judgement."""
from __future__ import annotations
from .models import CheckAuthority,CheckStatus,MilestoneGate,RepairBudget,RepairState,RepairStopReason,VerificationCheck,VerificationOutcome,VerificationResult,Wave1Acceptance

class AssuranceError(RuntimeError):pass
class VerifierIndependenceError(AssuranceError):pass
class PromotionBlocked(AssuranceError):pass

def compose_verification(*,producer_id:str,verifier_id:str,deterministic_checks:tuple[VerificationCheck,...],semantic_checks:tuple[VerificationCheck,...]=(),semantic_verdict:CheckStatus=CheckStatus.UNCHECKED,summary:str="")->VerificationResult:
    if not producer_id or not verifier_id:raise ValueError("Producer and verifier identities are required")
    if producer_id==verifier_id:raise VerifierIndependenceError("Implementation producer cannot approve its own work")
    if any(check.authority is not CheckAuthority.DETERMINISTIC for check in deterministic_checks):raise ValueError("Deterministic check set contains semantic evidence")
    if any(check.authority is not CheckAuthority.SEMANTIC for check in semantic_checks):raise ValueError("Semantic check set contains deterministic evidence")
    required=tuple(check for check in deterministic_checks if check.required)
    if any(check.status is CheckStatus.FAIL for check in required):
        outcome=VerificationOutcome.FAIL
    elif any(check.status is CheckStatus.UNCHECKED for check in required):
        outcome=VerificationOutcome.UNVERIFIED
    elif semantic_verdict is CheckStatus.FAIL:
        outcome=VerificationOutcome.FAIL
    elif semantic_verdict is CheckStatus.PASS:
        outcome=VerificationOutcome.PASS
    else:
        outcome=VerificationOutcome.PASS if required else VerificationOutcome.UNVERIFIED
    return VerificationResult(producer_id,verifier_id,outcome,deterministic_checks+semantic_checks,summary)

def authorize_artifact_promotion(artifact_id:str,result:VerificationResult)->str:
    if not artifact_id:raise ValueError("Artifact id is required")
    if not result.accepted:raise PromotionBlocked(f"Artifact {artifact_id} is not independently verified")
    return artifact_id

class RepairController:
    def __init__(self,budget:RepairBudget):self.state=RepairState(0,budget)
    def begin_attempt(self)->RepairState:
        if not self.state.can_retry:
            if self.state.stop_reason is None:self.state=RepairState(self.state.attempts_used,self.state.budget,RepairStopReason.ATTEMPT_BUDGET_EXHAUSTED)
            return self.state
        self.state=RepairState(self.state.attempts_used+1,self.state.budget)
        return self.state
    def finish(self,reason:RepairStopReason)->RepairState:
        self.state=RepairState(self.state.attempts_used,self.state.budget,reason);return self.state
    def exhausted(self)->bool:return self.state.attempts_used>=self.state.budget.max_attempts

def compose_wave1_acceptance(gates:tuple[MilestoneGate,...])->Wave1Acceptance:
    expected={f"M-VNEXT-0{i}" for i in range(1,7)}
    by_name={gate.milestone:gate for gate in gates}
    missing=sorted(expected-set(by_name))
    remaining=[f"{name}:missing" for name in missing]
    for name in sorted(expected&set(by_name)):
        gate=by_name[name]
        if not gate.portable_ok:remaining.append(f"{name}:portable")
        elif gate.live_required and not gate.live_ok:remaining.append(f"{name}:live")
    portable_ok=not missing and all(by_name[name].portable_ok for name in expected)
    live_ok=portable_ok and all((not by_name[name].live_required) or by_name[name].live_ok for name in expected)
    return Wave1Acceptance(gates,portable_ok,live_ok,portable_ok and live_ok,tuple(remaining))
