"""Deterministic research-quality semantics above Reverend's canonical web pipeline.

This module does not fetch, search, synthesize, or grant trust.  It annotates evidence
already produced by the existing bounded research path so downstream code can reason
about authority, transport, claim support, temporal events, corroboration and abstention
without asking a model to invent those labels.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
import re
from urllib.parse import urlsplit


class AuthorityKind(str, Enum):
    OFFICIAL_DOCUMENTATION = "official_documentation"
    OFFICIAL_ANNOUNCEMENT = "official_announcement"
    OFFICIAL_DEVELOPER_DOCUMENTATION = "official_developer_documentation"
    OFFICIAL_RELEASE_NOTES = "official_release_notes"
    OFFICIAL_SAFETY_OR_MODEL_CARD = "official_safety_or_model_card"
    GOVERNMENT_OR_REGULATOR = "government_or_regulator"
    STANDARDS_BODY = "standards_body"
    PEER_REVIEWED_PUBLICATION = "peer_reviewed_publication"
    PREPRINT = "preprint"
    OFFICIAL_DATASET = "official_dataset"
    REPUTABLE_INDEPENDENT_REPORTING = "reputable_independent_reporting"
    SPECIALIST_TECHNICAL_REPORTING = "specialist_technical_reporting"
    COMMUNITY = "community"
    AGGREGATOR = "aggregator"
    UNKNOWN = "unknown"


class SupportType(str, Enum):
    DIRECT = "direct"
    CORROBORATING = "corroborating"
    INDIRECT = "indirect"
    CONTRADICTING = "contradicting"
    UNSUPPORTED = "unsupported"


class TemporalEvent(str, Enum):
    GENERAL = "general"
    ANNOUNCEMENT = "announcement"
    PREVIEW = "preview"
    INITIAL_ROLLOUT = "initial_rollout"
    LIMITED_ACCESS = "limited_access"
    API_AVAILABILITY = "api_availability"
    CHATGPT_AVAILABILITY = "chatgpt_availability"
    BROAD_AVAILABILITY = "broad_availability"
    GENERAL_AVAILABILITY = "general_availability"
    RELEASE = "release"


class ConfidenceLabel(str, Enum):
    CONFIRMED_PRIMARY = "confirmed_by_primary_source"
    STRONGLY_SUPPORTED = "strongly_supported"
    CORROBORATED = "corroborated"
    REPORTED = "reported"
    CONFLICTING = "conflicting_evidence"
    INSUFFICIENT = "insufficient_evidence"


@dataclass(frozen=True)
class QueryFacet:
    id: str
    event: TemporalEvent
    query: str
    required: bool = True
    subject: str | None = None
    explicit_date_required: bool = False

    def metadata(self) -> dict:
        return {
            "id": self.id,
            "event": self.event.value,
            "query": self.query,
            "required": self.required,
            "subject": self.subject,
            "explicit_date_required": self.explicit_date_required,
        }


@dataclass(frozen=True)
class ClaimEvidence:
    claim_id: str
    event: TemporalEvent
    source: str
    support: SupportType
    event_date: str | None
    publication_date: str | None
    updated_date: str | None
    search_result_date: str | None
    retrieved_date: str | None
    authority_kind: str
    authority_fit: float
    independence_key: str
    transport: str
    transport_confidence: float
    rationale: str

    def metadata(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "event": self.event.value,
            "source": self.source,
            "support": self.support.value,
            "event_date": self.event_date,
            "publication_date": self.publication_date,
            "updated_date": self.updated_date,
            "search_result_date": self.search_result_date,
            "retrieved_date": self.retrieved_date,
            "authority_kind": self.authority_kind,
            "authority_fit": round(self.authority_fit, 3),
            "independence_key": self.independence_key,
            "transport": self.transport,
            "transport_confidence": round(self.transport_confidence, 3),
            "rationale": self.rationale,
        }


_VENDOR_DOMAINS = (
    ("openai", ("openai.com",)),
    ("anthropic", ("anthropic.com",)),
    ("claude", ("anthropic.com",)),
    ("google", ("google.com", "deepmind.google")),
    ("gemini", ("google.com", "deepmind.google")),
    ("deepmind", ("deepmind.google",)),
    ("microsoft", ("microsoft.com",)),
    ("azure", ("microsoft.com",)),
    ("meta", ("meta.com",)),
    ("nvidia", ("nvidia.com",)),
    ("deepseek", ("deepseek.com",)),
    ("mistral", ("mistral.ai",)),
    ("cohere", ("cohere.com",)),
    ("xai", ("x.ai",)),
    ("grok", ("x.ai",)),
    ("amazon", ("amazon.com",)),
    ("aws", ("amazon.com",)),
)

_COMMUNITY_PREFIXES = ("community.", "forum.", "forums.", "discuss.")
_PREPRINT_DOMAINS = {"arxiv.org", "biorxiv.org", "medrxiv.org"}
_PEER_REVIEWED_DOMAINS = {
    "acm.org", "dl.acm.org", "ieee.org", "ieeexplore.ieee.org",
    "nature.com", "science.org", "sciencedirect.com", "springer.com",
}
_SCHOLARLY_ARTICLE_PATHS = (
    re.compile(r"^/articles?/[a-z0-9._;()/:+-]+$", re.I),
    re.compile(r"^/doi/(?:abs/|full/|epdf/)?10\.[^/]+/.+", re.I),
    re.compile(r"^/document/\d+/?$", re.I),
    re.compile(r"^/science/article/(?:pii|abs/pii)/[a-z0-9]+/?$", re.I),
    re.compile(r"^/article/10\.[^/]+/.+", re.I),
    re.compile(r"^/chapter/10\.[^/]+/.+", re.I),
)
_SCHOLARLY_TITLE_MARKERS = (
    "research article",
    "original research",
    "journal article",
    "conference paper",
    "proceedings of ",
    "doi:",
)
_STANDARDS_DOMAINS = {"w3.org", "ietf.org", "iso.org", "nvlpubs.nist.gov"}
_REPUTABLE_REPORTING_DOMAINS = {
    "reuters.com", "apnews.com", "bbc.com", "bbc.co.uk",
    "ft.com", "nytimes.com", "theguardian.com",
}
_SPECIALIST_TECH_DOMAINS = {
    "arstechnica.com", "techcrunch.com", "theverge.com",
    "wired.com", "semianalysis.com",
}
_AGGREGATOR_DOMAINS = {
    "medium.com", "towardsdatascience.com", "aitoolsclub.com",
    "futuretools.io",
}
_MULTI_LABEL_SUFFIXES = {
    "co.uk", "org.uk", "gov.uk", "ac.uk", "com.au", "co.jp",
}
_ORGANIZATION_DOMAINS = {
    "openai.com": "openai.com",
    "anthropic.com": "anthropic.com",
    "google.com": "google.com",
    "deepmind.google": "google.com",
    "microsoft.com": "microsoft.com",
    "meta.com": "meta.com",
    "nvidia.com": "nvidia.com",
    "deepseek.com": "deepseek.com",
    "mistral.ai": "mistral.ai",
    "cohere.com": "cohere.com",
    "x.ai": "x.ai",
    "amazon.com": "amazon.com",
}


def _host(url: str) -> str:
    try:
        return (urlsplit(str(url or "")).hostname or "").casefold().rstrip(".")
    except ValueError:
        return ""


def _registered_domain(host: str) -> str:
    labels = [part for part in host.split(".") if part]
    if len(labels) <= 2:
        return host
    suffix = ".".join(labels[-2:])
    if suffix in _MULTI_LABEL_SUFFIXES and len(labels) >= 3:
        return ".".join(labels[-3:])
    return suffix


def preferred_primary_domains(text: str) -> tuple[str, ...]:
    """Return a small deterministic set of first-party domains named by the query."""
    tokens = set(re.findall(r"[a-z0-9]+", str(text or "").casefold()))
    domains: list[str] = []
    for token, candidates in _VENDOR_DOMAINS:
        if token not in tokens:
            continue
        for domain in candidates:
            if domain not in domains:
                domains.append(domain)
    return tuple(domains)


def source_independence_key(url: str, authority_domain: str | None = None) -> str:
    """Approximate source independence without pretending to infer syndication graphs."""
    host = _host(url)
    if authority_domain:
        domain = str(authority_domain).casefold().rstrip(".")
        return _ORGANIZATION_DOMAINS.get(domain, domain)
    registered = _registered_domain(host)
    return _ORGANIZATION_DOMAINS.get(registered, registered) or "unknown"


def _is_host_or_subdomain(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def _path_tokens(url: str) -> set[str]:
    try:
        path = urlsplit(str(url or "")).path.casefold()
    except ValueError:
        return set()
    return set(re.findall(r"[a-z0-9]+", path))


def _scholarly_publication_page(url: str, title: str = "") -> bool:
    """Require page-level evidence before claiming a source is peer reviewed."""
    try:
        path = urlsplit(str(url or "")).path or "/"
    except ValueError:
        return False
    if any(pattern.match(path) for pattern in _SCHOLARLY_ARTICLE_PATHS):
        return True
    lower_title = str(title or "").casefold()
    return any(marker in lower_title for marker in _SCHOLARLY_TITLE_MARKERS)


def _comparative_claim(text: str) -> bool:
    return bool(re.search(
        r"\b(?:best|better|strongest|leading|state[- ]of[- ]the[- ]art|"
        r"outperform(?:s|ed)?|superior|most capable)\b",
        str(text or ""),
        re.I,
    ))


def classify_source_authority(
    url: str,
    query: str = "",
    *,
    title: str = "",
) -> dict:
    """Return compatibility authority plus a more expressive query-relative type."""
    host = _host(url)
    domains = preferred_primary_domains(query)
    path = _path_tokens(url)
    lower_title = str(title or "").casefold()

    for domain in domains:
        if not _is_host_or_subdomain(host, domain):
            continue
        relative = host[: -(len(domain) + 1)] if host != domain else ""
        if any(relative.startswith(prefix.rstrip(".")) for prefix in _COMMUNITY_PREFIXES):
            return {
                "source_authority": "community",
                "source_authority_score": 0.25,
                "source_authority_kind": AuthorityKind.COMMUNITY.value,
                "research_authority_score": 0.20,
                "claim_authority_fit": 0.20,
                "authority_domain": domain,
                "source_independence_key": source_independence_key(url, domain),
            }

        if (
            "dataset" in path
            or "datasets" in path
            or "dataset" in lower_title
        ):
            kind = AuthorityKind.OFFICIAL_DATASET
        elif (
            "release" in path
            or "releases" in path
            or "changelog" in path
            or "release notes" in lower_title
        ):
            kind = AuthorityKind.OFFICIAL_RELEASE_NOTES
        elif (
            ("model" in path and "card" in path)
            or ("system" in path and "card" in path)
            or "safety" in path
            or "model card" in lower_title
            or "system card" in lower_title
        ):
            kind = AuthorityKind.OFFICIAL_SAFETY_OR_MODEL_CARD
        elif (
            relative.startswith(("platform", "developers", "developer"))
            or "docs" in path
            or "api" in path
        ):
            kind = AuthorityKind.OFFICIAL_DEVELOPER_DOCUMENTATION
        elif (
            "blog" in path
            or "news" in path
            or "index" in path
            or "announce" in lower_title
            or "introduc" in lower_title
            or "launch" in lower_title
        ):
            kind = AuthorityKind.OFFICIAL_ANNOUNCEMENT
        else:
            kind = AuthorityKind.OFFICIAL_DOCUMENTATION

        fit = 0.55 if _comparative_claim(query) else 1.0
        return {
            "source_authority": "primary",
            "source_authority_score": 1.0,
            "source_authority_kind": kind.value,
            "research_authority_score": 1.0,
            "claim_authority_fit": fit,
            "authority_domain": domain,
            "source_independence_key": source_independence_key(url, domain),
        }

    registered = _registered_domain(host)
    if (
        (host.startswith("data.") or "dataset" in _path_tokens(url))
        and (
            host.endswith(".gov")
            or host.endswith(".gov.uk")
            or registered in {"gov.uk", "europa.eu"}
        )
    ):
        kind = AuthorityKind.OFFICIAL_DATASET
        score = 0.92
    elif (
        host.endswith(".gov")
        or host.endswith(".gov.uk")
        or registered in {"gov.uk", "europa.eu"}
    ):
        kind = AuthorityKind.GOVERNMENT_OR_REGULATOR
        score = 0.90
    elif host in _STANDARDS_DOMAINS or registered in _STANDARDS_DOMAINS:
        kind = AuthorityKind.STANDARDS_BODY
        score = 0.90
    elif host in _PREPRINT_DOMAINS or registered in _PREPRINT_DOMAINS:
        kind = AuthorityKind.PREPRINT
        score = 0.70
    elif (
        host in _PEER_REVIEWED_DOMAINS
        or registered in _PEER_REVIEWED_DOMAINS
    ) and _scholarly_publication_page(url, title):
        kind = AuthorityKind.PEER_REVIEWED_PUBLICATION
        score = 0.85
    elif host in _PEER_REVIEWED_DOMAINS or registered in _PEER_REVIEWED_DOMAINS:
        kind = AuthorityKind.UNKNOWN
        score = 0.45
    elif host in _REPUTABLE_REPORTING_DOMAINS or registered in _REPUTABLE_REPORTING_DOMAINS:
        kind = AuthorityKind.REPUTABLE_INDEPENDENT_REPORTING
        score = 0.72
    elif host in _SPECIALIST_TECH_DOMAINS or registered in _SPECIALIST_TECH_DOMAINS:
        kind = AuthorityKind.SPECIALIST_TECHNICAL_REPORTING
        score = 0.62
    elif host in _AGGREGATOR_DOMAINS or registered in _AGGREGATOR_DOMAINS:
        kind = AuthorityKind.AGGREGATOR
        score = 0.20
    else:
        kind = AuthorityKind.UNKNOWN
        score = 0.45 if host else 0.30

    legacy = "unknown" if kind is AuthorityKind.UNKNOWN and not domains else "secondary"
    legacy_score = 0.5 if legacy == "unknown" else 0.0
    return {
        "source_authority": legacy,
        "source_authority_score": legacy_score,
        "source_authority_kind": kind.value,
        "research_authority_score": score,
        "claim_authority_fit": score,
        "source_independence_key": source_independence_key(url),
    }


_EVENT_PATTERNS = {
    TemporalEvent.ANNOUNCEMENT: (
        r"\bannounc(?:e|ed|ement|ing)\b",
        r"\bintroduc(?:e|ed|tion|ing)\b",
        r"\bunveil(?:ed|ing)?\b",
        r"\breveal(?:ed|ing)?\b",
    ),
    TemporalEvent.PREVIEW: (
        r"\bresearch preview\b", r"\bpreview(?:ed|ing)?\b", r"\bbeta\b",
    ),
    TemporalEvent.INITIAL_ROLLOUT: (
        r"\binitial rollout\b", r"\brolling out\b", r"\brollout\b",
    ),
    TemporalEvent.LIMITED_ACCESS: (
        r"\blimited access\b", r"\bselect users?\b", r"\bwaitlist\b",
    ),
    TemporalEvent.API_AVAILABILITY: (
        r"\bapi\b.*\b(?:available|availability|released|rollout)\b",
        r"\b(?:available|availability|released|rollout)\b.*\bapi\b",
    ),
    TemporalEvent.CHATGPT_AVAILABILITY: (
        r"\bchatgpt\b.*\b(?:available|availability|released|rollout)\b",
        r"\b(?:available|availability|released|rollout)\b.*\bchatgpt\b",
    ),
    TemporalEvent.BROAD_AVAILABILITY: (
        r"\bbroad(?:ly)? available\b", r"\bavailable to (?:all|everyone)\b",
        r"\ball users\b",
    ),
    TemporalEvent.GENERAL_AVAILABILITY: (
        r"\bgeneral availability\b", r"\bgenerally available\b", r"\bga\b",
    ),
    TemporalEvent.RELEASE: (
        r"\breleas(?:e|ed|ing)\b", r"\bshipp(?:ed|ing)\b",
    ),
}

_QUERY_EVENT_RULES = (
    (TemporalEvent.ANNOUNCEMENT, r"\b(?:announc(?:e|ed|ement|ing)|introduc(?:e|ed|tion|ing)|unveil(?:ed|ing)?|first revealed)\b"),
    (TemporalEvent.PREVIEW, r"\b(?:research preview|preview|beta)\b"),
    (TemporalEvent.INITIAL_ROLLOUT, r"\b(?:initial rollout|rolling out|rollout began)\b"),
    (TemporalEvent.LIMITED_ACCESS, r"\b(?:limited access|select users|waitlist)\b"),
    (TemporalEvent.API_AVAILABILITY, r"\bapi\b.{0,32}\b(?:availab(?:le|ility)?|releas(?:e|ed)|rollout)\b"),
    (TemporalEvent.CHATGPT_AVAILABILITY, r"\bchatgpt\b.{0,32}\b(?:availab(?:le|ility)?|releas(?:e|ed)|rollout)\b"),
    (TemporalEvent.BROAD_AVAILABILITY, r"\b(?:broad(?:ly)? available|all users|everyone)\b"),
    (TemporalEvent.GENERAL_AVAILABILITY, r"\b(?:general availability|generally available|\bga\b)"),
    (TemporalEvent.RELEASE, r"\b(?:release dates?|released|shipped)\b"),
)

_EVENT_SEARCH_TERMS = {
    TemporalEvent.ANNOUNCEMENT: "announcement announced date",
    TemporalEvent.PREVIEW: "research preview date",
    TemporalEvent.INITIAL_ROLLOUT: "initial rollout date",
    TemporalEvent.LIMITED_ACCESS: "limited access date",
    TemporalEvent.API_AVAILABILITY: "API availability date",
    TemporalEvent.CHATGPT_AVAILABILITY: "ChatGPT availability date",
    TemporalEvent.BROAD_AVAILABILITY: "broad availability date",
    TemporalEvent.GENERAL_AVAILABILITY: "general availability date",
    TemporalEvent.RELEASE: "release date",
    TemporalEvent.GENERAL: "",
}


def _query_subjects(query: str) -> tuple[str, ...]:
    quoted = tuple(
        dict.fromkeys(
            value.strip().casefold()
            for value in re.findall(r'"([^"\\n]{2,120})"', query)
            if value.strip()
        )
    )
    if len(quoted) >= 2:
        return quoted[:3]

    tokens = set(re.findall(r"[a-z0-9]+", query.casefold()))
    subjects: list[str] = []
    seen_domains: set[tuple[str, ...]] = set()
    for token, domains in _VENDOR_DOMAINS:
        if token not in tokens or domains in seen_domains:
            continue
        seen_domains.add(domains)
        subjects.append(token)
    return tuple(subjects[:3]) if len(subjects) >= 2 else ()


def decompose_query(query: str, *, max_facets: int = 4) -> tuple[QueryFacet, ...]:
    """Bound temporal/release questions into explicit, non-recursive claim facets."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("Research query must not be empty")
    if not isinstance(max_facets, int) or isinstance(max_facets, bool) or not 1 <= max_facets <= 6:
        raise ValueError("Research facet budget must be 1–6")

    lower = query.casefold()
    events: list[TemporalEvent] = []
    for event, pattern in _QUERY_EVENT_RULES:
        if re.search(pattern, lower, re.I | re.S) and event not in events:
            events.append(event)

    # "available" without a scoped form is intentionally represented as RELEASE rather
    # than guessed to mean broad/general/API availability.
    if not events and re.search(r"\b(?:available|availability|launch)\b", lower):
        events.append(TemporalEvent.RELEASE)
    if not events:
        events.append(TemporalEvent.GENERAL)

    subjects = _query_subjects(query)
    explicit_date_required = bool(
        re.search(
            r"\bwhen\b|\bdates?\b|\bon what (?:day|date)\b",
            lower,
            re.I,
        )
    )
    facet_specs = (
        [(event, subject) for subject in subjects for event in events]
        if subjects
        else [(event, None) for event in events]
    )

    facets = []
    for index, (event, subject) in enumerate(facet_specs[:max_facets], 1):
        suffix = _EVENT_SEARCH_TERMS[event]
        subject_term = subject or ""
        additions = " ".join(value for value in (subject_term, suffix) if value)
        facet_query = query.strip() if not additions else f"{query.strip()} {additions}"
        facets.append(QueryFacet(
            f"claim-{index}",
            event,
            facet_query[:600],
            subject=subject,
            explicit_date_required=explicit_date_required,
        ))
    return tuple(facets)


_MONTHS = (
    "January|February|March|April|May|June|July|August|September|October|"
    "November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
)
_DATE_RE = re.compile(
    rf"(?P<iso>\b\d{{4}}-\d{{2}}-\d{{2}}\b)|"
    rf"(?P<mdy>\b(?:{_MONTHS})\.?\s+\d{{1,2}}(?:st|nd|rd|th)?[,]?\s+\d{{4}}\b)|"
    rf"(?P<dmy>\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{_MONTHS})\.?[,]?\s+\d{{4}}\b)",
    re.I,
)
_MONTH_INDEX = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7,
    "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def _normalize_date(value: str) -> str | None:
    """Normalize only real Gregorian calendar dates within the accepted year bounds."""
    text = value.strip().replace(",", "")
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            year, month, day = (int(part) for part in text.split("-"))
        else:
            parts = re.sub(
                r"(\d)(?:st|nd|rd|th)\b",
                r"\1",
                text,
                flags=re.I,
            ).split()
            if len(parts) != 3:
                return None
            if parts[0].casefold().rstrip(".") in _MONTH_INDEX:
                month = _MONTH_INDEX[parts[0].casefold().rstrip(".")]
                day = int(parts[1])
                year = int(parts[2])
            else:
                day = int(parts[0])
                month = _MONTH_INDEX[parts[1].casefold().rstrip(".")]
                year = int(parts[2])
        if not 1900 <= year <= 2200:
            return None
        return date(year, month, day).isoformat()
    except (KeyError, ValueError):
        return None


def _sentences(text: str) -> tuple[str, ...]:
    return tuple(
        part.strip()
        for part in re.split(r"(?<=[.!?])\s+|[\r\n]+", str(text or ""))
        if part.strip()
    )


def _sentence_event_spans(sentence: str) -> tuple[tuple[TemporalEvent, re.Match], ...]:
    spans = []
    for candidate_event, patterns in _EVENT_PATTERNS.items():
        for pattern in patterns:
            for match in re.finditer(pattern, sentence, re.I | re.S):
                spans.append((candidate_event, match))
    return tuple(
        sorted(
            spans,
            key=lambda item: (item[1].start(), item[1].end()),
        )
    )


def event_dates(
    text: str,
    event: TemporalEvent,
    *,
    subject: str | None = None,
) -> tuple[str, ...]:
    """Bind explicit dates to the local lifecycle-event span that owns them."""
    if event is TemporalEvent.GENERAL:
        return ()
    dates: list[str] = []
    for sentence in _sentences(text):
        if subject and subject.casefold() not in sentence.casefold():
            continue

        all_events = _sentence_event_spans(sentence)
        target_indexes = [
            index
            for index, (candidate_event, _) in enumerate(all_events)
            if candidate_event is event
        ]
        if not target_indexes:
            continue

        date_matches = []
        for match in _DATE_RE.finditer(sentence):
            value = _normalize_date(match.group(0))
            if value:
                date_matches.append((match, value))
        if not date_matches:
            continue

        centers = [
            (match.start() + match.end()) / 2
            for _, match in all_events
        ]
        for index in target_indexes:
            event_center = centers[index]
            lower = (
                (centers[index - 1] + event_center) / 2
                if index > 0
                else float("-inf")
            )
            upper = (
                (event_center + centers[index + 1]) / 2
                if index + 1 < len(centers)
                else float("inf")
            )
            local_dates = [
                (match, value)
                for match, value in date_matches
                if lower
                <= ((match.start() + match.end()) / 2)
                < upper
            ]
            if not local_dates:
                continue
            nearest = min(
                local_dates,
                key=lambda item: abs(
                    ((item[0].start() + item[0].end()) / 2) - event_center
                ),
            )[1]
            if nearest not in dates:
                dates.append(nearest)
    return tuple(dates)


def _event_mentioned(
    text: str,
    event: TemporalEvent,
    *,
    subject: str | None = None,
) -> bool:
    if event is TemporalEvent.GENERAL:
        return True
    candidates = _sentences(text) if subject else (text,)
    return any(
        (not subject or subject.casefold() in candidate.casefold())
        and any(
            re.search(pattern, candidate, re.I | re.S)
            for pattern in _EVENT_PATTERNS.get(event, ())
        )
        for candidate in candidates
    )


def _is_public_source(source: dict) -> bool:
    trust = str(source.get("trust_class") or source.get("trust") or "").upper()
    corpus = str(source.get("corpus") or "").casefold()
    url = str(source.get("source") or source.get("url") or "")
    return (
        trust == "UNTRUSTED_EXTERNAL"
        or corpus == "public"
        or url.startswith("https://")
        or url.startswith("http://")
    )


def _transport(source: dict) -> tuple[str, float]:
    default_transport = "fetched_page" if _is_public_source(source) else "local_corpus"
    transport = str(source.get("source_transport") or default_transport)
    configured = source.get("transport_confidence")
    if configured is not None:
        try:
            confidence = max(0.0, min(1.0, float(configured)))
        except (TypeError, ValueError):
            confidence = 0.0
    else:
        confidence = 0.75 if transport == "search_snippet" else 1.0
    return transport, confidence


def assess_source(query: str, source: dict) -> tuple[ClaimEvidence, ...]:
    """Assess what one source actually supports for each deterministic query facet."""
    facets = decompose_query(query)
    url = str(source.get("source") or source.get("url") or "")
    title = str(source.get("source_title") or source.get("title") or "")
    content = str(source.get("content") or "")
    body = f"{title}\n{content}".strip()

    if _is_public_source(source):
        authority = classify_source_authority(url, query, title=title)
        authority_kind = str(
            source.get("source_authority_kind")
            or authority["source_authority_kind"]
        )
        try:
            authority_fit = float(
                source.get(
                    "claim_authority_fit",
                    authority["claim_authority_fit"],
                )
            )
        except (TypeError, ValueError):
            authority_fit = 0.0
        independence = str(
            source.get("source_independence_key")
            or authority["source_independence_key"]
        )
        legacy_authority = str(
            source.get("source_authority")
            or authority["source_authority"]
        )
    else:
        trust = str(source.get("trust_class") or "").upper()
        authority_kind = (
            "trusted_reference"
            if trust == "TRUSTED_REFERENCE"
            else "trusted_personal"
            if trust == "TRUSTED_PERSONAL"
            else "trusted_project"
            if trust == "TRUSTED_PROJECT"
            else "local_corpus"
        )
        authority_fit = 0.75
        independence = (
            "local:"
            + str(source.get("corpus") or "unknown").casefold()
        )
        legacy_authority = "local"
    transport, transport_confidence = _transport(source)

    result: list[ClaimEvidence] = []
    for facet in facets:
        dates = event_dates(body, facet.event, subject=facet.subject)
        mentioned = _event_mentioned(body, facet.event, subject=facet.subject)
        if facet.event is TemporalEvent.GENERAL:
            terms = {
                token for token in re.findall(r"[a-z0-9]+", query.casefold())
                if len(token) >= 3 and token not in {
                    "what", "when", "where", "which", "with", "from", "that",
                    "this", "were", "have", "does", "about", "into", "according",
                }
            }
            body_terms = set(re.findall(r"[a-z0-9]+", body.casefold()))
            overlap = len(terms & body_terms) / max(1, len(terms))
            if overlap >= 0.55:
                support = SupportType.DIRECT
                rationale = "source text directly covers most material query terms"
            elif overlap >= 0.25:
                support = SupportType.INDIRECT
                rationale = "source text only partially covers the requested claim"
            else:
                support = SupportType.UNSUPPORTED
                rationale = "source text does not support enough of the requested claim"
            event_date = None
        elif dates:
            support = SupportType.DIRECT
            event_date = dates[0]
            rationale = "event language and an explicit date occur in the same source sentence"
        elif mentioned and not facet.explicit_date_required:
            support = SupportType.DIRECT
            event_date = None
            rationale = "source directly states the requested event; the query does not require an exact event date"
        elif mentioned:
            support = SupportType.INDIRECT
            event_date = None
            rationale = "event is mentioned but the source excerpt does not state the exact date requested"
        else:
            support = SupportType.UNSUPPORTED
            event_date = None
            rationale = "requested event is not supported by the available source excerpt"

        if _comparative_claim(query) and legacy_authority == "primary":
            if support is SupportType.DIRECT:
                support = SupportType.INDIRECT
                rationale = "vendor source is self-asserted evidence for a comparative quality claim"

        result.append(ClaimEvidence(
            claim_id=facet.id,
            event=facet.event,
            source=url,
            support=support,
            event_date=event_date,
            publication_date=str(source.get("published_at") or "") or None,
            updated_date=str(source.get("updated_at") or "") or None,
            search_result_date=str(source.get("search_result_date") or "") or None,
            retrieved_date=str(source.get("retrieved_at") or source.get("created_at") or "") or None,
            authority_kind=authority_kind,
            authority_fit=max(0.0, min(1.0, authority_fit)),
            independence_key=independence,
            transport=transport,
            transport_confidence=transport_confidence,
            rationale=rationale,
        ))
    return tuple(result)


def _primary_kind(value: str) -> bool:
    return value.startswith("official_")


def evaluate_evidence(query: str, sources: list[dict] | tuple[dict, ...]) -> dict:
    """Aggregate claim support without equating source count with corroboration."""
    facets = decompose_query(query)
    by_claim: dict[str, list[ClaimEvidence]] = {facet.id: [] for facet in facets}
    for source in sources:
        for assessment in assess_source(query, source):
            by_claim.setdefault(assessment.claim_id, []).append(assessment)

    claims = []
    abstain = False
    conflict = False
    for facet in facets:
        rows = by_claim.get(facet.id, [])
        direct = [row for row in rows if row.support is SupportType.DIRECT]
        indirect = [row for row in rows if row.support is SupportType.INDIRECT]
        direct_dates = sorted({row.event_date for row in direct if row.event_date})
        independent = sorted({row.independence_key for row in direct if row.independence_key != "unknown"})
        fetched_primary = any(
            _primary_kind(row.authority_kind)
            and row.transport == "fetched_page"
            and row.authority_fit >= 0.8
            for row in direct
        )
        snippet_primary = any(
            _primary_kind(row.authority_kind)
            and row.transport == "search_snippet"
            and row.authority_fit >= 0.8
            for row in direct
        )

        if len(direct_dates) > 1:
            confidence = ConfidenceLabel.CONFLICTING
            conflict = True
        elif fetched_primary:
            confidence = ConfidenceLabel.CONFIRMED_PRIMARY
        elif len(independent) >= 2 and direct:
            if max((row.authority_fit * row.transport_confidence for row in direct), default=0.0) >= 0.7:
                confidence = ConfidenceLabel.STRONGLY_SUPPORTED
            else:
                confidence = ConfidenceLabel.CORROBORATED
        elif snippet_primary or direct:
            confidence = ConfidenceLabel.REPORTED
        else:
            confidence = ConfidenceLabel.INSUFFICIENT
            if facet.required:
                abstain = True

        primary_dates = {
            row.event_date
            for row in direct
            if (
                row.event_date
                and _primary_kind(row.authority_kind)
                and row.transport == "fetched_page"
                and row.authority_fit >= 0.8
            )
        }
        primary_anchor = (
            next(iter(primary_dates))
            if len(primary_dates) == 1
            else None
        )
        evidence_metadata = []
        for row in rows:
            item = row.metadata()
            if (
                primary_anchor
                and row.support is SupportType.DIRECT
                and row.event_date
                and row.event_date != primary_anchor
            ):
                item["support"] = SupportType.CONTRADICTING.value
                item["rationale"] = (
                    "explicit event date conflicts with fetched primary evidence "
                    "for the same subject/event facet"
                )
            evidence_metadata.append(item)

        claims.append({
            **facet.metadata(),
            "confidence": confidence.value,
            "event_dates": direct_dates,
            "direct_source_count": len(direct),
            "independent_source_count": len(independent),
            "independence_keys": independent,
            "indirect_source_count": len(indirect),
            "fetched_primary": fetched_primary,
            "snippet_primary": snippet_primary,
            "evidence": evidence_metadata,
        })

    if conflict:
        overall = ConfidenceLabel.CONFLICTING
    elif abstain:
        overall = ConfidenceLabel.INSUFFICIENT
    else:
        labels = {claim["confidence"] for claim in claims}
        if ConfidenceLabel.REPORTED.value in labels:
            overall = ConfidenceLabel.REPORTED
        elif ConfidenceLabel.CORROBORATED.value in labels:
            overall = ConfidenceLabel.CORROBORATED
        elif ConfidenceLabel.STRONGLY_SUPPORTED.value in labels:
            overall = ConfidenceLabel.STRONGLY_SUPPORTED
        else:
            overall = ConfidenceLabel.CONFIRMED_PRIMARY

    return {
        "outcome": overall.value,
        "abstain": abstain,
        "conflict": conflict,
        "claim_count": len(claims),
        "claims": claims,
    }


def annotate_source(query: str, source: dict) -> dict:
    """Return a copy enriched with deterministic authority and claim-support metadata."""
    row = dict(source)
    if _is_public_source(row):
        authority = classify_source_authority(
            str(row.get("source") or row.get("url") or ""),
            query,
            title=str(row.get("source_title") or row.get("title") or ""),
        )
        for key, value in authority.items():
            row.setdefault(key, value)

    assessments = assess_source(query, row)
    row["claim_support"] = [value.metadata() for value in assessments]
    support_weights = {
        SupportType.DIRECT: 1.0,
        SupportType.CORROBORATING: 0.85,
        SupportType.INDIRECT: 0.45,
        SupportType.CONTRADICTING: 0.0,
        SupportType.UNSUPPORTED: 0.0,
    }
    row["claim_support_score"] = max(
        (support_weights[value.support] for value in assessments),
        default=0.0,
    )
    transport, transport_confidence = _transport(row)
    row.setdefault("source_transport", transport)
    row.setdefault("transport_confidence", transport_confidence)
    if row.get("created_at") and not row.get("retrieved_at"):
        row["retrieved_at"] = row["created_at"]
    return row


def annotate_evidence_set(query: str, sources: list[dict] | tuple[dict, ...]) -> tuple[list[dict], dict]:
    annotated = [annotate_source(query, source) for source in sources]
    summary = evaluate_evidence(query, annotated)
    claim_status = {
        claim["id"]: claim["confidence"]
        for claim in summary["claims"]
    }
    for row in annotated:
        supports = []
        for assessment in row.get("claim_support", []):
            supports.append(
                f"{assessment['event']}={assessment['support']}"
                + (f"@{assessment['event_date']}" if assessment.get("event_date") else "")
                + f"[{claim_status.get(assessment['claim_id'], 'unknown')}]"
            )
        row["evidence_annotation"] = (
            "authority=" + str(row.get("source_authority_kind", "unknown"))
            + "; transport=" + str(row.get("source_transport", "unknown"))
            + f"({float(row.get('transport_confidence', 0.0)):.2f})"
            + ("; claims=" + ", ".join(supports) if supports else "")
        )[:1000]
    return annotated, summary


def facet_search_query(query: str, facet: QueryFacet) -> str:
    suffix = _EVENT_SEARCH_TERMS[facet.event]
    additions = " ".join(
        value for value in (facet.subject or "", suffix) if value
    )
    return (query.strip() + (" " + additions if additions else ""))[:600]


def missing_search_facets(query: str, rows: list[dict] | tuple[dict, ...]) -> tuple[QueryFacet, ...]:
    """Return requested temporal facets absent from current result titles/snippets."""
    facets = tuple(facet for facet in decompose_query(query) if facet.event is not TemporalEvent.GENERAL)
    if not facets:
        return ()
    combined = "\n".join(
        f"{row.get('title','')} {row.get('snippet','')}"
        for row in rows
    )
    missing = []
    for facet in facets:
        mentioned = _event_mentioned(
            combined,
            facet.event,
            subject=facet.subject,
        )
        tied_dates = event_dates(
            combined,
            facet.event,
            subject=facet.subject,
        )
        if (
            not mentioned
            or (
                facet.explicit_date_required
                and not tied_dates
            )
        ):
            missing.append(facet)
    return tuple(missing)
