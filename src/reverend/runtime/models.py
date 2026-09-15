"""Capability-based local model registry."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from enum import Enum
import threading
import time

from .providers import ModelInfo, ModelProvider


class ModelRegistryError(RuntimeError):
    """Raised when a configured model cannot be resolved."""


class ModelRole(str, Enum):
    FAST_GENERAL = "fast_general"
    FAST_CODE = "fast_code"
    STRONG_CODE = "strong_code"
    DEEP_REASON = "deep_reason"
    EMBED = "embed"
    ROUTER = "router"
    CRITIC = "critic"


class ModelRuntimeStatus(str, Enum):
    UNAVAILABLE = "unavailable"
    AVAILABLE = "available"
    LOADED = "loaded"


class ModelResidencyState(str, Enum):
    """Conceptual residency state.

    Ollama currently exposes installed-vs-loaded state. STAGED is reserved for runtimes
    that genuinely expose a staging phase; Reverend does not synthesize it for Ollama.
    """

    COLD = "cold"
    STAGED = "staged"
    HOT = "hot"
    PINNED = "pinned"


@dataclass(frozen=True)
class ModelSpec:
    """Configured logical model profile.

    Existing callers only need the original fields. The metadata below is additive and
    records runtime/resource intent without changing the provider API.
    """

    role: ModelRole
    model: str
    context: int
    think: bool
    keep_alive: str
    description: str
    exclusive_memory: bool = False
    logical_model_id: str | None = None
    provider: str = "ollama"
    runtime: str = "ollama"
    quantization: str | None = None
    capabilities: tuple[str, ...] = ()
    trust_profile: str = "trusted_local"
    context_limit: int | None = None
    estimated_ram_bytes: int = 0
    estimated_vram_bytes: int = 0
    estimated_runtime_seconds: float | None = None
    gpu_required: bool = False
    pinned: bool = False
    benchmark_references: tuple[str, ...] = ()
    spec_version: str = "1"
    lifecycle_policy: str = "provider_managed"
    residency_policy: str = "provider_managed"

    @property
    def id(self) -> str:
        return self.logical_model_id or self.role.value


@dataclass(frozen=True)
class ResolvedModel:
    spec: ModelSpec
    info: ModelInfo

    @property
    def digest(self) -> str | None:
        return self.info.digest


@dataclass(frozen=True)
class ModelProfile:
    """Registry view combining configuration with measured provider state."""

    logical_model_id: str
    role: ModelRole
    provider: str
    runtime: str
    checkpoint: str
    digest: str | None
    quantization: str | None
    capabilities: tuple[str, ...]
    trust_profile: str
    configured_context: int
    context_limit: int
    estimated_ram_bytes: int
    estimated_vram_bytes: int
    estimated_runtime_seconds: float | None
    gpu_required: bool
    exclusive_memory: bool
    installed: bool
    loaded: bool
    runtime_status: ModelRuntimeStatus
    residency: ModelResidencyState
    benchmark_references: tuple[str, ...]
    spec_version: str
    lifecycle_policy: str
    residency_policy: str
    loaded_size_bytes: int | None
    loaded_vram_bytes: int | None
    loaded_context_length: int | None
    loaded_expires_at: str | None


_GIB = 1024**3

DEFAULT_MODELS: dict[ModelRole, ModelSpec] = {
    ModelRole.FAST_GENERAL: ModelSpec(
        role=ModelRole.FAST_GENERAL,
        model="qwen3.5:4b",
        context=8192,
        think=False,
        keep_alive="10m",
        description=(
            "Fast routing, extraction, summarisation, "
            "and inexpensive transformations."
        ),
        capabilities=("general", "routing", "summarisation"),
        context_limit=8192,
        estimated_vram_bytes=3_341_958_511,
        gpu_required=True,
        benchmark_references=(
            "benchmarks/results/models/qwen3.5-4b-8k.json",
        ),
    ),
    ModelRole.FAST_CODE: ModelSpec(
        role=ModelRole.FAST_CODE,
        model="qwen2.5-coder:7b",
        context=16384,
        think=False,
        keep_alive="10m",
        description="Interactive coding and inexpensive edits.",
        capabilities=("code", "editing"),
        context_limit=16384,
        gpu_required=True,
    ),
    ModelRole.STRONG_CODE: ModelSpec(
        role=ModelRole.STRONG_CODE,
        model="qwen3-coder:30b",
        context=16384,
        think=False,
        keep_alive="10m",
        description="Primary high-capability repository coder.",
        exclusive_memory=True,
        capabilities=("code", "reasoning", "repository"),
        context_limit=16384,
        estimated_ram_bytes=13 * _GIB,
        estimated_vram_bytes=6_215_654_440,
        gpu_required=True,
        benchmark_references=(
            "benchmarks/results/models/qwen3-coder-30b-16k.json",
        ),
        residency_policy="exclusive",
    ),
    ModelRole.DEEP_REASON: ModelSpec(
        role=ModelRole.DEEP_REASON,
        model="deepseek-r1:8b",
        context=8192,
        think=True,
        keep_alive="5m",
        description=(
            "Deliberative reasoning, mathematical analysis, "
            "criticism, and difficult diagnosis."
        ),
        exclusive_memory=True,
        capabilities=("reasoning", "critique"),
        residency_policy="exclusive",
        context_limit=8192,
        gpu_required=True,
    ),
    ModelRole.EMBED: ModelSpec(
        role=ModelRole.EMBED,
        model="bge-m3:latest",
        context=4096,
        think=False,
        keep_alive="5m",
        description="Local embedding model for retrieval.",
        capabilities=("embedding",),
        context_limit=4096,
        gpu_required=True,
    ),
}

# Logical roles reuse existing local models; no additional downloads or residency.
DEFAULT_MODELS[ModelRole.ROUTER] = replace(
    DEFAULT_MODELS[ModelRole.FAST_GENERAL],
    role=ModelRole.ROUTER,
    logical_model_id=ModelRole.ROUTER.value,
    description="Bounded request classification",
    context=4096,
)
DEFAULT_MODELS[ModelRole.CRITIC] = replace(
    DEFAULT_MODELS[ModelRole.DEEP_REASON],
    role=ModelRole.CRITIC,
    logical_model_id=ModelRole.CRITIC.value,
    description="Independent local review",
)


class ModelRegistry:
    """Resolve logical capability roles to installed local models."""

    def __init__(
        self,
        provider: ModelProvider,
        specs: dict[ModelRole, ModelSpec] | None = None,
        *,
        inventory_ttl_seconds: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if (
            not isinstance(inventory_ttl_seconds, (int, float))
            or isinstance(inventory_ttl_seconds, bool)
            or inventory_ttl_seconds < 0
            or inventory_ttl_seconds > 300
        ):
            raise ValueError(
                "inventory_ttl_seconds must be between 0 and 300."
            )

        self.provider = provider
        self._specs = dict(specs if specs is not None else DEFAULT_MODELS)
        self._inventory_ttl_seconds = float(inventory_ttl_seconds)
        self._clock = clock
        self._inventory_lock = threading.RLock()
        self._inventory_cache: dict[str, ModelInfo] | None = None
        self._inventory_cached_at: float | None = None
        self._inventory_provider_reads = 0
        self._inventory_cache_hits = 0

    def roles(self) -> list[ModelRole]:
        return list(self._specs)

    def registered_specs(self) -> dict[ModelRole, ModelSpec]:
        with self._inventory_lock:
            return dict(self._specs)

    def register(
        self,
        spec: ModelSpec,
        *,
        replace_existing: bool = False,
    ) -> None:
        """Register a logical model profile without downloading or loading it."""

        with self._inventory_lock:
            if spec.role in self._specs and not replace_existing:
                raise ModelRegistryError(
                    f"Model role already registered: {spec.role.value}"
                )
            self._specs[spec.role] = spec

    def unregister(self, role: ModelRole) -> ModelSpec:
        with self._inventory_lock:
            try:
                return self._specs.pop(role)
            except KeyError as exc:
                raise ModelRegistryError(
                    f"No model configured for role: {role.value}"
                ) from exc

    def spec(self, role: ModelRole) -> ModelSpec:
        try:
            return self._specs[role]
        except KeyError as exc:
            raise ModelRegistryError(
                f"No model configured for role: {role.value}"
            ) from exc

    def invalidate_inventory(self) -> None:
        with self._inventory_lock:
            self._inventory_cache = None
            self._inventory_cached_at = None

    def installed_models(
        self,
        *,
        refresh: bool = False,
    ) -> dict[str, ModelInfo]:
        with self._inventory_lock:
            now = self._clock()

            if refresh:
                self._inventory_cache = None
                self._inventory_cached_at = None
            elif (
                self._inventory_cache is not None
                and self._inventory_cached_at is not None
                and (now - self._inventory_cached_at)
                < self._inventory_ttl_seconds
            ):
                self._inventory_cache_hits += 1
                return dict(self._inventory_cache)

            self._inventory_provider_reads += 1
            models = {
                model.name: model
                for model in self.provider.list_models()
            }
            self._inventory_cache = models
            self._inventory_cached_at = self._clock()
            return dict(models)

    def inventory_metrics(self) -> dict[str, int | float]:
        with self._inventory_lock:
            return {
                "provider_reads": self._inventory_provider_reads,
                "cache_hits": self._inventory_cache_hits,
                "cached_models": len(self._inventory_cache or {}),
                "ttl_seconds": self._inventory_ttl_seconds,
            }

    def resolve(self, role: ModelRole) -> ResolvedModel:
        spec = self.spec(role)
        installed = self.installed_models()
        info = installed.get(spec.model)

        if info is None:
            raise ModelRegistryError(
                f"Model for role {role.value!r} is not "
                f"installed: {spec.model!r}"
            )

        return ResolvedModel(spec=spec, info=info)

    def resolve_all(self) -> dict[ModelRole, ResolvedModel]:
        installed = self.installed_models()
        resolved: dict[ModelRole, ResolvedModel] = {}

        for role, spec in self._specs.items():
            info = installed.get(spec.model)
            if info is None:
                raise ModelRegistryError(
                    f"Model for role {role.value!r} is not "
                    f"installed: {spec.model!r}"
                )
            resolved[role] = ResolvedModel(spec=spec, info=info)

        return resolved

    def estimated_vram_bytes(self, role: ModelRole) -> int:
        """Return the best available enforceable VRAM estimate.

        Retained benchmark/profile measurements win. If a model is currently loaded,
        Ollama's measured `size_vram` is next. For an unprofiled cold model, the local
        inventory size is used with bounded headroom rather than silently treating the
        model as a zero-VRAM workload.
        """

        spec = self.spec(role)
        if spec.estimated_vram_bytes > 0:
            return spec.estimated_vram_bytes

        loaded_model_info = getattr(
            self.provider,
            "loaded_model_info",
            None,
        )
        if callable(loaded_model_info):
            try:
                for item in loaded_model_info():
                    if (
                        item.name == spec.model
                        and item.size_vram_bytes is not None
                        and item.size_vram_bytes > 0
                    ):
                        return int(item.size_vram_bytes)
            except Exception:
                pass

        info = self.installed_models().get(spec.model)
        if info is not None and info.size_bytes is not None and info.size_bytes > 0:
            return int(info.size_bytes * 1.15)

        return 0

    def profile(self, role: ModelRole) -> ModelProfile:
        """Return configured metadata plus truthful installed/loaded state."""

        spec = self.spec(role)
        installed = self.installed_models()
        info = installed.get(spec.model)

        loaded_names: set[str] = set()
        loaded_info = None
        loaded_model_info = getattr(
            self.provider,
            "loaded_model_info",
            None,
        )
        if callable(loaded_model_info):
            try:
                loaded_items = list(loaded_model_info())
                loaded_names = {
                    item.name
                    for item in loaded_items
                }
                loaded_info = next(
                    (
                        item
                        for item in loaded_items
                        if item.name == spec.model
                    ),
                    None,
                )
            except Exception:
                loaded_names = set()
                loaded_info = None
        else:
            loaded_models = getattr(self.provider, "loaded_models", None)
            if callable(loaded_models):
                try:
                    loaded_names = set(loaded_models())
                except Exception:
                    # Runtime status still truthfully reports installed availability.
                    loaded_names = set()

        is_installed = info is not None
        is_loaded = spec.model in loaded_names

        if is_loaded:
            residency = (
                ModelResidencyState.PINNED
                if spec.pinned
                else ModelResidencyState.HOT
            )
            status = ModelRuntimeStatus.LOADED
        elif is_installed:
            residency = ModelResidencyState.COLD
            status = ModelRuntimeStatus.AVAILABLE
        else:
            residency = ModelResidencyState.COLD
            status = ModelRuntimeStatus.UNAVAILABLE

        details = info.details if info is not None else {}
        quantization = (
            spec.quantization
            or details.get("quantization_level")
        )

        return ModelProfile(
            logical_model_id=spec.id,
            role=role,
            provider=spec.provider,
            runtime=spec.runtime,
            checkpoint=spec.model,
            digest=info.digest if info is not None else None,
            quantization=quantization,
            capabilities=spec.capabilities,
            trust_profile=spec.trust_profile,
            configured_context=spec.context,
            context_limit=spec.context_limit or spec.context,
            estimated_ram_bytes=spec.estimated_ram_bytes,
            estimated_vram_bytes=spec.estimated_vram_bytes,
            estimated_runtime_seconds=spec.estimated_runtime_seconds,
            gpu_required=spec.gpu_required,
            exclusive_memory=spec.exclusive_memory,
            installed=is_installed,
            loaded=is_loaded,
            runtime_status=status,
            residency=residency,
            benchmark_references=spec.benchmark_references,
            spec_version=spec.spec_version,
            lifecycle_policy=spec.lifecycle_policy,
            residency_policy=spec.residency_policy,
            loaded_size_bytes=(
                loaded_info.size_bytes
                if loaded_info is not None
                else None
            ),
            loaded_vram_bytes=(
                loaded_info.size_vram_bytes
                if loaded_info is not None
                else None
            ),
            loaded_context_length=(
                loaded_info.context_length
                if loaded_info is not None
                else None
            ),
            loaded_expires_at=(
                loaded_info.expires_at
                if loaded_info is not None
                else None
            ),
        )
