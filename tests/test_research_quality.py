from reverend.research.quality import (
    AuthorityKind,
    ConfidenceLabel,
    SupportType,
    TemporalEvent,
    annotate_evidence_set,
    assess_source,
    classify_source_authority,
    decompose_query,
    evaluate_evidence,
    event_dates,
    missing_search_facets,
    source_independence_key,
)


ASTRA_QUERY = (
    "When was GPT-6 Astra first announced, and when did it become broadly "
    "available? Distinguish the research announcement date from later product "
    "availability. Prefer official OpenAI primary sources and explain any "
    "conflicting dates."
)


def _source(
    url,
    content,
    *,
    title="",
    transport="fetched_page",
    published_at=None,
    updated_at=None,
    search_result_date=None,
):
    return {
        "source": url,
        "source_title": title or url,
        "content": content,
        "source_transport": transport,
        "transport_confidence": 0.75 if transport == "search_snippet" else 1.0,
        "published_at": published_at,
        "updated_at": updated_at,
        "search_result_date": search_result_date,
    }


def test_authority_hierarchy_is_query_relative_and_community_is_demoted():
    official = classify_source_authority(
        "https://openai.com/index/gpt-6-astra/",
        ASTRA_QUERY,
        title="Introducing GPT-6 Astra",
    )
    community = classify_source_authority(
        "https://community.openai.com/t/gpt-6-astra/123",
        ASTRA_QUERY,
    )
    aggregator = classify_source_authority(
        "https://medium.com/@someone/gpt-6-astra",
        ASTRA_QUERY,
    )
    paper = classify_source_authority(
        "https://arxiv.org/abs/2609.01234",
        "latest transformer research",
    )

    assert official["source_authority"] == "primary"
    assert official["source_authority_kind"] == AuthorityKind.OFFICIAL_ANNOUNCEMENT.value
    assert official["claim_authority_fit"] == 1.0
    assert community["source_authority"] == "community"
    assert community["source_authority_kind"] == AuthorityKind.COMMUNITY.value
    assert aggregator["source_authority_kind"] == AuthorityKind.AGGREGATOR.value
    assert aggregator["research_authority_score"] < official["research_authority_score"]
    assert paper["source_authority_kind"] == AuthorityKind.PREPRINT.value


def test_vendor_primary_is_not_unbiased_support_for_best_model_claim():
    result = classify_source_authority(
        "https://openai.com/index/model/",
        "Is OpenAI Model X the strongest model in the world?",
    )
    assert result["source_authority"] == "primary"
    assert result["claim_authority_fit"] < 0.8


def test_query_decomposition_separates_announcement_and_broad_availability():
    facets = decompose_query(ASTRA_QUERY)
    events = [facet.event for facet in facets]
    assert TemporalEvent.ANNOUNCEMENT in events
    assert TemporalEvent.BROAD_AVAILABILITY in events
    assert len(facets) <= 4


def test_event_date_is_not_inferred_from_publication_or_update_date():
    source = _source(
        "https://openai.com/index/gpt-6-astra/",
        (
            "OpenAI announced GPT-6 Astra on September 3, 2026. "
            "It became broadly available on September 9, 2026."
        ),
        title="GPT-6 Astra",
        published_at="2026-09-04",
        updated_at="2026-09-10",
        search_result_date="2026-09-11",
    )
    assessments = assess_source(ASTRA_QUERY, source)
    by_event = {row.event: row for row in assessments}
    assert by_event[TemporalEvent.ANNOUNCEMENT].event_date == "2026-09-03"
    assert by_event[TemporalEvent.BROAD_AVAILABILITY].event_date == "2026-09-09"
    assert by_event[TemporalEvent.ANNOUNCEMENT].publication_date == "2026-09-04"
    assert by_event[TemporalEvent.ANNOUNCEMENT].updated_date == "2026-09-10"
    assert by_event[TemporalEvent.ANNOUNCEMENT].search_result_date == "2026-09-11"


def test_date_extraction_requires_event_language():
    text = (
        "This page was updated September 9, 2026. "
        "OpenAI announced the model on September 3, 2026."
    )
    assert event_dates(text, TemporalEvent.ANNOUNCEMENT) == ("2026-09-03",)
    assert event_dates("Updated September 9, 2026.", TemporalEvent.BROAD_AVAILABILITY) == ()


def test_claim_support_is_direct_only_when_source_supports_requested_event():
    source = _source(
        "https://openai.com/index/gpt-6-astra/",
        "OpenAI announced GPT-6 Astra on September 3, 2026.",
    )
    assessments = {row.event: row for row in assess_source(ASTRA_QUERY, source)}
    assert assessments[TemporalEvent.ANNOUNCEMENT].support is SupportType.DIRECT
    assert assessments[TemporalEvent.BROAD_AVAILABILITY].support is SupportType.UNSUPPORTED


def test_primary_fetched_source_confirms_supported_claim_but_not_missing_claim():
    summary = evaluate_evidence(
        ASTRA_QUERY,
        [_source(
            "https://openai.com/index/gpt-6-astra/",
            "OpenAI announced GPT-6 Astra on September 3, 2026.",
        )],
    )
    claims = {claim["event"]: claim for claim in summary["claims"]}
    assert claims["announcement"]["confidence"] == ConfidenceLabel.CONFIRMED_PRIMARY.value
    assert claims["broad_availability"]["confidence"] == ConfidenceLabel.INSUFFICIENT.value
    assert summary["abstain"] is True


def test_primary_snippet_support_is_reported_not_confirmed():
    summary = evaluate_evidence(
        "When did OpenAI announce GPT-6 Astra?",
        [_source(
            "https://openai.com/index/gpt-6-astra/",
            "OpenAI announced GPT-6 Astra on September 3, 2026.",
            transport="search_snippet",
        )],
    )
    assert summary["outcome"] == ConfidenceLabel.REPORTED.value
    assert summary["abstain"] is False


def test_independent_sources_corroborate_but_same_organization_does_not_double_count():
    query = "When was OpenAI GPT-6 Astra announced?"
    sources = [
        _source(
            "https://openai.com/index/gpt-6-astra/",
            "OpenAI announced GPT-6 Astra on September 3, 2026.",
            transport="search_snippet",
        ),
        _source(
            "https://help.openai.com/en/articles/astra",
            "OpenAI announced GPT-6 Astra on September 3, 2026.",
        ),
        _source(
            "https://reuters.com/technology/astra",
            "OpenAI announced GPT-6 Astra on September 3, 2026.",
        ),
    ]
    summary = evaluate_evidence(query, sources)
    claim = summary["claims"][0]
    assert claim["independent_source_count"] == 2
    assert set(claim["independence_keys"]) == {"openai.com", "reuters.com"}


def test_conflicting_dates_are_exposed_only_within_same_event_facet():
    query = "When was OpenAI GPT-6 Astra announced?"
    sources = [
        _source(
            "https://openai.com/index/gpt-6-astra/",
            "OpenAI announced GPT-6 Astra on September 3, 2026.",
        ),
        _source(
            "https://reuters.com/technology/astra",
            "OpenAI announced GPT-6 Astra on September 4, 2026.",
        ),
    ]
    summary = evaluate_evidence(query, sources)
    assert summary["conflict"] is True
    assert summary["outcome"] == ConfidenceLabel.CONFLICTING.value
    assert summary["claims"][0]["event_dates"] == ["2026-09-03", "2026-09-04"]

    separated = evaluate_evidence(
        ASTRA_QUERY,
        [_source(
            "https://openai.com/index/gpt-6-astra/",
            (
                "OpenAI announced GPT-6 Astra on September 3, 2026. "
                "It became broadly available on September 9, 2026."
            ),
        )],
    )
    assert separated["conflict"] is False


def test_missing_facets_drive_at_most_bounded_followup_need():
    rows = [{
        "title": "GPT-6 Astra announcement",
        "snippet": "OpenAI announced GPT-6 Astra on September 3, 2026.",
    }]
    missing = missing_search_facets(ASTRA_QUERY, rows)
    assert [facet.event for facet in missing] == [TemporalEvent.BROAD_AVAILABILITY]


def test_evidence_annotation_keeps_authority_transport_and_claim_support_separate():
    annotated, summary = annotate_evidence_set(
        "When did OpenAI announce GPT-6 Astra?",
        [_source(
            "https://openai.com/index/gpt-6-astra/",
            "OpenAI announced GPT-6 Astra on September 3, 2026.",
            transport="search_snippet",
        )],
    )
    row = annotated[0]
    assert row["source_authority"] == "primary"
    assert row["source_authority_score"] == 1.0
    assert row["source_transport"] == "search_snippet"
    assert row["transport_confidence"] == 0.75
    assert "announcement=direct@2026-09-03" in row["evidence_annotation"]
    assert summary["outcome"] == ConfidenceLabel.REPORTED.value


def test_source_independence_uses_organization_domain_not_subdomain_count():
    assert source_independence_key(
        "https://community.openai.com/t/x",
        "openai.com",
    ) == "openai.com"
    assert source_independence_key(
        "https://www.bbc.co.uk/news/technology",
    ) == "bbc.co.uk"


def test_multi_entity_release_dates_are_separate_claims_not_a_false_conflict():
    query = "Compare OpenAI and Anthropic release dates"
    facets = decompose_query(query)
    assert [(facet.subject, facet.event) for facet in facets] == [
        ("openai", TemporalEvent.RELEASE),
        ("anthropic", TemporalEvent.RELEASE),
    ]
    summary = evaluate_evidence(
        query,
        [
            _source(
                "https://openai.com/index/model-x/",
                "OpenAI released Model X on September 3, 2026.",
            ),
            _source(
                "https://anthropic.com/news/model-y",
                "Anthropic released Model Y on September 5, 2026.",
            ),
        ],
    )
    assert summary["conflict"] is False
    claims = {claim["subject"]: claim for claim in summary["claims"]}
    assert claims["openai"]["event_dates"] == ["2026-09-03"]
    assert claims["anthropic"]["event_dates"] == ["2026-09-05"]


def test_release_event_without_exact_date_is_direct_when_query_does_not_ask_when():
    summary = evaluate_evidence(
        "What Widget version was released in the last 30 days?",
        [_source(
            "https://example.com/widget-release",
            "Widget version 5 was released in the last 30 days.",
        )],
    )
    assert summary["abstain"] is False
    assert summary["claims"][0]["confidence"] == ConfidenceLabel.REPORTED.value
    assert summary["claims"][0]["event_dates"] == []


def test_current_release_lookup_does_not_require_an_exact_event_date():
    query = "What Widget version was released in the last 30 days?"
    facets = decompose_query(query)
    assert len(facets) == 1
    assert facets[0].event is TemporalEvent.RELEASE
    assert facets[0].required is True
    assert facets[0].explicit_date_required is False
    summary = evaluate_evidence(
        query,
        [_source(
            "https://example.com/widget-release",
            "Widget version 5 was released in the last 30 days.",
        )],
    )
    assert summary["abstain"] is False



def test_exact_date_facet_remains_missing_when_search_text_has_event_but_no_date():
    rows = [{
        "title": "GPT-6 Astra availability",
        "snippet": (
            "OpenAI announced GPT-6 Astra on September 3, 2026 and later "
            "made it broadly available to users."
        ),
    }]
    missing = missing_search_facets(ASTRA_QUERY, rows)
    assert [facet.event for facet in missing] == [TemporalEvent.BROAD_AVAILABILITY]


def test_conflict_marks_secondary_date_as_contradicting_against_fetched_primary():
    summary = evaluate_evidence(
        "When was OpenAI GPT-6 Astra announced?",
        [
            _source(
                "https://openai.com/index/gpt-6-astra/",
                "OpenAI announced GPT-6 Astra on September 3, 2026.",
            ),
            _source(
                "https://reuters.com/technology/astra",
                "OpenAI announced GPT-6 Astra on September 4, 2026.",
            ),
        ],
    )
    evidence = summary["claims"][0]["evidence"]
    by_source = {row["source"]: row for row in evidence}
    assert by_source["https://openai.com/index/gpt-6-astra/"]["support"] == "direct"
    assert by_source["https://reuters.com/technology/astra"]["support"] == "contradicting"


def test_source_typing_reaches_safety_cards_and_official_datasets():
    safety = classify_source_authority(
        "https://openai.com/safety/model-card/",
        "OpenAI model safety card",
        title="Model Card",
    )
    dataset = classify_source_authority(
        "https://data.nasa.gov/dataset/example",
        "NASA dataset",
    )
    assert safety["source_authority_kind"] == AuthorityKind.OFFICIAL_SAFETY_OR_MODEL_CARD.value
    assert dataset["source_authority_kind"] == AuthorityKind.OFFICIAL_DATASET.value


def test_google_and_deepmind_first_party_domains_do_not_fake_independence():
    assert source_independence_key(
        "https://deepmind.google/research/example",
        "deepmind.google",
    ) == "google.com"



def test_two_lifecycle_dates_in_one_sentence_bind_to_nearest_event_phrase():
    text = (
        "OpenAI announced GPT-6 Astra on September 3, 2026, then made it "
        "broadly available on September 9, 2026."
    )
    assert event_dates(text, TemporalEvent.ANNOUNCEMENT) == ("2026-09-03",)
    assert event_dates(text, TemporalEvent.BROAD_AVAILABILITY) == ("2026-09-09",)



def test_announcement_date_does_not_leak_into_later_undated_availability_clause():
    text = (
        "OpenAI announced GPT-6 Astra on September 3, 2026 and later made "
        "it broadly available to users."
    )
    assert event_dates(text, TemporalEvent.ANNOUNCEMENT) == ("2026-09-03",)
    assert event_dates(text, TemporalEvent.BROAD_AVAILABILITY) == ()



def test_local_reference_uses_local_transport_not_fake_network_fetch():
    annotated, summary = annotate_evidence_set(
        "Explain rocket propulsion",
        [{
            "chunk_id": "local-ref",
            "source": "/reference/rocket.md",
            "source_title": "Rocket Propulsion",
            "corpus": "reference",
            "trust_class": "TRUSTED_REFERENCE",
            "content": "Rocket propulsion uses nozzles to accelerate exhaust.",
        }],
    )
    row = annotated[0]
    assert row["source_transport"] == "local_corpus"
    assert "source_authority" not in row
    evidence = summary["claims"][0]["evidence"][0]
    assert evidence["authority_kind"] == "trusted_reference"
    assert evidence["transport"] == "local_corpus"



def test_calendar_date_validation_accepts_real_leap_days_and_rejects_impossible_dates():
    valid_iso = (
        "OpenAI announced Model Leap on 2024-02-29."
    )
    valid_text = (
        "OpenAI announced Model Leap on February 29, 2024."
    )
    invalid_non_leap = (
        "OpenAI announced Model Invalid on 2026-02-29."
    )
    invalid_text = (
        "OpenAI announced Model Invalid on February 31, 2026."
    )
    invalid_month = (
        "OpenAI announced Model Invalid on 2026-99-99."
    )

    assert event_dates(valid_iso, TemporalEvent.ANNOUNCEMENT) == ("2024-02-29",)
    assert event_dates(valid_text, TemporalEvent.ANNOUNCEMENT) == ("2024-02-29",)
    assert event_dates(invalid_non_leap, TemporalEvent.ANNOUNCEMENT) == ()
    assert event_dates(invalid_text, TemporalEvent.ANNOUNCEMENT) == ()
    assert event_dates(invalid_month, TemporalEvent.ANNOUNCEMENT) == ()


def test_impossible_calendar_date_cannot_become_direct_temporal_evidence():
    summary = evaluate_evidence(
        "When did OpenAI announce Model Invalid?",
        [_source(
            "https://openai.com/index/model-invalid/",
            "OpenAI announced Model Invalid on February 31, 2026.",
        )],
    )
    claim = summary["claims"][0]
    assert claim["event_dates"] == []
    assert claim["confidence"] == ConfidenceLabel.INSUFFICIENT.value
    assert summary["abstain"] is True


def test_peer_review_requires_article_specific_page_evidence():
    positives = [
        ("https://nature.com/articles/s41586-026-00001-1", "Scaling laws"),
        ("https://science.org/doi/10.1126/science.abc1234", "Scaling laws"),
        ("https://dl.acm.org/doi/10.1145/1234567.1234568", "Scaling laws"),
        ("https://ieeexplore.ieee.org/document/12345678", "Scaling laws"),
        ("https://sciencedirect.com/science/article/pii/S0000000000000000", "Scaling laws"),
        ("https://link.springer.com/article/10.1007/s00000-026-00000-0", "Scaling laws"),
    ]
    negatives = [
        ("https://nature.com/news/latest-ai-news", "AI news"),
        ("https://science.org/", "Science homepage"),
        ("https://acm.org/about-acm", "About ACM"),
        ("https://ieee.org/about/index.html", "About IEEE"),
    ]

    for url, title in positives:
        result = classify_source_authority(url, "transformer scaling study", title=title)
        assert result["source_authority_kind"] == AuthorityKind.PEER_REVIEWED_PUBLICATION.value

    for url, title in negatives:
        result = classify_source_authority(url, "transformer scaling study", title=title)
        assert result["source_authority_kind"] != AuthorityKind.PEER_REVIEWED_PUBLICATION.value
        assert result["research_authority_score"] < 0.85
