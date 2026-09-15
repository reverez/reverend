from __future__ import annotations

import pytest

from reverend.runtime.policy import (
    InferencePolicy,
    PolicyViolation,
)
from reverend.runtime.providers import (
    OllamaProvider,
)


def test_policy_accepts_loopback():
    policy = InferencePolicy()

    assert (
        policy.validate_inference_endpoint(
            "http://127.0.0.1:11434"
        )
        == "http://127.0.0.1:11434"
    )


def test_policy_accepts_localhost():
    policy = InferencePolicy()

    assert (
        policy.validate_inference_endpoint(
            "http://localhost:11434"
        )
        == "http://localhost:11434"
    )


def test_policy_rejects_remote_endpoint():
    policy = InferencePolicy()

    with pytest.raises(
        PolicyViolation,
        match="LOCAL_ONLY",
    ):
        policy.validate_inference_endpoint(
            "https://api.example.com/v1"
        )


def test_policy_rejects_embedded_credentials():
    policy = InferencePolicy()

    with pytest.raises(
        PolicyViolation,
        match="Credentials",
    ):
        policy.validate_inference_endpoint(
            "http://user:secret@127.0.0.1:11434"
        )


def test_provider_parses_model_metadata(
    monkeypatch,
):
    provider = OllamaProvider(
        endpoint="http://127.0.0.1:11434"
    )

    monkeypatch.setattr(
        provider,
        "_request",
        lambda *args, **kwargs: {
            "models": [
                {
                    "name": "example:1b",
                    "digest": "abc123",
                    "size": 123456,
                    "modified_at":
                        "2026-09-13T00:00:00Z",
                    "details": {
                        "parameter_size": "1B",
                        "quantization_level": "Q4_K_M",
                    },
                }
            ]
        },
    )

    models = provider.list_models()

    assert len(models) == 1

    model = models[0]

    assert model.name == "example:1b"
    assert model.digest == "abc123"
    assert model.size_bytes == 123456
    assert (
        model.details["parameter_size"]
        == "1B"
    )


def test_generate_builds_local_request(
    monkeypatch,
):
    provider = OllamaProvider(
        endpoint="http://127.0.0.1:11434"
    )

    captured = {}

    def fake_request(
        path,
        payload=None,
        *,
        timeout=30,
    ):
        captured["path"] = path
        captured["payload"] = payload
        captured["timeout"] = timeout

        return {
            "response": "ok",
        }

    monkeypatch.setattr(
        provider,
        "_request",
        fake_request,
    )

    response = provider.generate(
        "example:1b",
        "hello",
        context=8192,
        predict=128,
        think=False,
    )

    assert response["response"] == "ok"

    assert captured["path"] == "/api/generate"

    assert (
        captured["payload"]["options"]["num_ctx"]
        == 8192
    )

    assert (
        captured["payload"]["options"][
            "num_predict"
        ]
        == 128
    )

    assert captured["payload"]["think"] is False



def test_provider_parses_loaded_model_residency(
    monkeypatch,
):
    provider = OllamaProvider(
        endpoint="http://127.0.0.1:11434"
    )

    monkeypatch.setattr(
        provider,
        "_request",
        lambda *args, **kwargs: {
            "models": [
                {
                    "name": "qwen3-coder:30b",
                    "size": 20436452636,
                    "size_vram": 6215654440,
                    "context_length": 16384,
                    "expires_at":
                        "2026-09-15T10:00:00+01:00",
                }
            ]
        },
    )

    loaded = provider.loaded_model_info()

    assert len(loaded) == 1
    assert loaded[0].name == "qwen3-coder:30b"
    assert loaded[0].size_bytes == 20436452636
    assert loaded[0].size_vram_bytes == 6215654440
    assert loaded[0].context_length == 16384
    assert (
        loaded[0].expires_at
        == "2026-09-15T10:00:00+01:00"
    )
    assert provider.loaded_models() == [
        "qwen3-coder:30b"
    ]


def test_generate_can_request_native_json_response_format(monkeypatch):
    provider=OllamaProvider(endpoint="http://127.0.0.1:11434")
    captured={}
    def fake_request(path,payload=None,*,timeout=30):
        captured["payload"]=payload
        return {"response":"{}"}
    monkeypatch.setattr(provider,"_request",fake_request)
    provider.generate(
        "deepseek-r1:8b",
        "return JSON",
        context=8192,
        predict=256,
        think=False,
        response_format="json",
    )
    assert captured["payload"]["format"]=="json"


def test_generate_rejects_invalid_response_format_before_request(monkeypatch):
    provider=OllamaProvider(endpoint="http://127.0.0.1:11434")
    monkeypatch.setattr(
        provider,
        "_request",
        lambda *args,**kwargs: (_ for _ in ()).throw(AssertionError("request should not run")),
    )
    with pytest.raises(ValueError,match="response_format"):
        provider.generate("model","prompt",response_format="xml")
