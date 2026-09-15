from __future__ import annotations

from reverend.benchmarks.catalog import m16_reliability_cases
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
    return next(case for case in m16_reliability_cases() if case.case_id==identity)


def test_m16_catalog_is_separate_fixture_backed_regression_suite():
    cases=m16_reliability_cases()
    assert len(cases)==4
    assert len({case.case_id for case in cases})==4
    assert all('m16-regression' in case.tags for case in cases)
    assert all('fixture-only' in case.tags for case in cases)


def test_expected_typed_failure_can_pass_reverendbench():
    case=_case('m16-reasoning-budget-exhausted')
    workstation=Workstation({
        'status':'failed',
        'response':'',
        'conversation_id':'conversation',
        'details':{
            'error':'Local reasoning exhausted the output budget before a final answer began.',
            'error_code':'reasoning_budget_exhausted_before_answer',
            'completion_reason':'reasoning_budget_exhausted_before_answer',
            'answer_started':False,
            'hidden_reasoning_present':True,
            'continuation_eligible':True,
            'model_calls':1,
            'retrieval_rounds':0,
        },
    })
    result=BenchmarkRunner(
        executor=WorkstationChatExecutor(workstation),
        evaluator=evaluate_expectations,
    ).run_case(case)
    assert result.status is BenchmarkStatus.PASS
    assert all(item.passed for item in result.assertions)


def test_output_limit_checkpoint_case_passes_contract():
    case=_case('m16-output-limit-checkpoint')
    workstation=Workstation({
        'status':'complete',
        'response':'partial answer',
        'conversation_id':'conversation',
        'details':{
            'completion_reason':'output_limit_reached',
            'incomplete':True,
            'continuation_eligible':True,
            'checkpoint':{'available':True},
            'agent_loop':{'stop_reason':'model_budget_exhausted'},
            'model_calls':1,
            'retrieval_rounds':0,
        },
    })
    result=BenchmarkRunner(
        executor=WorkstationChatExecutor(workstation),
        evaluator=evaluate_expectations,
    ).run_case(case)
    assert result.status is BenchmarkStatus.PASS


def test_unexpected_failed_job_remains_benchmark_error():
    case=_case('m16-high-assurance-verification')
    workstation=Workstation({
        'status':'failed',
        'response':'',
        'conversation_id':'conversation',
        'details':{'error':'unexpected provider failure'},
    })
    result=BenchmarkRunner(
        executor=WorkstationChatExecutor(workstation),
        evaluator=evaluate_expectations,
    ).run_case(case)
    assert result.status is BenchmarkStatus.ERROR


def test_response_empty_expectation_rejects_nonempty_failure():
    case=_case('m16-reasoning-budget-exhausted')
    workstation=Workstation({
        'status':'failed',
        'response':'unexpected text',
        'conversation_id':'conversation',
        'details':{
            'error_code':'reasoning_budget_exhausted_before_answer',
            'completion_reason':'reasoning_budget_exhausted_before_answer',
            'answer_started':False,
            'hidden_reasoning_present':True,
            'continuation_eligible':True,
            'model_calls':1,
            'retrieval_rounds':0,
        },
    })
    result=BenchmarkRunner(
        executor=WorkstationChatExecutor(workstation),
        evaluator=evaluate_expectations,
    ).run_case(case)
    assert result.status is BenchmarkStatus.FAIL
    assert any(
        item.name=='response_empty' and not item.passed
        for item in result.assertions
    )
