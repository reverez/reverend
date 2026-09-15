from __future__ import annotations

import pytest

from reverend.benchmarks.evaluator import (
    evaluate_expectations,
)
from reverend.benchmarks.models import (
    BenchmarkCase,
    BenchmarkCategory,
    BenchmarkObservation,
)


def make_case(expected):
    return BenchmarkCase(
        case_id="case",
        name="Case",
        category=BenchmarkCategory.RESEARCH,
        prompt="test",
        expected=expected,
    )


def test_response_contains_any_passes():
    assertions = evaluate_expectations(
        make_case(
            {
                "response_contains_any": (
                    "xavier",
                    "renegade angel",
                ),
            }
        ),
        BenchmarkObservation(
            response=(
                "Xavier: Renegade Angel is an "
                "animated television series."
            ),
        ),
    )

    assert all(
        assertion.passed
        for assertion in assertions
    )


def test_response_context_requirement_fails():
    assertions = evaluate_expectations(
        make_case(
            {
                "response_contains_any_context": (
                    "television",
                    "animated",
                    "series",
                ),
            }
        ),
        BenchmarkObservation(
            response="Xavier is a philosophical idea.",
        ),
    )

    context = next(
        assertion
        for assertion in assertions
        if assertion.name
        == "response_contains_any_context"
    )

    assert context.passed is False


def test_source_forbidden_terms_detect_bad_rag():
    assertions = evaluate_expectations(
        make_case(
            {
                "source_forbidden_terms": (
                    "probability",
                    "descartes",
                ),
            }
        ),
        BenchmarkObservation(
            response="A response.",
            metadata={
                "sources": [
                    {
                        "source": (
                            "/vault/Probability.md"
                        )
                    },
                    {
                        "source": (
                            "/vault/Descartes.md"
                        )
                    },
                ],
            },
        ),
    )

    assertion = next(
        item
        for item in assertions
        if item.name == "source_forbidden_terms"
    )

    assert assertion.passed is False
    assert "probability" in assertion.detail
    assert "descartes" in assertion.detail


def test_source_forbidden_terms_pass_clean_sources():
    assertions = evaluate_expectations(
        make_case(
            {
                "source_forbidden_terms": (
                    "probability",
                    "boolean",
                ),
            }
        ),
        BenchmarkObservation(
            response="A response.",
            metadata={
                "sources": [
                    {
                        "source": (
                            "/reference/Rocketry.md"
                        )
                    },
                ],
            },
        ),
    )

    assertion = next(
        item
        for item in assertions
        if item.name == "source_forbidden_terms"
    )

    assert assertion.passed is True


def test_response_forbidden_terms_are_supported():
    assertions = evaluate_expectations(
        make_case(
            {
                "response_forbidden_terms": (
                    "descartes",
                ),
            }
        ),
        BenchmarkObservation(
            response=(
                "This has nothing to do with Descartes."
            ),
        ),
    )

    assertion = next(
        item
        for item in assertions
        if item.name == "response_forbidden_terms"
    )

    assert assertion.passed is False


def test_unknown_expectation_is_error():
    with pytest.raises(
        ValueError,
        match="unsupported benchmark expectation",
    ):
        evaluate_expectations(
            make_case(
                {
                    "magic_judge": True,
                }
            ),
            BenchmarkObservation(
                response="answer",
            ),
        )


def test_empty_response_always_fails():
    assertions = evaluate_expectations(
        make_case({}),
        BenchmarkObservation(
            response="   ",
        ),
    )

    assert assertions[0].name == "response_nonempty"
    assert assertions[0].passed is False


def test_source_relevance_ratio_detects_mixed_bad_rag():
    assertions = evaluate_expectations(
        make_case(
            {
                "source_relevance_terms": (
                    "rocket",
                    "aerospace",
                    "propulsion",
                ),
                "min_source_relevance_ratio": 0.60,
            }
        ),
        BenchmarkObservation(
            response="answer",
            metadata={
                "sources": [
                    {
                        "source_title": "Aerospace Eng-Sources",
                        "section": "Rocket Propulsion",
                    },
                    {
                        "source_title": "Informal Logic Workflow",
                        "section": "Fallacy Drills",
                    },
                    {
                        "source_title": "Assembly Loops",
                        "section": "Reconstruction drills",
                    },
                    {
                        "source_title": "Rocket Propulsion Foundations",
                        "section": "Rocket Propulsion Foundations",
                    },
                    {
                        "source_title": "Register Files",
                        "section": "Construction drill",
                    },
                ],
            },
        ),
    )

    assertion = next(
        item
        for item in assertions
        if item.name == "source_relevance_ratio"
    )

    assert assertion.passed is False
    assert "2/5" in assertion.detail
    assert "0.400" in assertion.detail


def test_source_relevance_ratio_passes_good_retrieval():
    assertions = evaluate_expectations(
        make_case(
            {
                "source_relevance_terms": (
                    "rocket",
                    "propulsion",
                ),
                "min_source_relevance_ratio": 0.60,
            }
        ),
        BenchmarkObservation(
            response="answer",
            metadata={
                "sources": [
                    {"source_title": "Rocket Propulsion"},
                    {"section": "Rocket Engines"},
                    {"source_title": "General Engineering"},
                ],
            },
        ),
    )

    assertion = next(
        item
        for item in assertions
        if item.name == "source_relevance_ratio"
    )

    assert assertion.passed is True


def test_missing_future_capabilities_are_failures_not_inferred_success():
    case=BenchmarkCase(case_id='metadata',name='Metadata',category=BenchmarkCategory.OPEN_DOMAIN,prompt='entity',
        expected={'metadata_equals':{'evidence.outcome':'insufficient'},'metadata_contains':{'understanding.entities':'Entity'},'source_classes':['REFERENCE']})
    checks=evaluate_expectations(case,BenchmarkObservation(response='An answer',metadata={}))
    assert not all(c.passed for c in checks)
    checks=evaluate_expectations(case,BenchmarkObservation(response='An answer',metadata={
        'evidence':{'outcome':'insufficient'},'understanding':{'entities':['Entity']},'sources':[{'evidence_class':'REFERENCE'}]}))
    assert all(c.passed for c in checks)


@pytest.mark.parametrize('metadata,passed', [
    ({'issues': [{'code': 'evidence_insufficient'}], 'citation': {'status': 'not_applicable'}}, True),
    ({}, False),
    ({'issues': [], 'citation': {'status': 'present'}}, False),
    ({'issues': [{'code': 'evidence_insufficient'}, {'code': 'retrieval_failed'}],
      'citation': {'status': 'not_applicable'}}, False),
    ({'issues': 'evidence_insufficient', 'citation': None}, False),
])
def test_structured_issues_and_citation_contract(metadata, passed):
    checks = evaluate_expectations(make_case({
        'issue_codes': ['evidence_insufficient'], 'forbidden_issue_codes': ['retrieval_failed'],
        'citation_status': 'not_applicable',
    }), BenchmarkObservation(response='Cannot verify.', metadata=metadata))
    assert all(check.passed for check in checks) is passed
