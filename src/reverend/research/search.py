"""Configuration contract for bounded query-to-web search."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from reverend.config import runtime_value


BRAVE_SEARCH_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"


class WebSearchError(RuntimeError):
    """Typed public-search failure that never contains credentials."""

    code = "web_search_failed"


class WebSearchUnavailable(WebSearchError):
    code = "network_search_unavailable"


class WebSearchAuthenticationError(WebSearchError):
    code = "network_search_auth_failed"


class WebSearchRateLimitError(WebSearchError):
    code = "web_search_rate_limited"


class WebSearchPlanError(WebSearchError):
    code = "web_search_plan_unavailable"


class WebSearchRequestRejected(WebSearchError):
    code = "web_search_request_rejected"


@dataclass(frozen=True)
class WebSearchConfig:
    provider: str
    endpoint: str
    api_key: str | None = field(default=None, repr=False)
    country: str = "GB"
    language: str = "en"

    def __post_init__(self) -> None:
        provider=self.provider.strip().lower()
        if provider not in {"brave","searxng"}:
            raise WebSearchUnavailable("Unsupported web-search provider")
        endpoint=self.endpoint.strip()
        parsed=urlsplit(endpoint)
        if (
            not endpoint
            or parsed.username
            or parsed.password
            or parsed.fragment
            or not parsed.hostname
        ):
            raise WebSearchUnavailable("Invalid web-search endpoint")
        if provider=="brave":
            if endpoint.rstrip("/") != BRAVE_SEARCH_ENDPOINT:
                raise WebSearchUnavailable(
                    "Brave credentials may only be sent to the official Brave Search endpoint"
                )
            if not self.api_key:
                raise WebSearchUnavailable(
                    "Brave Search is configured but REVEREND_WEB_SEARCH_API_KEY is missing"
                )
        if provider=="searxng" and parsed.scheme not in {"http","https"}:
            raise WebSearchUnavailable("SearXNG endpoint must use HTTP or HTTPS")
        if not re.fullmatch(r"[A-Za-z]{2}",self.country):
            raise WebSearchUnavailable("Web-search country must be a two-letter code")
        if not re.fullmatch(r"[A-Za-z]{2,8}(?:-[A-Za-z0-9]{2,8})?",self.language):
            raise WebSearchUnavailable("Invalid web-search language")
        object.__setattr__(self,"provider",provider)
        object.__setattr__(self,"endpoint",endpoint.rstrip("/"))
        object.__setattr__(self,"country",self.country.upper())
        object.__setattr__(self,"language",self.language.lower())

    def safe_metadata(self) -> dict:
        parsed=urlsplit(self.endpoint)
        port=parsed.port
        authority=parsed.hostname or ""
        if port is not None:
            authority+=f":{port}"
        return {
            "provider":self.provider,
            "endpoint_host":authority,
            "credentialed":bool(self.api_key),
            "country":self.country,
            "language":self.language,
        }


def configured_web_search() -> WebSearchConfig | None:
    provider=str(
        runtime_value(
            "REVEREND_WEB_SEARCH_PROVIDER",
            "web_search_provider",
            "",
        )
        or ""
    ).strip().lower()
    if provider in {"","off","none","disabled"}:
        return None

    endpoint=str(
        runtime_value(
            "REVEREND_WEB_SEARCH_ENDPOINT",
            "web_search_endpoint",
            BRAVE_SEARCH_ENDPOINT if provider=="brave" else "",
        )
        or ""
    ).strip()
    country=str(
        runtime_value(
            "REVEREND_WEB_SEARCH_COUNTRY",
            "web_search_country",
            "GB",
        )
        or "GB"
    )
    language=str(
        runtime_value(
            "REVEREND_WEB_SEARCH_LANGUAGE",
            "web_search_language",
            "en",
        )
        or "en"
    )
    api_key=(
        os.environ.get("REVEREND_WEB_SEARCH_API_KEY")
        or (
            os.environ.get("BRAVE_SEARCH_API_KEY")
            if provider=="brave"
            else None
        )
    )

    if provider=="searxng" and not endpoint:
        raise WebSearchUnavailable(
            "SearXNG is configured but REVEREND_WEB_SEARCH_ENDPOINT is missing"
        )

    return WebSearchConfig(
        provider=provider,
        endpoint=endpoint,
        api_key=api_key,
        country=country,
        language=language,
    )



from .quality import (
    classify_source_authority,
    preferred_primary_domains,
)


def primary_source_search_query(text: str) -> str | None:
    """Build one bounded first-party search query when the vendor is known."""

    domains = preferred_primary_domains(text)
    if not domains:
        return None

    return bounded_search_query(
        f"site:{domains[0]} {text}"
    )


def source_authority(url: str, query: str, *, title: str = "") -> dict:
    """Compatibility wrapper for query-relative research authority metadata."""

    return classify_source_authority(
        url,
        query,
        title=title,
    )


def bounded_search_query(text: str) -> str:
    """Fit a user request into provider query limits without model rewriting."""
    if not isinstance(text,str):
        raise ValueError("Search query source must be text")
    words=text.strip().split()
    if not words:
        raise ValueError("Search query must not be empty")
    return " ".join(words[:75])[:600].rstrip()
