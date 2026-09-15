"""Live benchmark for Reverend model residency and load behaviour."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

from reverend.runtime import (
    ModelRegistry,
    ModelRole,
    ModelScheduler,
    OllamaProvider,
)


_GENERATION_ROLES = tuple(
    role
    for role in ModelRole
    if role is not ModelRole.EMBED
)


def _loaded_after(
    scheduler: ModelScheduler,
) -> list[dict]:
    detailed = getattr(
        scheduler.provider,
        "loaded_model_info",
        None,
    )

    if not callable(detailed):
        return [
            {
                "name": name,
            }
            for name in scheduler.provider.loaded_models()
        ]

    return [
        {
            "name": item.name,
            "size_bytes": item.size_bytes,
            "size_vram_bytes": item.size_vram_bytes,
            "context_length": item.context_length,
            "expires_at": item.expires_at,
        }
        for item in detailed()
    ]


def run_sequence(
    scheduler: ModelScheduler,
    roles: Iterable[ModelRole],
    *,
    predict: int = 32,
    keep_alive: str | int | None = None,
    delay_seconds: float = 0.0,
    sleep: Callable[[float], None] = time.sleep,
) -> list[dict]:
    """Run a bounded role sequence and return safe runtime measurements."""

    if predict <= 0:
        raise ValueError(
            "predict must be positive."
        )

    if delay_seconds < 0:
        raise ValueError(
            "delay_seconds cannot be negative."
        )

    sequence = tuple(roles)
    if not sequence:
        raise ValueError(
            "At least one role is required."
        )

    runs: list[dict] = []

    for index, role in enumerate(sequence):
        kwargs = {
            "predict": predict,
            "temperature": 0.0,
        }

        if keep_alive is not None:
            kwargs["keep_alive"] = keep_alive

        result = scheduler.generate(
            role,
            (
                "Return exactly the word OK and "
                "nothing else."
            ),
            **kwargs,
        )

        runs.append(
            {
                "index": index,
                "role": role.value,
                "model": result.model,
                "context": result.context,
                "exclusive_memory": (
                    result.exclusive_memory
                ),
                "provider_load_seconds": (
                    result.provider_load_seconds
                ),
                "provider_elapsed_seconds": (
                    result.elapsed_seconds
                ),
                "queue_wait_seconds": (
                    result.queue_wait_seconds
                ),
                "setup_seconds": (
                    result.setup_seconds
                ),
                "total_elapsed_seconds": (
                    result.total_elapsed_seconds
                ),
                "prompt_tokens": result.response.get(
                    "prompt_eval_count"
                ),
                "generated_tokens": result.response.get(
                    "eval_count"
                ),
                "done_reason": result.response.get(
                    "done_reason"
                ),
                "residency_policy": (
                    result.residency_policy
                ),
                "residency_state_before": (
                    result.residency_state_before
                ),
                "residency_target_was_loaded": (
                    result.residency_target_was_loaded
                ),
                "residency_loaded_before": list(
                    result.residency_loaded_before
                ),
                "residency_unloaded_models": list(
                    result.residency_unloaded_models
                ),
                "residency_loaded_vram_bytes_before": (
                    result.residency_loaded_vram_bytes_before
                ),
                "residency_target_vram_bytes_before": (
                    result.residency_target_vram_bytes_before
                ),
                "residency_target_expires_at_before": (
                    result.residency_target_expires_at_before
                ),
                "loaded_after": (
                    _loaded_after(
                        scheduler
                    )
                ),
            }
        )

        if (
            delay_seconds
            and index < len(sequence) - 1
        ):
            sleep(
                delay_seconds
            )

    return runs


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Measure cold/warm residency through Reverend's "
            "canonical local scheduler."
        )
    )
    parser.add_argument(
        "--roles",
        nargs="+",
        choices=[
            role.value
            for role in _GENERATION_ROLES
        ],
        default=[
            ModelRole.STRONG_CODE.value,
            ModelRole.STRONG_CODE.value,
        ],
    )
    parser.add_argument(
        "--predict",
        type=int,
        default=32,
    )
    parser.add_argument(
        "--keep-alive",
    )
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=0.0,
    )
    parser.add_argument(
        "--cold-start",
        action="store_true",
    )
    parser.add_argument(
        "--output",
        type=Path,
    )
    args = parser.parse_args()

    provider = OllamaProvider()
    registry = ModelRegistry(
        provider
    )
    scheduler = ModelScheduler(
        provider,
        registry,
    )
    roles = tuple(
        ModelRole(value)
        for value in args.roles
    )

    if args.cold_start:
        provider.unload(
            registry.spec(
                roles[0]
            ).model
        )

    runs = run_sequence(
        scheduler,
        roles,
        predict=args.predict,
        keep_alive=args.keep_alive,
        delay_seconds=args.delay_seconds,
    )

    report = {
        "created_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "roles": [
            role.value
            for role in roles
        ],
        "predict": args.predict,
        "keep_alive_override": (
            args.keep_alive
        ),
        "delay_seconds": (
            args.delay_seconds
        ),
        "cold_start": (
            args.cold_start
        ),
        "inventory_metrics": (
            registry.inventory_metrics()
        ),
        "runs": runs,
    }

    text = json.dumps(
        report,
        indent=2,
    )

    if args.output:
        args.output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        args.output.write_text(
            text + "\n",
            encoding="utf-8",
        )

    print(
        text
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
