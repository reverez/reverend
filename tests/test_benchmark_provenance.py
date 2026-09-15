from __future__ import annotations

from types import SimpleNamespace

from reverend.benchmarks.provenance import collect_regression_evidence


def test_regression_evidence_carries_revision_environment_models_and_trace(tmp_path):
    result = SimpleNamespace(
        metrics={
            "trace_id": "trace-123",
            "model_runs": [
                {
                    "role": "fast_general",
                    "model": "qwen3.5:4b",
                    "digest": "abc",
                    "context": 8192,
                    "prompt_tokens": 100,
                },
                {
                    "role": "fast_general",
                    "model": "qwen3.5:4b",
                    "digest": "abc",
                    "context": 8192,
                },
            ],
        }
    )

    evidence = collect_regression_evidence(
        results=(result,),
        code_root=tmp_path,
        revision="commit-abc",
        case_sha256="case-sha",
        case_count=1,
    )

    assert evidence["schema_version"] == 1
    assert evidence["implementation"]["code_revision"] == "commit-abc"
    assert evidence["benchmark"] == {
        "case_count": 1,
        "case_sha256": "case-sha",
    }
    assert evidence["environment"]["python_version"]
    assert evidence["runtime"]["trace_ids"] == ["trace-123"]
    assert evidence["runtime"]["models"] == [
        {
            "role": "fast_general",
            "model": "qwen3.5:4b",
            "digest": "abc",
            "context": 8192,
        }
    ]


def test_regression_evidence_excludes_model_payload_fields(tmp_path):
    result = SimpleNamespace(
        metrics={
            "model_runs": [
                {
                    "role": "router",
                    "model": "fixture",
                    "prompt": "private prompt payload",
                    "response": "private response payload",
                }
            ]
        }
    )

    evidence = collect_regression_evidence(
        results=(result,),
        code_root=tmp_path,
        revision=None,
        case_sha256="sha",
        case_count=1,
    )

    assert evidence["runtime"]["models"] == [
        {"role": "router", "model": "fixture"}
    ]
    serialized = str(evidence)
    assert "private prompt payload" not in serialized
    assert "private response payload" not in serialized
