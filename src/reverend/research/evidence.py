"""Canonical conversion of persisted public research into evidence rows."""
from __future__ import annotations


def public_source_candidate(
    source: dict,
    index: int,
    *,
    query: str = "",
) -> dict:
    """Normalize one persisted public source for the intelligence evidence gate."""

    if not isinstance(source, dict):
        raise ValueError("Public source must be an object")
    if not isinstance(index, int) or isinstance(index, bool) or index < 1:
        raise ValueError("Public source index must be positive")

    source_id = str(source.get("id", "")).strip()
    url = str(source.get("url", "")).strip()
    content = str(source.get("content", ""))

    if not source_id or not url or not content.strip():
        raise ValueError("Public source is missing required provenance or content")

    row = {
        "chunk_id": "public:" + source_id,
        "source": url,
        "source_title": source.get("source_title") or url,
        "corpus": "public",
        "trust_class": "UNTRUSTED_EXTERNAL",
        "content": content[:2000],
        "id": source_id,
        "citation_label": f"W{index}",
    }

    if query:
        from .search import source_authority
        row.update(source_authority(url, query))

    for key in (
        "content_hash",
        "created_at",
        "clipped",
        "search_provider",
        "search_rank",
        "published_at",
        "updated_at",
        "search_result_date",
        "retrieved_at",
        "search_age",
        "search_freshness",
        "source_authority",
        "source_authority_score",
        "authority_domain",
        "source_transport",
        "transport_confidence",
        "fetch_status",
        "fetch_error",
        "_image_candidate_url",
        "image_id",
    ):
        value = source.get(key)
        if value is not None:
            row[key] = value

    if query:
        from .quality import annotate_source
        row = annotate_source(query, row)

    return row
