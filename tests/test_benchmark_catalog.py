from __future__ import annotations

from reverend.benchmarks.catalog import builtin_cases
from reverend.benchmarks.models import BenchmarkCategory


def test_builtin_catalog_has_unique_case_ids():
    cases = builtin_cases()
    identities = [case.case_id for case in cases]

    assert len(cases) == 3
    assert len(identities) == len(set(identities))


def test_xavier_regression_case_is_registered():
    case = next(
        case
        for case in builtin_cases()
        if case.case_id == "open-domain-xavier-typo"
    )

    assert case.category == BenchmarkCategory.OPEN_DOMAIN
    assert case.parameters["mode"] == "research"
    assert case.parameters["knowledge"] is True
    assert "xaiver" in case.prompt.lower()
    assert "xavier" in case.expected["response_contains_any"]


def test_rocket_bad_rag_case_is_registered():
    case = next(
        case
        for case in builtin_cases()
        if case.case_id == "research-rocket-bad-rag"
    )

    assert case.category == BenchmarkCategory.RESEARCH

    terms = case.expected["source_relevance_terms"]

    assert "rocket" in terms
    assert "aerospace" in terms
    assert "propulsion" in terms
    assert case.expected["min_source_relevance_ratio"] == 0.60
    assert "bad-rag" in case.tags


def test_regression_cases_have_bounded_execution():
    for case in builtin_cases():
        assert case.budget.timeout_seconds == 120.0
        assert case.budget.max_model_calls == 2
        assert case.budget.max_retrieval_rounds == 1


def test_nonexistent_entity_regression_is_registered():
    case = next(
        case
        for case in builtin_cases()
        if case.case_id == "open-domain-nonexistent-entity"
    )

    assert case.category == BenchmarkCategory.OPEN_DOMAIN
    assert "Neral Vossmere" in case.prompt
    assert case.parameters["mode"] == "research"
    assert "hallucination" in case.tags
    assert case.expected["metadata_equals"]["generation_calls"] == 0
    assert "evidence_insufficient" in case.expected["issue_codes"]
    assert case.expected["citation_status"] == "not_applicable"
