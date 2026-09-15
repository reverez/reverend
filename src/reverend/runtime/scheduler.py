"""Serialized heavyweight local-model execution."""

from __future__ import annotations

import fcntl
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from reverend.config import DATA_ROOT

from .models import (
    ModelRegistry,
    ModelRole,
    ResolvedModel,
)
from .completion import CompletionSnapshot, classify_completion
from .providers import (
    LoadedModelInfo,
    ModelProvider,
)


class SchedulerError(RuntimeError):
    """Base model-scheduler error."""


class SchedulerCancelled(SchedulerError):
    """Cancelled while waiting for model capacity."""


class SchedulerTimeout(SchedulerError):
    """Raised when another inference run holds the model lock."""


@dataclass(frozen=True)
class ModelRunResult:
    role: ModelRole
    model: str
    digest: str | None
    context: int
    think: bool
    exclusive_memory: bool
    elapsed_seconds: float
    response: dict[str, Any]
    queue_wait_seconds: float = 0.0
    setup_seconds: float = 0.0
    total_elapsed_seconds: float = 0.0
    residency_policy: str = "shared"
    residency_unloaded_models: tuple[str, ...] = ()
    provider_load_seconds: float | None = None
    residency_state_before: str = "unknown"
    residency_target_was_loaded: bool | None = None
    residency_loaded_before: tuple[str, ...] = ()
    residency_loaded_vram_bytes_before: int | None = None
    residency_target_vram_bytes_before: int | None = None
    residency_target_expires_at_before: str | None = None


@dataclass(frozen=True)
class _ResidencyPreparation:
    loaded_before: tuple[str, ...] = ()
    target_was_loaded: bool | None = None
    unloaded_models: tuple[str, ...] = ()
    loaded_vram_bytes_before: int | None = None
    target_vram_bytes_before: int | None = None
    target_expires_at_before: str | None = None

    @property
    def state_before(self) -> str:
        if self.target_was_loaded is True:
            return "resident"
        if self.target_was_loaded is False:
            return "unloaded"
        return "unknown"


def _provider_duration_seconds(
    value: Any,
) -> float | None:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or value < 0
    ):
        return None

    return round(
        float(value) / 1_000_000_000,
        6,
    )


class ModelScheduler:
    """Serialize expensive local inference across processes.

    The lock protects development-engine model scheduling. Existing
    legacy commands can be migrated to this scheduler incrementally.
    """

    def __init__(
        self,
        provider: ModelProvider,
        registry: ModelRegistry,
        *,
        lock_path: Path | None = None,
    ) -> None:
        self.provider = provider
        self.registry = registry

        self.lock_path = (
            lock_path
            if lock_path is not None
            else DATA_ROOT
            / "runtime"
            / "model.lock"
        )

    @contextmanager
    def exclusive(
        self,
        *,
        timeout: float = 300.0,
        poll_interval: float = 0.1,
        cancel=None,
    ) -> Iterator[None]:
        self.lock_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with self.lock_path.open(
            "a+",
            encoding="utf-8",
        ) as handle:
            deadline = (
                time.monotonic()
                + timeout
            )

            while True:
                if cancel is not None and cancel.is_set():
                    raise SchedulerCancelled("Model request cancelled")
                try:
                    fcntl.flock(
                        handle.fileno(),
                        fcntl.LOCK_EX
                        | fcntl.LOCK_NB,
                    )
                    break

                except BlockingIOError:
                    if (
                        time.monotonic()
                        >= deadline
                    ):
                        raise SchedulerTimeout(
                            "Timed out waiting for "
                            "the local model scheduler."
                        )

                    time.sleep(
                        poll_interval
                    )

            try:
                yield
            finally:
                fcntl.flock(
                    handle.fileno(),
                    fcntl.LOCK_UN,
                )

    def _loaded_model_info(
        self,
    ) -> tuple[LoadedModelInfo, ...]:
        detailed = getattr(
            self.provider,
            "loaded_model_info",
            None,
        )

        if callable(detailed):
            return tuple(
                detailed()
            )

        return tuple(
            LoadedModelInfo(
                name=name,
                size_bytes=None,
                size_vram_bytes=None,
                context_length=None,
                expires_at=None,
            )
            for name in self.provider.loaded_models()
        )

    def _prepare_exclusive_residency(
        self,
        target_model: str,
    ) -> _ResidencyPreparation:
        loaded_info = self._loaded_model_info()
        loaded_before = tuple(
            item.name
            for item in loaded_info
        )
        target_info = next(
            (
                item
                for item in loaded_info
                if item.name == target_model
            ),
            None,
        )

        known_vram = [
            item.size_vram_bytes
            for item in loaded_info
        ]
        loaded_vram_bytes_before = (
            sum(
                int(value)
                for value in known_vram
            )
            if (
                known_vram
                and all(
                    value is not None
                    for value in known_vram
                )
            )
            else None
        )

        unloaded: list[str] = []

        for item in loaded_info:
            if item.name == target_model:
                continue

            self.provider.unload(
                item.name
            )
            unloaded.append(
                item.name
            )

        return _ResidencyPreparation(
            loaded_before=loaded_before,
            target_was_loaded=(
                target_info is not None
            ),
            unloaded_models=tuple(
                unloaded
            ),
            loaded_vram_bytes_before=(
                loaded_vram_bytes_before
            ),
            target_vram_bytes_before=(
                None
                if target_info is None
                else target_info.size_vram_bytes
            ),
            target_expires_at_before=(
                None
                if target_info is None
                else target_info.expires_at
            ),
        )

    def unload_others(
        self,
        target_model: str,
    ) -> list[str]:
        return list(
            self._prepare_exclusive_residency(
                target_model
            ).unloaded_models
        )

    def unload_role(
        self,
        role: ModelRole,
    ) -> None:
        resolved = self.registry.resolve(
            role
        )

        self.provider.unload(
            resolved.spec.model
        )

    def generate(
        self,
        role: ModelRole,
        prompt: str,
        *,
        context: int | None = None,
        predict: int | None = None,
        temperature: float = 0.0,
        think: bool | None = None,
        keep_alive: str | int | None = None,
        exclusive_memory: bool | None = None,
        response_format: str | dict | None = None,
        lock_timeout: float = 300.0,
        request_timeout: int = 1800,
    ) -> ModelRunResult:
        requested_at = time.monotonic()

        with self.exclusive(
            timeout=lock_timeout
        ):
            acquired_at = time.monotonic()

            resolved: ResolvedModel = (
                self.registry.resolve(role)
            )

            spec = resolved.spec

            actual_exclusive = (
                exclusive_memory
                if exclusive_memory is not None
                else spec.exclusive_memory
            )

            residency = _ResidencyPreparation()
            if actual_exclusive:
                residency = (
                    self._prepare_exclusive_residency(
                        spec.model
                    )
                )

            unloaded_models = (
                residency.unloaded_models
            )

            actual_context = (
                context
                if context is not None
                else spec.context
            )

            actual_think = (
                think
                if think is not None
                else spec.think
            )

            actual_keep_alive = (
                keep_alive
                if keep_alive is not None
                else spec.keep_alive
            )

            provider_started = time.monotonic()

            response = self.provider.generate(
                spec.model,
                prompt,
                context=actual_context,
                predict=predict,
                temperature=temperature,
                think=actual_think,
                keep_alive=actual_keep_alive,
                response_format=response_format,
                timeout=request_timeout,
            )

            finished_at = time.monotonic()

            provider_elapsed = (
                finished_at
                - provider_started
            )
            queue_wait = (
                acquired_at
                - requested_at
            )
            setup_elapsed = (
                provider_started
                - acquired_at
            )
            total_elapsed = (
                finished_at
                - requested_at
            )

            return ModelRunResult(
                role=role,
                model=spec.model,
                digest=resolved.digest,
                context=actual_context,
                think=actual_think,
                exclusive_memory=actual_exclusive,
                elapsed_seconds=round(
                    provider_elapsed,
                    6,
                ),
                response=response,
                queue_wait_seconds=round(
                    queue_wait,
                    6,
                ),
                setup_seconds=round(
                    setup_elapsed,
                    6,
                ),
                total_elapsed_seconds=round(
                    total_elapsed,
                    6,
                ),
                residency_policy=(
                    "exclusive"
                    if actual_exclusive
                    else "shared"
                ),
                residency_unloaded_models=(
                    unloaded_models
                ),
                provider_load_seconds=(
                    _provider_duration_seconds(
                        response.get(
                            "load_duration"
                        )
                    )
                ),
                residency_state_before=(
                    residency.state_before
                ),
                residency_target_was_loaded=(
                    residency.target_was_loaded
                ),
                residency_loaded_before=(
                    residency.loaded_before
                ),
                residency_loaded_vram_bytes_before=(
                    residency.loaded_vram_bytes_before
                ),
                residency_target_vram_bytes_before=(
                    residency.target_vram_bytes_before
                ),
                residency_target_expires_at_before=(
                    residency.target_expires_at_before
                ),
            )

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embedding requests share the same cross-process memory boundary."""
        with self.exclusive():
            resolved = self.registry.resolve(ModelRole.EMBED)
            if resolved.spec.exclusive_memory:
                self.unload_others(resolved.spec.model)
            result = self.provider.embed(resolved.spec.model, texts)
            vectors = result.get('embeddings', [])
            if len(vectors) != len(texts):
                raise SchedulerError('Embedding count mismatch')
            return vectors

    def stream(
        self,
        role: ModelRole,
        prompt: str,
        *,
        cancel=None,
        predict: int | None = None,
    ):
        """Stream through the existing scheduler; never publish thinking fields."""
        requested_at = time.monotonic()

        with self.exclusive(cancel=cancel):
            acquired_at = time.monotonic()

            if cancel is not None and cancel.is_set():
                return

            resolved = self.registry.resolve(role)
            spec = resolved.spec

            residency = _ResidencyPreparation()
            if spec.exclusive_memory:
                residency = (
                    self._prepare_exclusive_residency(
                        spec.model
                    )
                )

            unloaded_models = (
                residency.unloaded_models
            )

            provider_started = time.monotonic()
            queue_wait = (
                acquired_at
                - requested_at
            )
            setup_elapsed = (
                provider_started
                - acquired_at
            )

            actual_predict = (
                1536
                if predict is None
                else predict
            )

            response_chars = 0
            answer_started = False
            hidden_reasoning_present = False
            thinking_activity_count = 0

            for chunk in self.provider.stream(
                spec.model,
                prompt,
                cancel=cancel,
                context=spec.context,
                predict=actual_predict,
                think=spec.think,
                keep_alive=spec.keep_alive,
            ):
                now = time.monotonic()
                response_piece = str(
                    chunk.get('response') or ''
                )
                thinking_piece = chunk.pop('thinking', None)
                if thinking_piece:
                    hidden_reasoning_present = True
                    thinking_activity_count += 1
                # Raw private reasoning is intentionally discarded here.
                thinking_piece = None

                response_chars += len(response_piece)
                answer_started = (
                    answer_started
                    or bool(response_piece)
                )
                done = bool(chunk.get('done'))
                done_reason = chunk.get('done_reason')
                cancelled = bool(
                    cancel is not None
                    and cancel.is_set()
                )
                completion_reason = classify_completion(
                    done=done,
                    done_reason=done_reason,
                    answer_started=answer_started,
                    hidden_reasoning_present=(
                        hidden_reasoning_present
                    ),
                    cancelled=cancelled,
                )
                completion = CompletionSnapshot(
                    done=done,
                    done_reason=done_reason,
                    completion_reason=completion_reason,
                    prompt_tokens=chunk.get(
                        'prompt_eval_count'
                    ),
                    generated_tokens=chunk.get(
                        'eval_count'
                    ),
                    response_chars=response_chars,
                    answer_started=answer_started,
                    hidden_reasoning_present=(
                        hidden_reasoning_present
                    ),
                    thinking_activity_count=(
                        thinking_activity_count
                    ),
                    cancelled=cancelled,
                    output_budget=actual_predict,
                )

                yield {
                    'response': response_piece,
                    **completion.as_dict(),
                    'model':spec.model,
                    'role':role.value,
                    'digest':resolved.digest,
                    'context':spec.context,
                    'exclusive_memory':spec.exclusive_memory,
                    'residency_policy':(
                        'exclusive'
                        if spec.exclusive_memory
                        else 'shared'
                    ),
                    'residency_unloaded_models':list(
                        unloaded_models
                    ),
                    'residency_unload_count':len(
                        unloaded_models
                    ),
                    'provider_load_seconds':(
                        _provider_duration_seconds(
                            chunk.get(
                                'load_duration'
                            )
                        )
                    ),
                    'residency_state_before':(
                        residency.state_before
                    ),
                    'residency_target_was_loaded':(
                        residency.target_was_loaded
                    ),
                    'residency_loaded_before':list(
                        residency.loaded_before
                    ),
                    'residency_loaded_vram_bytes_before':(
                        residency.loaded_vram_bytes_before
                    ),
                    'residency_target_vram_bytes_before':(
                        residency.target_vram_bytes_before
                    ),
                    'residency_target_expires_at_before':(
                        residency.target_expires_at_before
                    ),
                    'elapsed_seconds':round(
                        now-provider_started,
                        3,
                    ),
                    'queue_wait_seconds':round(
                        queue_wait,
                        6,
                    ),
                    'setup_seconds':round(
                        setup_elapsed,
                        6,
                    ),
                    'total_elapsed_seconds':round(
                        now-requested_at,
                        6,
                    ),
                }
