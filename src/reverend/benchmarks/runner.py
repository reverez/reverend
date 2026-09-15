"""Deterministic execution engine for ReverendBench."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from time import perf_counter

from reverend.benchmarks.models import (
    BenchmarkAssertion,
    BenchmarkCase,
    BenchmarkObservation,
    BenchmarkExecutionError,
    BenchmarkResult,
    BenchmarkStatus,
)

BenchmarkExecutor = Callable[[BenchmarkCase], BenchmarkObservation]
BenchmarkEvaluator = Callable[
    [BenchmarkCase, BenchmarkObservation],
    tuple[BenchmarkAssertion, ...],
]


@dataclass(frozen=True)
class BenchmarkSummary:
    total: int
    passed: int
    failed: int
    errors: int
    timeouts: int
    skipped: int

    @classmethod
    def from_results(
        cls,
        results: Iterable[BenchmarkResult],
    ) -> "BenchmarkSummary":
        items = tuple(results)
        return cls(
            total=len(items),
            passed=sum(r.status is BenchmarkStatus.PASS for r in items),
            failed=sum(r.status is BenchmarkStatus.FAIL for r in items),
            errors=sum(r.status is BenchmarkStatus.ERROR for r in items),
            timeouts=sum(r.status is BenchmarkStatus.TIMEOUT for r in items),
            skipped=sum(r.status is BenchmarkStatus.SKIPPED for r in items),
        )


class BenchmarkRunner:
    """Run ReverendBench cases sequentially with explicit outcomes."""

    def __init__(
        self,
        *,
        executor: BenchmarkExecutor,
        evaluator: BenchmarkEvaluator,
        clock: Callable[[], float] = perf_counter,
    ) -> None:
        self._executor = executor
        self._evaluator = evaluator
        self._clock = clock

    def run_case(self, case: BenchmarkCase) -> BenchmarkResult:
        started = self._clock()

        try:
            observation = self._executor(case)
        except TimeoutError as exc:
            return self._terminal_result(
                case=case,
                started=started,
                status=BenchmarkStatus.TIMEOUT,
                error=str(exc) or "benchmark executor timed out",
                observation=exc.observation if isinstance(exc, BenchmarkExecutionError) else None,
            )
        except Exception as exc:
            return self._terminal_result(
                case=case,
                started=started,
                status=BenchmarkStatus.ERROR,
                error=f"{type(exc).__name__}: {exc}",
                observation=exc.observation if isinstance(exc, BenchmarkExecutionError) else None,
            )

        duration = max(0.0, self._clock() - started)

        if duration > case.budget.timeout_seconds:
            return BenchmarkResult(
                case_id=case.case_id,
                status=BenchmarkStatus.TIMEOUT,
                duration_seconds=duration,
                response=observation.response,
                metrics=dict(observation.metadata),
                error=(
                    "benchmark exceeded timeout budget: "
                    f"{duration:.6f}s > {case.budget.timeout_seconds:.6f}s"
                ),
            )

        try:
            assertions = tuple(self._evaluator(case, observation))
        except Exception as exc:
            return BenchmarkResult(
                case_id=case.case_id,
                status=BenchmarkStatus.ERROR,
                duration_seconds=duration,
                response=observation.response,
                metrics=dict(observation.metadata),
                error=f"{type(exc).__name__}: {exc}",
            )

        for key,maximum in [('model_calls',case.budget.max_model_calls),('retrieval_rounds',case.budget.max_retrieval_rounds)]:
            observed=observation.metadata.get(key)
            if observed is not None:
                valid=isinstance(observed,int) and not isinstance(observed,bool) and 0<=observed<=maximum
                assertions+= (BenchmarkAssertion(name=key+'_budget',passed=valid,
                    detail=f'observed {observed!r}; maximum {maximum}'),)

        if not assertions:
            return BenchmarkResult(
                case_id=case.case_id,
                status=BenchmarkStatus.ERROR,
                duration_seconds=duration,
                response=observation.response,
                metrics=dict(observation.metadata),
                error="benchmark evaluator returned no assertions",
            )

        status = (
            BenchmarkStatus.PASS
            if all(assertion.passed for assertion in assertions)
            else BenchmarkStatus.FAIL
        )

        return BenchmarkResult(
            case_id=case.case_id,
            status=status,
            duration_seconds=duration,
            response=observation.response,
            assertions=assertions,
            metrics=dict(observation.metadata),
        )

    def run(
        self,
        cases: Iterable[BenchmarkCase],
    ) -> tuple[BenchmarkResult, ...]:
        return tuple(self.run_case(case) for case in cases)

    def _terminal_result(
        self,
        *,
        case: BenchmarkCase,
        started: float,
        status: BenchmarkStatus,
        error: str,
        observation: BenchmarkObservation | None = None,
    ) -> BenchmarkResult:
        return BenchmarkResult(
            case_id=case.case_id,
            status=status,
            duration_seconds=max(0.0, self._clock() - started),
            error=error,
            response=observation.response if observation else "",
            metrics=dict(observation.metadata) if observation else {},
        )
