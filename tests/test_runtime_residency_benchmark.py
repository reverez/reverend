from __future__ import annotations

from types import SimpleNamespace

import pytest

from reverend.benchmarks.runtime_residency import (
    run_sequence,
)
from reverend.runtime import ModelRole


class _Provider:
    def __init__(self):
        self.after = []

    def loaded_model_info(self):
        return list(
            self.after
        )


class _Scheduler:
    def __init__(self):
        self.provider = _Provider()
        self.calls = []

    def generate(
        self,
        role,
        prompt,
        **kwargs,
    ):
        self.calls.append(
            (
                role,
                prompt,
                kwargs,
            )
        )
        warm = len(
            self.calls
        ) > 1
        self.provider.after = [
            SimpleNamespace(
                name="qwen3-coder:30b",
                size_bytes=20_000,
                size_vram_bytes=6_000,
                context_length=16384,
                expires_at="later",
            )
        ]

        return SimpleNamespace(
            model="qwen3-coder:30b",
            context=16384,
            exclusive_memory=True,
            provider_load_seconds=(
                0.005
                if warm
                else 2.0
            ),
            elapsed_seconds=2.1,
            queue_wait_seconds=0.0,
            setup_seconds=0.01,
            total_elapsed_seconds=2.11,
            response={
                "prompt_eval_count": 10,
                "eval_count": 1,
                "done_reason": "stop",
            },
            residency_policy="exclusive",
            residency_state_before=(
                "resident"
                if warm
                else "unloaded"
            ),
            residency_target_was_loaded=warm,
            residency_loaded_before=(
                ("qwen3-coder:30b",)
                if warm
                else ()
            ),
            residency_unloaded_models=(),
            residency_loaded_vram_bytes_before=(
                6_000
                if warm
                else None
            ),
            residency_target_vram_bytes_before=(
                6_000
                if warm
                else None
            ),
            residency_target_expires_at_before=(
                "later"
                if warm
                else None
            ),
        )


def test_runtime_residency_sequence_records_cold_then_warm():
    scheduler = _Scheduler()

    runs = run_sequence(
        scheduler,
        [
            ModelRole.STRONG_CODE,
            ModelRole.STRONG_CODE,
        ],
        predict=16,
    )

    assert [
        item["provider_load_seconds"]
        for item in runs
    ] == [
        2.0,
        0.005,
    ]
    assert runs[0][
        "residency_state_before"
    ] == "unloaded"
    assert runs[1][
        "residency_state_before"
    ] == "resident"
    assert runs[1][
        "loaded_after"
    ][0][
        "size_vram_bytes"
    ] == 6_000
    assert (
        "response"
        not in runs[0]
    )


def test_runtime_residency_sequence_applies_bounded_options():
    scheduler = _Scheduler()

    run_sequence(
        scheduler,
        [
            ModelRole.STRONG_CODE,
        ],
        predict=24,
        keep_alive="7m",
    )

    _, _, kwargs = (
        scheduler.calls[0]
    )
    assert kwargs["predict"] == 24
    assert kwargs["keep_alive"] == "7m"
    assert kwargs["temperature"] == 0.0


@pytest.mark.parametrize(
    ("predict", "delay"),
    [
        (0, 0.0),
        (16, -1.0),
    ],
)
def test_runtime_residency_sequence_rejects_invalid_bounds(
    predict,
    delay,
):
    with pytest.raises(
        ValueError
    ):
        run_sequence(
            _Scheduler(),
            [
                ModelRole.STRONG_CODE,
            ],
            predict=predict,
            delay_seconds=delay,
        )
