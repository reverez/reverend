from types import SimpleNamespace
from reverend.intelligence.development_specialist import development_handoff,development_specialist_spec,run_development_intelligence
from reverend.runtime import ModelRole

def test_development_specialist_uses_strong_code_but_has_no_approval_authority():
    spec=development_specialist_spec()
    assert spec.model_role is ModelRole.STRONG_CODE
    assert spec.authority_profile=="implementation_only"
    assert spec.metadata["self_approval"] is False
    assert spec.metadata["terminal_state"]=="READY_FOR_VERIFICATION"

def test_successful_engine_result_becomes_ready_for_verification_not_done():
    result=SimpleNamespace(status="pass",plan=object(),implementation=object(),initial_edits=object(),repair=None,verifier=object(),message="implemented",semantic_repairs_used=0,total_repairs_used=0)
    pack=development_handoff("task-1",result)
    assert pack.producer_status=="READY_FOR_VERIFICATION"
    assert pack.approved is False
    assert pack.verifier_observed is True

def test_failed_or_unverified_results_do_not_claim_ready():
    failed=development_handoff("task",SimpleNamespace(status="fail",plan=object(),implementation=None,initial_edits=None,repair=None,verifier=None,message="failed"))
    blocked=development_handoff("task",SimpleNamespace(status="unverified",plan=object(),implementation=None,initial_edits=None,repair=None,verifier=None,message="unverified"))
    assert failed.producer_status=="FAILED"
    assert blocked.producer_status=="BLOCKED"


def test_development_intelligence_invokes_existing_engine_and_returns_handoff():
    calls=[]
    result=SimpleNamespace(status="pass",plan=object(),implementation=object(),initial_edits=object(),repair=None,verifier=None,message="ready",semantic_repairs_used=0,total_repairs_used=0)
    def engine(connection,task_id,scheduler,**options):
        calls.append((connection,task_id,scheduler,options))
        return result
    pack=run_development_intelligence("db","task-9","scheduler",engine=engine,max_repairs=1)
    assert pack.producer_status=="READY_FOR_VERIFICATION"
    assert pack.approved is False
    assert calls==[("db","task-9","scheduler",{"max_repairs":1})]
