from __future__ import annotations

from reverend.runtime.leased_scheduler import LeasedModelScheduler
from reverend.runtime.models import ModelRegistry, ModelRole, ModelSpec
from reverend.runtime.resources import ResourceBroker, ResourceCapacity


class Provider:
    def list_models(self):
        return []


class BaseScheduler:
    def __init__(self, registry):
        self.registry = registry
        self.provider = Provider()
        self.calls = []

    def generate(self, role, prompt, **kwargs):
        self.calls.append(("generate", role, prompt, kwargs))
        return {"response": "ok"}

    def stream(self, role, prompt, **kwargs):
        self.calls.append(("stream", role, prompt, kwargs))
        yield {"response": "ok", "done": True}

    def embed(self, texts):
        self.calls.append(("embed", texts))
        return [[1.0] for _ in texts]


def registry_for(spec):
    return ModelRegistry(Provider(), specs={spec.role: spec})


def test_request_for_role_maps_model_resource_profile_to_job():
    spec = ModelSpec(
        role=ModelRole.STRONG_CODE,
        model="model:30b",
        context=16384,
        think=False,
        keep_alive="5m",
        description="strong",
        exclusive_memory=True,
        estimated_ram_bytes=100,
        estimated_vram_bytes=80,
        gpu_required=True,
    )
    base = BaseScheduler(registry_for(spec))
    leased = LeasedModelScheduler(
        base,
        ResourceBroker(
            ResourceCapacity(
                cpu_cores=2,
                ram_bytes=1000,
                gpu_count=1,
                gpu_vram_bytes=1000,
            )
        ),
    )

    request = leased.request_for_role(
        ModelRole.STRONG_CODE,
        job_id="job-1",
        priority=7,
    )

    assert request.job_id == "job-1"
    assert request.owner == "job-1"
    assert request.priority == 7
    assert request.ram_bytes == 100
    assert request.estimated_vram_bytes == 80
    assert request.gpu_required is True
    assert request.gpu_exclusive is True
    assert request.batchable is False
    assert request.model_id == "model:30b"


def test_generate_releases_lease_after_model_call():
    spec = ModelSpec(
        role=ModelRole.FAST_GENERAL,
        model="small",
        context=4096,
        think=False,
        keep_alive="5m",
        description="small",
    )
    base = BaseScheduler(registry_for(spec))
    broker = ResourceBroker(
        ResourceCapacity(cpu_cores=2, ram_bytes=1000),
    )
    leased = LeasedModelScheduler(base, broker)

    result = leased.generate(
        ModelRole.FAST_GENERAL,
        "hello",
        job_id="job-1",
    )

    assert result["response"] == "ok"
    assert broker.active_leases() == ()
    assert base.calls[0][0] == "generate"


def test_stream_holds_then_releases_lease():
    spec = ModelSpec(
        role=ModelRole.FAST_GENERAL,
        model="small",
        context=4096,
        think=False,
        keep_alive="5m",
        description="small",
    )
    base = BaseScheduler(registry_for(spec))
    broker = ResourceBroker(
        ResourceCapacity(cpu_cores=2, ram_bytes=1000),
    )
    leased = LeasedModelScheduler(base, broker)

    chunks = list(
        leased.stream(
            ModelRole.FAST_GENERAL,
            "hello",
            job_id="job-1",
        )
    )

    assert chunks[-1]["done"] is True
    assert broker.active_leases() == ()
