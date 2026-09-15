from reverend.benchmarks.codeintel import (
    CodeIntelligenceExecutor,
    codeintel_cases,
)
from reverend.benchmarks.evaluator import (
    evaluate_expectations,
)
from reverend.benchmarks.runner import (
    BenchmarkRunner,
)


def test_m12_codeintel_case_passes_deterministically():
    executor = CodeIntelligenceExecutor()

    for case in codeintel_cases():
        observation = executor(case)
        assertions = evaluate_expectations(
            case,
            observation,
        )

        assert assertions
        assert all(
            assertion.passed
            for assertion in assertions
        ), (
            case.case_id,
            assertions,
            observation.metadata,
        )


def test_m12_codeintel_case_respects_zero_model_budget():
    runner = BenchmarkRunner(
        executor=CodeIntelligenceExecutor(),
        evaluator=evaluate_expectations,
    )

    result = runner.run_case(
        codeintel_cases()[0]
    )

    assert result.passed
    assert result.metrics["model_calls"] == 0
    assert result.metrics["retrieval_rounds"] == 1
