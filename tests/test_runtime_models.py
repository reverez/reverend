from __future__ import annotations

from dataclasses import dataclass

import pytest

from reverend.runtime.models import (
    ModelRegistry,
    ModelRegistryError,
    ModelRole,
)
from reverend.runtime.providers import (
    ModelInfo,
)


@dataclass
class FakeProvider:
    models: list[ModelInfo]
    calls: int = 0
    fail: bool = False

    def list_models(self):
        self.calls += 1

        if self.fail:
            raise RuntimeError(
                "inventory unavailable"
            )

        return list(
            self.models
        )


def model(name: str) -> ModelInfo:
    return ModelInfo(
        name=name,
        digest=f"digest-{name}",
        size_bytes=123,
        modified_at=None,
        details={},
    )


def full_provider():
    return FakeProvider(
        models=[
            model("qwen3.5:4b"),
            model("qwen2.5-coder:7b"),
            model("qwen3-coder:30b"),
            model("deepseek-r1:8b"),
            model("bge-m3:latest"),
        ]
    )


def test_registry_resolves_all_roles():
    registry = ModelRegistry(
        full_provider()
    )

    resolved = registry.resolve_all()

    assert set(resolved) == set(
        ModelRole
    )

    assert (
        resolved[
            ModelRole.STRONG_CODE
        ].spec.model
        == "qwen3-coder:30b"
    )


def test_registry_captures_digest():
    registry = ModelRegistry(
        full_provider()
    )

    resolved = registry.resolve(
        ModelRole.FAST_GENERAL
    )

    assert (
        resolved.digest
        == "digest-qwen3.5:4b"
    )


def test_registry_rejects_missing_model():
    provider = FakeProvider(
        models=[]
    )

    registry = ModelRegistry(
        provider
    )

    with pytest.raises(
        ModelRegistryError,
        match="not installed",
    ):
        registry.resolve(
            ModelRole.STRONG_CODE
        )


def test_strong_code_profile_matches_benchmark():
    registry = ModelRegistry(
        full_provider()
    )

    resolved = registry.resolve(
        ModelRole.STRONG_CODE
    )

    assert resolved.spec.model == "qwen3-coder:30b"
    assert resolved.spec.context == 16384
    assert resolved.spec.keep_alive == "10m"
    assert resolved.spec.exclusive_memory is True



def test_registry_reuses_inventory_within_ttl():
    provider = full_provider()
    now = [100.0]
    registry = ModelRegistry(
        provider,
        inventory_ttl_seconds=5.0,
        clock=lambda: now[0],
    )

    first = registry.resolve(
        ModelRole.ROUTER
    )
    second = registry.resolve(
        ModelRole.FAST_GENERAL
    )
    available = (
        registry.installed_models()
    )

    assert provider.calls == 1
    assert (
        first.info.digest
        == "digest-qwen3.5:4b"
    )
    assert (
        second.info.digest
        == first.info.digest
    )
    assert (
        available[
            "qwen3.5:4b"
        ].digest
        == first.info.digest
    )
    assert (
        registry.inventory_metrics()[
            "provider_reads"
        ]
        == 1
    )
    assert (
        registry.inventory_metrics()[
            "cache_hits"
        ]
        == 2
    )


def test_registry_inventory_refreshes_after_ttl():
    provider = full_provider()
    now = [100.0]
    registry = ModelRegistry(
        provider,
        inventory_ttl_seconds=5.0,
        clock=lambda: now[0],
    )

    registry.installed_models()

    now[0] = 104.999
    registry.installed_models()

    assert provider.calls == 1

    now[0] = 105.0
    registry.installed_models()

    assert provider.calls == 2


def test_registry_explicit_refresh_and_invalidation():
    provider = full_provider()
    registry = ModelRegistry(
        provider,
        inventory_ttl_seconds=30.0,
    )

    registry.installed_models()
    registry.installed_models(
        refresh=True
    )

    assert provider.calls == 2

    registry.invalidate_inventory()
    registry.installed_models()

    assert provider.calls == 3


def test_failed_explicit_refresh_does_not_reuse_stale_inventory():
    provider = full_provider()
    registry = ModelRegistry(
        provider,
        inventory_ttl_seconds=30.0,
    )

    registry.installed_models()
    assert provider.calls == 1

    provider.fail = True

    with pytest.raises(
        RuntimeError,
        match="inventory unavailable",
    ):
        registry.installed_models(
            refresh=True
        )

    provider.fail = False
    registry.installed_models()

    assert provider.calls == 3


@pytest.mark.parametrize(
    "ttl",
    [
        -1,
        301,
        True,
        "5",
    ],
)
def test_registry_inventory_ttl_is_bounded(ttl):
    with pytest.raises(
        ValueError,
        match="inventory_ttl_seconds",
    ):
        ModelRegistry(
            full_provider(),
            inventory_ttl_seconds=ttl,
        )



def test_reasoning_roles_are_memory_exclusive():
    registry=ModelRegistry(
        full_provider()
    )
    deep=registry.resolve(
        ModelRole.DEEP_REASON
    )
    critic=registry.resolve(
        ModelRole.CRITIC
    )

    assert deep.spec.context==8192
    assert deep.spec.exclusive_memory is True
    assert critic.spec.model=='deepseek-r1:8b'
    assert critic.spec.exclusive_memory is True



def test_default_inventory_ttl_covers_typical_workflow_window():
    provider = full_provider()
    now = [100.0]
    registry = ModelRegistry(
        provider,
        clock=lambda: now[0],
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

    assert provider.calls == 1
    metrics = registry.inventory_metrics()
    assert metrics["cache_hits"] == 2
    assert metrics["ttl_seconds"] == 30.0
