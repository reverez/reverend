"""Lease-aware adapter around the existing local model scheduler."""

from __future__ import annotations

import threading
import uuid
from collections.abc import Iterator
from typing import Any

from .models import ModelRole
from .resources import (
    ResourceBroker,
    RuntimeResourceLease,
    RuntimeResourceRequest,
)
from .scheduler import ModelScheduler


class LeasedModelScheduler:
    """Require an atomic resource lease before entering the legacy model lock.

    The wrapped ModelScheduler remains the cross-process serialization boundary and
    preserves current inference behavior. New vNext callers gain queue/lease semantics
    without replacing that proven path.
    """

    def __init__(
        self,
        scheduler: ModelScheduler,
        broker: ResourceBroker,
    ) -> None:
        self.scheduler = scheduler
        self.broker = broker

    @property
    def provider(self):
        return self.scheduler.provider

    @property
    def registry(self):
        return self.scheduler.registry

    def request_for_role(
        self,
        role: ModelRole,
        *,
        job_id: str,
        priority: int = 0,
        cpu_cores: float = 1.0,
        ram_bytes: int | None = None,
        estimated_vram_bytes: int | None = None,
        gpu_exclusive: bool | None = None,
        ready: bool = True,
    ) -> RuntimeResourceRequest:
        spec = self.registry.spec(role)
        return RuntimeResourceRequest(
            request_id=str(uuid.uuid4()),
            job_id=job_id,
            cpu_cores=cpu_cores,
            ram_bytes=(
                spec.estimated_ram_bytes
                if ram_bytes is None
                else ram_bytes
            ),
            gpu_required=spec.gpu_required,
            estimated_vram_bytes=(
                self.registry.estimated_vram_bytes(role)
                if estimated_vram_bytes is None
                else estimated_vram_bytes
            ),
            gpu_exclusive=(
                spec.exclusive_memory
                if gpu_exclusive is None
                else gpu_exclusive
            ),
            estimated_runtime_seconds=spec.estimated_runtime_seconds,
            priority=priority,
            preemptible=False,
            # Ollama does not currently expose a Reverend-controlled batching
            # contract, so model calls are not marked batchable.
            batchable=False,
            model_id=spec.model,
            ready=ready,
        )

    def _start_heartbeat(
        self,
        lease: RuntimeResourceLease,
    ) -> tuple[threading.Event, threading.Thread]:
        stop = threading.Event()
        interval = max(
            0.05,
            min(30.0, self.broker.lease_ttl_seconds / 3.0),
        )

        def beat() -> None:
            while not stop.wait(interval):
                try:
                    self.broker.heartbeat(lease.lease_id, job_id=lease.job_id)
                except Exception:
                    return

        thread = threading.Thread(
            target=beat,
            name=f"reverend-lease-{lease.lease_id[:8]}",
            daemon=True,
        )
        thread.start()
        return stop, thread

    def _acquire(
        self,
        role: ModelRole,
        *,
        job_id: str,
        priority: int,
        timeout: float,
        cancel: Any = None,
    ) -> RuntimeResourceLease:
        request = self.request_for_role(
            role,
            job_id=job_id,
            priority=priority,
        )
        return self.broker.acquire(
            request,
            timeout=timeout,
            cancel=cancel,
        )

    def generate(
        self,
        role: ModelRole,
        prompt: str,
        *,
        job_id: str,
        priority: int = 0,
        resource_timeout: float = 300.0,
        cancel: Any = None,
        **kwargs: Any,
    ):
        lease = self._acquire(
            role,
            job_id=job_id,
            priority=priority,
            timeout=resource_timeout,
            cancel=cancel,
        )
        stop, thread = self._start_heartbeat(lease)
        try:
            return self.scheduler.generate(
                role,
                prompt,
                **kwargs,
            )
        finally:
            stop.set()
            thread.join(timeout=0.2)
            self.broker.release(lease.lease_id, job_id=lease.job_id)

    def stream(
        self,
        role: ModelRole,
        prompt: str,
        *,
        job_id: str,
        priority: int = 0,
        resource_timeout: float = 300.0,
        cancel: Any = None,
        **kwargs: Any,
    ) -> Iterator[dict[str, Any]]:
        lease = self._acquire(
            role,
            job_id=job_id,
            priority=priority,
            timeout=resource_timeout,
            cancel=cancel,
        )
        stop, thread = self._start_heartbeat(lease)
        try:
            yield from self.scheduler.stream(
                role,
                prompt,
                cancel=cancel,
                **kwargs,
            )
        finally:
            stop.set()
            thread.join(timeout=0.2)
            self.broker.release(lease.lease_id, job_id=lease.job_id)

    def embed(
        self,
        texts: list[str],
        *,
        job_id: str,
        priority: int = 0,
        resource_timeout: float = 300.0,
    ) -> list[list[float]]:
        lease = self._acquire(
            ModelRole.EMBED,
            job_id=job_id,
            priority=priority,
            timeout=resource_timeout,
        )
        stop, thread = self._start_heartbeat(lease)
        try:
            return self.scheduler.embed(texts)
        finally:
            stop.set()
            thread.join(timeout=0.2)
            self.broker.release(lease.lease_id, job_id=lease.job_id)
