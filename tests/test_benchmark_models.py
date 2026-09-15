from __future__ import annotations

import pytest

from reverend.benchmarks.models import (
    BenchmarkAssertion,
    BenchmarkBudget,
    BenchmarkCase,
    BenchmarkCategory,
    BenchmarkResult,
    BenchmarkStatus,
)


def test_benchmark_case_defaults():
    case = BenchmarkCase(
        case_id="open-domain-xavier",
        name="Resolve Xavier entity",
        category=BenchmarkCategory.OPEN_DOMAIN,
        prompt="xaiver the renegade angel",
    )

    assert case.budget.timeout_seconds == 30.0
    assert case.budget.max_model_calls == 1
    assert case.tags == ()


def test_budget_rejects_invalid_values():
    with pytest.raises(ValueError, match="timeout_seconds"):
        BenchmarkBudget(timeout_seconds=0)

    with pytest.raises(ValueError, match="max_model_calls"):
        BenchmarkBudget(max_model_calls=-1)

    with pytest.raises(ValueError, match="max_retrieval_rounds"):
        BenchmarkBudget(max_retrieval_rounds=-1)


def test_case_rejects_empty_identity_fields():
    with pytest.raises(ValueError, match="case_id"):
        BenchmarkCase(
            case_id="",
            name="Test",
            category=BenchmarkCategory.RESEARCH,
            prompt="hello",
        )

    with pytest.raises(ValueError, match="prompt"):
        BenchmarkCase(
            case_id="case",
            name="Test",
            category=BenchmarkCategory.RESEARCH,
            prompt=" ",
        )


def test_result_pass_property_and_serialization():
    result = BenchmarkResult(
        case_id="case",
        status=BenchmarkStatus.PASS,
        duration_seconds=0.25,
        assertions=(
            BenchmarkAssertion(
                name="answer-present",
                passed=True,
            ),
        ),
        metrics={"model_calls": 1},
    )

    assert result.passed is True

    payload = result.to_dict()

    assert payload["case_id"] == "case"
    assert payload["status"] == BenchmarkStatus.PASS
    assert payload["assertions"][0]["passed"] is True


def test_failed_result_is_not_passed():
    result = BenchmarkResult(
        case_id="case",
        status=BenchmarkStatus.FAIL,
        duration_seconds=0.1,
    )

    assert result.passed is False


def test_case_supports_execution_parameters():
    case = BenchmarkCase(
        case_id="research-case",
        name="Research case",
        category=BenchmarkCategory.RESEARCH,
        prompt="test",
        parameters={
            "mode": "research",
            "knowledge": True,
        },
    )

    assert case.parameters["mode"] == "research"
    assert case.parameters["knowledge"] is True
