from __future__ import annotations

import pytest

from reverend.benchmarks.models import (
    BenchmarkBudget,
    BenchmarkCase,
    BenchmarkCategory,
)
from reverend.benchmarks.workstation import (
    WorkstationChatExecutor,
)


class FakeStore:
    def __init__(self, jobs):
        self.jobs = list(jobs)
        self.index = 0

    def job(self, _identity):
        value = self.jobs[
            min(self.index, len(self.jobs) - 1)
        ]
        self.index += 1
        return value


class FakeWorkstation:
    def __init__(self, jobs):
        self.store = FakeStore(jobs)
        self.chat_calls = []
        self.cancelled = []

    def chat(self, text, **options):
        self.chat_calls.append((text, options))
        return {
            "job_id": "job-1",
            "conversation_id": "conversation-1",
        }

    def cancel(self, identity):
        self.cancelled.append(identity)
        return {"stopping": True}


def case(**parameters):
    return BenchmarkCase(
        case_id="case",
        name="Case",
        category=BenchmarkCategory.RESEARCH,
        prompt="xaiver the renegade angel",
        parameters=parameters,
        budget=BenchmarkBudget(
            timeout_seconds=5.0,
        ),
    )


def test_executor_uses_real_chat_contract():
    workstation = FakeWorkstation(
        [
            {
                "status": "running",
                "details": {},
            },
            {
                "status": "complete",
                "response": "Xavier is a TV series.",
                "conversation_id": "conversation-1",
                "details": {
                    "role": "fast_general",
                    "prompt_tokens": 100,
                    "generated_tokens": 20,
                    "sources": [],
                },
            },
        ]
    )

    executor = WorkstationChatExecutor(
        workstation,
        sleep=lambda _: None,
    )

    observation = executor(
        case(
            mode="research",
            knowledge=True,
        )
    )

    assert observation.response == (
        "Xavier is a TV series."
    )

    assert (
        observation.metadata["role"]
        == "fast_general"
    )

    assert (
        observation.metadata["prompt_tokens"]
        == 100
    )

    text, options = workstation.chat_calls[0]

    assert text == "xaiver the renegade angel"
    assert options["mode"] == "research"
    assert options["knowledge"] is True
    assert options["max_retrieval_rounds"] == 1


def test_executor_surfaces_failed_job():
    workstation = FakeWorkstation(
        [
            {
                "status": "failed",
                "response": "",
                "conversation_id": "conversation-1",
                "details": {
                    "error": "model failed",
                },
            },
        ]
    )

    executor = WorkstationChatExecutor(
        workstation,
    )

    with pytest.raises(
        RuntimeError,
        match="model failed",
    ):
        executor(case())


def test_executor_cancels_on_deadline():
    workstation = FakeWorkstation(
        [
            {
                "status": "running",
                "details": {},
            },
        ]
    )

    times = iter(
        [
            0.0,
            6.0,
        ]
    )

    executor = WorkstationChatExecutor(
        workstation,
        clock=lambda: next(times),
        sleep=lambda _: None,
    )

    with pytest.raises(
        TimeoutError,
        match="exceeded benchmark timeout",
    ):
        executor(case())

    assert workstation.cancelled == ["job-1"]


def test_executor_rejects_cancelled_job():
    workstation = FakeWorkstation(
        [
            {
                "status": "cancelled",
                "response": "partial",
                "conversation_id": "conversation-1",
                "details": {},
            },
        ]
    )

    executor = WorkstationChatExecutor(
        workstation,
    )

    with pytest.raises(
        RuntimeError,
        match="status cancelled",
    ):
        executor(case())


def test_network_policy_is_forwarded():
    workstation = FakeWorkstation([{'status': 'complete', 'response': 'Cannot verify.', 'details': {}}])
    WorkstationChatExecutor(workstation)(case(network_policy='ASK'))
    assert workstation.chat_calls[0][1]['network_policy'] == 'ASK'


def test_runner_preserves_failed_job_issues_and_usage():
    from reverend.benchmarks.runner import BenchmarkRunner
    from reverend.benchmarks.evaluator import evaluate_expectations
    from reverend.benchmarks.models import BenchmarkStatus
    details = {'error': 'retrieval failed', 'issues': [{'code': 'retrieval_failed'}],
               'model_calls': 1, 'evidence': {'attempts': [{'outcome': 'error'}]}}
    workstation = FakeWorkstation([{'status': 'failed', 'response': 'partial', 'details': details}])
    result = BenchmarkRunner(executor=WorkstationChatExecutor(workstation),
                             evaluator=evaluate_expectations).run_case(case())
    assert result.status == BenchmarkStatus.ERROR
    assert result.response == 'partial'
    assert result.metrics['issues'] == details['issues']
    assert result.metrics['model_calls'] == 1
    assert result.metrics['evidence'] == details['evidence']
    assert not result.assertions


def test_runner_preserves_timeout_snapshot():
    from reverend.benchmarks.runner import BenchmarkRunner
    from reverend.benchmarks.evaluator import evaluate_expectations
    from reverend.benchmarks.models import BenchmarkStatus
    workstation = FakeWorkstation([{'status': 'running', 'response': 'partial',
                                   'details': {'model_calls': 1, 'issues': []}}])
    times = iter([0.0, 6.0])
    executor = WorkstationChatExecutor(workstation, clock=lambda: next(times), sleep=lambda _: None)
    result = BenchmarkRunner(executor=executor, evaluator=evaluate_expectations).run_case(case())
    assert result.status == BenchmarkStatus.TIMEOUT
    assert result.response == 'partial'
    assert result.metrics['model_calls'] == 1
    assert workstation.cancelled == ['job-1']
