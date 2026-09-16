# M-VNEXT-03 — Compute + Model Runtime

**Branch:** `vnext/compute-model`
**Frozen contract:** `wave1-v1`
**Pre-Wave-1 product baseline:** `072c418cd5371a25a29ad6282356e22b5ecc4d22`
**Integration target:** `vnext/integration`

## Status

Implementation is complete for the branch-owned foundation. Portable CI and the required
target-machine Ollama/residency smoke are the acceptance gates before
`READY_FOR_INTEGRATION`.

## Audit before implementation

The accepted product already contained a functioning local runtime:

- `runtime/models.py`: logical roles, `ModelSpec`, `ModelRegistry`, installed-model
  inventory and M14 inventory caching;
- `runtime/providers.py`: local-only Ollama discovery, generation, streaming, embedding,
  loaded-model discovery and unload;
- `runtime/scheduler.py`: a cross-process `fcntl` model lock, exclusive-memory policy,
  heavyweight model unload behavior and queue/provider timing;
- M14 runtime benchmarks and M16 residency hardening;
- retained live benchmark evidence for `qwen3.5:4b` and `qwen3-coder:30b`.

The implementation therefore extends these seams. It does not create a parallel inference
provider or remove the accepted coarse scheduler lock.

## Frozen-contract reconciliation

The worker originally branched from the audited product baseline, matching the concurrent
observability branch. When `vnext/integration` published the frozen Wave-1 contracts, the
contract baseline was synchronized into this branch before relying on shared semantics.

The authoritative contract requires:

- atomic ResourceRequest allocation;
- explicit Job ownership;
- bounded ResourceLease lifetime;
- released/expired/revoked lease states;
- idempotent release;
- active matching lease before heavy GPU work;
- evolution of the existing ModelSpec rather than a shadow type.

`RuntimeResourceRequest` and `RuntimeResourceLease` are deliberately named normalized
runtime views/adapters. They do not claim to be a second cross-subsystem authority. The
Runtime Kernel Job adapter remains owned by M-VNEXT-01.

## Implemented foundation

### Model registry/profile

The existing `ModelSpec` now supports additive:

- stable logical identity;
- provider/runtime binding;
- capabilities and trust profile;
- configured/context limits;
- estimated RAM/VRAM/runtime profile;
- GPU requirement/exclusive-memory policy;
- lifecycle/residency policy;
- profile version;
- benchmark references.

`ModelRegistry.profile()` combines this configuration with provider truth. Ollama
installed-vs-loaded state maps to COLD/HOT (or PINNED when explicitly configured).
STAGED exists only as a conceptual state for providers that genuinely expose staging;
Reverend does not invent a staged Ollama state.

### Measured provider/runtime state

`OllamaProvider.loaded_model_info()` parses `/api/ps` for:

- loaded model size;
- loaded VRAM bytes;
- loaded context length;
- expiry;
- provider metadata.

Local hardware snapshots collect:

- logical CPU count;
- total/available RAM;
- NVIDIA GPU total/used/free VRAM and utilization when `nvidia-smi` is available.

Missing `nvidia-smi` degrades truthfully to CPU-only visibility.

### Atomic resource broker

The rule-based broker provides:

- CPU + RAM + GPU + VRAM all-or-nothing fit checks;
- deterministic rejection of requests that can never fit configured capacity;
- request lifecycle tracking;
- priority ordering;
- bounded priority aging;
- readiness/resource-fit backfilling;
- default GPU serialization;
- exclusive GPU leases;
- optional same-model sharing only when the runtime explicitly enables it and both jobs
  declare batchability;
- no speculative GPU overcommit.

### Lease lifecycle and recovery

A lease records:

- originating request;
- owning Job;
- concrete accounted CPU/RAM/GPU/VRAM;
- GPU device IDs;
- acquired/expiry/heartbeat times;
- active/released/expired/revoked state.

Heartbeats extend only active leases. Release is idempotent. Ownership checks prevent a
different Job from releasing/heartbeating a lease. Expiry and scheduler revocation recover
capacity.

### Inference compatibility

`LeasedModelScheduler` obtains the atomic lease before entering the existing
`ModelScheduler` path. The proven cross-process file lock remains the safety fallback.
Current inference APIs are therefore not replaced.

The adapter releases leases in `finally` for generation, streaming and embedding, and
maintains a bounded heartbeat while the provider call runs.

## Target hardware evidence retained

The retained `qwen3-coder:30b` 16K benchmark reports approximately 6.2 GB provider-loaded
VRAM on the RTX 5070 Laptop GPU and a large system-RAM footprint. The production profile
therefore keeps 16K and exclusive memory rather than increasing context or enabling
concurrent heavyweight models speculatively.

The retained `qwen3.5:4b` 8K benchmark reports approximately 3.34 GB loaded VRAM. Shared
same-model execution remains disabled by default because Ollama does not currently expose
a Reverend-controlled batching guarantee.

## Branch-owned acceptance coverage

Tests cover:

- model registration/profile compatibility;
- provider loaded-memory metadata;
- portable hardware measurement;
- ResourceRequest validation/rejection;
- request lifecycle;
- priority and aging;
- real threaded contention;
- GPU serialization;
- exclusive GPU blocking;
- same-model sharing guard;
- different-model incompatibility;
- atomic bundle allocation/no partial GPU reservation;
- heartbeat and expiry recovery;
- non-transferable ownership;
- idempotent release;
- revocation recovery;
- lease-aware model execution and cleanup;
- existing runtime model/provider/scheduler regression suites through repository CI.

## Integration seams

The following are intentionally deferred to their owning branches:

- M-VNEXT-01 supplies authoritative Runtime Kernel Job identity and durable lease references;
- M-VNEXT-02 consumes resource/model trace and metric hooks;
- M-VNEXT-05 binds specialists through logical registry interfaces.

No worker-owned change is required to the shared contract semantics for these seams.

## Required final gate

Before integration:

1. portable PR CI must pass;
2. relevant M14/M16 portable validation must remain green;
3. run targeted live Ollama/residency smoke on the actual WSL2/RTX 5070 workstation;
4. integrate into `vnext/integration`, never directly into `main`;
5. run the cross-subsystem Wave-1 gates after integration.

No automatic merge, tag or release is part of this branch.
