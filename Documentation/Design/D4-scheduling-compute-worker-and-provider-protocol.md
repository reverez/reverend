# D4 — Scheduling, Compute, Worker & Provider Protocol

> **Status:** DESIGN ACCEPTED FOR DEVELOPMENT  
> **Depends on:** A6, A10, A11, A12, D0, D1, D3  
> **Purpose:** Define the distributed execution fabric: Workflow Scheduler, Compute Scheduler, ComputeNode Registry, ResourceRequest/Lease, authenticated worker protocol, RunPod adapter, vLLM boundary, and scale-to-zero behavior.

---

## 1. Separation of Responsibilities

Cloud v1 contains four distinct components:

~~~text
Workflow Scheduler
  decides WHAT is ready

Compute Scheduler
  decides WHERE admitted work can run

Capacity Controller
  decides WHETHER infrastructure must start/stop

Executor / Worker
  performs the admitted operation
~~~

None owns Project/Run truth independently.

---

## 2. Workflow Scheduler

Input:

- active Run slot;
- Task DAG;
- Task statuses;
- approvals;
- budgets;
- required Artifacts;
- emergency controls.

Output:

- Tasks/Jobs eligible for READY/QUEUED execution.

The scheduler may run as a PostgreSQL-advisory-lock leader.

Wake signals:

- new Run;
- Job completion;
- approval;
- checkpoint;
- compute-state change;
- database notification.

Durable state is always re-read before transition.

---

## 3. Compute Scheduler

Input:

~~~text
Job
ResourceRequest
ModelRequirement
eligible ModelProfiles
ComputeNodes
active ResourceLeases
budget state
trust requirement
~~~

Output:

- grant on compatible node;
- remain queued;
- request Capacity Controller action;
- reject as impossible/policy denied.

Eligibility precedes optimization.

---

## 4. Placement Filters

Exclude node if any required dimension fails:

- wrong lifecycle state;
- stale heartbeat;
- insufficient trust class;
- insufficient CPU/RAM;
- insufficient GPU/VRAM;
- unsupported runtime;
- unavailable model profile;
- missing sandbox/network capability;
- conflict with exclusive lease;
- cost/budget admission failure.

Only eligible nodes are ranked.

---

## 5. Placement Ranking

Initial deterministic ranking:

1. required model already resident;
2. lower expected startup/load delay;
3. lower estimated cost;
4. higher safe VRAM headroom;
5. data/workspace locality;
6. lower utilization;
7. queue/critical-path priority.

Do not build a learned scheduler in v1.

Persist a structured decision reason.

---

## 6. ResourceRequest v1

~~~json
{
  "schema_version": 1,
  "request_id": "...",
  "job_id": "...",
  "cpu_cores": 2.0,
  "ram_bytes": 8589934592,
  "accelerators": [
    {
      "type": "nvidia_gpu",
      "count": 1,
      "min_vram_bytes": 80000000000,
      "capabilities": ["cuda"],
      "exclusive": true
    }
  ],
  "runtime_requirements": ["vllm"],
  "trust_requirement": "COMMUNITY_CLOUD_WORKER",
  "network_policy": "worker_private",
  "estimated_runtime_seconds": 300,
  "priority": 50,
  "request_class": "interactive",
  "preemptibility": "SAFE_AT_BOUNDARY",
  "batchable": false,
  "cost_ceiling_gbp": 1.0,
  "lease_duration_seconds": 120,
  "queue_timeout_seconds": 900
}
~~~

Existing RuntimeResourceRequest remains a local compatibility adapter.

---

## 7. ResourceLease v1

~~~json
{
  "schema_version": 1,
  "lease_id": "...",
  "request_id": "...",
  "job_id": "...",
  "node_id": "...",
  "runtime_epoch_id": "...",
  "granted_resources": {},
  "state": "ACTIVE",
  "acquired_at": "...",
  "expires_at": "...",
  "last_heartbeat_at": "..."
}
~~~

Properties:

- atomic;
- Job-owned;
- non-transferable;
- time-bounded;
- heartbeat-renewed;
- revocable;
- idempotently releasable.

---

## 8. Lease Heartbeat

Initial configuration target:

~~~text
lease TTL      120 seconds
heartbeat      every 30 seconds
~~~

Configuration may change.

If heartbeat expires:

- lease becomes EXPIRED;
- capacity is reconciled;
- Job becomes interrupted/recoverable;
- stale process cannot commit authoritative success without current lease/epoch validation.

---

## 9. Runtime Epoch

Each control-plane boot creates runtime_epoch_id.

Lease and worker session include the epoch.

Old-epoch result:

- may be stored as diagnostic evidence;
- may not transition a current Job to success without recovery/reconciliation.

This blocks zombie workers after restart.

---

## 10. ComputeNode v1

Worker registration normalizes:

~~~json
{
  "schema_version": 1,
  "node_id": "...",
  "provider": "runpod",
  "provider_instance_id": "...",
  "trust_class": "COMMUNITY_CLOUD_WORKER",
  "cpu": {"cores": 16},
  "ram_bytes": 134217728000,
  "accelerators": [
    {
      "type": "nvidia_gpu",
      "model": "A100 SXM",
      "count": 1,
      "vram_bytes": 85899345920,
      "capabilities": ["cuda", "bf16"]
    }
  ],
  "runtimes": [
    {
      "type": "vllm",
      "version": "...",
      "profiles": ["qwen3.8-27b-a100-64k-v1"]
    }
  ],
  "resident_models": [],
  "worker_version": "...",
  "container_digest": "sha256:..."
}
~~~

Server sets/validates trust class from launch policy.

Worker does not self-promote.

---

## 11. Worker Network Direction

Prefer worker-initiated outbound HTTPS to the persistent Control Plane.

Benefits:

- no public worker port;
- no direct raw runtime exposure;
- simpler NAT/firewall;
- vLLM remains loopback/private;
- worker replacement is straightforward.

---

## 12. Bootstrap Credential

Capacity Controller creates a one-time bootstrap secret bound to:

- expected provider instance;
- intended worker profile;
- intended trust class;
- expiry.

Properties:

~~~text
random >= 256 bits
stored hashed server-side
single use
~10 minute validity
~~~

Injected through provider startup configuration.

---

## 13. Worker Registration

### POST /internal/v1/workers/register

Worker submits:

~~~json
{
  "bootstrap_token": "...",
  "provider_instance_id": "...",
  "worker_version": "...",
  "capabilities": {},
  "runtime_profiles": []
}
~~~

Server:

1. validates token/expiry/unused state;
2. verifies expected provider instance;
3. assigns node_id;
4. normalizes capabilities;
5. consumes bootstrap credential;
6. issues short-lived worker session.

---

## 14. Worker Session

Bound to:

~~~text
node_id
runtime_epoch_id
allowed internal endpoints
expiry
~~~

Initial target validity:

~~~text
15 minutes
~~~

Worker renews while healthy.

Revoke on:

- drain/terminate;
- heartbeat loss;
- epoch change;
- provider mismatch;
- emergency stop.

---

## 15. Worker Heartbeat

### POST /internal/v1/workers/{node_id}/heartbeat

Payload:

~~~json
{
  "runtime_epoch_id": "...",
  "health": "ready",
  "resource_telemetry": {
    "cpu_used": 1.4,
    "ram_used_bytes": 12000000000,
    "gpu": {
      "utilization": 0.0,
      "vram_used_bytes": 60000000000
    }
  },
  "resident_models": ["qwen3.8-27b-a100-64k-v1"],
  "active_lease_ids": []
}
~~~

Control Plane normalizes/stores telemetry.

A worker cannot create leases by merely reporting them.

---

## 16. Assignment Delivery

Cloud v1 uses long-poll retrieval.

### GET /internal/v1/workers/{node_id}/assignments/next?wait=25

Response:

~~~json
{"assignment": null}
~~~

or:

~~~json
{
  "assignment": {
    "job_id": "...",
    "lease_id": "...",
    "executor_type": "inference",
    "payload_ref": "...",
    "deadline": "..."
  }
}
~~~

Scheduler has already assigned the Job/lease.

Worker cannot claim arbitrary queued Jobs.

---

## 17. Assignment ACK

### POST /internal/v1/workers/{node_id}/assignments/{job_id}/ack

Server validates:

- active current-epoch lease;
- assignment to same node;
- worker session;
- Job still runnable;
- no cancellation/revocation.

Then execution may begin.

---

## 18. Result Submission

### POST /internal/v1/workers/{node_id}/jobs/{job_id}/result

Contains:

- lease_id;
- runtime_epoch_id;
- outcome;
- bounded metrics;
- Artifact/result refs;
- error classification.

Server revalidates current Job/lease.

Late/zombie results cannot overwrite a newer attempt.

---

## 19. vLLM Boundary

On GPU worker:

~~~text
Reverend Worker Agent
        ↓
localhost/private call
        ↓
vLLM
        ↓
Qwen3.8-27B
~~~

vLLM is not externally routed.

Worker adapter owns:

- request formatting;
- model readiness;
- cancellation;
- timeout;
- token accounting;
- response sanitization;
- runtime metrics.

The persistent Control Plane speaks Reverend worker protocol, not raw vLLM.

---

## 20. InferenceRuntime Interface

~~~text
health()
profiles()
ensure_loaded(profile_id)
generate(request)
stream(request)
embed(request)
cancel(invocation_id)
metrics()
~~~

Capabilities are advertised.

Not every runtime implements every method.

Ollama remains local adapter.

SGLang can implement the same interface later.

---

## 21. ComputeProvider Interface

~~~text
provision(profile, bootstrap_spec)
inspect(provider_instance_id)
start(provider_instance_id)
stop(provider_instance_id)
terminate(provider_instance_id)
estimate_rate(profile)
list_available_profiles()
~~~

Only Capacity Controller mutates provider lifecycle.

Provider adapter never receives Agent prompts.

---

## 22. RunPod Adapter

Inputs:

- GPU profile;
- container image;
- storage profile;
- one-time bootstrap secret;
- region preference;
- provider RateSnapshot.

Outputs:

- provider_instance_id;
- actual lifecycle;
- region;
- hardware metadata;
- billing metadata.

RunPod API credential is resolved through Secret Broker only inside provider adapter action.

---

## 23. Baseline Deployment Profile

Profile ID example:

~~~text
qwen3.8-27b-a100sxm80-vllm-64k-v1
~~~

Profile records:

~~~json
{
  "provider_class": "runpod_community",
  "gpu_class": "A100_SXM_80GB",
  "runtime": "vllm",
  "model": "Qwen/Qwen3.8-27B",
  "model_revision": "<pinned>",
  "quantization": "reference/native",
  "max_context_tokens": 65536,
  "trust_class": "COMMUNITY_CLOUD_WORKER",
  "container_digest": "sha256:...",
  "reverendbench_profile": "baseline"
}
~~~

Pin actual revision/digest during C7 live validation.

---

## 24. Model Loading State

Separate:

~~~text
PROVIDER_RUNNING
WORKER_REGISTERING
RUNTIME_READY
MODEL_LOADING
NODE_READY
~~~

Do not grant inference lease until functional smoke health passes.

---

## 25. Zero-GPU State

Zero GPU workers is normal.

When a GPU Job becomes READY and no node fits:

~~~text
Compute Scheduler
→ Capacity Controller
→ RunPod
→ worker bootstrap
→ registration
→ model load
→ lease
~~~

The Control Plane remains online throughout.

---

## 26. Capacity Lifecycle

Conceptual states:

~~~text
ABSENT
PROVISIONING
BOOTING
REGISTERING
LOADING
READY
BUSY
IDLE_GRACE
DRAINING
STOPPING
STOPPED
TERMINATED
UNHEALTHY
~~~

Provider state is reconciled against RunPod API.

Local desired state alone is insufficient.

---

## 27. Idle Grace

Initial Design default:

~~~text
REVEREND_GPU_IDLE_GRACE_SECONDS = 420
~~~

Seven minutes lies within A12's accepted 5–10 minute range.

Eligibility:

- no active leases;
- no immediately runnable compatible GPU Job;
- no resume-next demand;
- no shutdown inhibitor;
- required state/metrics safe.

Then enter DRAINING.

---

## 28. Draining

DRAINING:

- accepts no new lease;
- waits for safe action completion;
- persists metrics/results;
- ensures no worker-unique project progress;
- revokes worker session;
- stops/terminates provider resource.

Disposable GPU worker shutdown does not require full Control Plane RecoveryGeneration.

---

## 29. CPU Execution

Low-risk bounded internal work may initially run on control host only if strict isolation/resource limits prove it cannot threaten authority.

Heavy/untrusted work uses dedicated sandbox worker.

Future CPU worker uses same registration/assignment/lease protocol.

Do not keep GPU worker active for unrelated CPU-only work.

---

## 30. Internal Parallelism

One active top-level Run may still execute:

- CPU research/indexing;
- tests/builds;
- inference;
- independent verification;

concurrently when dependencies/resources allow.

Mutation conflicts serialize regardless of spare compute.

---

## 31. Batching

Initial conservative policy:

~~~text
batchable = false
~~~

for autonomous interactive generation until ReverendBench validates controlled same-model concurrency.

Later deployment profiles may opt in.

---

## 32. Provider Failure

If RunPod instance disappears:

1. provider reconciliation marks node UNREACHABLE;
2. leases expire/revoke;
3. Job becomes interrupted/recoverable;
4. worker credential is invalid;
5. D5 recovery classifies current operation;
6. Capacity Controller may provision replacement.

Run authority remains on persistent Control Plane.

---

## 33. Scheduling Event

Emit structured event:

~~~json
{
  "job_id": "...",
  "request_id": "...",
  "decision": "placed",
  "node_id": "...",
  "eligible_profiles": ["..."],
  "reasons": [
    "trust_satisfied",
    "model_resident",
    "vram_sufficient"
  ],
  "estimated_cost_gbp": 0.08
}
~~~

This is observability data, not private reasoning.

---

## 34. Metrics

Capture:

- READY-to-lease wait;
- provider provisioning;
- worker registration;
- model load;
- inference;
- lease duration;
- GPU utilization;
- VRAM;
- provider billed interval;
- idle grace;
- drain time.

These feed D8 and ReverendBench.

---

## 35. Acceptance Tests

Must prove:

- no node fit → Job remains queued / capacity requested;
- trust mismatch rejects Community worker;
- atomic request never partially grants;
- lease expiry recovers capacity;
- stale-epoch result cannot succeed current Job;
- worker cannot claim another node's assignment;
- bootstrap secret expires/one-time;
- raw vLLM not public;
- zero-GPU provisioning works;
- idle drain works;
- control API remains available at zero GPU;
- worker loss creates recoverable Job;
- CPU-only work does not retain GPU lease.

---

## 36. Exit Condition

C7 is ready when Reverend can provision one A100 SXM worker from zero, authenticate/register it, load a pinned vLLM/Qwen profile, grant a Job-owned lease, execute one inference Job, collect metrics, release, drain/stop, and recover correctly from worker disappearance.


---

## 37. Recursive Architecture Hardening — Worker Data Plane and Lease Atomicity

The original worker protocol defined assignment control but left payload/blob transfer and several race conditions implicit. Cloud v1 freezes the following additional contract.

### Job-scoped worker data plane

Workers never receive filesystem paths into Control Plane storage.

For an assigned Job, the Control Plane issues short-lived, job-scoped data capabilities for only the referenced inputs and outputs.

Conceptual endpoints:

~~~text
GET  /internal/v1/workers/{node_id}/jobs/{job_id}/inputs/{ref}
POST /internal/v1/workers/{node_id}/jobs/{job_id}/outputs
~~~

Every transfer validates:

- current worker session;
- current runtime epoch;
- assigned node;
- active lease;
- Job identity;
- Artifact/Blob allowlist;
- maximum bytes/media type;
- expected hash where known.

Output upload is:

~~~text
stream to bounded temporary object
→ compute SHA-256
→ verify declared size/type
→ publish to BlobStore
→ return opaque BlobRef
~~~

A worker may not choose an arbitrary `content_ref` or server path.

### Assignment delivery is idempotent

Until ACK or lease expiry, repeated long-poll delivery for the same assigned Job returns the same assignment identity. A Job is not concurrently delivered to a second node while its current lease remains ACTIVE.

### Worker-session renewal

Worker sessions are short lived and rotated through an authenticated renewal operation bound to:

~~~text
node_id
runtime_epoch_id
provider_instance_id
current worker credential
~~~

Renewal cannot widen endpoint scope or trust class. Failure to renew causes the worker to stop accepting new assignments and eventually lose lease authority.

### Lease renewal

A worker heartbeat may renew an ACTIVE lease only when the server independently verifies that:

- the lease belongs to that node and Job;
- the Job is still executable;
- the runtime epoch is current;
- no cancellation/drain/revocation applies.

A worker-reported `active_lease_ids` list is telemetry, not authority.

### Atomic placement and overcommit prevention

Granting a ResourceLease is one PostgreSQL transaction that locks the selected ComputeNode/resource-accounting rows, recomputes currently ACTIVE capacity, verifies budget reservation, creates the lease and updates Job assignment state.

The scheduler must not rely on a previously read capacity snapshot to grant resources.

D1 additionally enforces at most one ACTIVE lease per Job and per ResourceRequest.

### Atomic result finalization

Accepting a terminal worker result atomically:

1. validates current lease/epoch/attempt;
2. records result Artifact references;
3. transitions the Job;
4. releases the ResourceLease;
5. emits the terminal Event.

If the transaction fails, the Job is not authoritatively complete and recovery may safely retry/reconcile.

### Provider-instance uniqueness

A live provider instance maps to at most one ComputeNode identity. D1 enforces uniqueness for `(provider, provider_instance_id)` when a provider instance ID is present.


---

## 38. Recursive Audit Cycle 2 — Worker Reconnect, Capability Validation and Provider-Side-Effect Recovery

### Worker reconnect after Control Plane restart

Bootstrap is one-time, but a healthy provider instance may outlive a Control Plane process.

At initial registration the server exchanges bootstrap authority for a D1 `worker_identities` credential plus the short-lived epoch session.

After runtime-epoch change:

~~~text
worker detects 401/epoch change
→ POST /internal/v1/workers/reconnect
→ present worker identity credential + provider instance identity
→ server verifies node/provider state
→ issue fresh current-epoch session
→ worker resumes heartbeat
~~~

Old ResourceLeases remain stale and are never resurrected. The node may be reused only for newly granted leases after recovery.

### Capability validation

Worker self-report is never sufficient to establish hardware/runtime capability.

Effective node capabilities are the intersection of:

1. trusted expected launch profile;
2. provider API metadata where available;
3. worker telemetry/probes;
4. Reverend functional health checks.

A contradiction marks the capability/node unhealthy or lowers eligibility; self-report cannot strengthen trust.

### Provider lifecycle actions use the Action Journal

`provision/start/stop/terminate` are external side effects even though they are initiated by Capacity Controller rather than an Agent tool.

Before every charge-bearing provider mutation:

~~~text
persist provider ActionRecord / PowerSession intent
→ reserve budget
→ call provider
→ reconcile provider instance
→ persist result
→ settle reservation/cost state
~~~

On process crash, Capacity Controller queries provider inventory using Reverend tags/IDs before issuing another provisioning call.

This prevents duplicate paid Pods after “provider accepted request, local process died”.

### Capacity demand aggregation

Capacity Controller derives desired capacity from the set of admitted ResourceRequests plus explicit concurrency/budget ceilings.

It does not provision one new worker blindly per scheduler wake-up.

Provisioning intents are deduplicated by deployment/resource profile and recorded durably through provider ActionRecords/PowerSessions.

### Billing-aware stop semantics

A node enters `STOPPED` for economic purposes only after provider state confirms that chargeable compute has stopped under the captured provider billing model.

If provider “stop” continues material compute billing, Capacity Controller must terminate instead when scale-to-zero policy requires zero compute charge.

Persistent volume/storage charges remain separately represented in the cost ledger.


---

## 39. Recursive Audit Cycle 3 — CPU Execution Baseline and Authority-Host Protection

The original Design required heavy/untrusted CPU work to leave the authority process but left its Cloud v1 baseline ambiguous.

Cloud v1 therefore freezes two CPU execution classes.

### CONTROL_HOST_BOUNDED_SANDBOX

For small, bounded repository operations only:

~~~text
separate subprocess
separate OS user where practical
bubblewrap / namespace isolation
cgroup or equivalent CPU/RAM/PID limits
no PostgreSQL credential
no Secret Broker socket/key
no Docker socket
no host home
network OFF unless explicit tool policy permits
bounded Run/Task workspace
~~~

The authority process itself never executes untrusted build/test commands inline.

The persistent host reserves enough CPU/RAM/disk for PostgreSQL, API, scheduler and recovery. If safe quota cannot be granted, the Job remains queued rather than risking Control Plane liveness.

### REMOTE_CPU_WORKER

A dedicated remote CPU worker uses the same worker identity, assignment, ResourceLease, payload and recovery protocol as GPU workers.

It is the required path for work that exceeds the bounded local sandbox envelope.

The initial implementation may defer a specific paid CPU provider until measured workloads require one, but the scheduler must fail/queue explicitly rather than silently executing an oversized untrusted workload on the authority host.

### GPU worker CPU is not free fallback

CPU tasks may execute on an already-leased GPU worker only when:

- the Task is part of the same admitted Job/workload;
- resource accounting includes its CPU/RAM consumption;
- doing so does not retain/extend an expensive GPU PowerSession solely for CPU work.

Reverend must not keep an A100 alive just to run generic tests that could wait for an appropriate CPU executor.
