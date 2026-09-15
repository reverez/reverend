"""Deterministic tests must never depend on user runtime databases or live search config."""
import os
import tempfile

import pytest


if 'AI_DATA_ROOT' not in os.environ:
    os.environ['AI_DATA_ROOT'] = tempfile.mkdtemp(prefix='reverend-tests-')


@pytest.fixture(autouse=True)
def isolate_live_web_search(monkeypatch):
    """Unit tests opt into provider configuration explicitly per test."""
    monkeypatch.setenv('REVEREND_WEB_SEARCH_PROVIDER','off')
    for name in (
        'REVEREND_WEB_SEARCH_API_KEY',
        'BRAVE_SEARCH_API_KEY',
        'REVEREND_WEB_SEARCH_ENDPOINT',
        'REVEREND_WEB_SEARCH_COUNTRY',
        'REVEREND_WEB_SEARCH_LANGUAGE',
    ):
        monkeypatch.delenv(name,raising=False)
