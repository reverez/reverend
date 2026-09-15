import pytest
from reverend.intelligence.security_specialist import SecurityFinding,build_security_pack,security_methodology,security_specialist_spec,run_security_assessment
from reverend.runtime import ModelRole

def test_security_specialist_is_independent_and_cannot_implement():
    spec=security_specialist_spec()
    assert spec.model_role is ModelRole.CRITIC
    assert spec.independent_verifier is True
    assert spec.metadata["cannot_implement"] is True
    assert "implementation_patch" not in spec.output_artifact_types

def test_critical_findings_block_promotion_automatically():
    finding=SecurityFinding("SEC-1","Sandbox escape","critical","repro evidence","sandbox boundary","deny capability")
    pack=build_security_pack(objective="review",assets=("repo",),actors=("worker",),trust_boundaries=("worker/host",),capabilities_reviewed=("tool.execute",),findings=(finding,))
    assert finding.blocking is True
    assert pack.promotion_blocked is True
    assert pack.highest_severity=="critical"

def test_nonblocking_medium_finding_does_not_block():
    finding=SecurityFinding("SEC-2","Verbose error","medium","trace","API boundary","redact")
    pack=build_security_pack(objective="review",assets=("logs",),actors=("user",),trust_boundaries=("UI/API",),capabilities_reviewed=(),findings=(finding,))
    assert pack.promotion_blocked is False

def test_assessment_requires_trust_boundaries():
    with pytest.raises(ValueError,match="trust boundaries"):
        build_security_pack(objective="review",assets=(),actors=(),trust_boundaries=(),capabilities_reviewed=(),findings=())

def test_methodology_covers_abuse_paths_and_mitigations():
    steps=security_methodology()
    assert "test_abuse_paths" in steps and "specify_mitigations" in steps


class FakeResult:
    model="critic";digest="digest"
    response={"response":'{"assets":["repo"],"actors":["worker"],"trust_boundaries":["sandbox"],"findings":[{"finding_id":"SEC-9","title":"escape","severity":"critical","evidence":"boundary bypass","trust_boundary":"sandbox","mitigation":"deny","blocking":false}],"residual_risks":[]}'}
class FakeScheduler:
    def generate(self,role,prompt,**kwargs):
        assert role is ModelRole.CRITIC
        response_schema=kwargs["response_format"]
        assert response_schema["type"]=="object"
        assert response_schema["additionalProperties"] is False
        finding_schema=response_schema["properties"]["findings"]["items"]
        assert finding_schema["additionalProperties"] is False
        assert set(finding_schema["required"])=={
            "finding_id","title","severity","evidence",
            "trust_boundary","mitigation","blocking",
        }
        return FakeResult()

def test_security_invocation_enforces_critical_blocking():
    pack=run_security_assessment(FakeScheduler(),objective="review",architecture_data="sandbox",capabilities=("tool.execute",))
    assert pack.findings[0].blocking is True
    assert pack.promotion_blocked is True


def test_security_missing_required_finding_evidence_fails_closed():
    class MissingResult:
        model="critic"
        digest="digest"
        response={
            "response": (
                '{"assets":["repo"],"actors":["worker"],'
                '"trust_boundaries":["sandbox"],'
                '"findings":[{"finding_id":"SEC-1","title":"escape",'
                '"severity":"high","evidence":"","trust_boundary":"sandbox",'
                '"mitigation":"deny","blocking":false}],'
                '"residual_risks":[]}'
            )
        }

    class MissingScheduler:
        def generate(self,*args,**kwargs):
            return MissingResult()

    with pytest.raises(
        ValueError,
        match="identity/title/evidence",
    ):
        run_security_assessment(
            MissingScheduler(),
            objective="review",
            architecture_data="sandbox",
            capabilities=("tool.execute",),
        )
