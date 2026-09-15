from reverend.intelligence.contracts import EvidenceClass
from reverend.intelligence.evidence import (
    classify_evidence,
    relevance_score,
    retrieval_scopes,
    select_evidence,
    freshness_satisfies,
)


def test_provenance_maps_to_semantic_evidence_classes():
    assert classify_evidence({
        "corpus": "obsidian",
        "trust_class": "TRUSTED_PERSONAL",
    }) == EvidenceClass.PERSONAL

    assert classify_evidence({
        "corpus": "reference",
        "trust_class": "TRUSTED_REFERENCE",
    }) == EvidenceClass.REFERENCE

    assert classify_evidence({
        "corpus": "public-cache",
        "trust_class": "UNTRUSTED_EXTERNAL",
    }) == EvidenceClass.FRESH

    assert classify_evidence({
        "corpus": "synthetic",
        "trust_class": "TRUSTED_PRIMARY",
    }) is None


def test_retrieval_scopes_do_not_promote_personal_to_reference():
    assert retrieval_scopes(
        (EvidenceClass.PERSONAL,)
    ) == ((None, "TRUSTED_PERSONAL"),)

    assert retrieval_scopes(
        (EvidenceClass.REFERENCE,)
    ) == ((None, "TRUSTED_REFERENCE"),)


def test_relevance_gate_rejects_wrong_class_and_irrelevant_material():
    rows = [
        {
            "chunk_id": "personal",
            "source": "/vault/rocket.md",
            "source_title": "My rocket note",
            "corpus": "obsidian",
            "trust_class": "TRUSTED_PERSONAL",
            "content": "rocket propulsion",
        },
        {
            "chunk_id": "irrelevant",
            "source": "/reference/ethics.md",
            "source_title": "Virtue Ethics",
            "corpus": "reference",
            "trust_class": "TRUSTED_REFERENCE",
            "content": "Aristotle and moral character",
        },
        {
            "chunk_id": "relevant",
            "source": "/reference/rocket.md",
            "source_title": "Rocket Propulsion",
            "corpus": "reference",
            "trust_class": "TRUSTED_REFERENCE",
            "content": "Rocket propulsion and nozzle fundamentals",
        },
    ]

    result = select_evidence(
        "Explain rocket propulsion",
        rows,
        (EvidenceClass.REFERENCE,),
    )

    assert result.outcome == "relevant"
    assert [
        row["chunk_id"] for row in result.accepted
    ] == ["relevant"]

    reasons = {
        row["chunk_id"]: row["evidence_rejection"]
        for row in result.rejected
    }

    assert reasons["personal"] == "class_not_requested"
    assert reasons["irrelevant"] == "low_relevance"


def test_missing_evidence_is_explicit():
    result = select_evidence(
        "Who is an unsupported entity?",
        [],
        (EvidenceClass.REFERENCE,),
    )

    assert result.outcome == "insufficient"
    assert result.metadata()["accepted_count"] == 0


def test_vague_query_preserves_eligible_evidence_as_partial():
    row = {
        "chunk_id": "one",
        "source": "/reference/one.md",
        "corpus": "reference",
        "trust_class": "TRUSTED_REFERENCE",
        "content": "Evidence",
    }

    assert relevance_score("Explain this", row) == 0.5

    result = select_evidence(
        "Explain this",
        [row],
        (EvidenceClass.REFERENCE,),
    )

    assert result.outcome == "partial"
    assert len(result.accepted) == 1



def test_title_entity_resolution_repairs_a_typo_conservatively():
    from reverend.intelligence.evidence import resolve_entity

    rows = [{
        "source": "/reference/xavier.md",
        "source_title": "Xavier: Renegade Angel",
        "evidence_class": "REFERENCE",
        "content": "Animated television series",
    }]

    result = resolve_entity(
        "xaiver the renegade angel",
        rows,
    )

    assert result is not None
    assert result.entity == "Xavier: Renegade Angel"
    assert result.confidence >= 0.84


def test_title_entity_resolution_rejects_unrelated_titles():
    from reverend.intelligence.evidence import resolve_entity

    rows = [{
        "source": "/reference/ethics.md",
        "source_title": "Virtue Ethics",
        "evidence_class": "REFERENCE",
        "content": "Aristotle",
    }]

    assert resolve_entity(
        "xaiver the renegade angel",
        rows,
    ) is None


def test_duplicate_candidates_do_not_duplicate_accepted_provenance():
    row = {'chunk_id': 'reference', 'source': '/reference/rocket',
           'trust_class': 'TRUSTED_REFERENCE', 'content': 'rocket propulsion',
           'content_hash': 'hash', 'indexed_at': '2026-09-14'}
    result = select_evidence('rocket propulsion', [row, dict(row)], (EvidenceClass.REFERENCE,))
    assert len(result.accepted) == 1
    assert result.accepted[0]['content_hash'] == 'hash'
    assert result.accepted[0]['indexed_at'] == '2026-09-14'
    assert 'evidence_class' not in row



def test_freshness_window_provenance_requires_equal_or_tighter_window():
    row={'search_freshness':'week'}
    assert freshness_satisfies(row,'week')
    assert freshness_satisfies(row,'month')
    assert freshness_satisfies(row,'year')
    assert not freshness_satisfies(row,'day')
    assert not freshness_satisfies({},'month')
    assert freshness_satisfies({},'stable')


def test_primary_fresh_evidence_ranks_before_more_lexical_secondary_source():
    rows = [
        {
            "chunk_id": "secondary",
            "source": "https://example.com/gpt-6-astra",
            "source_title": "GPT-6 Astra announcement availability",
            "corpus": "public",
            "trust_class": "UNTRUSTED_EXTERNAL",
            "content": (
                "GPT-6 Astra announcement availability official OpenAI "
                "release date and broad availability."
            ),
            "source_authority": "secondary",
            "source_authority_score": 0.0,
        },
        {
            "chunk_id": "primary",
            "source": "https://openai.com/index/gpt-6-astra/",
            "source_title": "GPT-6 Astra",
            "corpus": "public",
            "trust_class": "UNTRUSTED_EXTERNAL",
            "content": "OpenAI announced GPT-6 Astra and described availability.",
            "source_authority": "primary",
            "source_authority_score": 1.0,
        },
    ]

    result = select_evidence(
        "OpenAI GPT-6 Astra announcement availability",
        rows,
        (EvidenceClass.FRESH,),
        min_relevance=0.20,
    )

    assert len(result.accepted) == 2
    assert result.accepted[0]["chunk_id"] == "primary"
    assert result.accepted[1]["chunk_id"] == "secondary"


def test_primary_authority_can_rescue_borderline_fresh_relevance():
    query = (
        "OpenAI GPT-6 Astra first announced broadly available distinguish "
        "research announcement later product availability rollout dates"
    )
    base = {
        "source_title": "GPT-6 Astra",
        "corpus": "public",
        "trust_class": "UNTRUSTED_EXTERNAL",
        "content": "OpenAI introduced Astra for a limited rollout.",
    }

    primary = {
        **base,
        "chunk_id": "primary-borderline",
        "source": "https://openai.com/index/gpt-6-astra/",
        "source_authority": "primary",
        "source_authority_score": 1.0,
    }
    secondary = {
        **base,
        "chunk_id": "secondary-borderline",
        "source": "https://example.com/astra",
        "source_authority": "secondary",
        "source_authority_score": 0.0,
    }

    primary_result = select_evidence(
        query,
        [primary],
        (EvidenceClass.FRESH,),
        min_relevance=0.34,
    )
    secondary_result = select_evidence(
        query,
        [secondary],
        (EvidenceClass.FRESH,),
        min_relevance=0.34,
    )

    assert len(primary_result.accepted) == 1
    assert primary_result.accepted[0]["evidence_authority_boost"] == 0.15
    assert primary_result.accepted[0]["evidence_gate_score"] >= 0.34
    assert len(secondary_result.accepted) == 0



def test_typed_research_authority_outranks_unknown_domain_without_vendor_hint():
    from reverend.research.quality import annotate_source

    query = "current transformer research announcement"
    reputable = annotate_source(query, {
        "chunk_id": "reuters",
        "source": "https://reuters.com/technology/example",
        "source_title": "Transformer research announcement",
        "corpus": "public",
        "trust_class": "UNTRUSTED_EXTERNAL",
        "content": "Transformer research announcement details.",
    })
    unknown = annotate_source(query, {
        "chunk_id": "unknown",
        "source": "https://random-example.invalid/article",
        "source_title": "Transformer research announcement",
        "corpus": "public",
        "trust_class": "UNTRUSTED_EXTERNAL",
        "content": "Transformer research announcement details.",
    })

    result = select_evidence(
        query,
        [unknown, reputable],
        (EvidenceClass.FRESH,),
        min_relevance=0.20,
    )

    assert [row["chunk_id"] for row in result.accepted] == ["reuters", "unknown"]
    assert result.accepted[0]["research_authority_score"] > result.accepted[1]["research_authority_score"]
