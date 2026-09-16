# D0 — System Contracts & Codebase Boundaries

> **Status:** DESIGN ACCEPTED FOR DEVELOPMENT  
> **Depends on:** A0, A1, A12  
> **Purpose:** Freeze concrete service boundaries, package ownership, identifier/version conventions, transaction principles, and migration seams before feature implementation.

---

## 1. Design Goal

Reverend already contains most of the semantic ingredients required for Cloud v1.

The development task is not to create a second system beside Reverend.

It is to evolve the existing system into:

~~~text
one durable authoritative backend
+
thin clients
+
bounded cognitive runtime
+
replaceable execution workers
~~~

while preserving the accepted local reliability baseline.

This document defines which package owns which concern so Development does not accidentally recreate the state/orchestration fragmentation identified in A0.

---

## 2. Authority Ownership Matrix

| Concern | Canonical owner | Non-authoritative consumers |
|---|---|---|
| human identity/session | security/identity service + PostgreSQL | API/UI |
| Project membership | Control Plane / PostgreSQL | UI, policy |
| Run lifecycle | Control Plane | scheduler, UI, recovery |
| Workflow/Task/Job | Control Plane | Agents, scheduler, UI |
| immutable events | Control Plane event store | SSE, audit, metrics |
| Artifact metadata/lineage | Control Plane artifact repository | context, UI |
| large Artifact bytes | BlobStore | context, workers |
| Agent definitions | Specialist Registry | Agent runtime |
| Agent execution assignment | Control Plane + Agent runtime | UI |
| Team membership/grouping | Agent runtime backed by Control Plane IDs | UI |
| context selection | Context Broker/Compiler | Agent invocation |
| model eligibility | Model Registry/Router | Agent runtime |
| resource placement | Compute Scheduler | workers |
| provider lifecycle | Capacity Controller | UI/status |
| secrets | Secret Broker | trusted tool adapters only |
| approvals | Control Plane + policy | UI/tool broker |
| Git external identity | Run owner + GitHubIdentity binding | Git tool |
| recovery | Recovery Service + Control Plane | clients as replicas |
| cost ledger | Cost service | UI/budget evaluator |

No package may store a second authoritative copy merely for convenience.

---

## 3. Modular-Monolith First

Cloud v1 should begin as a modular monolith on the persistent control host.

Rationale:

- two users;
- one active top-level Run;
- small service count;
- lower operational burden;
- easier transactions;
- simpler fault injection;
- no need for distributed service discovery.

Logical boundaries still matter.

The Python process may host:

~~~text
API
scheduler
agent runtime
context
policy
cost
recovery coordination
~~~

while PostgreSQL remains the durable authority.

Heavy/untrusted execution and GPU inference are outside that process.

Future process separation must preserve the same contracts.

---

## 4. Proposed Package Layout

New/extended package direction:

~~~text
src/reverend/
├── api/
│   ├── app.py
│   ├── auth.py
│   ├── errors.py
│   ├── schemas.py
│   ├── sse.py
│   └── routes/
│       ├── auth.py
│       ├── projects.py
│       ├── runs.py
│       ├── queue.py
│       ├── approvals.py
│       ├── artifacts.py
│       ├── events.py
│       ├── costs.py
│       └── system.py
│
├── persistence/
│   ├── postgres.py
│   ├── migrations.py
│   ├── blobstore.py
│   └── schema/
│       └── *.sql
│
├── controlplane/
│   ├── models.py              # existing contracts evolved
│   ├── repositories.py
│   ├── runs.py
│   ├── transitions.py
│   ├── queue.py
│   ├── events.py
│   ├── artifacts.py
│   ├── approvals.py
│   ├── checkpoints.py
│   └── actions.py
│
├── specialists/
│   ├── models.py              # evolve SpecialistSpec
│   ├── registry.py
│   ├── agents.py
│   ├── teams.py
│   └── context.py
│
├── intelligence/
│   ├── runtime.py
│   ├── model_requirements.py
│   ├── context_broker.py
│   └── model_router.py
│
├── runtime/
│   ├── models.py
│   ├── resources.py
│   ├── compute_nodes.py
│   ├── compute_scheduler.py
│   ├── capacity.py
│   ├── compute_providers.py
│   ├── inference_runtimes.py
│   ├── worker_protocol.py
│   └── providers.py           # compatibility during migration
│
├── security/
│   ├── identity.py
│   ├── sessions.py
│   ├── secrets.py
│   ├── workers.py
│   └── git_identity.py
│
├── policy/
│   └── ... existing policy engine extended
│
├── development/
│   └── ... current worktree/sandbox/dev plane retained
│
├── observability/
│   └── ... current telemetry/redaction extended
│
└── workstation/
    └── ... retained local compatibility surface
~~~

The precise file split can change, but ownership boundaries may not.

---

## 5. Dependency Direction

Preferred dependency graph:

~~~text
api
 ↓
application services / controlplane
 ↓
domain contracts
 ↓
repository interfaces

runtime / security / intelligence
 ↓
domain contracts

persistence
 ↓ implements repository interfaces

provider adapters
 ↓ implement runtime interfaces
~~~

Avoid:

~~~text
controlplane
→ imports FastAPI routes

domain model
→ imports RunPod SDK

specialist model
→ imports vLLM

policy engine
→ imports UI code
~~~

Provider/framework dependencies must stay at edges.

---

## 6. Concrete Framework Direction

### Cloud API

Use an asynchronous ASGI API implementation.

Recommended initial stack:

~~~text
FastAPI
Pydantic v2
Uvicorn
~~~

Reasons:

- versioned REST schemas;
- explicit validation;
- SSE support through streaming responses;
- mature async integration;
- generated OpenAPI useful for independent frontend work;
- clean dependency injection for authenticated principal.

The current stdlib loopback server remains local compatibility mode until feature parity is reached.

### PostgreSQL

Recommended driver:

~~~text
psycopg 3
~~~

Use explicit SQL/repository methods rather than introducing an ORM as a second domain model.

Benefits:

- current code already uses explicit SQL;
- transition invariants remain visible;
- fewer hidden ORM lifecycle semantics;
- PostgreSQL features such as FOR UPDATE, advisory locks, partial indexes, JSONB, and LISTEN/NOTIFY remain accessible.

A query-builder/ORM may be added later only if it demonstrably reduces complexity without duplicating domain state.

---

## 7. Identifier Conventions

Use opaque UUID identifiers generated server-side.

Initial rule:

~~~text
uuid.uuid4()
~~~

for externally visible object IDs.

Reason:

- Python 3.11 compatibility;
- no new ID dependency;
- safe distributed generation;
- no client-derived authority.

Examples:

~~~text
user_id
project_id
run_id
workflow_id
task_id
job_id
artifact_id
approval_id
agent_instance_id
team_id
lease_id
action_id
checkpoint_id
~~~

Human-readable labels are presentation fields only.

Event ordering uses a PostgreSQL BIGINT sequence, not lexicographic UUID ordering.

---

## 8. Time Conventions

All durable timestamps:

~~~text
TIMESTAMPTZ
UTC
~~~

Application code uses timezone-aware UTC datetime values.

Never infer ordering from client clocks.

Ordering-sensitive streams use server sequence numbers.

---

## 9. Schema Version Conventions

Every persisted/network envelope that needs independent evolution includes:

~~~text
schema_version = 1
~~~

Major semantic changes require a new version.

Database migration version is separate from object schema version.

Example:

~~~text
database migration 0007
may still store
Artifact schema v1
~~~

Do not conflate them.

---

## 10. Transaction Rule

Any operation that changes authoritative lifecycle state and emits the corresponding durable event must commit in one PostgreSQL transaction.

Example:

~~~text
transition Run QUEUED → STARTING
+
set started_at
+
insert RunStateChanged event
~~~

must be atomic.

The API must not return success before the transaction commits.

---

## 11. Transition Rule

State changes go through named domain transition services.

Rejected:

~~~python
db.execute("UPDATE runs SET status='running' ...")
~~~

from arbitrary route/tool code.

Accepted conceptual call:

~~~text
RunService.transition(
  run_id,
  expected=STARTING,
  target=RUNNING,
  actor=...
)
~~~

The transition service:

1. locks the row;
2. validates current state;
3. applies invariant checks;
4. updates state;
5. inserts event;
6. commits.

Equivalent rules apply to Workflow, Task, Job, Approval, ActionRecord, and leases.

---

## 12. Runtime Epoch

Every authoritative backend boot creates:

~~~text
runtime_epoch_id
~~~

Leases and worker sessions are associated with an epoch.

On unclean restart:

- previous-epoch active leases are stale;
- stale worker sessions lose execution authority;
- durable Run state is recovered separately.

This implements A7 without pretending process-local authority survived a restart.

---

## 13. Singleton Scheduler Leadership

Cloud v1 normally runs one scheduler/capacity-controller leader.

Use PostgreSQL advisory locks rather than assuming only one process can ever start.

Conceptual locks:

~~~text
reverend:workflow-scheduler:v1
reverend:capacity-controller:v1
reverend:recovery-controller:v1
~~~

Only the process holding the relevant lock performs that controller's active loop.

A passive API process may continue serving reads/commands.

This preserves a clean scale-out path without adding Redis.

---

## 14. Background Loop Design

Background services must be:

- restartable;
- idempotent;
- driven by durable state;
- bounded;
- cancellable on graceful shutdown.

Recommended loop pattern:

~~~text
acquire leader lock
↓
read durable candidates
↓
attempt one bounded unit of work
↓
commit transition/event
↓
sleep or await notification
~~~

Do not retain unreconstructable scheduler queues only in RAM.

---

## 15. Event Notification

PostgreSQL remains event authority.

Implementation may use:

~~~text
LISTEN / NOTIFY
~~~

only as a wake-up optimization.

If a notification is lost, consumers recover by sequence cursor from the events table.

Therefore NOTIFY is never authoritative.

---

## 16. BlobStore Contract

Large immutable bytes should not inflate PostgreSQL rows.

Interface:

~~~text
BlobStore.put(bytes, media_type?) -> BlobRef
BlobStore.get(blob_ref) -> bytes/stream
BlobStore.exists(blob_ref) -> bool
BlobStore.verify(blob_ref) -> bool
~~~

BlobRef includes:

~~~text
algorithm = sha256
digest
size_bytes
storage_key
~~~

Cloud v1 initial implementation:

~~~text
FileBlobStore
AI_DATA_ROOT/objects/sha256/<prefix>/<digest>
~~~

Write algorithm:

1. calculate hash;
2. write temporary file;
3. fsync file;
4. atomic rename;
5. fsync parent directory where practical;
6. return reference.

Later object storage can implement the same contract.

---

## 17. Repository / Workspace Identity

Project authority is based on server Project identity, not local path.

Workspace is execution state.

Conceptual mapping:

~~~text
Project
→ repository_identity

Run
→ workspace_id / workspace_ref

Task
→ isolated worktree where mutation required
~~~

The current worktree implementation remains the basis for repository isolation.

---

## 18. Local Compatibility Mode

Local 0.4.0 mode remains available while cloud development proceeds.

The local mode may continue using:

- SQLite;
- current loopback Workstation;
- Ollama;
- current local scheduler.

Cloud code should use interfaces that allow:

~~~text
SQLite adapter
PostgreSQL adapter
~~~

where practical, but Cloud semantics must not be weakened to preserve every local implementation quirk.

---

## 19. Configuration Layers

Use explicit configuration precedence:

~~~text
built-in defaults
< config file
< environment
< command-line explicit override
~~~

Never load credentials from repository config files.

Cloud-specific configuration should include:

~~~text
REVEREND_MODE=cloud
REVEREND_DATABASE_URL
REVEREND_PUBLIC_BASE_URL
REVEREND_SECRET_KEY_FILE
REVEREND_STATE_ROOT
REVEREND_RUNPOD_SECRET_REF
REVEREND_WORKER_BOOTSTRAP_TTL
REVEREND_GPU_IDLE_GRACE_SECONDS
~~~

Exact environment names may be normalized in Development but should remain documented.

---

## 20. Error Taxonomy

Create stable domain error classes/codes.

Minimum API-facing categories:

~~~text
validation_error
unauthenticated
forbidden
not_found
conflict
invalid_state_transition
idempotency_conflict
budget_exceeded
approval_required
recovery_blocked
resource_unavailable
provider_unavailable
internal_error
~~~

Internal exceptions may be richer, but the client contract stays stable.

---

## 21. Logging Rule

Operational logging may contain:

- object IDs;
- event IDs;
- state changes;
- error codes;
- durations;
- provider resource IDs where non-secret.

It must never contain:

- session bearer tokens;
- GitHub credentials;
- provider API keys;
- secret values;
- raw Authorization headers;
- hidden chain-of-thought.

Use the existing redaction layer as a mandatory sink wrapper.

---

## 22. Test Structure Direction

Add tests by contract family rather than only by module.

Recommended new groups:

~~~text
tests/cloud/test_contract_versions.py
tests/cloud/test_postgres_schema.py
tests/cloud/test_run_transitions.py
tests/cloud/test_api_auth.py
tests/cloud/test_sse_replay.py
tests/cloud/test_agent_team_runtime.py
tests/cloud/test_compute_scheduler.py
tests/cloud/test_worker_protocol.py
tests/cloud/test_action_journal.py
tests/cloud/test_recovery.py
tests/cloud/test_secrets.py
tests/cloud/test_cost_ledger.py
tests/cloud/test_end_to_end.py
~~~

Provider/live tests must remain separately marked/gated.

---

## 23. Design Acceptance Gate

D0 is satisfied when Development can implement C0 without asking:

- which service owns a concern;
- which package should mutate lifecycle state;
- where provider code belongs;
- how IDs/time/versions are represented;
- which state is authoritative;
- how large blobs are stored;
- how local compatibility remains available.


---

## 24. Recursive Architecture Hardening — Privilege Separation and Referential Integrity

The pre-development architecture audit found two boundaries that were too implicit. The following rules are **mandatory Cloud v1 constraints** and supersede any looser interpretation elsewhere in D0–D9.

### Secret Broker is a privilege boundary

The Control Plane remains a modular monolith for normal application logic, but the **secret-encryption master key must not be readable by the general Reverend application process**.

Cloud v1 therefore uses a minimal local privilege-separated Secret Broker helper:

~~~text
Reverend application process
        ↓ authenticated local IPC
Secret Broker helper
        ↓
protected master-key material
~~~

Requirements:

- run under a distinct OS identity or equivalently isolated credential boundary;
- communicate over a root-owned Unix-domain socket or equivalent local authenticated IPC;
- expose only bounded operations such as resolve-for-action/create/rotate/revoke/metadata;
- never expose the master key;
- return plaintext secret material only to an explicitly authorized trusted adapter invocation and only for the lifetime of that bounded action;
- never expose the socket to sandboxes, workers, models, browser clients or GPU containers.

This is a deliberate exception to the modular-monolith-first rule because Python module boundaries are not security boundaries.

### Database integrity must back application integrity

Where two identifiers must describe the same Project/Run/Task/owner, Development must enforce that relationship with one of:

1. an explicit foreign/composite key;
2. a PostgreSQL constraint trigger;
3. a transaction-scoped validation performed while all relevant rows are locked.

Application convention alone is insufficient for cross-authority security invariants.

Examples include:

- Run owner must be a Project member;
- Run GitHubIdentity must belong to the immutable Run owner;
- Task dependencies must stay in the same Workflow;
- Agent/Team membership must stay in the same Run;
- Artifact-parent relationships must satisfy Project isolation;
- active ResourceLeases must be unique and capacity-safe.

### Hard-delete policy

Authoritative Run/Workflow/Task/Job/Artifact/Approval/Action/Cost history is soft-retained. The normal application database role receives no general-purpose DELETE privilege over audit-critical lineage tables. Retention/GC runs through explicit maintenance procedures that first prove no active recovery, provenance or audit reference depends on the rows or blobs.

### Pre-emption lineage

MAX_PREEMPTION_DEPTH=1 must be represented by durable Run lineage, not inferred only from queue order. D1 defines the canonical `preempts_run_id` relationship.


---

## 25. Recursive Audit Cycle 6 — Leader Fencing and Typed Durable Events

### Advisory-lock connection semantics

PostgreSQL session advisory locks are held on **dedicated long-lived database connections** owned by each active controller.

Rules:

- do not acquire a leadership lock on a pooled connection that may be returned to the pool;
- loss of the lock connection immediately cancels/stops that controller loop;
- a controller re-enters active mode only after obtaining a fresh lock;
- external effects initiated by controllers still use D5 Action Journal/provider reconciliation because an external call can race connection loss.

LISTEN/NOTIFY uses a similarly restartable dedicated listener connection; on reconnect, consumers resume from durable Event sequence rather than trusting missed notifications.

### Typed Event construction

The generic `events.payload JSONB` column does not authorize arbitrary payload persistence.

Every production Event type has a versioned presentation/audit schema.

Event builders accept allowlisted structured fields and references, not raw:

- model prompts/responses;
- tool stdout/stderr;
- environment maps;
- request headers;
- secret-bearing adapter responses.

Redaction remains defence in depth; schema minimization is the primary control.

SSE uses an additional presentation projection so an internal audit Event cannot become client-visible merely because it exists in the Event table.


---

## 26. Recursive Audit Cycle 8 — Commit-Ordered Durable Cursors

PostgreSQL identity/sequence values are **not commit ordered**. Two concurrent transactions can allocate sequence 41 and 42, commit 42 first, and cause a naïve `sequence > cursor` consumer to skip 41 forever after advancing to 42.

Therefore any sequence used as a durable replay/high-water cursor must be allocated under transactional serialization that is held until commit.

This applies to:

- global Event replay sequence used by SSE;
- per-Run Action Journal watermark used by checkpoints/recovery.

Ordinary object IDs/counters that are not replay cursors may still use PostgreSQL identity sequences.

D1 defines the concrete cursor counters.

LISTEN/NOTIFY remains a wake-up only; consumers always replay from commit-safe durable cursors.
