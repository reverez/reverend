"""Runtime foundation for local-only model execution."""

from .completion import (
    CompletionReason,
    CompletionSnapshot,
    classify_completion,
)
from .hardware import (
    GpuSnapshot,
    HardwareSnapshot,
    measure_hardware,
)
from .leased_scheduler import LeasedModelScheduler
from .models import (
    DEFAULT_MODELS,
    ModelProfile,
    ModelRegistry,
    ModelRegistryError,
    ModelResidencyState,
    ModelRole,
    ModelRuntimeStatus,
    ModelSpec,
    ResolvedModel,
)
from .policy import (
    InferenceMode,
    InferencePolicy,
    PolicyViolation,
    discover_wsl_windows_gateway,
)
from .providers import (
    LoadedModelInfo,
    ModelInfo,
    ModelProvider,
    OllamaProvider,
    ProviderError,
)
from .resources import (
    LeaseState,
    ResourceBroker,
    ResourceCancelled,
    ResourceCapacity,
    ResourceError,
    ResourceRejected,
    ResourceRequestState,
    ResourceTimeout,
    RuntimeResourceLease,
    RuntimeResourceRequest,
    normalize_resource_request,
)
from .scheduler import (
    ModelRunResult,
    ModelScheduler,
    SchedulerError,
    SchedulerTimeout,
)

__all__ = [
    "CompletionReason",
    "CompletionSnapshot",
    "DEFAULT_MODELS",
    "GpuSnapshot",
    "HardwareSnapshot",
    "InferenceMode",
    "InferencePolicy",
    "LeaseState",
    "LeasedModelScheduler",
    "LoadedModelInfo",
    "ModelInfo",
    "ModelProfile",
    "ModelProvider",
    "ModelRegistry",
    "ModelRegistryError",
    "ModelResidencyState",
    "ModelRole",
    "ModelRunResult",
    "ModelRuntimeStatus",
    "ModelScheduler",
    "ModelSpec",
    "OllamaProvider",
    "PolicyViolation",
    "ProviderError",
    "ResolvedModel",
    "ResourceBroker",
    "ResourceCancelled",
    "ResourceCapacity",
    "ResourceError",
    "ResourceRejected",
    "ResourceRequestState",
    "ResourceTimeout",
    "RuntimeResourceLease",
    "RuntimeResourceRequest",
    "SchedulerError",
    "SchedulerTimeout",
    "classify_completion",
    "discover_wsl_windows_gateway",
    "measure_hardware",
    "normalize_resource_request",
]
