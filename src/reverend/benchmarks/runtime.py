"""Deterministic M14 runtime optimisation benchmarks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from reverend.benchmarks.models import (
    BenchmarkBudget,
    BenchmarkCase,
    BenchmarkCategory,
    BenchmarkObservation,
)
from reverend.intelligence.understanding import understand
from reverend.runtime.models import (
    ModelInfo,
    ModelRegistry,
    ModelRole,
)


@dataclass
class _InventoryProvider:
    calls: int = 0

    def list_models(
        self,
    ) -> list[ModelInfo]:
        self.calls += 1

        return [
            ModelInfo(
                name=name,
                digest=(
                    "digest-"
                    + name
                ),
                size_bytes=1,
                modified_at=None,
                details={},
            )
            for name
            in {
                "qwen3.5:4b",
                "qwen2.5-coder:7b",
                "qwen3-coder:30b",
                "deepseek-r1:8b",
                "bge-m3:latest",
            }
        ]


def runtime_cases() -> tuple[
    BenchmarkCase,
    ...,
]:
    return (
        BenchmarkCase(
            case_id=(
                "m14-inventory-burst"
            ),
            name=(
                "model inventory burst reuse"
            ),
            category=(
                BenchmarkCategory.ROUTING
            ),
            prompt=(
                "Resolve classifier, "
                "availability and answer roles."
            ),
            expected={
                "metadata_equals": {
                    "inventory_calls": 1,
                    "router_model": (
                        "qwen3.5:4b"
                    ),
                    "answer_model": (
                        "qwen3.5:4b"
                    ),
                    "available_fast_general": (
                        True
                    ),
                    "model_calls": 0,
                }
            },
            budget=BenchmarkBudget(
                timeout_seconds=1,
                max_model_calls=0,
                max_retrieval_rounds=0,
            ),
            tags=(
                "m14",
                "runtime",
                "deterministic",
            ),
        ),
        BenchmarkCase(
            case_id=(
                "m14-clear-fact-fast-path"
            ),
            name=(
                "clear public fact avoids router"
            ),
            category=(
                BenchmarkCategory.ROUTING
            ),
            prompt=(
                "Who is Ada Lovelace?"
            ),
            expected={
                "metadata_equals": {
                    "classifier_calls": 0,
                    "intent": (
                        "open_domain_fact"
                    ),
                    "evidence_need": (
                        "reference"
                    ),
                    "method": (
                        "deterministic"
                    ),
                    "model_calls": 0,
                }
            },
            budget=BenchmarkBudget(
                timeout_seconds=1,
                max_model_calls=0,
                max_retrieval_rounds=0,
            ),
            tags=(
                "m14",
                "intelligence",
                "deterministic",
            ),
        ),
        BenchmarkCase(
            case_id=(
                "m14-ambiguous-router-guard"
            ),
            name=(
                "ambiguous request keeps router"
            ),
            category=(
                BenchmarkCategory.ROUTING
            ),
            prompt=(
                "Who is he?"
            ),
            expected={
                "metadata_equals": {
                    "classifier_calls": 1,
                    "method": (
                        "local_router"
                    ),
                    "model_calls": 0,
                }
            },
            budget=BenchmarkBudget(
                timeout_seconds=1,
                max_model_calls=0,
                max_retrieval_rounds=0,
            ),
            tags=(
                "m14",
                "intelligence",
                "safety-guard",
            ),
        ),
    )


def runtime_optimization_cases() -> tuple[
    BenchmarkCase,
    ...,
]:
    """Post-M14 deterministic runtime optimization cases."""

    return (
        BenchmarkCase(
            case_id=(
                "runtime-inventory-session-window"
            ),
            name=(
                "model inventory session-window reuse"
            ),
            category=(
                BenchmarkCategory.ROUTING
            ),
            prompt=(
                "Resolve models across a representative "
                "multi-step local workflow."
            ),
            expected={
                "metadata_equals": {
                    "baseline_inventory_calls": 3,
                    "optimized_inventory_calls": 1,
                    "provider_read_delta": -2,
                    "optimized_cache_hits": 2,
                    "inventory_ttl_seconds": 30.0,
                    "model_calls": 0,
                }
            },
            budget=BenchmarkBudget(
                timeout_seconds=1,
                max_model_calls=0,
                max_retrieval_rounds=0,
            ),
            tags=(
                "runtime",
                "optimization",
                "deterministic",
            ),
        ),
    )


class RuntimeInventoryExecutor:
    def __call__(
        self,
        case: BenchmarkCase,
    ) -> BenchmarkObservation:
        if (
            case.case_id
            in {
                "m14-clear-fact-fast-path",
                "m14-ambiguous-router-guard",
            }
        ):
            classifier_calls = 0

            def classifier(
                text: str,
            ) -> dict:
                nonlocal classifier_calls
                classifier_calls += 1

                return {
                    "intent": "open_domain_fact",
                    "entities": [],
                    "evidence_need": "reference",
                    "confidence": 0.9,
                }

            result = understand(
                case.prompt,
                classifier=classifier,
            )

            return BenchmarkObservation(
                response=(
                    "Deterministic request "
                    "understanding."
                ),
                metadata={
                    "classifier_calls": (
                        classifier_calls
                    ),
                    "intent": (
                        result.intent.value
                    ),
                    "evidence_need": (
                        result.evidence_need
                    ),
                    "method": (
                        result.method
                    ),
                    "model_calls": 0,
                    "retrieval_rounds": 0,
                },
            )

        if (
            case.case_id
            == "runtime-inventory-session-window"
        ):
            def measure(
                ttl_seconds: float | None,
            ) -> tuple[int, dict[str, int | float]]:
                provider = (
                    _InventoryProvider()
                )
                now = [100.0]
                kwargs: dict[str, Any] = {
                    "clock": lambda: now[0],
                }

                if ttl_seconds is not None:
                    kwargs[
                        "inventory_ttl_seconds"
                    ] = ttl_seconds

                registry = ModelRegistry(
                    provider,
                    **kwargs,
                )

                registry.resolve(
                    ModelRole.ROUTER
                )
                now[0] = 112.0
                registry.resolve(
                    ModelRole.STRONG_CODE
                )
                now[0] = 124.0
                registry.resolve(
                    ModelRole.STRONG_CODE
                )

                return (
                    provider.calls,
                    registry.inventory_metrics(),
                )

            baseline_calls, _ = measure(
                5.0
            )
            (
                optimized_calls,
                optimized_metrics,
            ) = measure(
                None
            )

            return BenchmarkObservation(
                response=(
                    "Compared baseline and optimized "
                    "bounded model-inventory reuse."
                ),
                metadata={
                    "baseline_inventory_calls": (
                        baseline_calls
                    ),
                    "optimized_inventory_calls": (
                        optimized_calls
                    ),
                    "provider_read_delta": (
                        optimized_calls
                        - baseline_calls
                    ),
                    "optimized_cache_hits": (
                        optimized_metrics[
                            "cache_hits"
                        ]
                    ),
                    "inventory_ttl_seconds": (
                        optimized_metrics[
                            "ttl_seconds"
                        ]
                    ),
                    "model_calls": 0,
                    "retrieval_rounds": 0,
                },
            )

        if (
            case.case_id
            != "m14-inventory-burst"
        ):
            raise ValueError(
                "Unknown runtime case."
            )

        provider = (
            _InventoryProvider()
        )
        now = [100.0]
        registry = ModelRegistry(
            provider,
            inventory_ttl_seconds=5.0,
            clock=lambda: now[0],
        )

        router = registry.resolve(
            ModelRole.ROUTER
        )
        available = (
            registry.installed_models()
        )
        answer = registry.resolve(
            ModelRole.FAST_GENERAL
        )

        return BenchmarkObservation(
            response=(
                "Resolved local model "
                "inventory with bounded reuse."
            ),
            metadata={
                "inventory_calls": (
                    provider.calls
                ),
                "router_model": (
                    router.spec.model
                ),
                "answer_model": (
                    answer.spec.model
                ),
                "available_fast_general": (
                    "qwen3.5:4b"
                    in available
                ),
                "model_calls": 0,
                "retrieval_rounds": 0,
            },
        )
