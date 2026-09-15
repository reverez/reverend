from __future__ import annotations

import pytest

from reverend.runtime.models import (
    ModelRegistry,
    ModelRegistryError,
    ModelResidencyState,
    ModelRole,
    ModelRuntimeStatus,
    ModelSpec,
)
from reverend.runtime.providers import LoadedModelInfo, ModelInfo


class Provider:
    def __init__(self, *, loaded=()):
        self.loaded = list(loaded)

    def list_models(self):
        return [
            ModelInfo(
                name="example:1b",
                digest="abc",
                size_bytes=123,
                modified_at=None,
                details={"quantization_level": "Q4_K_M"},
            )
        ]

    def loaded_models(self):
        return list(self.loaded)

    def loaded_model_info(self):
        return [
            LoadedModelInfo(
                name=name,
                size_bytes=456,
                size_vram_bytes=321,
                context_length=4096,
                expires_at="2026-09-15T10:00:00+01:00",
                details={},
            )
            for name in self.loaded
        ]


def spec():
    return ModelSpec(
        role=ModelRole.FAST_GENERAL,
        model="example:1b",
        context=4096,
        think=False,
        keep_alive="5m",
        description="example",
        capabilities=("general",),
        context_limit=8192,
        estimated_vram_bytes=1234,
        gpu_required=True,
        benchmark_references=("benchmarks/example.json",),
    )


def test_profile_combines_config_and_loaded_provider_state():
    registry = ModelRegistry(
        Provider(loaded=("example:1b",)),
        specs={ModelRole.FAST_GENERAL: spec()},
    )

    profile = registry.profile(ModelRole.FAST_GENERAL)

    assert profile.logical_model_id == ModelRole.FAST_GENERAL.value
    assert profile.quantization == "Q4_K_M"
    assert profile.context_limit == 8192
    assert profile.estimated_vram_bytes == 1234
    assert profile.runtime_status is ModelRuntimeStatus.LOADED
    assert profile.residency is ModelResidencyState.HOT
    assert profile.benchmark_references == ("benchmarks/example.json",)
    assert profile.spec_version == "1"
    assert profile.loaded_size_bytes == 456
    assert profile.loaded_vram_bytes == 321
    assert profile.loaded_context_length == 4096
    assert profile.loaded_expires_at == "2026-09-15T10:00:00+01:00"


def test_registry_supports_explicit_registration_without_loading_model():
    registry = ModelRegistry(Provider(), specs={})
    model = spec()

    registry.register(model)

    assert registry.spec(ModelRole.FAST_GENERAL) == model
    with pytest.raises(ModelRegistryError, match="already registered"):
        registry.register(model)



def test_vram_estimate_prefers_loaded_measurement_for_unprofiled_model():
    model = ModelSpec(
        role=ModelRole.FAST_GENERAL,
        model="example:1b",
        context=4096,
        think=False,
        keep_alive="5m",
        description="example",
        gpu_required=True,
    )
    registry = ModelRegistry(
        Provider(loaded=("example:1b",)),
        specs={ModelRole.FAST_GENERAL: model},
    )

    assert registry.estimated_vram_bytes(ModelRole.FAST_GENERAL) == 321


def test_vram_estimate_uses_local_inventory_with_headroom_when_cold():
    model = ModelSpec(
        role=ModelRole.FAST_GENERAL,
        model="example:1b",
        context=4096,
        think=False,
        keep_alive="5m",
        description="example",
        gpu_required=True,
    )
    registry = ModelRegistry(
        Provider(),
        specs={ModelRole.FAST_GENERAL: model},
    )

    estimate = registry.estimated_vram_bytes(ModelRole.FAST_GENERAL)

    assert estimate > 123
