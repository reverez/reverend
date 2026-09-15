from pathlib import Path

import yaml

from reverend.research.search_worker import FRESHNESS_SEARX


ROOT=Path(__file__).resolve().parents[1]


def test_local_searxng_profile_enables_json_and_stays_non_public():
    settings=yaml.safe_load(
        (ROOT/"deploy"/"searxng"/"settings.yml").read_text(encoding="utf-8")
    )
    assert settings["use_default_settings"] is True
    assert "json" in settings["search"]["formats"]
    assert settings["server"]["public_instance"] is False
    assert settings["server"]["image_proxy"] is False


def test_searxng_helper_is_loopback_only_and_api_key_free():
    script=(ROOT/"scripts"/"reverend-searxng").read_text(encoding="utf-8")
    assert '127.0.0.1:${PORT}:8080' in script
    assert 'REVEREND_WEB_SEARCH_PROVIDER=searxng' in script
    assert 'REVEREND_WEB_SEARCH_ENDPOINT=$ENDPOINT' in script
    assert 'REVEREND_WEB_SEARCH_API_KEY' not in script
    assert 'ghcr.io/searxng/searxng:2026.9.13-96479fff6' in script


def test_searxng_week_uses_supported_provider_window():
    assert FRESHNESS_SEARX["day"]=="day"
    assert FRESHNESS_SEARX["week"]=="month"
    assert FRESHNESS_SEARX["month"]=="month"
    assert FRESHNESS_SEARX["year"]=="year"
