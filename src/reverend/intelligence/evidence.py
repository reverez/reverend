"""Deterministic evidence classification, selection and relevance gating."""
from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re

from .contracts import EvidenceClass


_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "do", "for",
    "from", "how", "i", "in", "is", "it", "me", "of", "on", "or",
    "please", "tell", "explain", "describe", "summarize", "summarise",
    "that", "the", "their", "this", "to", "was",
    "what", "when", "where", "which", "who", "why", "with", "would",
    "could", "should", "build",
}


@dataclass(frozen=True)
class EvidenceResult:
    accepted: tuple[dict, ...]
    rejected: tuple[dict, ...]
    outcome: str
    requested_classes: tuple[EvidenceClass, ...]

    def metadata(self) -> dict:
        reasons: dict[str, int] = {}
        for row in self.rejected:
            reason = str(row.get("evidence_rejection", "rejected"))
            reasons[reason] = reasons.get(reason, 0) + 1

        return {
            "outcome": self.outcome,
            "requested_classes": [
                value.value for value in self.requested_classes
            ],
            "accepted_count": len(self.accepted),
            "rejected_count": len(self.rejected),
            "rejection_reasons": reasons,
        }


@dataclass(frozen=True)
class EntityResolution:
    """Evidence-backed conservative entity/title resolution."""

    entity: str
    confidence: float
    source: str
    method: str = "title_fuzzy"

    def metadata(self) -> dict:
        return {
            "status": "resolved",
            "entity": self.entity,
            "confidence": round(self.confidence, 4),
            "source": self.source,
            "method": self.method,
        }


def _ordered_terms(value: str) -> tuple[str, ...]:
    return tuple(
        token
        for token in re.findall(
            r"[^\W_]+",
            value.casefold(),
            re.UNICODE,
        )
        if len(token) >= 2 and token not in _STOPWORDS
    )


def reference_subject(query: str) -> str | None:
    """Named subject before an appositive, independent of any particular entity."""
    match = re.match(r'(?i)^(?:who|what)\s+(?:is|was|are|were)\s+([^,?]+)', query.strip())
    if not match:
        return None
    subject = match[1].strip()
    return subject if len(re.findall(r'\b[A-Z][a-z]+\b', subject)) >= 2 else None


def reference_terms(query: str) -> tuple[str, ...]:
    return _ordered_terms(query)


def resolve_entity(
    query: str,
    rows: list[dict] | tuple[dict, ...],
    *,
    minimum_confidence: float = 0.84,
) -> EntityResolution | None:
    """Resolve only when accepted evidence titles support the correction."""

    if not 0 <= minimum_confidence <= 1:
        raise ValueError("Invalid entity resolution threshold")

    query_terms = _ordered_terms(query)
    if not query_terms:
        return None

    query_set = set(query_terms)
    best: EntityResolution | None = None

    for row in rows:
        titles = tuple(
            dict.fromkeys(
                str(value).strip()
                for value in (
                    row.get("source_title"),
                    row.get("title"),
                    row.get("section"),
                )
                if str(value or "").strip()
            )
        )

        for title in titles:
            title_terms = _ordered_terms(title)
            if not title_terms:
                continue

            title_set = set(title_terms)
            overlap = len(query_set & title_set) / len(title_set)

            if len(title_terms) == 1:
                fuzzy = 1.0 if title_terms[0] in query_set else 0.0
            else:
                if overlap < 0.5:
                    continue

                window_size = len(title_terms)
                windows = (
                    [
                        query_terms[start:start + window_size]
                        for start in range(
                            max(1, len(query_terms) - window_size + 1)
                        )
                    ]
                    if len(query_terms) >= window_size
                    else [query_terms]
                )
                target = " ".join(title_terms)
                fuzzy = max(
                    SequenceMatcher(
                        None,
                        " ".join(window),
                        target,
                    ).ratio()
                    for window in windows
                )

            confidence = max(overlap, fuzzy)
            if confidence < minimum_confidence:
                continue

            candidate = EntityResolution(
                entity=title,
                confidence=confidence,
                source=str(row.get("source", "")),
            )
            if (
                best is None
                or candidate.confidence > best.confidence
            ):
                best = candidate

    return best


def classify_evidence(row: dict) -> EvidenceClass | None:
    """Map storage provenance to the semantic evidence taxonomy."""

    corpus = str(row.get("corpus", "")).strip().lower()
    trust = str(row.get("trust_class", "")).strip().upper()

    if trust == "TRUSTED_PERSONAL" or corpus == "obsidian":
        return EvidenceClass.PERSONAL

    if (
        trust == "TRUSTED_PROJECT"
        or corpus.startswith("project:")
    ):
        return EvidenceClass.PROJECT

    if (
        trust == "TRUSTED_REFERENCE"
        or corpus in {
            "reference",
            "references",
            "wikipedia",
            "kiwix",
        }
    ):
        return EvidenceClass.REFERENCE

    if trust == "UNTRUSTED_EXTERNAL":
        return EvidenceClass.FRESH

    # TRUSTED_PRIMARY is deliberately not promoted to REFERENCE.
    # The current canonical database contains synthetic primary material,
    # not a verified general reference corpus.
    return None


_FRESHNESS_WINDOW_ORDER={
    "day":0,
    "week":1,
    "month":2,
    "year":3,
}


def freshness_satisfies(row: dict, required_window: str) -> bool:
    """Require provider-window provenance equal to or tighter than the request."""

    if required_window=="stable":
        return True
    required=_FRESHNESS_WINDOW_ORDER.get(required_window)
    observed=_FRESHNESS_WINDOW_ORDER.get(
        str(row.get("search_freshness","")).strip().lower()
    )
    if required is None:
        raise ValueError("Unknown freshness window")
    return observed is not None and observed<=required


def retrieval_scopes(
    classes: tuple[EvidenceClass, ...],
) -> tuple[tuple[str | None, str | None], ...]:
    """Translate semantic evidence classes to safe local retrieval scopes."""

    result: list[tuple[str | None, str | None]] = []

    for evidence_class in classes:
        if not isinstance(evidence_class, EvidenceClass):
            evidence_class = EvidenceClass(evidence_class)

        if evidence_class == EvidenceClass.PERSONAL:
            result.append((None, "TRUSTED_PERSONAL"))
        elif evidence_class == EvidenceClass.REFERENCE:
            result.append((None, "TRUSTED_REFERENCE"))
        elif evidence_class == EvidenceClass.FRESH:
            result.append((None, "UNTRUSTED_EXTERNAL"))
        # PROJECT evidence comes from the registered repository/memory
        # path rather than the global knowledge registry.

    return tuple(dict.fromkeys(result))


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(
            r"[^\W_]+",
            value.lower(),
            re.UNICODE,
        )
        if len(token) >= 2 and token not in _STOPWORDS
    }


def relevance_score(query: str, row: dict) -> float:
    """Cheap lexical evidence-quality signal independent of model confidence."""

    query_terms = _tokens(query)

    # If a request is too vague for lexical assessment, preserve eligible
    # evidence as partial rather than pretending it is irrelevant.
    if not query_terms:
        return 0.5

    title = (
        str(row.get("source_title", ""))
        + " "
        + str(row.get("section", ""))
    )
    body = title + " " + str(row.get("content", ""))

    subject = reference_subject(query)
    if subject:
        subject_terms = _tokens(subject) - {'professor', 'doctor', 'dr', 'mr', 'mrs', 'ms', 'sir'}
        if subject_terms and len(subject_terms & _tokens(body)) / len(subject_terms) < 0.8:
            return 0.0

    title_terms = _tokens(title)
    body_terms = _tokens(body)

    matched = query_terms & body_terms
    title_matched = query_terms & title_terms

    if not matched:
        return 0.0

    score = (
        len(matched)
        + 0.5 * len(title_matched)
    ) / len(query_terms)

    return min(1.0, score)


def select_evidence(
    query: str,
    rows: list[dict] | tuple[dict, ...],
    allowed_classes: tuple[EvidenceClass, ...],
    *,
    limit: int = 5,
    min_relevance: float = 0.34,
) -> EvidenceResult:
    """Deduplicate, classify and gate evidence before prompt compilation."""

    if limit < 0:
        raise ValueError("Evidence limit cannot be negative")

    if not 0 <= min_relevance <= 1:
        raise ValueError("Invalid evidence relevance threshold")

    allowed = tuple(
        value
        if isinstance(value, EvidenceClass)
        else EvidenceClass(value)
        for value in allowed_classes
    )
    allowed_set = set(allowed)

    # Short title-like requests should not accumulate unrelated partial-title hits
    # when one eligible source confidently resolves the whole requested title.
    query_terms = _ordered_terms(query)
    title_focus = None
    if 2 <= len(query_terms) <= 6 and reference_subject(query) is None:
        title_rows = [row for row in rows
                      if classify_evidence(row) in allowed_set
                      and classify_evidence(row) == EvidenceClass.REFERENCE
                      and len(_ordered_terms(str(row.get('source_title', '')))) >= len(query_terms)]
        resolution = resolve_entity(query, title_rows)
        if resolution is not None:
            title_focus = set(_ordered_terms(resolution.entity))

    accepted: list[dict] = []
    rejected: list[dict] = []
    seen: set[tuple] = set()

    for original in rows:
        row = dict(original)

        identity = (
            row.get("chunk_id"),
            row.get("source"),
            row.get("section"),
            row.get("page"),
        )

        if identity in seen:
            continue

        seen.add(identity)

        evidence_class = classify_evidence(row)

        if evidence_class is None:
            row["evidence_rejection"] = "unclassified_provenance"
            rejected.append(row)
            continue

        row["evidence_class"] = evidence_class.value

        if evidence_class not in allowed_set:
            row["evidence_rejection"] = "class_not_requested"
            rejected.append(row)
            continue

        score = relevance_score(query, row)
        row["evidence_relevance"] = score

        authority_score = float(
            row.get("source_authority_score", 0.0)
            or 0.0
        )
        authority_boost = (
            0.15
            if (
                evidence_class == EvidenceClass.FRESH
                and authority_score >= 1.0
            )
            else 0.0
        )
        gate_score = min(
            1.0,
            score + authority_boost,
        )
        row["evidence_gate_score"] = gate_score
        if authority_boost:
            row["evidence_authority_boost"] = authority_boost

        if gate_score < min_relevance:
            row["evidence_rejection"] = "low_relevance"
            rejected.append(row)
            continue

        if (title_focus and evidence_class == EvidenceClass.REFERENCE
                and not title_focus <= set(_ordered_terms(str(row.get('source_title', ''))))):
            row['evidence_rejection'] = 'resolved_title_mismatch'
            rejected.append(row)
            continue

        accepted.append(row)

    accepted.sort(
        key=lambda row: (
            -float(row.get("research_authority_score", 0.0)),
            -float(row.get("source_authority_score", 0.0)),
            -float(row.get("claim_support_score", 0.0)),
            -float(row.get("transport_confidence", 1.0)),
            -float(
                row["fabric_score"]
                if row.get("fabric_score") is not None
                else row.get("evidence_relevance", 0.0)
            ),
            -float(row.get("evidence_relevance", 0.0)),
            -float(row.get("rrf_score", row.get("relevance", 0.0))),
            str(row.get("chunk_id", "")),
        )
    )

    accepted = accepted[:limit]

    if accepted:
        mean = sum(
            float(row.get("evidence_relevance", 0.0))
            for row in accepted
        ) / len(accepted)

        outcome = "relevant" if mean >= 0.60 else "partial"
    elif rows:
        outcome = "irrelevant"
    else:
        outcome = "insufficient"

    return EvidenceResult(
        accepted=tuple(accepted),
        rejected=tuple(rejected),
        outcome=outcome,
        requested_classes=allowed,
    )
