from __future__ import annotations

from reverend.benchmarks.catalog import m17_freshness_cases
from reverend.benchmarks.evaluator import evaluate_expectations
from reverend.benchmarks.models import BenchmarkStatus
from reverend.benchmarks.runner import BenchmarkRunner
from reverend.benchmarks.workstation import WorkstationChatExecutor


class Store:
    def __init__(self,job):
        self._job=job
    def job(self,_identity):
        return self._job


class Workstation:
    def __init__(self,job):
        self.store=Store(job)
        self.calls=[]
    def chat(self,text,**options):
        self.calls.append((text,options))
        return {'job_id':'job','conversation_id':'conversation'}
    def cancel(self,_identity):
        return {'stopping':True}


def _case(identity):
    return next(
        case
        for case in m17_freshness_cases()
        if case.case_id==identity
    )


def _run(case,job):
    workstation=Workstation(job)
    result=BenchmarkRunner(
        executor=WorkstationChatExecutor(workstation),
        evaluator=evaluate_expectations,
    ).run_case(case)
    return workstation,result


def test_m17_catalog_is_separate_fixture_backed_suite():
    cases=m17_freshness_cases()
    assert len(cases)==4
    assert len({case.case_id for case in cases})==4
    assert all('m17-regression' in case.tags for case in cases)
    assert all('fixture-only' in case.tags for case in cases)


def test_frontier_case_passes_fresh_search_contract():
    case=_case('m17-frontier-30-day-fresh')
    workstation,result=_run(case,{
        'status':'complete',
        'response':'Model X was released recently [W1].',
        'conversation_id':'conversation',
        'details':{
            'understanding':{'freshness':'current'},
            'evidence':{
                'web_search':{
                    'attempted':True,
                    'freshness':'month',
                    'provider':'searxng',
                },
            },
            'sources':[{
                'source':'https://example.com/model-x',
                'source_title':'Model X release',
                'evidence_class':'FRESH',
            }],
            'citation':{'status':'present'},
            'issues':[],
            'abstained':False,
            'model_calls':1,
            'retrieval_rounds':2,
        },
    })
    assert result.status is BenchmarkStatus.PASS
    assert workstation.calls[0][1]['network_policy']=='AUTO'


def test_stale_external_case_passes_fail_closed_contract():
    case=_case('m17-stale-external-fails-closed')
    _,result=_run(case,{
        'status':'complete',
        'response':'I cannot verify the latest release from fresh evidence.',
        'conversation_id':'conversation',
        'details':{
            'understanding':{'freshness':'current'},
            'abstained':True,
            'generation_calls':0,
            'evidence':{'outcome':'insufficient'},
            'issues':[
                {'code':'fresh_evidence_missing'},
                {'code':'evidence_insufficient'},
            ],
            'model_calls':0,
            'retrieval_rounds':1,
        },
    })
    assert result.status is BenchmarkStatus.PASS


def test_ask_policy_case_preserves_network_policy():
    case=_case('m17-ask-policy-never-searches')
    workstation,result=_run(case,{
        'status':'complete',
        'response':'Fresh public acquisition requires approval.',
        'conversation_id':'conversation',
        'details':{
            'understanding':{'freshness':'current'},
            'network_policy':'ASK',
            'abstained':True,
            'generation_calls':0,
            'issues':[
                {'code':'network_approval_required'},
                {'code':'evidence_insufficient'},
            ],
            'model_calls':0,
            'retrieval_rounds':1,
        },
    })
    assert result.status is BenchmarkStatus.PASS
    assert workstation.calls[0][1]['network_policy']=='ASK'


def test_stable_local_case_requires_reference_and_no_web_attempt():
    case=_case('m17-stable-local-first')
    _,result=_run(case,{
        'status':'complete',
        'response':'Widget uses a modular control plane [K1].',
        'conversation_id':'conversation',
        'details':{
            'understanding':{'freshness':'stable'},
            'retrieval_rounds':1,
            'evidence':{'web_search':{'attempted':False}},
            'sources':[{
                'source':'zim://fixture/widget',
                'source_title':'Widget architecture',
                'evidence_class':'REFERENCE',
            }],
            'citation':{'status':'present'},
            'issues':[],
            'abstained':False,
            'model_calls':1,
        },
    })
    assert result.status is BenchmarkStatus.PASS


def test_frontier_case_fails_when_source_is_only_reference():
    case=_case('m17-frontier-30-day-fresh')
    _,result=_run(case,{
        'status':'complete',
        'response':'A stale answer [K1].',
        'conversation_id':'conversation',
        'details':{
            'understanding':{'freshness':'current'},
            'evidence':{
                'web_search':{
                    'attempted':True,
                    'freshness':'month',
                },
            },
            'sources':[{
                'source':'zim://fixture/stale',
                'source_title':'Old reference',
                'evidence_class':'REFERENCE',
            }],
            'citation':{'status':'present'},
            'issues':[],
            'abstained':False,
            'model_calls':1,
            'retrieval_rounds':2,
        },
    })
    assert result.status is BenchmarkStatus.FAIL
    assert any(
        item.name=='source_classes' and not item.passed
        for item in result.assertions
    )
