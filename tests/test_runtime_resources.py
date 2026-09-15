from __future__ import annotations

import threading

import pytest

from reverend.runtime.hardware import GpuSnapshot, HardwareSnapshot
from reverend.runtime.resources import (
    LeaseState,
    ResourceBroker,
    ResourceCapacity,
    ResourceError,
    ResourceRejected,
    ResourceRequestState,
    RuntimeResourceRequest,
)


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def request(
    request_id: str,
    *,
    job_id: str | None = None,
    cpu: float = 1.0,
    ram: int = 0,
    gpu: bool = False,
    vram: int = 0,
    exclusive: bool = False,
    priority: int = 0,
    batchable: bool = False,
    model_id: str | None = None,
    submitted_at: float = 0.0,
    lease_duration: float = 120.0,
):
    return RuntimeResourceRequest(
        request_id=request_id,
        job_id=job_id or request_id,
        cpu_cores=cpu,
        ram_bytes=ram,
        gpu_required=gpu,
        estimated_vram_bytes=vram,
        gpu_exclusive=exclusive,
        priority=priority,
        batchable=batchable,
        model_id=model_id,
        submitted_at=submitted_at,
        lease_duration_seconds=lease_duration,
    )


def test_request_lifecycle_pending_then_granted():
    broker = ResourceBroker(
        ResourceCapacity(cpu_cores=1, ram_bytes=100),
    )
    broker.enqueue(request("job"))

    assert broker.request_state("job") is ResourceRequestState.PENDING

    lease = broker.grant_ready()[0]

    assert broker.request_state("job") is ResourceRequestState.GRANTED
    assert lease.job_id == "job"
    assert lease.active is True


def test_request_that_can_never_fit_is_rejected_without_partial_allocation():
    broker = ResourceBroker(
        ResourceCapacity(
            cpu_cores=2,
            ram_bytes=100,
            gpu_count=1,
            gpu_vram_bytes=50,
        ),
    )
    impossible = request(
        "too-large",
        cpu=1,
        gpu=True,
        vram=51,
    )

    with pytest.raises(ResourceRejected):
        broker.enqueue(impossible)

    assert (
        broker.request_state("too-large")
        is ResourceRequestState.REJECTED
    )
    assert broker.active_leases() == ()
    assert broker.queued_requests() == ()


def test_not_ready_request_remains_pending_until_scheduler_marks_ready():
    broker = ResourceBroker(
        ResourceCapacity(cpu_cores=1, ram_bytes=100),
    )
    pending = request("blocked")
    pending = RuntimeResourceRequest(
        **{
            **pending.__dict__,
            "ready": False,
        }
    )
    broker.enqueue(pending)

    assert broker.grant_ready() == ()
    assert broker.request_state("blocked") is ResourceRequestState.PENDING

    broker.set_ready("blocked", True)
    granted = broker.grant_ready()

    assert [lease.request_id for lease in granted] == ["blocked"]


def test_priority_queue_grants_highest_priority_first():
    broker = ResourceBroker(
        ResourceCapacity(cpu_cores=1, ram_bytes=100),
    )
    broker.enqueue(request("low", priority=1))
    broker.enqueue(request("high", priority=10))

    granted = broker.grant_ready()

    assert len(granted) == 1
    assert granted[0].request_id == "high"
    assert [item.request_id for item in broker.queued_requests()] == ["low"]


def test_priority_aging_prevents_indefinite_starvation():
    clock = Clock()
    broker = ResourceBroker(
        ResourceCapacity(cpu_cores=1, ram_bytes=100),
        aging_interval_seconds=10,
        clock=clock,
    )
    broker.enqueue(request("old", priority=0, submitted_at=0.0))
    clock.advance(35)
    broker.enqueue(request("new", priority=2, submitted_at=35.0))

    granted = broker.grant_ready()

    assert granted[0].request_id == "old"


def test_gpu_jobs_are_serialized_by_default():
    broker = ResourceBroker(
        ResourceCapacity(
            cpu_cores=4,
            ram_bytes=100,
            gpu_count=1,
            gpu_vram_bytes=100,
        )
    )
    broker.enqueue(request("a", gpu=True, vram=40, model_id="m"))
    broker.enqueue(request("b", gpu=True, vram=40, model_id="m"))

    first = broker.grant_ready()
    assert len(first) == 1
    assert len(broker.active_leases()) == 1

    assert broker.release(first[0].lease_id, job_id=first[0].job_id) is True
    second = broker.grant_ready()
    assert len(second) == 1
    assert second[0].request_id != first[0].request_id


def test_real_contention_waits_until_gpu_lease_is_released():
    broker = ResourceBroker(
        ResourceCapacity(
            cpu_cores=4,
            ram_bytes=100,
            gpu_count=1,
            gpu_vram_bytes=100,
        ),
    )
    first = broker.acquire(
        request("first", gpu=True, vram=80),
        timeout=1.0,
    )

    second_acquired = threading.Event()
    errors: list[Exception] = []

    def acquire_second() -> None:
        try:
            lease = broker.acquire(
                request("second", gpu=True, vram=80),
                timeout=1.0,
            )
            second_acquired.set()
            broker.release(lease.lease_id, job_id=lease.job_id)
        except Exception as exc:  # pragma: no cover - assertion reports it
            errors.append(exc)
            second_acquired.set()

    thread = threading.Thread(target=acquire_second)
    thread.start()

    assert second_acquired.wait(0.05) is False
    assert len(broker.active_leases()) == 1

    broker.release(first.lease_id, job_id=first.job_id)
    assert second_acquired.wait(1.0) is True
    thread.join(timeout=1.0)

    assert errors == []
    assert broker.active_leases() == ()


def test_exclusive_gpu_lease_blocks_competing_gpu_access():
    broker = ResourceBroker(
        ResourceCapacity(
            cpu_cores=4,
            ram_bytes=100,
            gpu_count=1,
            gpu_vram_bytes=100,
        ),
        allow_same_model_gpu_sharing=True,
    )
    broker.enqueue(
        request(
            "exclusive",
            gpu=True,
            vram=30,
            exclusive=True,
            batchable=True,
            model_id="m",
            priority=10,
        )
    )
    broker.enqueue(
        request(
            "shared",
            gpu=True,
            vram=30,
            batchable=True,
            model_id="m",
        )
    )

    granted = broker.grant_ready()
    assert len(granted) == 1
    assert granted[0].request_id == "exclusive"
    assert [item.request_id for item in broker.queued_requests()] == ["shared"]


def test_same_model_gpu_sharing_requires_explicit_support():
    broker = ResourceBroker(
        ResourceCapacity(
            cpu_cores=4,
            ram_bytes=100,
            gpu_count=1,
            gpu_vram_bytes=100,
        ),
        allow_same_model_gpu_sharing=True,
    )
    broker.enqueue(
        request("a", gpu=True, vram=30, batchable=True, model_id="m")
    )
    broker.enqueue(
        request("b", gpu=True, vram=30, batchable=True, model_id="m")
    )

    granted = broker.grant_ready()

    assert {item.request_id for item in granted} == {"a", "b"}


def test_different_models_do_not_share_gpu_even_when_sharing_is_enabled():
    broker = ResourceBroker(
        ResourceCapacity(
            cpu_cores=4,
            ram_bytes=100,
            gpu_count=1,
            gpu_vram_bytes=100,
        ),
        allow_same_model_gpu_sharing=True,
    )
    broker.enqueue(
        request("a", gpu=True, vram=30, batchable=True, model_id="m1")
    )
    broker.enqueue(
        request("b", gpu=True, vram=30, batchable=True, model_id="m2")
    )

    assert len(broker.grant_ready()) == 1
    assert len(broker.queued_requests()) == 1


def test_atomic_allocation_never_partially_reserves_gpu():
    broker = ResourceBroker(
        ResourceCapacity(
            cpu_cores=2,
            ram_bytes=100,
            gpu_count=1,
            gpu_vram_bytes=100,
        )
    )

    broker.enqueue(request("cpu-holder", cpu=1.5, priority=20))
    holder = broker.grant_ready()[0]

    broker.enqueue(
        request(
            "blocked-bundle",
            cpu=1.0,
            gpu=True,
            vram=80,
            priority=10,
        )
    )
    broker.enqueue(
        request(
            "fits",
            cpu=0.5,
            gpu=True,
            vram=80,
            priority=1,
        )
    )

    granted = broker.grant_ready()

    assert [lease.request_id for lease in granted] == ["fits"]
    assert [item.request_id for item in broker.queued_requests()] == [
        "blocked-bundle"
    ]
    assert holder.active is True


def test_expired_lease_recovers_capacity():
    clock = Clock()
    broker = ResourceBroker(
        ResourceCapacity(
            cpu_cores=1,
            ram_bytes=100,
            gpu_count=1,
            gpu_vram_bytes=100,
        ),
        lease_ttl_seconds=10,
        clock=clock,
    )

    broker.enqueue(
        request(
            "first",
            gpu=True,
            vram=100,
            lease_duration=10,
        )
    )
    first = broker.grant_ready()[0]
    broker.enqueue(request("second", gpu=True, vram=100))

    clock.advance(11)
    expired = broker.reap_expired()
    second = broker.grant_ready()[0]

    assert expired == (first.lease_id,)
    assert first.state is LeaseState.EXPIRED
    assert second.request_id == "second"


def test_heartbeat_extends_lease_lifetime():
    clock = Clock()
    broker = ResourceBroker(
        ResourceCapacity(cpu_cores=1, ram_bytes=100),
        lease_ttl_seconds=10,
        clock=clock,
    )
    broker.enqueue(request("job", lease_duration=10))
    lease = broker.grant_ready()[0]

    clock.advance(8)
    broker.heartbeat(lease.lease_id, job_id="job")
    clock.advance(5)

    assert broker.reap_expired() == ()
    assert lease.state is LeaseState.ACTIVE
    assert broker.release(lease.lease_id, job_id="job") is True
    assert lease.state is LeaseState.RELEASED


def test_release_is_idempotent_and_lease_is_non_transferable():
    broker = ResourceBroker(
        ResourceCapacity(cpu_cores=1, ram_bytes=100),
    )
    lease = broker.acquire(request("job-1"), timeout=1.0)

    with pytest.raises(ResourceError, match="different job"):
        broker.release(lease.lease_id, job_id="job-2")

    assert broker.release(lease.lease_id, job_id="job-1") is True
    assert broker.release(lease.lease_id, job_id="job-1") is True
    assert lease.state is LeaseState.RELEASED


def test_revoke_recovers_resources_and_is_idempotent():
    broker = ResourceBroker(
        ResourceCapacity(cpu_cores=1, ram_bytes=100),
    )
    lease = broker.acquire(request("job"), timeout=1.0)

    assert broker.revoke(lease.lease_id) is True
    assert broker.revoke(lease.lease_id) is True
    assert lease.state is LeaseState.REVOKED
    assert broker.active_leases() == ()



def test_capacity_uses_total_hardware_minus_reserve_not_current_free():
    snapshot = HardwareSnapshot(
        captured_at=1.0,
        cpu_logical_cores=8,
        ram_total_bytes=32_000,
        ram_available_bytes=2_000,
        gpus=(
            GpuSnapshot(
                index=0,
                name="GPU",
                memory_total_bytes=8_000,
                memory_used_bytes=7_000,
                memory_free_bytes=1_000,
                utilization_percent=0.0,
            ),
        ),
    )

    capacity = ResourceCapacity.from_hardware(
        snapshot,
        ram_reserve_bytes=1_000,
        vram_reserve_bytes=500,
    )

    assert capacity.cpu_cores == 8
    assert capacity.ram_bytes == 31_000
    assert capacity.gpu_vram_bytes == 7_500
