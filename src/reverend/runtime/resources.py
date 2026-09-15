"""Atomic resource queue and lease accounting for Reverend vNext.

The frozen Wave-1 ResourceRequest/ResourceLease contracts are semantic contracts rather
than a second implementation package. RuntimeResourceRequest and RuntimeResourceLease are
the compute runtime's normalized adapter views of those contracts; they deliberately keep
the "Runtime" prefix to avoid claiming a competing cross-subsystem authority.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from enum import Enum
import threading
import time
from typing import Any
import uuid

from .hardware import HardwareSnapshot, measure_hardware


class ResourceError(RuntimeError):
    """Base error for local resource scheduling."""


class ResourceTimeout(ResourceError):
    """Raised when a pending request cannot obtain an atomic grant in time."""


class ResourceCancelled(ResourceError):
    """Raised when a pending request is cancelled while waiting."""


class ResourceRejected(ResourceError):
    """Raised when a request can never fit the configured local capacity."""


class ResourceRequestState(str, Enum):
    CREATED = "created"
    PENDING = "pending"
    GRANTED = "granted"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class LeaseState(str, Enum):
    ACTIVE = "active"
    RELEASED = "released"
    EXPIRED = "expired"
    REVOKED = "revoked"


@dataclass(frozen=True)
class ResourceCapacity:
    """Capacity that this broker is permitted to allocate."""

    cpu_cores: float
    ram_bytes: int
    gpu_count: int = 0
    gpu_vram_bytes: int = 0

    @classmethod
    def from_hardware(
        cls,
        snapshot: HardwareSnapshot | None = None,
        *,
        ram_reserve_bytes: int = 1 * 1024**3,
        vram_reserve_bytes: int = 512 * 1024**2,
    ) -> "ResourceCapacity":
        snapshot = snapshot or measure_hardware()
        gpu = snapshot.gpus[0] if snapshot.gpus else None
        return cls(
            cpu_cores=float(snapshot.cpu_logical_cores),
            # Capacity is the broker's allocatable ceiling, not instantaneous
            # free memory. Current free/used values remain HardwareSnapshot
            # telemetry; residency transitions may legitimately reclaim memory
            # after a lease is granted (for example exclusive Ollama unloads).
            ram_bytes=max(
                0,
                snapshot.ram_total_bytes - max(0, ram_reserve_bytes),
            ),
            gpu_count=1 if gpu is not None else 0,
            gpu_vram_bytes=(
                max(0, gpu.memory_total_bytes - max(0, vram_reserve_bytes))
                if gpu is not None
                else 0
            ),
        )


@dataclass(frozen=True)
class RuntimeResourceRequest:
    """Normalized runtime view of the frozen ResourceRequest contract."""

    request_id: str
    job_id: str
    cpu_cores: float = 1.0
    ram_bytes: int = 0
    gpu_required: bool = False
    estimated_vram_bytes: int = 0
    gpu_exclusive: bool = False
    gpu_device_ids: tuple[int, ...] = ()
    estimated_runtime_seconds: float | None = None
    priority: int = 0
    request_class: str = "interactive"
    preemptible: bool = False
    batchable: bool = False
    model_id: str | None = None
    ready: bool = True
    lease_duration_seconds: float = 120.0
    queue_timeout_seconds: float = 300.0
    submitted_at: float = field(default_factory=time.monotonic)

    @property
    def owner(self) -> str:
        """Compatibility alias; the frozen contract's owner is the Job."""

        return self.job_id


@dataclass
class RuntimeResourceLease:
    """Concrete time-bounded resource ownership for one Job."""

    lease_id: str
    request_id: str
    job_id: str
    cpu_cores: float
    ram_bytes: int
    gpu_required: bool
    vram_bytes: int
    gpu_exclusive: bool
    gpu_device_ids: tuple[int, ...]
    model_id: str | None
    acquired_at: float
    expires_at: float
    last_heartbeat_at: float
    lease_duration_seconds: float
    state: LeaseState = LeaseState.ACTIVE
    released_at: float | None = None

    @property
    def owner(self) -> str:
        return self.job_id

    @property
    def granted_at(self) -> float:
        """Compatibility alias for older runtime metrics/tests."""

        return self.acquired_at

    @property
    def active(self) -> bool:
        return self.state is LeaseState.ACTIVE


def _value(source: Any, *names: str, default: Any = None) -> Any:
    if isinstance(source, dict):
        for name in names:
            if name in source:
                return source[name]
        return default

    for name in names:
        if hasattr(source, name):
            return getattr(source, name)
    return default


def normalize_resource_request(
    request: Any,
    *,
    clock: Callable[[], float] = time.monotonic,
) -> RuntimeResourceRequest:
    """Adapt the shared contract/object shape into the allocator's immutable view."""

    if isinstance(request, RuntimeResourceRequest):
        return request

    request_id = _value(request, "request_id", "id")
    job_id = _value(request, "job_id", "owner", "owner_id")
    if not request_id:
        request_id = str(uuid.uuid4())
    if not job_id:
        raise ValueError("Resource request requires an owner job_id.")

    cpu = float(_value(request, "cpu_cores", "cpu", default=1.0) or 0)
    ram = int(_value(request, "ram_bytes", "ram", default=0) or 0)
    gpu_required = bool(
        _value(request, "gpu_required", "requires_gpu", "gpu", default=False)
    )
    vram = int(
        _value(
            request,
            "estimated_vram_bytes",
            "vram_bytes",
            "estimated_vram",
            default=0,
        )
        or 0
    )
    gpu_exclusive = bool(
        _value(request, "gpu_exclusive", "exclusive_gpu", default=False)
    )
    estimated_runtime = _value(
        request,
        "estimated_runtime_seconds",
        "estimated_runtime",
        default=None,
    )
    if estimated_runtime is not None:
        estimated_runtime = float(estimated_runtime)

    raw_devices = _value(
        request,
        "gpu_device_ids",
        "gpu_devices",
        default=(),
    )
    devices = tuple(int(item) for item in (raw_devices or ()))

    submitted = _value(request, "submitted_at", "requested_at", default=None)
    if submitted is None:
        submitted = clock()

    normalised = RuntimeResourceRequest(
        request_id=str(request_id),
        job_id=str(job_id),
        cpu_cores=cpu,
        ram_bytes=ram,
        gpu_required=gpu_required,
        estimated_vram_bytes=vram,
        gpu_exclusive=gpu_exclusive,
        gpu_device_ids=devices,
        estimated_runtime_seconds=estimated_runtime,
        priority=int(_value(request, "priority", default=0) or 0),
        request_class=str(
            _value(request, "request_class", "priority_class", default="interactive")
            or "interactive"
        ),
        preemptible=bool(_value(request, "preemptible", default=False)),
        batchable=bool(_value(request, "batchable", default=False)),
        model_id=(
            None
            if _value(request, "model_id", "model", default=None) is None
            else str(_value(request, "model_id", "model"))
        ),
        ready=bool(_value(request, "ready", default=True)),
        lease_duration_seconds=float(
            _value(request, "lease_duration_seconds", "lease_ttl_seconds", default=120.0)
        ),
        queue_timeout_seconds=float(
            _value(request, "queue_timeout_seconds", "timeout_seconds", default=300.0)
        ),
        submitted_at=float(submitted),
    )

    if normalised.cpu_cores < 0:
        raise ValueError("cpu_cores must be non-negative.")
    if normalised.ram_bytes < 0 or normalised.estimated_vram_bytes < 0:
        raise ValueError("RAM/VRAM requests must be non-negative.")
    if normalised.gpu_exclusive and not normalised.gpu_required:
        raise ValueError("gpu_exclusive requires gpu_required.")
    if normalised.estimated_vram_bytes and not normalised.gpu_required:
        raise ValueError("VRAM cannot be requested without a GPU.")
    if normalised.gpu_device_ids and not normalised.gpu_required:
        raise ValueError("GPU device constraints require gpu_required.")
    if normalised.lease_duration_seconds <= 0:
        raise ValueError("lease_duration_seconds must be positive.")
    if normalised.queue_timeout_seconds <= 0:
        raise ValueError("queue_timeout_seconds must be positive.")

    return normalised


class ResourceBroker:
    """Rule-based atomic allocator with priority aging and expiring leases.

    The existing cross-process ModelScheduler lock remains the final process boundary.
    This broker provides structured request/lease semantics without weakening that
    proven safety fallback.
    """

    def __init__(
        self,
        capacity: ResourceCapacity,
        *,
        lease_ttl_seconds: float = 120.0,
        aging_interval_seconds: float = 30.0,
        allow_same_model_gpu_sharing: bool = False,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if lease_ttl_seconds <= 0:
            raise ValueError("lease_ttl_seconds must be positive.")
        if aging_interval_seconds <= 0:
            raise ValueError("aging_interval_seconds must be positive.")
        if capacity.cpu_cores < 0 or capacity.ram_bytes < 0:
            raise ValueError("Resource capacity cannot be negative.")
        if capacity.gpu_count < 0 or capacity.gpu_vram_bytes < 0:
            raise ValueError("GPU capacity cannot be negative.")

        self.capacity = capacity
        self.lease_ttl_seconds = float(lease_ttl_seconds)
        self.aging_interval_seconds = float(aging_interval_seconds)
        self.allow_same_model_gpu_sharing = bool(
            allow_same_model_gpu_sharing
        )
        self._clock = clock
        self._condition = threading.Condition(threading.RLock())
        self._queued: dict[str, RuntimeResourceRequest] = {}
        self._leases: dict[str, RuntimeResourceLease] = {}
        self._lease_by_request: dict[str, str] = {}
        self._request_states: dict[str, ResourceRequestState] = {}

    @classmethod
    def from_hardware(
        cls,
        snapshot: HardwareSnapshot | None = None,
        **kwargs: Any,
    ) -> "ResourceBroker":
        return cls(ResourceCapacity.from_hardware(snapshot), **kwargs)

    def request_state(self, request_id: str) -> ResourceRequestState | None:
        with self._condition:
            return self._request_states.get(request_id)

    def _can_ever_fit(self, request: RuntimeResourceRequest) -> bool:
        if request.cpu_cores > self.capacity.cpu_cores:
            return False
        if request.ram_bytes > self.capacity.ram_bytes:
            return False
        if request.gpu_required:
            if self.capacity.gpu_count < 1:
                return False
            if request.estimated_vram_bytes > self.capacity.gpu_vram_bytes:
                return False
            if request.gpu_device_ids and any(
                device < 0 or device >= self.capacity.gpu_count
                for device in request.gpu_device_ids
            ):
                return False
        return True

    def enqueue(self, request: Any) -> RuntimeResourceRequest:
        normalised = normalize_resource_request(request, clock=self._clock)
        with self._condition:
            if (
                normalised.request_id in self._queued
                or normalised.request_id in self._lease_by_request
                or self._request_states.get(normalised.request_id)
                in {
                    ResourceRequestState.PENDING,
                    ResourceRequestState.GRANTED,
                }
            ):
                raise ResourceError(
                    f"Duplicate resource request: {normalised.request_id}"
                )

            self._request_states[normalised.request_id] = (
                ResourceRequestState.CREATED
            )
            if not self._can_ever_fit(normalised):
                self._request_states[normalised.request_id] = (
                    ResourceRequestState.REJECTED
                )
                raise ResourceRejected(
                    f"Resource request exceeds configured capacity: "
                    f"{normalised.request_id}"
                )

            self._queued[normalised.request_id] = normalised
            self._request_states[normalised.request_id] = (
                ResourceRequestState.PENDING
            )
            self._condition.notify_all()
        return normalised

    def cancel(self, request_id: str) -> bool:
        with self._condition:
            removed = self._queued.pop(request_id, None)
            if removed is not None:
                self._request_states[request_id] = (
                    ResourceRequestState.CANCELLED
                )
                self._condition.notify_all()
                return True

            return (
                self._request_states.get(request_id)
                is ResourceRequestState.CANCELLED
            )

    def set_ready(
        self,
        request_id: str,
        ready: bool = True,
    ) -> RuntimeResourceRequest:
        """Change readiness for a still-pending request without changing identity."""

        with self._condition:
            request = self._queued.get(request_id)
            if request is None:
                raise ResourceError(
                    f"Request is not pending: {request_id}"
                )
            updated = replace(request, ready=bool(ready))
            self._queued[request_id] = updated
            self._condition.notify_all()
            return updated

    def queued_requests(self) -> tuple[RuntimeResourceRequest, ...]:
        with self._condition:
            return tuple(
                sorted(
                    self._queued.values(),
                    key=lambda item: (
                        -self._effective_priority(item),
                        item.submitted_at,
                        item.request_id,
                    ),
                )
            )

    def active_leases(self) -> tuple[RuntimeResourceLease, ...]:
        with self._condition:
            self._reap_expired_locked()
            return tuple(
                lease
                for lease in self._leases.values()
                if lease.active
            )

    def lease(self, lease_id: str) -> RuntimeResourceLease | None:
        with self._condition:
            self._reap_expired_locked()
            return self._leases.get(lease_id)

    def _effective_priority(self, request: RuntimeResourceRequest) -> int:
        age = max(0.0, self._clock() - request.submitted_at)
        return request.priority + int(age // self.aging_interval_seconds)

    def _usage(self) -> tuple[float, int, int, list[RuntimeResourceLease]]:
        active = [
            lease
            for lease in self._leases.values()
            if lease.active
        ]
        return (
            sum(lease.cpu_cores for lease in active),
            sum(lease.ram_bytes for lease in active),
            sum(lease.vram_bytes for lease in active if lease.gpu_required),
            active,
        )

    def _gpu_compatible(
        self,
        request: RuntimeResourceRequest,
        active: list[RuntimeResourceLease],
    ) -> bool:
        gpu_leases = [lease for lease in active if lease.gpu_required]
        if not gpu_leases:
            return True

        if request.gpu_exclusive or any(
            lease.gpu_exclusive for lease in gpu_leases
        ):
            return False

        if not self.allow_same_model_gpu_sharing:
            return False

        if not request.batchable or not request.model_id:
            return False

        return all(
            lease.model_id == request.model_id
            and lease.gpu_device_ids
            == (
                request.gpu_device_ids
                or lease.gpu_device_ids
            )
            for lease in gpu_leases
        )

    def can_fit(self, request: Any) -> bool:
        normalised = normalize_resource_request(request, clock=self._clock)
        with self._condition:
            self._reap_expired_locked()
            used_cpu, used_ram, used_vram, active = self._usage()

            if not self._can_ever_fit(normalised):
                return False
            if used_cpu + normalised.cpu_cores > self.capacity.cpu_cores:
                return False
            if used_ram + normalised.ram_bytes > self.capacity.ram_bytes:
                return False

            if normalised.gpu_required:
                if (
                    used_vram + normalised.estimated_vram_bytes
                    > self.capacity.gpu_vram_bytes
                ):
                    return False
                if not self._gpu_compatible(normalised, active):
                    return False

            return True

    def _select_gpu_devices(
        self,
        request: RuntimeResourceRequest,
    ) -> tuple[int, ...]:
        if not request.gpu_required:
            return ()
        if request.gpu_device_ids:
            return request.gpu_device_ids
        return (0,)

    def _grant_locked(
        self,
        request: RuntimeResourceRequest,
    ) -> RuntimeResourceLease:
        now = self._clock()
        duration = min(
            request.lease_duration_seconds,
            self.lease_ttl_seconds,
        )
        lease = RuntimeResourceLease(
            lease_id=str(uuid.uuid4()),
            request_id=request.request_id,
            job_id=request.job_id,
            cpu_cores=request.cpu_cores,
            ram_bytes=request.ram_bytes,
            gpu_required=request.gpu_required,
            vram_bytes=request.estimated_vram_bytes,
            gpu_exclusive=request.gpu_exclusive,
            gpu_device_ids=self._select_gpu_devices(request),
            model_id=request.model_id,
            acquired_at=now,
            expires_at=now + duration,
            last_heartbeat_at=now,
            lease_duration_seconds=duration,
        )
        self._queued.pop(request.request_id, None)
        self._leases[lease.lease_id] = lease
        self._lease_by_request[request.request_id] = lease.lease_id
        self._request_states[request.request_id] = (
            ResourceRequestState.GRANTED
        )
        self._condition.notify_all()
        return lease

    def grant_ready(self) -> tuple[RuntimeResourceLease, ...]:
        """Grant highest-ranked ready requests that atomically fit now."""

        granted: list[RuntimeResourceLease] = []
        with self._condition:
            self._reap_expired_locked()

            while True:
                candidates = [
                    request
                    for request in self._queued.values()
                    if request.ready
                ]
                candidates.sort(
                    key=lambda item: (
                        -self._effective_priority(item),
                        item.submitted_at,
                        item.request_id,
                    )
                )

                selected = next(
                    (
                        candidate
                        for candidate in candidates
                        if self.can_fit(candidate)
                    ),
                    None,
                )
                if selected is None:
                    break
                granted.append(self._grant_locked(selected))

        return tuple(granted)

    def acquire(
        self,
        request: Any,
        *,
        timeout: float | None = None,
        poll_interval: float = 0.05,
        cancel: Any = None,
    ) -> RuntimeResourceLease:
        normalised = self.enqueue(request)
        effective_timeout = normalised.queue_timeout_seconds
        if timeout is not None:
            if timeout <= 0:
                raise ValueError("timeout must be positive.")
            effective_timeout = min(effective_timeout, float(timeout))
        deadline = self._clock() + effective_timeout

        with self._condition:
            while True:
                if cancel is not None and cancel.is_set():
                    self._queued.pop(normalised.request_id, None)
                    self._request_states[normalised.request_id] = (
                        ResourceRequestState.CANCELLED
                    )
                    self._condition.notify_all()
                    raise ResourceCancelled("Resource request cancelled.")

                self.grant_ready()
                lease_id = self._lease_by_request.get(normalised.request_id)
                if lease_id is not None:
                    return self._leases[lease_id]

                remaining = deadline - self._clock()
                if remaining <= 0:
                    self._queued.pop(normalised.request_id, None)
                    self._request_states[normalised.request_id] = (
                        ResourceRequestState.EXPIRED
                    )
                    self._condition.notify_all()
                    raise ResourceTimeout(
                        f"Timed out waiting for resources: {normalised.request_id}"
                    )

                self._condition.wait(timeout=min(poll_interval, remaining))

    def _owned_lease(
        self,
        lease_id: str,
        *,
        job_id: str | None = None,
        require_active: bool = False,
    ) -> RuntimeResourceLease:
        lease = self._leases.get(lease_id)
        if lease is None:
            raise ResourceError(f"Unknown lease: {lease_id}")
        if job_id is not None and lease.job_id != job_id:
            raise ResourceError(
                f"Lease {lease_id} is owned by a different job."
            )
        if require_active and not lease.active:
            raise ResourceError(f"Lease is not active: {lease_id}")
        return lease

    def heartbeat(
        self,
        lease_id: str,
        *,
        job_id: str | None = None,
    ) -> RuntimeResourceLease:
        with self._condition:
            self._reap_expired_locked()
            lease = self._owned_lease(
                lease_id,
                job_id=job_id,
                require_active=True,
            )
            now = self._clock()
            lease.last_heartbeat_at = now
            lease.expires_at = now + lease.lease_duration_seconds
            self._condition.notify_all()
            return lease

    def release(
        self,
        lease_id: str,
        *,
        job_id: str | None = None,
    ) -> bool:
        """Idempotently release an active lease owned by the same Job."""

        with self._condition:
            lease = self._leases.get(lease_id)
            if lease is None:
                return False
            if job_id is not None and lease.job_id != job_id:
                raise ResourceError(
                    f"Lease {lease_id} is owned by a different job."
                )
            if lease.state is LeaseState.RELEASED:
                return True
            if not lease.active:
                return False

            lease.state = LeaseState.RELEASED
            lease.released_at = self._clock()
            self._lease_by_request.pop(lease.request_id, None)
            self._condition.notify_all()
            return True

    def revoke(self, lease_id: str) -> bool:
        """Scheduler-side recovery path for an active lease."""

        with self._condition:
            lease = self._leases.get(lease_id)
            if lease is None:
                return False
            if lease.state is LeaseState.REVOKED:
                return True
            if not lease.active:
                return False

            lease.state = LeaseState.REVOKED
            lease.released_at = self._clock()
            self._lease_by_request.pop(lease.request_id, None)
            self._condition.notify_all()
            return True

    def _reap_expired_locked(self) -> tuple[str, ...]:
        now = self._clock()
        expired: list[str] = []
        for lease in self._leases.values():
            if lease.active and now >= lease.expires_at:
                lease.state = LeaseState.EXPIRED
                lease.released_at = now
                self._lease_by_request.pop(lease.request_id, None)
                expired.append(lease.lease_id)

        if expired:
            self._condition.notify_all()
        return tuple(expired)

    def reap_expired(self) -> tuple[str, ...]:
        with self._condition:
            return self._reap_expired_locked()
