"""Built-in ReverendBench case catalogue."""

from __future__ import annotations

from reverend.benchmarks.models import (
    BenchmarkBudget,
    BenchmarkCase,
    BenchmarkCategory,
)


def builtin_cases() -> tuple[BenchmarkCase, ...]:
    """Return canonical Reverend product regression cases."""

    return (
        BenchmarkCase(
            case_id="open-domain-xavier-typo",
            name="Resolve Xavier: Renegade Angel from typo",
            category=BenchmarkCategory.OPEN_DOMAIN,
            prompt="xaiver the renegade angel",
            parameters={
                "mode": "research",
                "knowledge": True,
            },
            expected={
                "citation_status": "present",
                "forbidden_issue_codes": ("citation_missing", "citation_unknown_source", "evidence_insufficient"),
                "metadata_contains": {"understanding.entities": "Xavier: Renegade Angel"},
                "source_classes": ("REFERENCE",),
                "source_relevance_terms": ("xavier", "renegade angel"),
                "min_source_relevance_ratio": 1.0,
                "response_contains_any": (
                    "xavier",
                    "renegade angel",
                ),
                "response_contains_any_context": (
                    "television",
                    "tv",
                    "animated",
                    "series",
                    "show",
                ),
            },
            tags=(
                "v0.3-regression",
                "entity-resolution",
                "bad-rag",
                "open-domain",
            ),
            budget=BenchmarkBudget(
                timeout_seconds=120.0,
                max_model_calls=2,
                max_retrieval_rounds=1,
            ),
        ),
        BenchmarkCase(
            case_id="research-rocket-bad-rag",
            name="Reject irrelevant local evidence for rocket query",
            category=BenchmarkCategory.RESEARCH,
            prompt="How do I build a rocket?",
            parameters={
                "mode": "research",
                "knowledge": True,
            },
            expected={
                "citation_status": "present",
                "forbidden_issue_codes": ("citation_missing", "citation_unknown_source", "evidence_insufficient"),
                "metadata_equals": {"understanding.domain": "aerospace_engineering"},
                "response_contains_any": ("propulsion", "aerodynamics", "stability", "model rocketry"),
                "source_relevance_terms": (
                    "rocket",
                    "aerospace",
                    "propulsion",
                    "astronautics",
                ),
                "min_source_relevance_ratio": 0.60,
            },
            tags=(
                "v0.3-regression",
                "retrieval-quality",
                "bad-rag",
                "evidence-gate",
            ),
            budget=BenchmarkBudget(
                timeout_seconds=120.0,
                max_model_calls=2,
                max_retrieval_rounds=1,
            ),
        ),
        BenchmarkCase(
            case_id="open-domain-nonexistent-entity",
            name="Reject synthetic nonexistent entity",
            category=BenchmarkCategory.OPEN_DOMAIN,
            prompt=(
                "Who is Professor Neral Vossmere, winner of the "
                "1998 Nobel Prize in Computer Science?"
            ),
            parameters={
                "mode": "research",
                "knowledge": True,
            },
            expected={
                "metadata_equals": {
                    "job_status": "complete", "evidence.outcome": "insufficient",
                    "abstained": True, "generation_calls": 0, "sources": [],
                },
                "issue_codes": ("evidence_insufficient", "network_disabled"),
                "forbidden_issue_codes": ("retrieval_failed", "citation_unknown_source", "citation_missing"),
                "citation_status": "not_applicable",
            },
            tags=(
                "v0.3-regression",
                "hallucination",
                "false-premise",
                "entity-resolution",
            ),
            budget=BenchmarkBudget(
                timeout_seconds=120.0,
                max_model_calls=2,
                max_retrieval_rounds=1,
            ),
        ),
    )



def m16_reliability_cases() -> tuple[BenchmarkCase, ...]:
    """Deterministic M16 reliability regressions for fixture-backed execution."""

    return (
        BenchmarkCase(
            case_id="m16-reasoning-budget-exhausted",
            name="Reasoning-only exhaustion is typed and private",
            category=BenchmarkCategory.ROUTING,
            prompt="Prove the result rigorously and verify every step.",
            parameters={"mode":"reason","fixture_profile":"reasoning_exhausted"},
            expected={
                "response_empty":True,
                "metadata_equals":{
                    "job_status":"failed",
                    "error_code":"reasoning_budget_exhausted_before_answer",
                    "completion_reason":"reasoning_budget_exhausted_before_answer",
                    "answer_started":False,
                    "hidden_reasoning_present":True,
                    "continuation_eligible":True,
                },
            },
            tags=("m16-regression","fixture-only","completion-integrity"),
            budget=BenchmarkBudget(
                timeout_seconds=30.0,
                max_model_calls=1,
                max_retrieval_rounds=0,
            ),
        ),
        BenchmarkCase(
            case_id="m16-output-limit-checkpoint",
            name="Output limit preserves partial answer and checkpoint",
            category=BenchmarkCategory.ROUTING,
            prompt="Exercise 41 — produce the requested long structured answer.",
            parameters={"mode":"ask","fixture_profile":"output_limit"},
            expected={
                "metadata_equals":{
                    "job_status":"complete",
                    "completion_reason":"output_limit_reached",
                    "incomplete":True,
                    "continuation_eligible":True,
                    "checkpoint.available":True,
                    "agent_loop.stop_reason":"model_budget_exhausted",
                },
            },
            tags=("m16-regression","fixture-only","checkpoint","continuation"),
            budget=BenchmarkBudget(
                timeout_seconds=30.0,
                max_model_calls=1,
                max_retrieval_rounds=0,
            ),
        ),
        BenchmarkCase(
            case_id="m16-high-assurance-verification",
            name="Machine-checkable requirements are verified",
            category=BenchmarkCategory.ROUTING,
            prompt=(
                "Exercise 42\nRequirements:\n"
                "- The output MUST contain exactly 2 items.\n"
                "- DO NOT emit \"BETA\"."
            ),
            parameters={"mode":"ask","fixture_profile":"verification_pass"},
            expected={
                "response_forbidden_terms":("beta",),
                "metadata_equals":{
                    "job_status":"complete",
                    "high_assurance":True,
                    "verification.outcome":"pass",
                    "verification.failed_count":0,
                },
            },
            tags=("m16-regression","fixture-only","high-assurance","verification"),
            budget=BenchmarkBudget(
                timeout_seconds=30.0,
                max_model_calls=2,
                max_retrieval_rounds=0,
            ),
        ),
        BenchmarkCase(
            case_id="m16-verification-fails-closed",
            name="Known-bad answer is not silently accepted",
            category=BenchmarkCategory.ROUTING,
            prompt=(
                "Exercise 43\nRequirements:\n"
                "- The output MUST contain exactly 2 items."
            ),
            parameters={"mode":"ask","fixture_profile":"verification_fail"},
            expected={
                "metadata_equals":{
                    "job_status":"failed",
                    "error_code":"verification_failed",
                    "verification.outcome":"fail",
                },
            },
            tags=("m16-regression","fixture-only","verification","fail-closed"),
            budget=BenchmarkBudget(
                timeout_seconds=30.0,
                max_model_calls=1,
                max_retrieval_rounds=0,
            ),
        ),
    )



def m17_freshness_cases() -> tuple[BenchmarkCase, ...]:
    """Deterministic M17 fresh-web/frontier regressions for fixture execution."""

    return (
        BenchmarkCase(
            case_id="m17-frontier-30-day-fresh",
            name="Thirty-day frontier query requires fresh searched evidence",
            category=BenchmarkCategory.RESEARCH,
            prompt=(
                "What important open-weight language models were released "
                "in the last 30 days?"
            ),
            parameters={
                "mode":"research",
                "network_policy":"AUTO",
                "fixture_profile":"fresh_month",
            },
            expected={
                "metadata_equals":{
                    "job_status":"complete",
                    "understanding.freshness":"current",
                    "evidence.web_search.attempted":True,
                    "evidence.web_search.freshness":"month",
                    "abstained":False,
                },
                "source_classes":("FRESH",),
                "citation_status":"present",
                "forbidden_issue_codes":(
                    "fresh_evidence_missing",
                    "evidence_insufficient",
                    "network_search_unavailable",
                ),
            },
            tags=(
                "m17-regression",
                "fixture-only",
                "frontier-detection",
                "fresh-web",
            ),
            budget=BenchmarkBudget(
                timeout_seconds=30.0,
                max_model_calls=2,
                max_retrieval_rounds=2,
            ),
        ),
        BenchmarkCase(
            case_id="m17-stale-external-fails-closed",
            name="Cached external page cannot masquerade as fresh evidence",
            category=BenchmarkCategory.RESEARCH,
            prompt="What is the latest Widget release?",
            parameters={
                "mode":"research",
                "network_policy":"OFF",
                "fixture_profile":"stale_external",
            },
            expected={
                "metadata_equals":{
                    "job_status":"complete",
                    "understanding.freshness":"current",
                    "abstained":True,
                    "generation_calls":0,
                    "evidence.outcome":"insufficient",
                },
                "issue_codes":(
                    "fresh_evidence_missing",
                    "evidence_insufficient",
                ),
            },
            tags=(
                "m17-regression",
                "fixture-only",
                "freshness-provenance",
                "fail-closed",
            ),
            budget=BenchmarkBudget(
                timeout_seconds=30.0,
                max_model_calls=2,
                max_retrieval_rounds=1,
            ),
        ),
        BenchmarkCase(
            case_id="m17-ask-policy-never-searches",
            name="ASK policy requests approval instead of searching",
            category=BenchmarkCategory.RESEARCH,
            prompt="What changed in the last 7 days?",
            parameters={
                "mode":"research",
                "network_policy":"ASK",
                "fixture_profile":"approval_required",
            },
            expected={
                "metadata_equals":{
                    "job_status":"complete",
                    "understanding.freshness":"current",
                    "network_policy":"ASK",
                    "abstained":True,
                    "generation_calls":0,
                },
                "issue_codes":(
                    "network_approval_required",
                    "evidence_insufficient",
                ),
            },
            tags=(
                "m17-regression",
                "fixture-only",
                "network-policy",
                "fail-closed",
            ),
            budget=BenchmarkBudget(
                timeout_seconds=30.0,
                max_model_calls=2,
                max_retrieval_rounds=1,
            ),
        ),
        BenchmarkCase(
            case_id="m17-stable-local-first",
            name="Stable research keeps accepted local reference before web",
            category=BenchmarkCategory.RESEARCH,
            prompt="Explain Widget architecture",
            parameters={
                "mode":"research",
                "network_policy":"AUTO",
                "fixture_profile":"local_reference",
            },
            expected={
                "metadata_equals":{
                    "job_status":"complete",
                    "understanding.freshness":"stable",
                    "retrieval_rounds":1,
                    "evidence.web_search.attempted":False,
                    "abstained":False,
                },
                "source_classes":("REFERENCE",),
                "citation_status":"present",
            },
            tags=(
                "m17-regression",
                "fixture-only",
                "local-first",
                "network-policy",
            ),
            budget=BenchmarkBudget(
                timeout_seconds=30.0,
                max_model_calls=2,
                max_retrieval_rounds=2,
            ),
        ),
    )
