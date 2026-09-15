from __future__ import annotations

import json
from types import SimpleNamespace

from reverend.benchmarks.m12_validation import (
    _live_ok,
    _run_live_localizer,
    run_validation,
)
from reverend.runtime import (
    ModelRole,
)


class FakeScheduler:
    def generate(
        self,
        role,
        prompt,
        **kwargs,
    ):
        assert (
            role
            == ModelRole.STRONG_CODE
        )
        assert (
            "src/example/guard.py"
            in prompt
        )
        assert (
            "call:transition_task->enforce"
            in prompt
        )

        response = {
            "summary": (
                "Tighten transition validation "
                "through the existing helper."
            ),
            "files": [
                {
                    "path": (
                        "src/example/guard.py"
                    ),
                    "action": "modify",
                    "reason": (
                        "Contains the existing "
                        "transition validation helper."
                    ),
                },
                {
                    "path": (
                        "tests/test_tasks.py"
                    ),
                    "action": "modify",
                    "reason": (
                        "Add rejected-change coverage."
                    ),
                },
            ],
            "implementation_steps": [
                "Tighten helper validation.",
                "Add deterministic regression coverage.",
            ],
            "verification": [
                "python -m pytest -q"
            ],
            "risks": [],
            "needs_more_context": False,
        }
        payload = json.dumps(
            response
        )

        return SimpleNamespace(
            role=role,
            model="m12-fixture-model",
            digest="m12-fixture-digest",
            context=int(
                kwargs.get(
                    "context",
                    16384,
                )
            ),
            think=bool(
                kwargs.get(
                    "think",
                    False,
                )
            ),
            exclusive_memory=bool(
                kwargs.get(
                    "exclusive_memory",
                    True,
                )
            ),
            elapsed_seconds=0.001,
            response={
                "response": payload,
                "prompt_eval_count": max(
                    1,
                    len(prompt) // 4,
                ),
                "eval_count": max(
                    1,
                    len(payload) // 4,
                ),
            },
        )


def test_live_decision_requires_focused_grounded_localizer():
    accepted = {
        "context_dependency_focused": True,
        "context_test_focused": True,
        "needs_more_context": False,
        "model_calls": 1,
        "plan_grounded": True,
        "relevant_plan_path": True,
        "model": "qwen3-coder",
        "prompt_estimated_tokens": 4000,
    }

    assert (
        _live_ok(
            accepted
        )
        is True
    )

    rejected = dict(
        accepted
    )
    rejected[
        "context_dependency_focused"
    ] = False

    assert (
        _live_ok(
            rejected
        )
        is False
    )


def test_live_fixture_exercises_real_localizer_path():
    metadata = (
        _run_live_localizer(
            FakeScheduler
        )
    )

    assert (
        _live_ok(
            metadata
        )
        is True
    )
    assert (
        metadata[
            "model_calls"
        ]
        == 1
    )
    assert (
        "src/example/guard.py"
        in metadata[
            "context_paths"
        ]
    )
    assert (
        "tests/test_tasks.py"
        in metadata[
            "context_paths"
        ]
    )


def test_portable_validation_cannot_claim_live_acceptance(
    tmp_path,
):
    code, summary = (
        run_validation(
            report_root=tmp_path,
            skip_tests=True,
            skip_live_model=True,
        )
    )

    assert code == 2
    assert (
        summary[
            "portable_ok"
        ]
        is True
    )
    assert (
        summary[
            "overall_ok"
        ]
        is False
    )
    assert (
        summary[
            "portable_codeintel"
        ]["failed"]
        == 0
    )
    assert (
        summary[
            "portable_codeintel"
        ]["passed"]
        == 1
    )
    assert (
        summary[
            "live_localizer"
        ]["skipped"]
        is True
    )
    assert (
        tmp_path
        / summary[
            "summary_path"
        ].split("/")[-1]
    ).is_file()
