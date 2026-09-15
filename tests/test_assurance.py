from __future__ import annotations
from types import SimpleNamespace
import pytest
from reverend.assurance import CheckAuthority,CheckStatus,MilestoneGate,PromotionBlocked,RepairBudget,RepairController,RepairStopReason,VerificationCheck,VerificationOutcome,VerifierIndependenceError,authorize_artifact_promotion,compose_verification,compose_wave1_acceptance,development_checks,workstation_checks

def deterministic(name,status=CheckStatus.PASS,required=True):return VerificationCheck(name,status,CheckAuthority.DETERMINISTIC,required)
def semantic(name,status=CheckStatus.PASS):return VerificationCheck(name,status,CheckAuthority.SEMANTIC,False)

def test_implementation_cannot_self_approve():
    with pytest.raises(VerifierIndependenceError):compose_verification(producer_id="developer",verifier_id="developer",deterministic_checks=(deterministic("tests"),),semantic_verdict=CheckStatus.PASS)
def test_deterministic_failure_overrides_semantic_pass():
    result=compose_verification(producer_id="developer",verifier_id="verifier",deterministic_checks=(deterministic("pytest",CheckStatus.FAIL),),semantic_checks=(semantic("review"),),semantic_verdict=CheckStatus.PASS)
    assert result.outcome is VerificationOutcome.FAIL
def test_missing_required_deterministic_evidence_is_not_a_pass():
    result=compose_verification(producer_id="developer",verifier_id="verifier",deterministic_checks=(deterministic("tests",CheckStatus.UNCHECKED),),semantic_verdict=CheckStatus.PASS)
    assert result.outcome is VerificationOutcome.UNVERIFIED
def test_deterministic_only_success_can_pass():
    result=compose_verification(producer_id="producer",verifier_id="independent",deterministic_checks=(deterministic("schema"),deterministic("tests")))
    assert result.outcome is VerificationOutcome.PASS and result.accepted
def test_promotion_requires_accepted_independent_verification():
    good=compose_verification(producer_id="producer",verifier_id="verifier",deterministic_checks=(deterministic("tests"),))
    assert authorize_artifact_promotion("artifact",good)=="artifact"
    bad=compose_verification(producer_id="producer",verifier_id="verifier",deterministic_checks=(deterministic("tests",CheckStatus.FAIL),))
    with pytest.raises(PromotionBlocked):authorize_artifact_promotion("artifact",bad)
def test_repair_controller_has_explicit_attempt_budget_and_stop_reason():
    controller=RepairController(RepairBudget(2));assert controller.begin_attempt().attempts_used==1;assert controller.begin_attempt().attempts_used==2
    state=controller.begin_attempt();assert state.stop_reason is RepairStopReason.ATTEMPT_BUDGET_EXHAUSTED and not state.can_retry
def test_wave1_acceptance_separates_portable_and_live_gates():
    gates=tuple(MilestoneGate(f"M-VNEXT-0{i}",True,live_required=(i in {3,4}),live_ok=(i==3)) for i in range(1,7))
    result=compose_wave1_acceptance(gates);assert result.portable_ok is True and result.live_ok is False and result.overall_ok is False;assert result.remaining_gates==("M-VNEXT-04:live",)
def test_existing_verification_adapters_preserve_deterministic_authority():
    ws=SimpleNamespace(checks=(SimpleNamespace(requirement="exact",status="pass",message="ok"),));assert workstation_checks(ws)[0].authority is CheckAuthority.DETERMINISTIC
    dev=SimpleNamespace(checks=(SimpleNamespace(name="pytest",passed=False,required=True,summary="failed"),));check=development_checks(dev)[0];assert check.status is CheckStatus.FAIL and check.required
