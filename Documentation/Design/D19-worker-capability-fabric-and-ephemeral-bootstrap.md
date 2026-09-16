# D19 — Worker Capability Fabric & Ephemeral Bootstrap

> **Status:** DESIGN ACCEPTED FOR DEVELOPMENT  
> **Depends on:** A6, A10, A11, A12, D4, D5, D6, __D20__, D18  
> **Purpose:** Generalize compute from “CPU vs GPU inference” into capability-scoped disposable workers, and freeze the ephemeral-first RunPod bootstrap/storage model.

---

## 1. Core Decision

> **Persistent intelligence and durable state; disposable expensive execution.**

The A100 is not Reverend's server.

The persistent Control Plane remains online with zero GPU workers.

GPU/CPU/browser workers execute admitted Jobs and may disappear without destroying Project truth.

---

## 2. Worker Taxonomy

### CONTROL_HOST_BOUNDED_SANDBOX

For very small bounded commands only.

Not a general worker.

### CPU_BUILD_WORKER

~~~text
builds
tests
linters
package operations
repository indexing
LSP/type services
document parsing
data transforms
~~~

### BROWSER_WORKER

Modes:

~~~text
RESEARCH_BROWSER
FRONTEND_TEST_BROWSER
~~~

### MODEL_GPU_WORKER

~~~text
vLLM/SGLang
generation
embeddings/reranking when routed there
vision/model inference
~~~

### ACCELERATED_COMPUTE_GPU

~~~text
CUDA scientific compute
CFD
FEA
numerical simulation
other GPU kernels
~~~

### MEDIA_GPU

~~~text
image generation
3D/render
video/audio pipelines
future media runtimes
~~~

The last two are frozen interfaces. Their concrete C9 implementation is required only when selected v1 workloads depend on them.

---

## 3. Physical Workers May Implement Multiple Capabilities

A worker may advertise multiple verified capabilities.

Example:

~~~text
A100 worker
├── inference.generate
├── inference.vision
└── compute.cuda
~~~

Scheduler treats them independently.

A CPU-only Task must not retain an A100 PowerSession merely because the worker also has CPUs.

---

## 4. WorkerProfile

~~~text
WorkerProfile
├── profile_id
├── capability_ids
├── trust_class
├── resource envelope
├── provider profile
├── container image
├── BootstrapSpec
├── StorageProfile
├── network profile
├── sandbox profile
├── health contract
├── idle policy
└── cost profile
~~~

This is distinct from Model DeploymentProfile.

---

## 5. BootstrapSpec v1

~~~yaml
schema_version: 1

worker_image:
  digest: sha256:...

worker_runtime:
  version: ...

control_plane:
  endpoint: https://...

bootstrap:
  credential_ref: one-time-injected-secret
  expires_at: ...

expected_provider_instance:
  id: ...

worker_profile:
  id: ...

deployment_profile:
  id: optional-model-profile

storage_profile:
  id: ...

trust_class:
  COMMUNITY_CLOUD_WORKER
~~~

Sensitive bootstrap material is injected at provision time and not persisted in plaintext profile data.

---

## 6. StorageProfile v1

Initial RunPod target:

~~~yaml
id: runpod-community-a100-ephemeral-v1

container:
  size_gb: 200
  persistence: ephemeral
  authoritative: false

warm_volume:
  enabled: true
  size_gb: 10
  mount_path: /workspace
  authoritative: false
  disposable: true

model_weights:
  persistence_required: false
  fetch_on_cache_miss: true

runtime_cache:
  persistence_required: false

workspace:
  local_execution_allowed: true
  durable_checkpoint_required: true

shutdown:
  require_durability_flush: true
  allow_stop: true
  allow_terminate: true
~~~

Capacities are initial deployment targets, not universal invariants.

A provider/profile may use no warm volume.

---

## 7. Storage Classification

### Durable authoritative

Never worker-only:

~~~text
PostgreSQL authority
Git/repository recovery refs
Action Journal
RunCheckpoint manifests
retained Artifacts/Evidence
cost ledger
Requirements/Decisions/Memory
workspace reconstruction refs
~~~

### Reconstructible

May disappear:

~~~text
model weights
runtime/container cache
CUDA state
KV/prefix cache
Tree-sitter/LSP cache
temporary clone/worktree
build output
package cache
browser cache
temporary downloads
~~~

### Optional warm cache

Provider-local cache may reduce startup.

Loss means slower reconstruction only.

---

## 8. Bootstrap Lifecycle

GPU example:

~~~text
GPU Job READY
↓
no compatible READY node
↓
Capacity Controller
↓
budget + blast-radius admission
↓
one-time bootstrap credential
↓
ComputeProvider.provision()
↓
PROVISIONING
↓
BOOTING
↓
worker runtime starts
↓
register / receive node identity + epoch session
↓
validate WorkerProfile / storage
↓
receive required DeploymentProfile
↓
download only required model on cache miss
↓
verify artifact manifest
↓
start vLLM
↓
load model
↓
functional smoke
↓
NODE_READY
↓
ResourceLease
~~~

No SSH/manual installation is part of normal activation.

---

## 9. Worker Lifecycle States

Generalized lifecycle:

~~~text
ABSENT
PROVISIONING
BOOTING
REGISTERING
RUNTIME_STARTING
ARTIFACT_LOADING
MODEL_LOADING
READY
BUSY
IDLE_GRACE
DRAINING
STOPPING
STOPPED
TERMINATING
TERMINATED
UNHEALTHY
UNREACHABLE
~~~

Not every profile uses MODEL_LOADING.

---

## 10. WorkerDurabilityGate

Hard rule:

~~~text
worker_unique_state == true
→ destructive stop/terminate forbidden
~~~

Before destruction, trusted DrainController verifies:

- no active lease;
- no STARTED/UNKNOWN worker-local effect requiring reconciliation;
- unique workspace changes durably represented;
- required output Artifacts uploaded;
- checkpoint/workspace manifest published when required;
- cost/telemetry needed for reconciliation persisted;
- off-host ActionIntent barrier satisfied where applicable.

The gate is server-authoritative.

Worker cannot declare itself safe to delete.

---

## 11. Workspace Externalization

Safe-boundary representations may include:

~~~text
Git commit/ref
patch Blob
untracked-file Blob manifest
workspace snapshot
Artifact output
content hashes
~~~

Reverend need not push every internal checkpoint to public GitHub.

It does need enough durable information to reconstruct.

---

## 12. Unexpected Worker Loss

~~~text
heartbeat expires/provider absent
↓
ComputeNode UNREACHABLE
↓
lease expires/revokes
↓
Job INTERRUPTED
↓
Action classification/reconciliation
↓
Run RECOVERING
↓
replacement capacity
↓
rebuild workspace/runtime
↓
new attempt
~~~

Worker-local caches are irrelevant to correctness.

---

## 13. Idle Grace

Initial target:

~~~text
420 seconds
~~~

Eligibility:

- no active leases;
- no immediately runnable compatible Jobs;
- no RESUME_NEXT demand;
- no shutdown inhibitor;
- no durability blocker.

Idle policy may later become adaptive based on cold-start economics.

---

## 14. Stop vs Terminate

~~~text
WARM_PERSISTENT
→ STOP when provider economics justify retained storage/state

EPHEMERAL
→ TERMINATE after durability gate
~~~

Default cheap GPU profile is EPHEMERAL.

Provider stopped state must actually be checked for compute billing.

---

## 15. Model Download Policy

A Model GPU worker downloads only the selected DeploymentProfile.

Never:

~~~text
download every Reverend model at worker boot
~~~

Cold-start telemetry determines whether a persistent model cache is economically useful.

---

## 16. Browser Worker Bootstrap

Browser profile pins:

- Reverend worker image;
- Playwright version;
- browser binary/version;
- OS dependencies;
- sandbox/network policy.

Browser binary cache is reconstructible.

Research browser receives no personal session.

Frontend test browser receives only test-specific ephemeral credentials through a bounded test adapter when required.

---

## 17. CPU Worker Bootstrap

CPU worker pins:

- worker image;
- supported compilers/toolchains;
- sandbox runtime;
- language servers where configured;
- resource limits.

Project-specific dependencies live inside Task/workspace environments rather than on the persistent Control Plane host.

---

## 18. Accelerated / Media Workers

These profiles use the same contracts:

~~~text
ComputeNode
WorkerProfile
ResourceRequest
ResourceLease
Action/Artifact
DurabilityGate
Cost
~~~

Specialized runtime adapters define:

- inputs;
- GPU/VRAM requirements;
- output Artifacts;
- deterministic validation;
- checkpointability;
- cancellation.

This avoids creating separate schedulers for CFD/media later.

---

## 19. Provider Independence

RunPod is the initial provider adapter.

Generic:

~~~text
ComputeProvider
├── provision(worker_profile, bootstrap_spec)
├── inspect()
├── start()
├── stop()
├── terminate()
├── estimate_rate()
└── list_available_profiles()
~~~

Worker/StorageProfile semantics remain provider-neutral.

---

## 20. Worker Trust

Community GPU worker remains lower-assurance.

Worker receives:

- Job-scoped payloads;
- ContextManifest-approved data;
- short-lived worker/session credentials;
- opaque Blob capabilities.

Worker does not receive:

- provider lifecycle key;
- GitHub personal credential;
- PostgreSQL credential;
- Secret Broker socket/key;
- unrelated Project material.

Browser and CPU workers have separate network/trust profiles.

---

## 21. Capacity Safety

Initial paid GPU ceilings remain:

~~~text
MAX_PAID_GPU_WORKERS_TOTAL = 1
MAX_PROVISIONING_GPU_WORKERS_TOTAL = 1
~~~

CPU/browser limits are separate and cheaper, but still policy/budget bounded.

Capability Scheduler must not interpret spare workers as permission to exceed the one-active-top-level-Run policy.

---

## 22. Cold-Start Telemetry

Capture:

~~~text
provider_provision_seconds
boot_seconds
registration_seconds
image/runtime_ready_seconds
artifact/model_download_seconds
verification_seconds
model_load_seconds
runtime_warmup_seconds
worker_ready_seconds
cold_start_total_seconds
cache_hit/miss
download_bytes
~~~

Without these measurements Reverend cannot choose cache/idle policy rationally.

---

## 23. Cost Accounting

PowerSession spans full provider-billed lifecycle:

~~~text
requested
→ provider billing
→ boot
→ load
→ lease work
→ idle grace
→ drain
→ provider billing end
~~~

ComputeLeaseUsage represents attributable useful lease time.

Startup/warm/idle/drain are separate overhead categories.

---

## 24. Local Development

Most Development/CI uses:

~~~text
PostgreSQL
cloud API
FakeComputeProvider
FakeWorker
MockInferenceRuntime
fake Browser/CPU capability adapters
~~~

Paid RunPod validation is explicit and protected.

---

## 25. Acceptance Tests

### Cold start from zero

Provision → bootstrap → load required model → READY → execute without SSH.

### Total provider loss

Delete worker/cache/volume/model weights; Project/Run remains recoverable.

### Durability gate

Unique unexternalized state blocks terminate.

### Cache loss

Destroy warm cache; behavior remains correct after slower startup.

### Worker replacement

Kill worker; replacement reconstructs and continues.

### Browser replacement

Lose browser worker; no Project authority lost.

### CPU isolation

Heavy build cannot starve Control Plane.

### Capability mismatch

MODEL_GPU Task cannot land on browser/CPU-only worker.

---

## 26. Exit Condition

The worker fabric is ready when Reverend can reconstruct the exact admitted environment on an empty compatible worker, execute a typed capability, externalize all unique progress and safely destroy the worker with no correctness dependency on provider-local disk.


---

## 27. Recursive Capability Audit — Capability Attestation & Artifact Delivery

### Capability advertisement is not self-authority

Effective worker capability is the intersection of:

~~~text
trusted WorkerProfile expected capability
provider metadata
worker probes
functional capability smoke
policy/trust class
~~~

A worker cannot gain a capability by advertising a string.

### Capability-specific health

READY is capability-relative.

Examples:

~~~text
MODEL_GPU
  runtime health + exact DeploymentProfile loaded + inference smoke

CPU_BUILD
  sandbox + toolchain health + resource limits

BROWSER
  pinned browser/runtime + network interception + DOM/screenshot smoke

REPOSITORY_LSP
  pinned language server + workspace isolation + protocol smoke
~~~

Scheduler only places a Job against the capability whose health passed.

### Artifact delivery

Workers receive Job-scoped Blob capabilities, not durable storage paths.

Large input/output transfer is hash-verified and bounded.

A Browser or CPU worker cannot enumerate unrelated BlobStore content.

### Warm-volume contamination

Optional provider warm volumes are cache only and may survive between worker instances.

Before reuse:

- identify expected cache namespace/profile;
- never store plaintext Secret material;
- never trust workspace/project files from a previous Run as authority;
- validate cached model/runtime artifacts by digest;
- clear/quarantine unknown content.

Project workspace data should default to ephemeral container/worktree state rather than shared warm cache.


---

## 28. Recursive Capability Audit — Reproducible Build Environments & Cross-Worker Tests

### ExecutionEnvironmentSpec

Ephemeral CPU/GPU execution must not depend on manually installed laptop state.

~~~text
ExecutionEnvironmentSpec
├── base worker image/digest
├── OS/toolchain profile
├── language/runtime versions
├── Project dependency manifest refs
├── lockfile hashes
├── environment variables excluding Secrets
├── network/dependency policy
├── resource limits
└── provenance
~~~

Project source may propose environment requirements, but trusted policy resolves them to approved worker/toolchain profiles.

### Dependency acquisition

Build/test execution is network-off by default after dependencies are prepared.

A separate bounded dependency-acquisition step may access allowlisted registries such as the Project's configured Python/npm/system artifact sources.

Requirements:

- respect Project lockfiles where present;
- record package/version/source provenance;
- use cache only after hash/profile validation;
- no arbitrary curl/script execution on the Control Plane;
- package install hooks execute only inside the isolated worker when Project policy permits;
- network closes again for deterministic build/test when feasible.

Package/wheel/npm caches are reconstructible.

### Test application to Browser Worker

Frontend testing may require one worker to host the application while a Browser Worker drives it.

Use an ephemeral TestEndpoint:

~~~text
CPU/Test worker
→ binds private task-scoped endpoint
→ Control Plane records opaque TestEndpoint capability
→ Browser Worker receives short-lived route
→ only browser-test lease can access
→ endpoint revoked on Job/lease completion
~~~

Do not expose development servers publicly merely so Playwright can reach them.

### Control Plane sizing

The persistent host baseline is protected for authority work.

If PostgreSQL/API/scheduler/recovery headroom would be violated, repository indexing, search engines, Qdrant-heavy work, browser activity and builds must move to separate CPU capacity or remain queued.


---

## 29. Recursive Capability Audit — Task-Scoped TestEndpoint Authentication

An opaque route reference alone is not authorization.

TestEndpoint activation creates a short-lived, lease-bound connection capability containing:

~~~text
test_endpoint_id
producer Job / ResourceLease
consumer Browser Job / ResourceLease
allowed protocol/port/path scope
expiry
random connection credential or mutually authenticated channel identity
~~~

Rules:

- route is private/non-public;
- endpoint accepts only the bound Browser Worker identity/credential;
- Browser Worker can reach only the declared test service, not arbitrary producer-worker ports;
- credential is not embedded in browser-visible page source or durable logs;
- producer/consumer lease revocation immediately invalidates access;
- redirects from the test app to non-allowlisted private endpoints are blocked;
- TestEndpoint cannot outlive the creating Run/Jobs.

Frontend tests requiring user login use explicit test-only accounts/secrets scoped to the ephemeral test environment. Real user sessions are not copied into the Browser Worker by default.


---

## 30. Recursive Capability Audit — Background Work and Browser Output Boundaries

### No hidden background cognitive workers

CPU/Browser/GPU workers execute admitted capability Jobs.

They do not wake independently to:

- crawl the web;
- re-plan Projects;
- refresh Memory;
- modify repositories;
- spawn Agent Teams.

Operational controllers may run housekeeping defined by __D20__/D5, but cognitive/project work remains Run-owned.

### Browser output handling

Browser screenshot/video/trace/download output is uploaded through Job-scoped Blob capabilities.

Worker performs no direct durable publication.

Control Plane validates:

- expected media/type;
- maximum size;
- content hash;
- Artifact sensitivity;
- current Job/attempt;
- retention policy.

Raw browser profiles, cookies and caches are destroyed with the worker/job unless a specific test Artifact contract retains sanitized output.


---

## 31. Recursive Capability Audit — Large Artifact Data Plane

Large simulation/media/browser/build Artifacts must not require buffering through the Control Plane API process or fitting on its local 80 GB disk.

BlobStore therefore supports two implementation classes behind one authority contract:

~~~text
LocalBlobStore
  suitable for small/initial durable objects

ObjectBlobStore
  suitable for large durable artifacts / scale
~~~

For a remote worker, upload capability may resolve to:

~~~text
Control-Plane streaming endpoint
or
short-lived, object-scoped direct upload capability
~~~

Rules:

- capability authorizes one expected object/size/media scope;
- worker never receives general BlobStore credentials;
- content hash/size verified before Artifact publication;
- incomplete multipart/temp upload is not a durable Artifact;
- Artifact metadata becomes authoritative only after Blob publication succeeds;
- quotas/budgets checked before accepting very large output;
- abandoned uploads are GC-able after safe grace period.

This allows future CFD/media outputs to be large without turning the Control Plane filesystem into a hidden scaling limit.
