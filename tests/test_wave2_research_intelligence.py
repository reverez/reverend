from reverend.intelligence.research_specialist import build_evidence_pack,research_specialist_spec
from reverend.runtime import ModelRole

def test_research_specialist_has_evidence_only_authority():
    spec=research_specialist_spec()
    assert spec.model_role is ModelRole.DEEP_REASON
    assert spec.output_artifact_types==("evidence_pack",)
    assert "network.public_read" in spec.required_capabilities
    assert spec.authority_profile=="evidence_synthesis_only"

def test_supported_evidence_pack_is_typed_and_research_backed():
    def evaluator(query,sources):
        return {"overall_confidence":"strongly_supported","claims":[{"id":"claim-1","confidence":"strongly_supported"}],"abstain":False}
    pack=build_evidence_pack("What changed?",[{"url":"https://example.com"}],evaluator=evaluator)
    assert pack.status=="supported"
    assert pack.provenance_class=="RESEARCH_BACKED"
    assert pack.metadata()["artifact_type"]=="evidence_pack"
    assert pack.source_count==1

def test_conflict_and_insufficient_never_become_supported():
    conflict=build_evidence_pack("q",[],evaluator=lambda q,s:{"overall_confidence":"conflicting_evidence","claims":[]})
    insufficient=build_evidence_pack("q",[],evaluator=lambda q,s:{"overall_confidence":"insufficient_evidence","claims":[],"abstain":True})
    assert conflict.status=="conflicting"
    assert insufficient.status=="insufficient"
