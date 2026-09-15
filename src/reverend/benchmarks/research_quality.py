"""Fixture-backed adversarial ResearchBench for deterministic evidence quality."""
from __future__ import annotations

import json

from reverend.research.quality import (
    AuthorityKind,
    ConfidenceLabel,
    TemporalEvent,
    classify_source_authority,
    decompose_query,
    evaluate_evidence,
    event_dates,
)


ASTRA_QUERY = (
    "When was GPT-6 Astra first announced, and when did it become broadly "
    "available? Distinguish the research announcement date from later product "
    "availability. Prefer official OpenAI primary sources and explain any "
    "conflicting dates."
)


def _source(url, content, *, transport="fetched_page", **metadata):
    return {
        "source": url,
        "source_title": metadata.pop("source_title", url),
        "content": content,
        "source_transport": transport,
        "transport_confidence": 0.75 if transport == "search_snippet" else 1.0,
        **metadata,
    }


def _case(identifier, category, passed, details):
    return {
        "id": identifier,
        "category": category,
        "passed": bool(passed),
        "details": details,
    }


def run_research_bench() -> dict:
    cases = []

    primary = classify_source_authority(
        "https://openai.com/index/astra/", ASTRA_QUERY, title="Introducing Astra"
    )
    aggregator = classify_source_authority(
        "https://medium.com/@x/astra", ASTRA_QUERY
    )
    cases.append(_case(
        "A", "primary_vs_aggregator",
        primary["source_authority"] == "primary"
        and aggregator["source_authority_kind"] == AuthorityKind.AGGREGATOR.value
        and primary["research_authority_score"] > aggregator["research_authority_score"],
        {"primary": primary["source_authority_kind"], "aggregator": aggregator["source_authority_kind"]},
    ))

    conflict = evaluate_evidence(
        "When was OpenAI GPT-6 Astra announced?",
        [
            _source("https://openai.com/index/astra/", "OpenAI announced GPT-6 Astra on September 3, 2026."),
            _source("https://reuters.com/technology/astra", "OpenAI announced GPT-6 Astra on September 4, 2026."),
        ],
    )
    cases.append(_case(
        "B", "conflicting_dates",
        conflict["conflict"] and conflict["outcome"] == ConfidenceLabel.CONFLICTING.value,
        {"outcome": conflict["outcome"], "dates": conflict["claims"][0]["event_dates"]},
    ))

    separated = evaluate_evidence(
        ASTRA_QUERY,
        [_source(
            "https://openai.com/index/astra/",
            "OpenAI announced GPT-6 Astra on September 3, 2026. "
            "It became broadly available on September 9, 2026.",
        )],
    )
    dates = {claim["event"]: claim["event_dates"] for claim in separated["claims"]}
    cases.append(_case(
        "C", "announcement_vs_availability",
        not separated["conflict"]
        and dates.get("announcement") == ["2026-09-03"]
        and dates.get("broad_availability") == ["2026-09-09"],
        {"dates": dates},
    ))

    blocked = evaluate_evidence(
        "When did OpenAI announce GPT-6 Astra?",
        [_source(
            "https://openai.com/index/astra/",
            "OpenAI announced GPT-6 Astra on September 3, 2026.",
            transport="search_snippet",
            fetch_status="blocked",
        )],
    )
    cases.append(_case(
        "D", "first_party_blocked_fetch",
        blocked["outcome"] == ConfidenceLabel.REPORTED.value
        and blocked["claims"][0]["snippet_primary"] is True,
        {"outcome": blocked["outcome"], "snippet_primary": blocked["claims"][0]["snippet_primary"]},
    ))

    community = classify_source_authority(
        "https://community.openai.com/t/astra/1", ASTRA_QUERY
    )
    cases.append(_case(
        "E", "community_subdomain_demotion",
        community["source_authority"] == "community"
        and community["source_authority_kind"] == AuthorityKind.COMMUNITY.value,
        {"authority": community["source_authority"], "kind": community["source_authority_kind"]},
    ))

    corroborated = evaluate_evidence(
        "When was OpenAI GPT-6 Astra announced?",
        [
            _source("https://openai.com/index/astra/", "OpenAI announced GPT-6 Astra on September 3, 2026.", transport="search_snippet"),
            _source("https://help.openai.com/astra", "OpenAI announced GPT-6 Astra on September 3, 2026."),
            _source("https://reuters.com/technology/astra", "OpenAI announced GPT-6 Astra on September 3, 2026."),
        ],
    )
    cases.append(_case(
        "F", "independent_corroboration",
        corroborated["claims"][0]["independent_source_count"] == 2,
        {"independence_keys": corroborated["claims"][0]["independence_keys"]},
    ))

    temporal = evaluate_evidence(
        "When was OpenAI GPT-6 Astra announced?",
        [_source(
            "https://openai.com/index/astra/",
            "This page was updated September 9, 2026. "
            "OpenAI announced GPT-6 Astra on September 3, 2026.",
            published_at="2026-09-04",
            updated_at="2026-09-09",
            search_result_date="2026-09-10",
        )],
    )
    temporal_evidence = temporal["claims"][0]["evidence"][0]
    cases.append(_case(
        "G", "event_vs_page_dates",
        temporal["claims"][0]["event_dates"] == ["2026-09-03"]
        and temporal_evidence["publication_date"] == "2026-09-04"
        and temporal_evidence["updated_date"] == "2026-09-09"
        and temporal_evidence["search_result_date"] == "2026-09-10",
        temporal_evidence,
    ))

    unsupported = evaluate_evidence(
        ASTRA_QUERY,
        [_source(
            "https://openai.com/index/astra/",
            "OpenAI announced GPT-6 Astra on September 3, 2026.",
        )],
    )
    cases.append(_case(
        "H", "unsupported_claim",
        unsupported["abstain"]
        and any(
            claim["event"] == "broad_availability"
            and claim["confidence"] == ConfidenceLabel.INSUFFICIENT.value
            for claim in unsupported["claims"]
        ),
        {"outcome": unsupported["outcome"], "abstain": unsupported["abstain"]},
    ))

    cases.append(_case(
        "I", "search_snippet_only",
        blocked["outcome"] == ConfidenceLabel.REPORTED.value
        and blocked["outcome"] != ConfidenceLabel.CONFIRMED_PRIMARY.value,
        {"outcome": blocked["outcome"]},
    ))

    absent = evaluate_evidence(
        "When was OpenAI GPT-6 Astra announced?", []
    )
    cases.append(_case(
        "J", "no_adequate_evidence",
        absent["abstain"] and absent["outcome"] == ConfidenceLabel.INSUFFICIENT.value,
        {"outcome": absent["outcome"], "abstain": absent["abstain"]},
    ))

    comparison = evaluate_evidence(
        "Compare OpenAI and Anthropic release dates",
        [
            _source("https://openai.com/index/model-x/", "OpenAI released Model X on September 3, 2026."),
            _source("https://anthropic.com/news/model-y", "Anthropic released Model Y on September 5, 2026."),
        ],
    )
    comparison_dates = {claim["subject"]: claim["event_dates"] for claim in comparison["claims"]}
    cases.append(_case(
        "K", "multi_entity_comparison",
        not comparison["conflict"]
        and comparison_dates.get("openai") == ["2026-09-03"]
        and comparison_dates.get("anthropic") == ["2026-09-05"],
        {"dates": comparison_dates, "facets": [facet.metadata() for facet in decompose_query("Compare OpenAI and Anthropic release dates")]},
    ))

    peer = classify_source_authority(
        "https://nature.com/articles/example", "transformer scaling study"
    )
    preprint = classify_source_authority(
        "https://arxiv.org/abs/2609.01234", "transformer scaling study"
    )
    cases.append(_case(
        "L", "academic_source_types",
        peer["source_authority_kind"] == AuthorityKind.PEER_REVIEWED_PUBLICATION.value
        and preprint["source_authority_kind"] == AuthorityKind.PREPRINT.value
        and peer["research_authority_score"] > preprint["research_authority_score"],
        {"peer_reviewed": peer["source_authority_kind"], "preprint": preprint["source_authority_kind"]},
    ))

    leap_valid = (
        event_dates(
            "OpenAI announced Model Leap on 2024-02-29.",
            TemporalEvent.ANNOUNCEMENT,
        )
        == ("2024-02-29",)
    )
    impossible_dates_rejected = all(
        event_dates(text, TemporalEvent.ANNOUNCEMENT) == ()
        for text in (
            "OpenAI announced Model Invalid on 2026-02-29.",
            "OpenAI announced Model Invalid on February 31, 2026.",
            "OpenAI announced Model Invalid on 2026-99-99.",
        )
    )
    cases.append(_case(
        "M", "calendar_date_validity",
        leap_valid and impossible_dates_rejected,
        {
            "leap_day_valid": leap_valid,
            "impossible_dates_rejected": impossible_dates_rejected,
        },
    ))

    scholarly = classify_source_authority(
        "https://nature.com/articles/s41586-026-00001-1",
        "transformer scaling study",
    )
    publisher_news = classify_source_authority(
        "https://nature.com/news/latest-ai-news",
        "transformer scaling study",
        title="AI news",
    )
    publisher_landing = classify_source_authority(
        "https://ieee.org/about/index.html",
        "transformer scaling study",
        title="About IEEE",
    )
    cases.append(_case(
        "N", "peer_review_page_specificity",
        scholarly["source_authority_kind"] == AuthorityKind.PEER_REVIEWED_PUBLICATION.value
        and publisher_news["source_authority_kind"] != AuthorityKind.PEER_REVIEWED_PUBLICATION.value
        and publisher_landing["source_authority_kind"] != AuthorityKind.PEER_REVIEWED_PUBLICATION.value,
        {
            "scholarly": scholarly["source_authority_kind"],
            "publisher_news": publisher_news["source_authority_kind"],
            "publisher_landing": publisher_landing["source_authority_kind"],
        },
    ))

    passed = sum(case["passed"] for case in cases)
    total = len(cases)
    return {
        "benchmark": "ResearchBench-RQ1",
        "passed": passed,
        "total": total,
        "score": passed / total if total else 0.0,
        "all_passed": passed == total,
        "cases": cases,
        "metrics": {
            "contradiction_detection": int(cases[1]["passed"]),
            "temporal_separation": int(cases[2]["passed"] and cases[6]["passed"]),
            "snippet_certainty_downgrade": int(cases[8]["passed"]),
            "unsupported_claim_abstention": int(cases[7]["passed"] and cases[9]["passed"]),
            "independent_corroboration": int(cases[5]["passed"]),
            "multi_entity_separation": int(cases[10]["passed"]),
            "calendar_date_validity": int(cases[12]["passed"]),
            "peer_review_page_specificity": int(cases[13]["passed"]),
        },
    }


def main() -> int:
    result = run_research_bench()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
