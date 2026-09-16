# D17 — Model Hydration, Cold Start & Cache Economics

> **Status:** DESIGN ACCEPTED FOR DEVELOPMENT  
> **Depends on:** A12, D4, D7, D8, D15, ADR-001, ADR-004  
> **Purpose:** Define how disposable workers obtain pinned model weights, how cold-start state is exposed, how cache integrity is enforced, and when persistent model storage is economically justified.

---

## 1. Objective

Cloud v1 should minimize recurring spend while keeping model/runtime reconstruction deterministic.

The baseline principle is:

> **Persist authority; reconstruct models.**

Model weights are large but reproducible deployment artifacts. Reverend therefore does not pay for permanent cloud model storage by default merely to reduce occasional cold-start latency.

---

## 2. Baseline Cold-Start Flow

~~~text
GPU Job READY
    ↓
no compatible READY worker
    ↓
Capacity Controller provisions worker
    ↓
worker boots pinned container
    ↓
worker registers/authenticates
    ↓
resolve DeploymentProfile
    ↓
check verified worker-local cache
    ↓
missing
    ↓
hydrate exact pinned revision from approved upstream source
    ↓
verify artifact manifest/revision/checksums
    ↓
atomically publish local verified snapshot
    ↓
runtime loads model
    ↓
functional smoke test
    ↓
node/profile READY
    ↓
lease may be granted
~~~

No inference lease is granted during hydration/loading.

---

## 3. Hydration Source Order

Cloud v1 initial order:

~~~text
1. verified model already resident/available on the live worker
2. verified worker-local ephemeral disk snapshot
3. approved upstream model repository at exact pinned revision
4. optional approved persistent cache, only if explicitly enabled later
5. otherwise MODEL_HYDRATION_UNAVAILABLE
~~~

If a future persistent cache is enabled, policy may rank it ahead of upstream download when benchmarked economics justify it.

Cloud v1 does not require client model seeding.

---

## 4. ModelArtifactManifest

Every production DeploymentProfile references a validated model artifact manifest.

Recommended fields:

~~~text
model_artifact_manifest_id
model_profile_id
repository
immutable_revision
required_files[]
weight_format
expected_file_identities/checksums
tokenizer/config files
license_ref
remote_code_required=false
expected_logical_size_bytes
created_at
validated_at
~~~

The manifest is deployment metadata, not a copy of the weights.

---

## 5. HydrationPolicy

Recommended DeploymentProfile sub-contract:

~~~text
HydrationPolicy
├── mode = EPHEMERAL_UPSTREAM
├── approved_sources[]
├── persistent_cache_enabled = false
├── max_hydration_attempts
├── hydration_timeout_seconds
├── minimum_free_disk_bytes
├── parallel_transfer_policy
├── partial_file_policy
├── integrity_policy
└── failure_policy
~~~

A DeploymentProfile cannot silently switch to an unapproved source.

---

## 6. Worker Startup States

D4 lifecycle is refined:

~~~text
ABSENT
PROVISIONING
BOOTING
REGISTERING
RUNTIME_READY
MODEL_RESOLVING
MODEL_HYDRATING
MODEL_VERIFYING
MODEL_LOADING
MODEL_SMOKE_TEST
READY
BUSY
IDLE_GRACE
DRAINING
STOPPING
STOPPED
TERMINATED
UNHEALTHY
~~~

The UI may collapse these states visually, but the server records them independently for cost/diagnosis.

---

## 7. Ephemeral Disk Contract

The worker receives enough ephemeral disk to hold:

- required model snapshot;
- transfer staging/partial files;
- runtime cache;
- bounded logs/temp files.

Admission checks required free disk before hydration.

The persistent Control Plane host does **not** become the model-weight cache.

Model snapshots must never consume disk reserved for PostgreSQL, WAL, recovery or authoritative BlobStore data.

---

## 8. Safe Download/Publish

Hydration uses a staging path:

~~~text
/models/.staging/<profile>/<attempt>/
~~~

Only after all required files pass validation does the worker atomically expose:

~~~text
/models/verified/<profile>/<revision>/
~~~

A cancelled/failed partial download is never advertised as a valid cache.

Partial files may be resumed only when the upstream transfer mechanism and manifest identity make that safe.

---

## 9. Integrity

Before MODEL_LOADING:

- immutable revision matches DeploymentProfile;
- expected required files exist;
- safe weight format policy passes;
- expected checksums/object identities match where available;
- tokenizer/config manifest matches;
- remote/custom code policy passes;
- local snapshot identity is recorded.

Failure:

~~~text
MODEL_ARTIFACT_MISMATCH
→ quarantine/delete invalid local snapshot
→ node/profile remains ineligible
~~~

No fallback to latest.

---

## 10. Upstream Credentials

Public models may not require credentials, but an approved repository token may be used for rate-limit/reliability reasons.

Credential handling:

- Secret Broker resolves token server-side;
- token is delivered only to the trusted worker operation that requires it;
- never stored in Project context;
- never logged;
- never embedded into model manifests.

---

## 11. Transfer Performance

Implementation should use the approved repository's high-performance/resumable transfer mechanism when available.

Parallelism is bounded by:

- provider bandwidth;
- source policy/rate limits;
- worker CPU/disk;
- diminishing returns;
- failure behavior.

Reverend records actual bytes/time rather than assuming a fixed internet speed.

Home/dorm client bandwidth is not part of normal hydration planning.

---

## 12. Runtime Load

Hydration completion does not mean inference readiness.

Separate:

~~~text
MODEL_HYDRATION_SECONDS
MODEL_VERIFY_SECONDS
MODEL_LOAD_SECONDS
MODEL_SMOKE_TEST_SECONDS
~~~

This lets Reverend determine whether future optimization should target network transfer, artifact verification, runtime initialization or model loading.

---

## 13. Residency Reuse

While a compatible worker remains alive, the scheduler should prefer verified resident models when quality/trust/cost requirements are otherwise satisfied.

Back-to-back Runs may reuse a live model deployment if:

- one-global-Run authority is preserved;
- prior Run leases are closed;
- model prompt/KV/session state is cleared;
- workspace/project access is rebound;
- worker identity remains valid;
- Project sensitivity/trust policy allows reuse.

Weights are non-Project state; prompts/KV/workspaces are Project-sensitive and must not leak across Runs.

---

## 14. Idle Grace

D4 idle grace remains a deliberate trade-off.

During idle grace:

- model may remain resident;
- no active inference lease exists;
- provider billing continues and is visible;
- queued compatible resume/priority work can avoid another cold start.

At idle-grace expiry, terminate when zero-compute policy requires it.

Do not retain the GPU for hours merely to avoid a future hydration unless measured economics justify it.

---

## 15. Persistent Cache Is an Optimization, Not a Requirement

Persistent model cache starts disabled.

Possible future forms:

- provider persistent/network volume;
- external object/model mirror;
- provider-local shared cache.

Any such cache remains reconstructible and non-authoritative.

A persistent cache profile must define:

~~~text
provider/location compatibility
storage rate
transfer rate/fees
revision invalidation
cache key
integrity policy
garbage collection
encryption/access policy
~~~

---

## 16. Cache Economics

Reverend computes observed cost rather than using a permanent architectural assumption.

Per hydration:

~~~text
hydration_billable_cost
=
billable_worker_seconds_during_hydration
× captured_provider_rate
+ direct_transfer_charge
~~~

Monthly estimate:

~~~text
observed_monthly_hydration_cost
=
sum(hydration_billable_cost)
~~~

Candidate cache estimate:

~~~text
candidate_monthly_cache_cost
=
stored_GB × captured_storage_rate
+ operations/transfer charges
~~~

Promotion recommendation requires:

1. enough representative cold starts;
2. stable model revision horizon;
3. candidate cache supported in required region/provider class;
4. projected total verified-task cost improvement;
5. explicit operator acceptance.

Reverend may **recommend** paid cache enablement but does not silently create recurring storage.

---

## 17. Cache Decision States

~~~text
DISABLED
OBSERVING
RECOMMENDED
ENABLED
RETIRING
~~~

Cloud v1 starts:

~~~text
persistent_model_cache = DISABLED
~~~

Recommendation is advisory until accepted by an authorized operator.

---

## 18. Cold-Start Metrics

Per worker/profile:

~~~text
cold_start_total_seconds
provider_provision_seconds
worker_boot_seconds
worker_register_seconds
model_resolve_seconds
model_hydration_bytes
model_hydration_seconds
model_hydration_source
model_verify_seconds
model_load_seconds
model_smoke_seconds
ready_at
hydration_estimated_cost_gbp
hydration_reconciled_cost_gbp?
~~~

Repeated failed hydration must be visible separately from successful startup.

---

## 19. Cost Attribution

Hydration is part of the relevant PowerSession startup overhead.

Initial D8 shared-transient policy may allocate pre-lease hydration overhead according to the accepted shared rule unless a single queued Run exclusively caused the provisioning action and policy attributes it directly.

The ledger must still make hydration cost separately inspectable.

---

## 20. Failure Policy

Examples:

### Source unavailable

~~~text
MODEL_HYDRATION_SOURCE_UNAVAILABLE
~~~

Retry within bounded policy, then block the Job.

### Disk insufficient

~~~text
MODEL_HYDRATION_DISK_INSUFFICIENT
~~~

Do not start download and fill worker disk unpredictably.

### Hash/revision mismatch

~~~text
MODEL_ARTIFACT_MISMATCH
~~~

Fail closed.

### Timeout

Terminate/retry according to provider/cost policy.

Repeated hydration failure should release an expensive worker rather than burn unlimited GPU time.

---

## 21. User Experience

Chat/Run UI should show bounded startup progress:

~~~text
Provisioning A100…
Worker connected.
Downloading Qwen3.8-27B pinned revision… 38%
Verifying model…
Loading vLLM model…
Running health check…
Ready.
~~~

The UI may also show:

- downloaded GB;
- elapsed cold-start time;
- estimated startup cost;
- whether the model was reused or cold-hydrated.

The user is not asked to upload model weights for normal startup.

---

## 22. Optional Local Developer Copies

Developers may independently retain exact pinned model copies on personal disks.

These copies:

- are not required;
- are not authoritative;
- are not part of disaster recovery;
- are not advertised to the scheduler;
- do not need to be online for a Run;
- are useful only as manual archival/emergency convenience unless a future ADR introduces a secure seed protocol.

This preserves the cloud-only product boundary.

---

## 23. Container Image Rule

Worker container images contain:

- CUDA/runtime dependencies;
- vLLM/media runtime;
- Reverend worker code;
- transfer/integrity tooling.

They do not contain the large production model weights by default.

Model revision and worker image revision therefore evolve independently.

---

## 24. Media and Specialist Models

The same hydration contract applies to:

- Qwen primary engineering;
- optional coding specialist;
- media model;
- future reranker/embedding GPU profiles.

Only hydrate a model when there is admitted near-term demand.

Do not cold-load every known model at worker boot.

---

## 25. Security

- approved source allowlist;
- HTTPS/provider-authenticated transport;
- pinned revision;
- safe format;
- checksum/object identity validation;
- no trust_remote_code in baseline;
- bounded parser/file sizes;
- credentials from Secret Broker;
- no model repository instructions treated as orchestration authority.

---

## 26. Development Programme

### C0
Add ModelArtifactManifest/HydrationPolicy/startup-state contracts.

### C4
Expose model availability requirements to scheduler/context without making models authoritative.

### C7
Implement:

1. fake hydration source;
2. local fixture hydration;
3. upstream pinned-revision hydration;
4. staging/verification/atomic publish;
5. vLLM load/smoke;
6. metrics/cost attribution;
7. same-worker residency reuse;
8. termination/reconstruction;
9. cache-economics observation.

Persistent cache implementation is optional after baseline evidence.

### C8
Expose startup progress/cost and cache recommendation to users/operators.

### C9
Run live cold-start/failure/cost acceptance.

---

## 27. ReverendBench / Acceptance

Required live tests:

- empty A100 worker → exact Qwen profile READY;
- second Job on same live worker reuses resident verified model;
- terminated worker → new worker reconstructs from upstream;
- wrong revision/hash fails closed;
- source outage does not substitute an unapproved model;
- disconnected clients do not affect hydration;
- model weights absent from Control Plane recovery;
- hydration metrics/cost reconcile to provider session;
- persistent cache remains disabled unless explicitly enabled.

---

## 28. Exit Condition

D17 is satisfied when Reverend can bring an empty disposable worker to a reproducible model-ready state from a pinned upstream revision, account for the cold-start cost, safely reuse live residency, discard reconstructible model state at termination, and make future persistent caching an evidence-driven economic optimization rather than a default recurring expense.
