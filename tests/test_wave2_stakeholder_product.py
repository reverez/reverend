import pytest
from reverend.intelligence.product_specialist import StakeholderFinding,build_product_decision_pack,detect_stakeholder_conflicts,product_specialist_spec,stakeholder_specialist_spec,run_product_strategy

def test_stakeholder_output_is_always_simulated_not_evidence():
    finding=StakeholderFinding("S1","student","simple onboarding","complex setup","novice users may abandon")
    assert finding.provenance_class=="SIMULATED"
    spec=stakeholder_specialist_spec()
    assert spec.metadata["cannot_create_evidence"] is True
    with pytest.raises(ValueError,match="SIMULATED"):
        StakeholderFinding("S2","admin","auditability","none","r",provenance_class="RESEARCH_BACKED")

def test_product_pack_records_simulation_ids_separately_from_evidence_refs():
    finding=StakeholderFinding("S1","student","simple onboarding","complex setup","r")
    pack=build_product_decision_pack(
        objective="ship MVP",requirements=("one-click start",),non_goals=("enterprise SSO",),
        scope=("local app",),priorities=("reliability",),tradeoffs=("less customization",),
        success_criteria=("first task succeeds",),validation_plan=("usability test",),
        evidence_refs=("artifact:evidence-1",),stakeholder_findings=(finding,))
    assert pack.evidence_refs==("artifact:evidence-1",)
    assert pack.stakeholder_finding_ids==("S1",)
    assert pack.provenance_class=="GENERATED"

def test_product_pack_requires_success_and_validation():
    with pytest.raises(ValueError,match="success criteria"):
        build_product_decision_pack(objective="x",requirements=("r",),non_goals=(),scope=(),priorities=(),tradeoffs=(),success_criteria=(),validation_plan=("test",),evidence_refs=())
    with pytest.raises(ValueError,match="validation plan"):
        build_product_decision_pack(objective="x",requirements=("r",),non_goals=(),scope=(),priorities=(),tradeoffs=(),success_criteria=("ok",),validation_plan=(),evidence_refs=())

def test_simple_conflict_detection_is_deterministic():
    a=StakeholderFinding("A","user","offline mode","mandatory cloud","r")
    b=StakeholderFinding("B","operator","mandatory cloud","offline mode","r")
    assert detect_stakeholder_conflicts((a,b))==(("A","B"),)

def test_product_strategist_consumes_but_does_not_treat_simulation_as_evidence():
    spec=product_specialist_spec()
    assert "stakeholder_findings" in spec.input_artifact_types
    assert spec.metadata["stakeholder_input_is_not_evidence"] is True


class FakeResult:
    model="reasoner";digest="digest"
    response={"response":'{"requirements":["fast start"],"non_goals":["cloud"],"scope":["local"],"priorities":["reliability"],"tradeoffs":["less sync"],"success_criteria":["task passes"],"validation_plan":["user test"]}'}
class FakeScheduler:
    def generate(self,role,prompt,**kwargs):
        assert "SIMULATED" in prompt
        assert kwargs["response_format"]=="json"
        return FakeResult()

def test_product_strategy_invocation_keeps_evidence_and_simulation_separate():
    finding=StakeholderFinding("S1","student","fast start","complexity","r")
    pack=run_product_strategy(FakeScheduler(),objective="MVP",evidence_summary="observed usage",stakeholder_findings=(finding,),project_constraints=("local only",),evidence_refs=("E1",))
    assert pack.evidence_refs==("E1",)
    assert pack.stakeholder_finding_ids==("S1",)
    assert pack.metadata["model"]=="reasoner"
