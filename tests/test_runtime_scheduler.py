from __future__ import annotations

import multiprocessing
import time
from pathlib import Path

import pytest

from reverend.runtime.models import (
    ModelRegistry,
    ModelRole,
)
from reverend.runtime.providers import (
    ModelInfo,
)
from reverend.runtime.scheduler import (
    ModelScheduler,
    SchedulerTimeout,
)


class FakeProvider:
    def __init__(self):
        self.generated = []
        self.streamed = []
        self.unloaded = []
        self.stream_chunks = None
        self.loaded = [
            "bge-m3:latest",
        ]

    def list_models(self):
        return [
            ModelInfo(
                name="qwen3.5:4b",
                digest="fast-digest",
                size_bytes=1,
                modified_at=None,
                details={},
            ),
            ModelInfo(
                name="qwen2.5-coder:7b",
                digest="fast-code-digest",
                size_bytes=1,
                modified_at=None,
                details={},
            ),
            ModelInfo(
                name="qwen3-coder:30b",
                digest="strong-digest",
                size_bytes=1,
                modified_at=None,
                details={},
            ),
            ModelInfo(
                name="deepseek-r1:8b",
                digest="reason-digest",
                size_bytes=1,
                modified_at=None,
                details={},
            ),
            ModelInfo(
                name="bge-m3:latest",
                digest="embed-digest",
                size_bytes=1,
                modified_at=None,
                details={},
            ),
        ]

    def loaded_models(self):
        return list(self.loaded)

    def unload(self, model):
        self.unloaded.append(model)

        if model in self.loaded:
            self.loaded.remove(model)

    def generate(
        self,
        model,
        prompt,
        **kwargs,
    ):
        was_loaded = (
            model in self.loaded
        )
        self.generated.append(
            (
                model,
                prompt,
                kwargs,
            )
        )

        if not was_loaded:
            self.loaded.append(
                model
            )

        return {
            "response": "ok",
            "load_duration": (
                5_000_000
                if was_loaded
                else 2_000_000_000
            ),
        }

    def stream(
        self,
        model,
        prompt,
        **kwargs,
    ):
        was_loaded = (
            model in self.loaded
        )
        self.streamed.append(
            (
                model,
                prompt,
                kwargs,
            )
        )

        if not was_loaded:
            self.loaded.append(
                model
            )

        if self.stream_chunks is not None:
            yield from self.stream_chunks
            return

        yield {
            "response": "ok",
            "done": True,
            "done_reason": "stop",
            "prompt_eval_count": 10,
            "eval_count": 2,
            "load_duration": (
                5_000_000
                if was_loaded
                else 2_000_000_000
            ),
        }


def test_scheduler_generates_by_role(
    tmp_path,
):
    provider = FakeProvider()

    registry = ModelRegistry(
        provider
    )

    scheduler = ModelScheduler(
        provider,
        registry,
        lock_path=tmp_path / "model.lock",
    )

    result = scheduler.generate(
        ModelRole.STRONG_CODE,
        "implement feature",
        predict=64,
    )

    assert (
        result.model
        == "qwen3-coder:30b"
    )

    assert (
        result.digest
        == "strong-digest"
    )

    assert result.exclusive_memory is True
    assert result.residency_policy == "exclusive"
    assert result.residency_unloaded_models == (
        "bge-m3:latest",
    )

    assert (
        result.response["response"]
        == "ok"
    )
    assert result.queue_wait_seconds >= 0
    assert result.setup_seconds >= 0
    assert result.elapsed_seconds >= 0
    assert (
        result.total_elapsed_seconds
        >= result.elapsed_seconds
    )
    assert (
        result.total_elapsed_seconds
        >= (
            result.queue_wait_seconds
            + result.setup_seconds
        )
    )


def test_scheduler_can_unload_other_models(
    tmp_path,
):
    provider = FakeProvider()

    scheduler = ModelScheduler(
        provider,
        ModelRegistry(provider),
        lock_path=tmp_path / "model.lock",
    )

    unloaded = scheduler.unload_others(
        "qwen3-coder:30b"
    )

    assert unloaded == [
        "bge-m3:latest",
    ]


def _hold_lock(
    lock_path: str,
    ready,
):
    provider = FakeProvider()

    scheduler = ModelScheduler(
        provider,
        ModelRegistry(provider),
        lock_path=Path(lock_path),
    )

    with scheduler.exclusive(
        timeout=2.0
    ):
        ready.set()
        time.sleep(0.5)


def test_scheduler_lock_times_out(
    tmp_path,
):
    lock_path = tmp_path / "model.lock"

    ready = multiprocessing.Event()

    process = multiprocessing.Process(
        target=_hold_lock,
        args=(
            str(lock_path),
            ready,
        ),
    )

    process.start()

    try:
        assert ready.wait(
            timeout=2.0
        )

        provider = FakeProvider()

        scheduler = ModelScheduler(
            provider,
            ModelRegistry(provider),
            lock_path=lock_path,
        )

        with pytest.raises(
            SchedulerTimeout
        ):
            with scheduler.exclusive(
                timeout=0.1,
                poll_interval=0.02,
            ):
                pass

    finally:
        process.join(
            timeout=2.0
        )

        if process.is_alive():
            process.terminate()
            process.join()



def test_scheduler_stream_honors_output_token_budget(
    tmp_path,
):
    provider = FakeProvider()
    scheduler = ModelScheduler(
        provider,
        ModelRegistry(provider),
        lock_path=(
            tmp_path
            / "model.lock"
        ),
    )

    chunks = list(
        scheduler.stream(
            ModelRole.FAST_GENERAL,
            "answer briefly",
            predict=384,
        )
    )

    assert chunks[-1][
        "done"
    ] is True
    assert len(
        provider.streamed
    ) == 1
    model, prompt, kwargs = (
        provider.streamed[0]
    )
    assert model == "qwen3.5:4b"
    assert prompt == "answer briefly"
    assert kwargs[
        "predict"
    ] == 384



def test_scheduler_stream_discards_raw_thinking_and_tracks_safe_metadata(
    tmp_path,
):
    provider = FakeProvider()
    provider.stream_chunks = [
        {
            "thinking": "private chain of thought",
            "response": "",
            "done": False,
        },
        {
            "response": "partial answer",
            "done": True,
            "done_reason": "length",
            "prompt_eval_count": 12,
            "eval_count": 384,
        },
    ]
    scheduler = ModelScheduler(
        provider,
        ModelRegistry(provider),
        lock_path=tmp_path / "model.lock",
    )

    chunks = list(
        scheduler.stream(
            ModelRole.DEEP_REASON,
            "reason carefully",
            predict=384,
        )
    )
    final = chunks[-1]

    assert all("thinking" not in chunk for chunk in chunks)
    assert "private chain of thought" not in repr(chunks)
    assert final["done_reason"] == "length"
    assert final["completion_reason"] == "output_limit_reached"
    assert final["hidden_reasoning_present"] is True
    assert final["thinking_activity_count"] == 1
    assert final["answer_started"] is True
    assert final["response_chars"] == len("partial answer")
    assert final["output_budget"] == 384


def test_scheduler_detects_reasoning_budget_exhausted_before_answer(
    tmp_path,
):
    provider = FakeProvider()
    provider.stream_chunks = [
        {
            "thinking": "private chain of thought",
            "response": "",
            "done": False,
        },
        {
            "response": "",
            "done": True,
            "done_reason": "length",
            "prompt_eval_count": 20,
            "eval_count": 256,
        },
    ]
    scheduler = ModelScheduler(
        provider,
        ModelRegistry(provider),
        lock_path=tmp_path / "model.lock",
    )

    final = list(
        scheduler.stream(
            ModelRole.DEEP_REASON,
            "prove it",
            predict=256,
        )
    )[-1]

    assert final["completion_reason"] == (
        "reasoning_budget_exhausted_before_answer"
    )
    assert final["answer_started"] is False
    assert final["hidden_reasoning_present"] is True
    assert final["thinking_activity_count"] == 1
    assert "thinking" not in final


def test_scheduler_marks_natural_stop_complete(
    tmp_path,
):
    provider = FakeProvider()
    scheduler = ModelScheduler(
        provider,
        ModelRegistry(provider),
        lock_path=tmp_path / "model.lock",
    )

    final = list(
        scheduler.stream(
            ModelRole.FAST_GENERAL,
            "answer",
            predict=128,
        )
    )[-1]

    assert final["done_reason"] == "stop"
    assert final["completion_reason"] == "complete"
    assert final["answer_started"] is True
    assert final["hidden_reasoning_present"] is False



def test_deep_reason_unloads_competing_models_before_stream(
    tmp_path,
):
    provider=FakeProvider()
    provider.loaded=[
        'qwen3.5:4b',
        'deepseek-r1:8b',
        'bge-m3:latest',
    ]
    scheduler=ModelScheduler(
        provider,
        ModelRegistry(provider),
        lock_path=tmp_path/'model.lock',
    )

    final=list(
        scheduler.stream(
            ModelRole.DEEP_REASON,
            'reason',
            predict=128,
        )
    )[-1]

    assert provider.unloaded==[
        'qwen3.5:4b',
        'bge-m3:latest',
    ]
    assert final['exclusive_memory'] is True
    assert final['residency_policy']=='exclusive'
    assert final['residency_unload_count']==2
    assert final['residency_unloaded_models']==[
        'qwen3.5:4b',
        'bge-m3:latest',
    ]
    assert final['context']==8192


def test_fast_general_keeps_shared_residency(
    tmp_path,
):
    provider=FakeProvider()
    provider.loaded=[
        'qwen3.5:4b',
        'bge-m3:latest',
    ]
    scheduler=ModelScheduler(
        provider,
        ModelRegistry(provider),
        lock_path=tmp_path/'model.lock',
    )

    final=list(
        scheduler.stream(
            ModelRole.FAST_GENERAL,
            'answer',
            predict=128,
        )
    )[-1]

    assert provider.unloaded==[]
    assert final['exclusive_memory'] is False
    assert final['residency_policy']=='shared'
    assert final['residency_unload_count']==0
    assert final['residency_unloaded_models']==[]



def test_repeated_strong_model_reports_cold_then_resident_reuse(
    tmp_path,
):
    provider = FakeProvider()
    provider.loaded = []
    scheduler = ModelScheduler(
        provider,
        ModelRegistry(provider),
        lock_path=tmp_path / "model.lock",
    )

    cold = scheduler.generate(
        ModelRole.STRONG_CODE,
        "first",
        predict=16,
    )
    warm = scheduler.generate(
        ModelRole.STRONG_CODE,
        "second",
        predict=16,
    )

    assert cold.residency_state_before == "unloaded"
    assert cold.residency_target_was_loaded is False
    assert cold.residency_loaded_before == ()
    assert cold.provider_load_seconds == 2.0

    assert warm.residency_state_before == "resident"
    assert warm.residency_target_was_loaded is True
    assert warm.residency_loaded_before == (
        "qwen3-coder:30b",
    )
    assert warm.provider_load_seconds == 0.005
    assert provider.unloaded == []


def test_shared_model_does_not_add_residency_probe(
    tmp_path,
):
    provider = FakeProvider()
    provider.loaded = [
        "qwen3.5:4b",
        "bge-m3:latest",
    ]
    calls = {"loaded": 0}
    original = provider.loaded_models

    def counted_loaded_models():
        calls["loaded"] += 1
        return original()

    provider.loaded_models = counted_loaded_models
    scheduler = ModelScheduler(
        provider,
        ModelRegistry(provider),
        lock_path=tmp_path / "model.lock",
    )

    result = scheduler.generate(
        ModelRole.FAST_GENERAL,
        "answer",
        predict=16,
    )

    assert calls["loaded"] == 0
    assert result.residency_state_before == "unknown"
    assert result.residency_target_was_loaded is None



def test_generation_failure_releases_scheduler_lock(
    tmp_path,
):
    class FlakyProvider(FakeProvider):
        def __init__(self):
            super().__init__()
            self.fail_generation = True
            self.loaded = [
                "qwen3-coder:30b",
            ]

        def generate(
            self,
            model,
            prompt,
            **kwargs,
        ):
            if self.fail_generation:
                raise RuntimeError(
                    "generation failed"
                )

            return super().generate(
                model,
                prompt,
                **kwargs,
            )

    provider = FlakyProvider()
    scheduler = ModelScheduler(
        provider,
        ModelRegistry(provider),
        lock_path=tmp_path / "model.lock",
    )

    with pytest.raises(
        RuntimeError,
        match="generation failed",
    ):
        scheduler.generate(
            ModelRole.STRONG_CODE,
            "first",
            predict=16,
        )

    provider.fail_generation = False

    recovered = scheduler.generate(
        ModelRole.STRONG_CODE,
        "second",
        predict=16,
        lock_timeout=0.1,
    )

    assert (
        recovered.response["response"]
        == "ok"
    )


def test_unload_failure_is_explicit_and_next_request_recovers(
    tmp_path,
):
    class FlakyUnloadProvider(FakeProvider):
        def __init__(self):
            super().__init__()
            self.fail_unload = True
            self.loaded = [
                "bge-m3:latest",
            ]

        def unload(
            self,
            model,
        ):
            if self.fail_unload:
                raise RuntimeError(
                    "unload failed"
                )

            return super().unload(
                model
            )

    provider = FlakyUnloadProvider()
    scheduler = ModelScheduler(
        provider,
        ModelRegistry(provider),
        lock_path=tmp_path / "model.lock",
    )

    with pytest.raises(
        RuntimeError,
        match="unload failed",
    ):
        scheduler.generate(
            ModelRole.STRONG_CODE,
            "first",
            predict=16,
        )

    assert provider.generated == []

    provider.fail_unload = False

    recovered = scheduler.generate(
        ModelRole.STRONG_CODE,
        "second",
        predict=16,
        lock_timeout=0.1,
    )

    assert (
        recovered.response["response"]
        == "ok"
    )
    assert provider.unloaded == [
        "bge-m3:latest",
    ]


def test_scheduler_passes_structured_response_format_to_provider(tmp_path):
    provider=FakeProvider()
    scheduler=ModelScheduler(
        provider,
        ModelRegistry(provider),
        lock_path=tmp_path/"model.lock",
    )
    scheduler.generate(
        ModelRole.DEEP_REASON,
        "structured",
        response_format="json",
    )
    assert provider.generated[-1][2]["response_format"]=="json"
