from __future__ import annotations

from reverend.benchmarks.models import (
    BenchmarkAssertion,
    BenchmarkBudget,
    BenchmarkCase,
    BenchmarkCategory,
    BenchmarkObservation,
    BenchmarkStatus,
)
from reverend.benchmarks.runner import (
    BenchmarkRunner,
    BenchmarkSummary,
)


def case(
    case_id: str = "case",
    *,
    timeout_seconds: float = 30.0,
) -> BenchmarkCase:
    return BenchmarkCase(
        case_id=case_id,
        name=f"Case {case_id}",
        category=BenchmarkCategory.OPEN_DOMAIN,
        prompt="test prompt",
        budget=BenchmarkBudget(
            timeout_seconds=timeout_seconds,
        ),
    )


def test_runner_passes_when_all_assertions_pass():
    runner = BenchmarkRunner(
        executor=lambda _: BenchmarkObservation(
            response="answer",
            metadata={"model_calls": 1},
        ),
        evaluator=lambda _case, observation: (
            BenchmarkAssertion(
                name="answer-present",
                passed=bool(observation.response),
            ),
        ),
    )

    result = runner.run_case(case())

    assert result.status is BenchmarkStatus.PASS
    assert result.passed is True
    assert result.metrics["model_calls"] == 1


def test_runner_fails_when_assertion_fails():
    runner = BenchmarkRunner(
        executor=lambda _: BenchmarkObservation(
            response="wrong answer",
        ),
        evaluator=lambda _case, _observation: (
            BenchmarkAssertion(
                name="expected-answer",
                passed=False,
                detail="answer did not match",
            ),
        ),
    )

    result = runner.run_case(case())

    assert result.status is BenchmarkStatus.FAIL
    assert result.passed is False
    assert result.assertions[0].detail == "answer did not match"


def test_runner_records_executor_error():
    def broken_executor(_case):
        raise RuntimeError("executor exploded")

    runner = BenchmarkRunner(
        executor=broken_executor,
        evaluator=lambda _case, _observation: (),
    )

    result = runner.run_case(case())

    assert result.status is BenchmarkStatus.ERROR
    assert result.error == "RuntimeError: executor exploded"


def test_runner_records_explicit_timeout():
    def timed_out(_case):
        raise TimeoutError("model deadline exceeded")

    runner = BenchmarkRunner(
        executor=timed_out,
        evaluator=lambda _case, _observation: (),
    )

    result = runner.run_case(case())

    assert result.status is BenchmarkStatus.TIMEOUT
    assert result.error == "model deadline exceeded"


def test_runner_detects_elapsed_budget_overrun():
    times = iter((10.0, 12.0))

    runner = BenchmarkRunner(
        executor=lambda _: BenchmarkObservation(
            response="late",
        ),
        evaluator=lambda _case, _observation: (
            BenchmarkAssertion(
                name="unused",
                passed=True,
            ),
        ),
        clock=lambda: next(times),
    )

    result = runner.run_case(
        case(timeout_seconds=1.0),
    )

    assert result.status is BenchmarkStatus.TIMEOUT
    assert result.duration_seconds == 2.0
    assert "exceeded timeout budget" in (result.error or "")


def test_runner_rejects_empty_assertion_set():
    runner = BenchmarkRunner(
        executor=lambda _: BenchmarkObservation(
            response="answer",
        ),
        evaluator=lambda _case, _observation: (),
    )

    result = runner.run_case(case())

    assert result.status is BenchmarkStatus.ERROR
    assert result.error == "benchmark evaluator returned no assertions"


def test_runner_preserves_case_order():
    runner = BenchmarkRunner(
        executor=lambda benchmark_case: BenchmarkObservation(
            response=benchmark_case.case_id,
        ),
        evaluator=lambda _case, _observation: (
            BenchmarkAssertion(
                name="ok",
                passed=True,
            ),
        ),
    )

    results = runner.run(
        (
            case("first"),
            case("second"),
            case("third"),
        )
    )

    assert [result.case_id for result in results] == [
        "first",
        "second",
        "third",
    ]


def test_summary_counts_statuses():
    runner = BenchmarkRunner(
        executor=lambda benchmark_case: BenchmarkObservation(
            response=benchmark_case.case_id,
        ),
        evaluator=lambda benchmark_case, _observation: (
            BenchmarkAssertion(
                name="expected",
                passed=benchmark_case.case_id != "fail",
            ),
        ),
    )

    results = runner.run(
        (
            case("pass"),
            case("fail"),
        )
    )

    summary = BenchmarkSummary.from_results(results)

    assert summary.total == 2
    assert summary.passed == 1
    assert summary.failed == 1
    assert summary.errors == 0
    assert summary.timeouts == 0
    assert summary.skipped == 0


def test_runner_preserves_observation_response():
    runner = BenchmarkRunner(
        executor=lambda _: BenchmarkObservation(
            response="the exact model response",
        ),
        evaluator=lambda _case, _observation: (
            BenchmarkAssertion(
                name="ok",
                passed=True,
            ),
        ),
    )

    result = runner.run_case(case())

    assert result.response == "the exact model response"


def test_measured_usage_cannot_pass_an_exceeded_budget():
    runner=BenchmarkRunner(executor=lambda _:BenchmarkObservation(response='answer',metadata={'model_calls':2,'retrieval_rounds':1}),
        evaluator=lambda *_:(BenchmarkAssertion(name='answer',passed=True),))
    result=runner.run_case(case())
    assert result.status==BenchmarkStatus.FAIL
    assert next(a for a in result.assertions if a.name=='model_calls_budget').passed is False
