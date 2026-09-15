"""Deterministic expectation evaluator for ReverendBench."""

from __future__ import annotations

import json
from collections.abc import Iterable

from reverend.benchmarks.models import (
    BenchmarkAssertion,
    BenchmarkCase,
    BenchmarkObservation,
)


_SUPPORTED_EXPECTATIONS = {
    "response_contains_any",
    "response_contains_any_context",
    "response_forbidden_terms",
    "source_forbidden_terms",
    "source_relevance_terms",
    "min_source_relevance_ratio",
    "metadata_equals",
    "metadata_contains",
    "source_classes",
    "citation_status",
    "issue_codes",
    "forbidden_issue_codes",
    "response_empty",
}


def _terms(
    value: object,
    *,
    name: str,
) -> tuple[str, ...]:
    if isinstance(value, str):
        values: Iterable[object] = (value,)
    elif isinstance(value, (list, tuple)):
        values = value
    else:
        raise ValueError(
            f"{name} must be a string, list, or tuple"
        )

    result = tuple(
        str(item).strip().lower()
        for item in values
        if str(item).strip()
    )

    if not result:
        raise ValueError(
            f"{name} must contain at least one term"
        )

    return result


def _contains_any(
    haystack: str,
    terms: tuple[str, ...],
) -> tuple[bool, tuple[str, ...]]:
    matches = tuple(
        term
        for term in terms
        if term in haystack
    )

    return bool(matches), matches


def evaluate_expectations(
    case: BenchmarkCase,
    observation: BenchmarkObservation,
) -> tuple[BenchmarkAssertion, ...]:
    """Evaluate one observation without model-based judging."""

    unknown = (
        set(case.expected)
        - _SUPPORTED_EXPECTATIONS
    )

    if (
        "min_source_relevance_ratio" in case.expected
        and "source_relevance_terms" not in case.expected
    ):
        raise ValueError(
            "min_source_relevance_ratio requires "
            "source_relevance_terms"
        )

    if unknown:
        raise ValueError(
            "unsupported benchmark expectation(s): "
            + ", ".join(sorted(unknown))
        )

    response = observation.response.lower()

    sources = json.dumps(
        observation.metadata.get("sources", []),
        ensure_ascii=False,
        sort_keys=True,
    ).lower()

    expects_empty = case.expected.get("response_empty")
    if expects_empty not in {None, True, False}:
        raise ValueError("response_empty must be boolean")

    if expects_empty is True:
        assertions: list[BenchmarkAssertion] = [
            BenchmarkAssertion(
                name="response_empty",
                passed=not bool(observation.response.strip()),
                detail=(
                    ""
                    if not observation.response.strip()
                    else "response was not empty"
                ),
            )
        ]
    else:
        assertions = [
            BenchmarkAssertion(
                name="response_nonempty",
                passed=bool(observation.response.strip()),
                detail=(
                    ""
                    if observation.response.strip()
                    else "response was empty"
                ),
            )
        ]

    if "response_contains_any" in case.expected:
        terms = _terms(
            case.expected["response_contains_any"],
            name="response_contains_any",
        )
        passed, matches = _contains_any(
            response,
            terms,
        )

        assertions.append(
            BenchmarkAssertion(
                name="response_contains_any",
                passed=passed,
                detail=(
                    "matched: " + ", ".join(matches)
                    if matches
                    else "none of: " + ", ".join(terms)
                ),
            )
        )

    if (
        "response_contains_any_context"
        in case.expected
    ):
        terms = _terms(
            case.expected[
                "response_contains_any_context"
            ],
            name="response_contains_any_context",
        )
        passed, matches = _contains_any(
            response,
            terms,
        )

        assertions.append(
            BenchmarkAssertion(
                name="response_contains_any_context",
                passed=passed,
                detail=(
                    "matched: " + ", ".join(matches)
                    if matches
                    else "none of: " + ", ".join(terms)
                ),
            )
        )

    if "response_forbidden_terms" in case.expected:
        terms = _terms(
            case.expected["response_forbidden_terms"],
            name="response_forbidden_terms",
        )
        _, matches = _contains_any(
            response,
            terms,
        )

        assertions.append(
            BenchmarkAssertion(
                name="response_forbidden_terms",
                passed=not matches,
                detail=(
                    "found forbidden: "
                    + ", ".join(matches)
                    if matches
                    else ""
                ),
            )
        )

    if "source_relevance_terms" in case.expected:
        terms = _terms(
            case.expected["source_relevance_terms"],
            name="source_relevance_terms",
        )

        source_rows = observation.metadata.get("sources", [])
        relevant = 0

        for source in source_rows:
            searchable = " ".join(
                str(source.get(key, ""))
                for key in (
                    "source",
                    "source_title",
                    "section",
                )
            ).lower()

            if any(term in searchable for term in terms):
                relevant += 1

        ratio = (
            relevant / len(source_rows)
            if source_rows
            else 0.0
        )

        minimum = float(
            case.expected.get(
                "min_source_relevance_ratio",
                1.0,
            )
        )

        assertions.append(
            BenchmarkAssertion(
                name="source_relevance_ratio",
                passed=ratio >= minimum,
                detail=(
                    f"{relevant}/{len(source_rows)} "
                    f"relevant = {ratio:.3f}; "
                    f"minimum = {minimum:.3f}"
                ),
            )
        )

    if "source_forbidden_terms" in case.expected:
        terms = _terms(
            case.expected["source_forbidden_terms"],
            name="source_forbidden_terms",
        )
        _, matches = _contains_any(
            sources,
            terms,
        )

        assertions.append(
            BenchmarkAssertion(
                name="source_forbidden_terms",
                passed=not matches,
                detail=(
                    "found forbidden: "
                    + ", ".join(matches)
                    if matches
                    else ""
                ),
            )
        )

    for operation in ('metadata_equals','metadata_contains'):
        expectations=case.expected.get(operation,{})
        if not isinstance(expectations,dict):raise ValueError(operation+' must be an object')
        for path,expected in expectations.items():
            actual=observation.metadata
            for component in path.split('.'):
                actual=actual.get(component) if isinstance(actual,dict) else None
            passed=(actual==expected) if operation=='metadata_equals' else isinstance(actual,(list,tuple)) and expected in actual
            assertions.append(BenchmarkAssertion(name=operation+':'+path,passed=passed,
                detail=f'expected {expected!r}; observed {actual!r}'))

    if 'source_classes' in case.expected:
        allowed=_terms(case.expected['source_classes'],name='source_classes')
        rows=observation.metadata.get('sources',[])
        passed=bool(rows) and all(str(row.get('evidence_class','')).lower() in allowed for row in rows)
        assertions.append(BenchmarkAssertion(name='source_classes',passed=passed,
            detail='All sources must carry a permitted evidence class: '+', '.join(allowed)))

    if 'citation_status' in case.expected:
        expected = case.expected['citation_status']
        if expected not in {'not_applicable', 'missing', 'present', 'unknown_source'}:
            raise ValueError('Invalid citation_status expectation')
        citation = observation.metadata.get('citation')
        actual = citation.get('status') if isinstance(citation, dict) else None
        assertions.append(BenchmarkAssertion(name='citation_status', passed=actual == expected,
            detail=f'expected {expected!r}; observed {actual!r}'))

    for operation in ('issue_codes', 'forbidden_issue_codes'):
        if operation not in case.expected:
            continue
        expected = set(_terms(case.expected[operation], name=operation))
        issues = observation.metadata.get('issues')
        valid = isinstance(issues, (list, tuple)) and all(
            isinstance(issue, dict) and isinstance(issue.get('code'), str) for issue in issues)
        actual = {issue['code'] for issue in issues} if valid else set()
        passed = valid and (expected <= actual if operation == 'issue_codes' else not expected & actual)
        assertions.append(BenchmarkAssertion(name=operation, passed=passed,
            detail=f'expected {operation}: {sorted(expected)!r}; observed {sorted(actual)!r}; metadata valid: {valid}'))

    return tuple(assertions)
