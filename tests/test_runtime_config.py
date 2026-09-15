import json

import pytest

from reverend.config import (
    read_runtime_config,
    runtime_value,
)


def test_missing_runtime_config_is_empty(tmp_path):
    assert read_runtime_config(
        tmp_path / "missing.json"
    ) == {}


def test_runtime_config_reads_json(tmp_path):
    path = tmp_path / "runtime.json"

    path.write_text(
        json.dumps(
            {
                "qdrant_url":
                    "http://127.0.0.1:6333",
                "qdrant_collection":
                    "local_knowledge_v3",
            }
        ),
        encoding="utf-8",
    )

    assert read_runtime_config(path) == {
        "qdrant_url":
            "http://127.0.0.1:6333",
        "qdrant_collection":
            "local_knowledge_v3",
    }


def test_runtime_config_requires_object(tmp_path):
    path = tmp_path / "runtime.json"

    path.write_text(
        '["not", "an", "object"]',
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeError,
        match="JSON object",
    ):
        read_runtime_config(path)


def test_environment_overrides_runtime_config(
    monkeypatch,
):
    config = {
        "qdrant_url":
            "http://127.0.0.1:6333",
    }

    monkeypatch.setenv(
        "QDRANT_URL",
        "http://override:6333",
    )

    assert runtime_value(
        "QDRANT_URL",
        "qdrant_url",
        config=config,
    ) == "http://override:6333"


def test_runtime_config_used_without_environment(
    monkeypatch,
):
    monkeypatch.delenv(
        "QDRANT_URL",
        raising=False,
    )

    assert runtime_value(
        "QDRANT_URL",
        "qdrant_url",
        config={
            "qdrant_url":
                "http://127.0.0.1:6333",
        },
    ) == "http://127.0.0.1:6333"


def test_reverend_runtime_config_env_has_priority(
    monkeypatch,
):
    monkeypatch.setenv(
        "REVEREND_RUNTIME_CONFIG",
        "/tmp/reverend-runtime.json",
    )

    monkeypatch.setenv(
        "AI_RUNTIME_CONFIG",
        "/tmp/legacy-runtime.json",
    )

    from reverend import config

    assert (
        str(config._runtime_config_path())
        == "/tmp/reverend-runtime.json"
    )


def test_legacy_runtime_config_env_is_supported(
    monkeypatch,
):
    monkeypatch.delenv(
        "REVEREND_RUNTIME_CONFIG",
        raising=False,
    )

    monkeypatch.setenv(
        "AI_RUNTIME_CONFIG",
        "/tmp/legacy-runtime.json",
    )

    from reverend import config

    assert (
        str(config._runtime_config_path())
        == "/tmp/legacy-runtime.json"
    )
