# D8 — Observability, Cost, Budgets, Operations & Deployment

> **Status:** DESIGN ACCEPTED FOR DEVELOPMENT  
> **Depends on:** A6, A7, A8, A11, A12, D1, D4, D5, D6, D7  
> **Purpose:** Define the operational plane required to run Reverend Cloud v1 safely: metrics, tracing, event observability, immutable cost accounting, budget enforcement, provider reconciliation, backups, health, deployment, upgrades and operational runbooks.

---

## 1. Operational Principle

Reverend Cloud must make autonomous work inspectable and attributable.

For any meaningful action, operators should be able to answer:

~~~text
Who caused this work?
Which Project / Run / Task / Agent / Job?
Which model/runtime/node?
Which resource lease?
Which external action?
Which approval?
Which Artifact / evidence?
How long did it take?
How much did it cost?
Did verification pass?
Can the result be recovered?
~~~

Observability is not optional decoration.

It is part of correctness, recovery, security and economics.

---

## 2. Observability Layers

Cloud v1 distinguishes:

~~~text
Durable Domain Events
Operational Logs
Metrics
Trace Context
Provider Usage / Billing
Audit Events
Recovery Evidence
~~~

These layers may correlate through IDs, but they have different retention and authority.

Durable Events are authoritative history for state transitions.

Logs/metrics are operational telemetry and may be sampled/rotated.

---

## 3. Trace Context

Every request / Run execution path carries:

~~~text
trace_id
request_id
user_id
project_id
run_id
workflow_id?
task_id?
agent_instance_id?
job_id?
lease_id?
node_id?
action_id?
~~~

Null means genuinely not applicable.

It must not mean the system forgot to capture identity.

---

## 4. Logging Format

Use structured JSON logs in Cloud mode.

Example:

~~~json
{
  "timestamp": "2026-09-16T12:00:00Z",
  "level": "INFO",
  "service": "compute_scheduler",
  "event": "resource_lease_granted",
  "trace_id": "...",
  "run_id": "...",
  "job_id": "...",
  "node_id": "...",
  "lease_id": "...",
  "duration_ms": 12
}
~~~

Logs must pass through redaction before output.

---

## 5. Logging Prohibitions

Never log:

- session tokens;
- CSRF secrets;
- Authorization headers;
- GitHub credentials;
- RunPod API keys;
- Secret Broker plaintext;
- DB passwords;
- recovery keys;
- raw private keys;
- hidden model chain-of-thought;
- unrestricted prompt bodies by default.

Prompt/context logging is disabled by default.

If debugging requires a content capture, it must use an explicit local/admin diagnostic mode with redaction and short retention.

---

## 6. Metrics Categories

### Control Plane

~~~text
api_request_count
api_latency_seconds
api_error_count
postgres_transaction_latency
event_append_latency
sse_client_count
sse_replay_count
scheduler_loop_latency
scheduler_leader_status
~~~

### Run / Workflow

~~~text
runs_queued
runs_running
runs_paused
runs_awaiting_approval
runs_recovery_blocked
task_ready_wait_seconds
job_attempt_count
repair_rounds
~~~

### Agent / Model

~~~text
model_invocation_count
model_input_tokens
model_output_tokens
model_queue_wait_seconds
model_setup_seconds
model_inference_seconds
structured_output_failure_count
tool_call_count
context_tokens_selected
context_items_omitted
~~~

### Compute

~~~text
compute_nodes_by_state
resource_leases_active
lease_wait_seconds
worker_heartbeat_age
gpu_utilization
gpu_vram_used
provider_provision_seconds
worker_register_seconds
model_load_seconds
gpu_idle_grace_seconds
~~~

### Recovery

~~~text
checkpoint_commit_seconds
checkpoint_failure_count
recovery_generation_age
recovery_replica_ack_count
recovery_run_count
recovery_blocked_count
action_unknown_count
~~~

### Economics

~~~text
estimated_cost_gbp
actual_cost_gbp
gpu_billable_seconds
gpu_lease_seconds
shared_overhead_gbp
budget_remaining_gbp
provider_reconciliation_delta_gbp
~~~

---

## 7. Metrics Backend

Cloud v1 does not require a complex metrics stack to begin Development.

Acceptable initial implementation:

- existing Reverend observability store/events;
- structured logs;
- PostgreSQL cost/event queries;
- optional Prometheus-compatible endpoint.

If Prometheus is added, metrics must be operational projections, not a source of authority.

No Kubernetes dependency is introduced.

---

## 8. Durable Event vs Metric

Example:

~~~text
Run RUNNING → PAUSED
~~~

must produce a durable Event.

A metric:

~~~text
runs_paused = 1
~~~

may be regenerated.

Do not rely on a time-series metric to reconstruct Run state.

---

## 9. Cost Accounting Objects

A11 defines the canonical accounting model.

Cloud v1 persists:

~~~text
RateSnapshot
CostEvent
ComputeLeaseUsage
PowerSession
~~~

D1 includes durable RateSnapshot and CostEvent tables.

Development should add explicit repositories/services for ComputeLeaseUsage and PowerSession if not represented as typed CostEvents alone.

Recommended approach:

- keep PowerSession and ComputeLeaseUsage as first-class tables for lifecycle reconciliation;
- emit CostEvents from their state changes;
- derive user-facing totals from immutable CostEvents.

---

## 10. PowerSession

Represents one provider-billable worker lifecycle interval.

~~~text
PowerSession
├── power_session_id
├── provider
├── provider_instance_id
├── node_id?
├── deployment_profile_id
├── requested_start_at
├── provider_running_at
├── stop_requested_at
├── provider_stopped_at
├── billing_start_at
├── billing_end_at
├── rate_snapshot_id
├── estimated_cost_gbp
├── actual_cost_gbp?
└── reconciliation_state
~~~

A PowerSession may exist before any Run lease becomes attributable.

---

## 11. ComputeLeaseUsage

Represents attributable ResourceLease use.

~~~text
ComputeLeaseUsage
├── lease_id
├── user_id
├── project_id
├── run_id
├── job_id
├── node_id
├── deployment_profile_id
├── acquired_at
├── released_at
├── duration_seconds
├── rate_snapshot_id
└── estimated_cost_gbp
~~~

Lease time is attributed to the immutable Run owner.

---

## 12. RateSnapshot

RateSnapshot freezes the provider/FX rate used for historical estimates.

Fields:

~~~text
provider
product
provider tier
native rate
native currency
billing increment
minimum duration
FX source
FX rate to GBP
effective_at
captured_at
~~~

Historical bills never change because a later FX/provider price changes.

---

## 13. Rate Acquisition

Provider rate is captured when:

- a deployment profile is created/refreshed;
- before a new paid PowerSession starts if current snapshot is stale;
- provider reconciliation returns a differing billed rate.

Rate acquisition may use:

- provider API;
- manually configured validated rate;
- operator-approved snapshot.

If a reliable provider rate is unavailable:

- show estimate quality as unknown/low;
- hard budget admission should use conservative configured ceiling;
- do not pretend exact cost.

---

## 14. Cost Categories

### Variable attributable to Run owner

- active GPU lease;
- separately provisioned Run CPU worker;
- paid external model/API;
- Run-specific storage/egress.

### Shared fixed

Initial 50/50 split:

- persistent Control Plane host;
- baseline PostgreSQL/storage;
- backups;
- domain/DNS where paid;
- shared monitoring.

### Shared transient GPU overhead

Initial 50/50 split:

- provider boot before first attributable lease;
- model warm/load outside Run lease;
- idle grace after final lease;
- controlled drain;
- unavoidable provider reconciliation gap.

This policy is explicit and changeable later.

---

## 15. Cost Event Categories

Suggested enum:

~~~text
CONTROL_PLANE_FIXED
GPU_POWER_SESSION
GPU_LEASE
CPU_WORKER
EXTERNAL_API
STORAGE
NETWORK_EGRESS
BACKUP
SHARED_GPU_OVERHEAD
CREDIT_ADJUSTMENT
PROVIDER_RECONCILIATION
~~~

CostEvent is append-only.

Corrections use compensating events, not mutation of history.

---

## 16. Cost Estimation

Before paid admission:

~~~text
estimated duration
× current rate
+ expected startup overhead where applicable
~~~

For a newly provisioning GPU:

- Run budget must admit expected Run-specific lease;
- shared startup overhead follows shared policy.

Estimate is conservative.

The UI labels:

~~~text
estimated
~~~

until reconciliation.

---

## 17. Provider Reconciliation

Periodic/terminal reconciliation:

1. query provider instance/billing data;
2. match provider instance to PowerSession;
3. compute native actual;
4. apply stored/reconciliation FX RateSnapshot;
5. compare ledger estimate;
6. append reconciliation CostEvent;
7. mark PowerSession reconciled.

A material mismatch raises an operational alert.

No silent counter overwrite.

---

## 18. Budget Hierarchy

Canonical:

~~~text
User monthly
   ↓
Run
   ↓
Team
   ↓
Task
   ↓
Agent
   ↓
Job / operation
~~~

Cloud v1 minimum policy fields:

~~~text
max_run_cost_gbp
max_run_runtime_seconds
monthly_user_soft_limit_gbp
monthly_user_hard_limit_gbp
~~~

Optional child budgets are introduced through Agent/Team policies.

---

## 19. Soft Budget

Soft limit behavior:

- emit BudgetWarning Event;
- surface UI warning;
- allow current execution;
- optionally ask orchestrator to reduce optional work.

Soft limit does not revoke authority by itself.

---

## 20. Hard Budget

Hard limit behavior:

- prevent next charge-bearing action;
- allow current unsafe/non-interruptible action to settle;
- checkpoint at safe boundary;
- release paid resources where possible;
- transition Task/Run to blocked/failure policy as appropriate;
- surface bounded operator options.

Do not terminate a Git push/deployment in the middle merely to satisfy a cost limit.

---

## 21. Budget Reservation

Before expensive operation, reserve estimated amount against parent budget.

Conceptual:

~~~text
available = hard_limit - settled_cost - active_reservations
~~~

A reservation:

- has operation/Job identity;
- expires if admission never occurs;
- converts to measured usage as CostEvents arrive.

This prevents simultaneous Team Jobs from each assuming the same remaining budget.

---

## 22. Cost Dashboard

Per Run:

- owner;
- active deployment profile;
- active lease time;
- GPU/CPU usage;
- provider PowerSession estimate;
- shared overhead allocation;
- estimated total;
- reconciled total;
- hard/soft budget;
- remaining amount.

Per user/month:

- Run-variable spend;
- paid APIs;
- shared fixed allocation;
- shared transient overhead;
- actual/estimated status.

---

## 23. Primary Economic Metric

Reverend optimization remains:

> **GBP per verified successful engineering Task**

Benchmark record must distinguish:

~~~text
model/provider billed time
resource lease time
idle/warm overhead
verified success
human intervention
repair rounds
~~~

Tokens/second alone is not an economic success metric.

---

## 24. Health Model

Separate:

~~~text
liveness
readiness
functional health
provider health
recovery health
~~~

### Control Plane liveness

Process/event loop alive.

### Control Plane readiness

- PostgreSQL reachable;
- migrations supported;
- Secret Broker service healthy/reachable;
- no unresolved global recovery gate;
- scheduler/recovery service state valid.

### Worker health

Defined in D4.

### Model functional health

Bounded smoke request succeeds for expected DeploymentProfile.

---

## 25. Health Endpoints

Internal/administrative:

~~~text
/health/live
/health/ready
~~~

Public/system API exposes sanitized:

~~~text
GET /api/v1/system/status
~~~

Do not expose DB credentials/provider internals.

---

## 26. Alerts

Initial alert-worthy conditions:

- PostgreSQL unavailable;
- scheduler leader absent too long;
- RecoveryGeneration too old;
- no recovery replica ACK beyond threshold;
- repeated worker registration failure;
- provider provisioning timeout;
- cost reconciliation delta exceeds threshold;
- hard budget unexpectedly bypassed;
- Secret Broker key unavailable;
- RECOVERY_BLOCKED Run;
- Event/SSE sequence corruption;
- backup verification failure;
- disk capacity low.

Cloud v1 can initially deliver alerts through logs/UI; external notification integration is optional.

---

## 27. PostgreSQL Backup

Minimum policy:

- nightly logical backup;
- backup before schema-destructive migration;
- recovery generation before planned authoritative host replacement/shutdown;
- periodic restore test.

Use encrypted storage.

A backup is not accepted until:

- command succeeds;
- file hash recorded;
- restore test policy satisfied.

---

## 28. BlobStore Backup

Content-addressed durable objects referenced by active:

- Artifacts;
- checkpoints;
- recovery generations;
- Project state

must be included in backup/replication policy.

Garbage collection cannot remove objects referenced by any retained durable manifest.

---

## 29. Secret Backup

Backup contains encrypted secret rows and protected recovery-key procedure/material.

Do not copy plaintext secrets into generic backup archives.

Test secret restoration on an isolated replacement environment.

---

## 30. Recovery Replica Monitoring

Track:

~~~text
latest complete RecoveryGeneration
latest ACK per recovery-enabled device
age since acknowledged generation
device revoked/offline state
~~~

Planned authoritative-host shutdown gate consumes these metrics.

---

## 31. Persistent Host Deployment

Initial target:

~~~text
Hetzner CX33-class x86
4 vCPU
8 GB RAM
80 GB NVMe
EU region
~~~

Recommended deployment style:

- Debian/Ubuntu LTS;
- dedicated reverend service user;
- PostgreSQL;
- Python virtualenv or pinned application container;
- systemd services;
- HTTPS reverse proxy;
- Tailscale/private network.

No Kubernetes.

---

## 32. Service Units

Suggested logical systemd units:

~~~text
reverend-api.service
postgresql.service
reverend-backup.timer
reverend-backup.service
reverend-recovery-replication.timer
~~~

Scheduler/capacity/recovery loops may initially live inside reverend-api/application process under PostgreSQL leader locks.

If later split, service boundaries already exist in code.

---

## 33. Reverse Proxy

Acceptable choices:

~~~text
Caddy
or
nginx
~~~

Responsibilities:

- TLS;
- request size limits;
- security headers;
- proxy to private ASGI bind;
- SSE streaming without buffering;
- no direct PostgreSQL/vLLM exposure.

Do not place application identity solely in proxy headers without cryptographic/session validation.

---

## 34. PostgreSQL Network

PostgreSQL binds only to local/private interface required by Reverend.

No public internet port.

Use a dedicated database role with only required schema privileges.

Migration role is separate from the normal runtime role in Cloud v1.

---

## 35. Disk Layout

Suggested:

~~~text
/var/lib/reverend/
├── objects/
├── workspaces/
├── backups/
└── state/

/etc/reverend/
├── runtime.env
└── secret-key
~~~

Exact paths may follow distro conventions.

Secrets/config permissions are restricted.

Repository source checkout is separate from state directory.

---

## 36. Upgrade Procedure

Cloud application upgrade:

1. ensure clean Git/release artifact;
2. run portable tests/contract tests;
3. create backup;
4. place scheduler in drain/maintenance mode;
5. allow active Run safe boundary or pause;
6. apply backward-compatible DB migrations;
7. restart application with new runtime epoch;
8. recovery controller reconciles stale leases/work;
9. verify readiness;
10. resume queued work.

Do not hot-upgrade model/provider code in the middle of an unjournalled side effect.

---

## 37. Schema Migration Safety

Before destructive migration:

- backup;
- validate old schema version;
- migration transaction where possible;
- run integrity checks;
- refuse startup if migration partially applied.

Migration checksums are recorded.

Production does not auto-run unknown newer migrations.

---

## 38. Provider/Model Upgrade

A DeploymentProfile upgrade creates a new profile identity.

Do not mutate:

~~~text
qwen3.8-...-v1
~~~

to point silently at a different model/runtime image.

Create:

~~~text
...-v2
~~~

benchmark it, promote it, then disable/retire v1 for new Jobs.

Historical Runs preserve original profile provenance.

---

## 39. Maintenance Mode

Persistent Control Plane supports a durable maintenance flag.

While enabled:

- clients can authenticate/read;
- no new Run enters STARTING;
- current Run may be safely paused/drained;
- provider provisioning disabled unless explicitly needed for recovery;
- admin operations/backups allowed.

Maintenance state is visible to UI.

---

## 40. Provider Outage

If RunPod unavailable:

- queued GPU Jobs remain queued;
- Capacity Controller records provider unavailable;
- Control Plane remains online;
- no weaker trust/model profile is silently selected;
- user sees bounded status;
- CPU-only work may continue if dependencies allow.

If an active worker survives provider API outage, scheduler may continue using it while lease/worker health remain valid, but destructive lifecycle actions may be deferred.

---

## 41. Control Host Resource Protection

Persistent authority must remain responsive.

Reserve resources for Control Plane.

Do not run arbitrary heavyweight builds directly on authority host.

Use:

- process memory/CPU limits for bounded internal tasks;
- separate CPU worker for untrusted/heavy work.

Disk monitor must protect PostgreSQL/WAL from workspace/cache exhaustion.

---

## 42. Local Development Environment

Development should provide a local cloud-stack profile, for example:

~~~text
PostgreSQL container/local service
Reverend cloud API
fake/in-memory ComputeProvider
fake worker
mock InferenceRuntime
~~~

This permits deterministic CI without real RunPod cost.

Live provider tests run separately.

---

## 43. Configuration Validation

At startup validate:

- DATABASE_URL;
- state/blob root;
- secret key;
- public URL;
- auth/session settings;
- RunPod provider secret reference if enabled;
- recovery policy;
- idle grace;
- budget defaults.

Invalid security-critical configuration fails startup.

---

## 44. CI Layers

### Portable unit/contract CI

No paid providers.

### PostgreSQL integration CI

Ephemeral PostgreSQL.

### Fault-injection CI

Recovery/action/checkpoint tests.

### Browser/API CI

Auth + SSE + UI contract.

### Live provider validation

Explicit/manual/protected:
- RunPod provisioning;
- vLLM model load;
- ReverendBench smoke;
- billing reconciliation.

Live tests never run automatically on every commit without explicit cost authorization.

---

## 45. Operational Runbooks

Documentation/Design should lead Development to create operational runbooks before C9 for:

~~~text
restore PostgreSQL/BlobStore
rotate master secret key
rotate GitHub credential
rotate RunPod API key
recover RECOVERY_BLOCKED Run
replace control host
handle provider outage
drain GPU worker
disable compromised worker
stop Project/Global execution
perform Cloud upgrade
reconcile billing mismatch
~~~

Runbooks should reference executable commands, not only prose.

---

## 46. D8 Acceptance Tests

Must prove:

- cost derived from immutable events;
- RateSnapshot preserves historical estimate;
- Run-owner lease cost attribution;
- shared overhead split policy;
- hard budget blocks next paid action safely;
- PowerSession reconciles provider actual;
- logs redact seeded test secrets;
- readiness fails when DB/key missing;
- zero-GPU status remains ready;
- PostgreSQL backup restores to blank instance;
- BlobStore referenced object restores/validates;
- maintenance mode stops new execution;
- profile version change preserves historical provenance.

---

## 47. Exit Condition

C8 is ready when operators can observe identity-to-cost lineage for a Run, enforce budgets safely, recover/backup authoritative state, operate the persistent host without exposing worker/model internals publicly, and distinguish estimated from provider-reconciled cost.


---

## 48. Recursive Architecture Hardening — Durable Economics and Recovery Operations

### PowerSession and ComputeLeaseUsage are mandatory

The ambiguity in Section 9 is resolved: Cloud v1 persists both `PowerSession` and `ComputeLeaseUsage` as first-class D1 records.

They are not optional projections because provider reconciliation and owner attribution require stable lifecycle identities.

### Budget reservations are durable

The Section 21 reservation is implemented with D1 `budget_reservations`.

Reservation creation is transactional with paid-operation admission.

A crash cannot leave unbounded phantom reservations:

- ACTIVE reservations have explicit expiry;
- startup reconciliation releases/settles expired reservations only after checking related Job/lease/provider state;
- settlement references immutable CostEvents.

### Cost reconciliation is idempotent

Every provider-derived CostEvent uses a stable `external_event_key` or deterministic reconciliation key.

Repeated provider polling with the same billable event therefore returns the existing ledger effect rather than appending another charge.

Corrections remain compensating immutable events.

### Off-host recovery freshness target

Nightly database backup alone is not sufficient for the accepted durability goal.

Initial Cloud v1 recovery policy:

~~~text
RecoveryGeneration target age <= 15 minutes while authoritative state is changing
+
immediate generation after a high-value safe boundary when practical:
  Run pause
  approval wait
  high-level Task completion
  protected external side effect
  planned Control Plane shutdown
~~~

Implementation may optimize with incremental/WAL-aware techniques later, but user-visible recovery health is measured against the effective off-host acknowledged generation age.

If no authorized recovery peer/object target acknowledges within the target:

- system remains operational;
- recovery health becomes DEGRADED;
- operator/UI receives an alert;
- planned authoritative-host shutdown remains inhibited.

### Backup independence

A local backup on the persistent host is not counted as off-host disaster recovery.

At least one acknowledged encrypted off-host copy is required to claim healthy control-host disaster recovery.

### Billing uncertainty

When provider actual usage is not yet available, the UI and APIs must distinguish:

~~~text
estimated
provisional
reconciled_actual
~~~

A provisional value must never be presented as final actual spend.

### Disk-exhaustion protection

The persistent host reserves minimum free space for PostgreSQL/WAL and critical recovery writes.

Workspace, model cache, logs and BlobStore growth are subject to quotas/GC thresholds that stop non-critical work before the authority store can be starved of disk.

### Time and monotonic measurement

Wall-clock timestamps are authoritative for durable audit/billing records.

Process duration measurements use a monotonic clock and are converted into durable duration fields; elapsed-time calculations must not rely on wall-clock subtraction across clock adjustments.


---

## 49. Recursive Audit Cycle 2 — Provider-Cost Leakage, GC Safety and Recovery Health

### Provider lifecycle cost safety

Provider provision/start/stop/terminate operations are Action-Journalled charge-bearing operations.

Before provisioning:

- create provider ActionRecord intent;
- create/associate PowerSession;
- reserve budget;
- attach Reverend reconciliation tags/idempotency metadata where the provider permits.

After crash/restart, Capacity Controller reconciles provider inventory before creating replacement capacity.

### Zero-compute means provider-confirmed zero compute billing

“GPU count is zero” is not inferred from local worker absence.

Scale-to-zero success requires provider state proving that billable compute has stopped. If a provider stop state still incurs compute charges, Cloud v1 terminates the instance when zero-compute policy requires it.

Persistent disk/storage cost remains visible separately.

### Blob GC and backup coordination

BlobStore GC is two-phase mark-and-sweep with:

- roots from live Artifacts/checkpoints/RecoveryGenerations/backups;
- a minimum age grace period for unpublished objects;
- coordination/advisory locking with RecoveryGeneration publication;
- post-sweep integrity sampling.

GC never races a newly published recovery manifest into deleting its object set.

### Recovery health states

Expose:

~~~text
HEALTHY
DEGRADED
UNSAFE
~~~

Interpretation:

- HEALTHY — valid off-host acknowledged RecoveryGeneration within target age;
- DEGRADED — durable local state is healthy but off-host recovery point is stale/unavailable;
- UNSAFE — authoritative local state/backup integrity is itself uncertain.

A DEGRADED system may continue bounded work but planned host shutdown remains inhibited and UI/operator alerts remain visible.

### Worker reuse after backend restart

A surviving worker reconnect may reduce unnecessary provider cost, but no previous-epoch lease is revived.

Cost attribution for idle time during backend recovery remains a PowerSession/provider cost, not fabricated Run lease usage.


---

## 50. Recursive Audit Cycle 3 — Authority-Host Resource Reservation and Time Integrity

### Control Plane resource reservation

The persistent host maintains explicit headroom for authority services.

Configuration defines minimum reserved:

~~~text
CPU capacity
RAM
filesystem free bytes
PostgreSQL/WAL free bytes
process/file descriptor headroom
~~~

The local bounded sandbox may use only the remainder.

If admitting a local Job would violate these reserves, Compute Scheduler keeps it queued or targets a remote CPU worker.

### Disk pressure priority

When storage pressure crosses safety threshold, stop/admit in this order:

1. stop new cache/model/index growth;
2. stop new large Artifact/workspace creation;
3. pause non-critical execution at safe boundaries;
4. preserve PostgreSQL/WAL, Action Journal, checkpoints and recovery writes.

Authority durability has priority over throughput.

### Clock integrity

The host runs reliable time synchronization.

Durable expiry/auth/billing timestamps use UTC wall clock, while in-process elapsed durations use monotonic clocks.

A detected material backward/forward wall-clock jump creates an operational warning and security-sensitive expiry checks use conservative behavior until time health is restored.


---

## 51. Recursive Audit Cycle 4 — Privilege-Separated Service Operations

Because Secret Broker is now an OS-level privilege boundary:

- Control Plane readiness checks **Secret Broker service health/reachability**, not whether the general application process can read the master key;
- the key file is owned/readable only by the Secret Broker helper identity;
- systemd/service supervision includes the Secret Broker helper;
- application startup fails closed for operations requiring secrets if the helper is unavailable, while read-only/status paths may remain available.

Recommended logical units now include:

~~~text
reverend-api.service
reverend-secret-broker.service
postgresql.service
reverend-backup.timer
reverend-recovery-replication.timer
~~~

The Secret Broker Unix socket is not mounted or permissioned into sandbox/worker identities.

### Recovery-key monitoring

Recovery health verifies not only replica age but also that at least one currently authorized recovery recipient can decrypt the current key envelope according to a periodic non-destructive recovery test policy.

A generation with no usable key recipient is not HEALTHY even if all bytes and hashes are present.


---

## 52. Recursive Audit Cycle 5 — Database Privilege and Safety-Budget Operations

### Runtime database credentials

Production application uses a non-owner `reverend_app` PostgreSQL role.

Schema migration uses a separate `reverend_migrator` credential available only during controlled deployment/migration.

The runtime role cannot:

- ALTER/DROP schema;
- disable immutable-history triggers;
- grant itself privileges;
- perform unrestricted hard deletes.

The previous wording that a separate migration role “may” be used is superseded: role separation is mandatory for Cloud v1.

### Local PostgreSQL authentication

On a single persistent host, prefer Unix-socket/peer or tightly scoped SCRAM authentication so a reusable database password need not be exposed broadly.

Regardless of mechanism, sandbox/worker identities cannot authenticate as the application database role.

### Safety recovery reserve

Budget policy includes a small configured safety reserve separate from ordinary Run productive budget.

It can pay only for trusted cleanup/reconciliation described in D5.

Dashboard exposes:

~~~text
productive spend
shared overhead
safety recovery overrun
reconciled actual
~~~

This keeps the hard budget meaningful without making it unsafe.

### Emergency mode observability

While STOP_GLOBAL/Project/Run is active, health/status distinguishes:

~~~text
productive execution blocked
safety cleanup in progress
safe/drained
~~~

An emergency-stop UI must not display “stopped” until required cleanup has settled.


---

## 53. Recursive Audit Cycle 6 — Host Storage and Process Hardening

Production host baseline includes:

- encrypted-at-rest persistent volume or equivalent provider storage encryption;
- restrictive mount/file ownership;
- Secret Broker helper key material inaccessible to the general service user;
- core dumps disabled or tightly controlled for Secret Broker/credential adapter processes;
- swap disabled or encrypted when Secret-bearing processes could page;
- firewall default-deny except required HTTPS/private management paths;
- PostgreSQL bound only to required local/private interface;
- regular security updates with controlled restart procedure.

These are host-security requirements, not substitutes for application authorization.

### Event/log data minimization

Operational logs and durable Events prefer identifiers, hashes, status codes and bounded summaries over raw content.

A debug mode that captures raw prompts/tool output cannot run by default in production and must advertise that it weakens confidentiality.


---

## 54. Recursive Audit Cycle 7 — Control/Inhibitor Operations

Operational status surfaces:

- active SYSTEM/PROJECT/RUN execution controls;
- who created them;
- safe public reason summary;
- whether productive execution is blocked;
- whether safety cleanup remains active;
- current shutdown/drain inhibitors.

### Inhibitor watchdog

A periodic controller scans expired/stale shutdown inhibitors.

It clears one only after proving the owning Action/Job is terminal or reconciled.

An inhibitor with ambiguous external state creates an alert/RECOVERY_BLOCKED path rather than being force-cleared automatically.

### Maintenance migration interaction

Schema migration activates a SYSTEM MAINTENANCE control and a MIGRATION shutdown inhibitor before DDL begins.

Runtime API may serve bounded read/status endpoints, but no scheduler/provider work begins until migration and post-migration integrity checks complete and the control is explicitly cleared.


---

## 55. Recursive Audit Cycle 9 — Ledger Reconciliation Semantics

### Source cost vs allocation

The cost ledger distinguishes provider/system SOURCE_COST from user ALLOCATION.

For shared 50/50 overhead:

~~~text
one SOURCE_COST = actual provider/control-host cost
↓
two ALLOCATION events = policy shares
~~~

System-wide spend reports source economic cost once.

Per-user reports consume allocation events.

A reconciliation test verifies allocations do not create or destroy cost unintentionally.

### Billing periods

Monthly user soft/hard limits use an explicit configured billing timezone/calendar definition; Cloud v1 default is UTC calendar month.

The API reports the period start/end alongside totals so clients do not infer local-month boundaries differently.

### Model metrics are not duplicate invoices

Token/model invocation telemetry on self-hosted GPU is observability used for optimization and attribution.

It is not added as a second payable cost on top of provider PowerSession/lease charges unless a distinct paid API actually invoices by usage.


---

## 56. Recursive Audit Cycle 12 — Recovery Intent Target Operations

Operational recovery health now has two independent dimensions:

~~~text
full RecoveryGeneration freshness
external-action write-ahead availability
~~~

Status must show:

- latest full off-host generation/age;
- ACTIVE recovery targets;
- whether at least one target can currently ACK `OFF_HOST_INTENT_ACK` actions;
- count/age of intent deltas not yet subsumed by a later full RecoveryGeneration.

An old full generation may be DEGRADED while external mutation safety remains available through current ActionIntent ACKs.

Conversely, a fresh generation does not authorize a new high-risk external effect when no current durable target can ACK its intent.

### Object-store recovery target

The recovery-target interface supports a small encrypted object-store backend in addition to client peers.

Requirements:

- credentials resolved only at trusted enforcement boundary;
- content encrypted/authenticated before upload;
- immutable/content-addressed object naming where practical;
- write success verified before ACK;
- no public bucket/container;
- lifecycle/retention must preserve objects referenced by retained generations/intents.

Selecting a concrete object-store provider is an operational deployment choice, not a new authority model.


---

## 57. Recursive Audit Cycle 13 — Static Economic Kill Limits

Cloud v1 deployment configuration contains operator-owned hard ceilings such as:

~~~text
REVEREND_MAX_PAID_GPU_WORKERS_TOTAL=1
REVEREND_MAX_PROVISIONING_GPU_WORKERS_TOTAL=1
REVEREND_MAX_GPU_HOURLY_RATE_GBP=<operator ceiling>
REVEREND_MAX_PROVIDER_DAILY_SAFETY_GBP=<operator ceiling>
~~~

Exact names may be normalized in Development.

Properties:

- values are validated at startup;
- they are not writable by Agents/models/Project policies;
- a dynamic user/Run/system budget cannot exceed them;
- lowering a ceiling triggers reconciliation/drain policy, not abrupt unsafe process kill;
- raising a ceiling is an operator-controlled configuration/deployment action.

### Provider-wide daily circuit breaker

Capacity Controller derives provider spend from reconciled/estimated PowerSessions.

When the system safety ceiling is reached:

- no new paid capacity is provisioned;
- currently necessary safety cleanup may continue;
- existing productive leases follow configured safe drain/budget policy;
- operator alert is raised.

This circuit breaker is defence against both software bugs and compromised high-level orchestration.

### Orphan inventory audit

Periodic provider reconciliation compares:

~~~text
provider inventory tagged as Reverend
vs
ComputeNode + PowerSession + ActionJournal state
~~~

Any orphan/unrecognized billed resource is treated as a high-severity operational incident and safely terminated after identity/reconciliation checks.

Do not wait for the user's Run dashboard to reveal it.


---

## 58. Recursive Audit Cycle 14 — Build and Runtime Provenance Operations

Deployment operations retain provenance for the Control Plane and worker release artifacts:

~~~text
Reverend source commit
Python dependency lock/hash set
worker image digest
worker build source commit
vLLM/runtime version
base image digest
model artifact manifest
model revision
~~~

Security updates to a runtime image are deployed as a new immutable release/profile identity.

Operations should periodically review:

- base image vulnerabilities;
- Python dependency advisories;
- vLLM/runtime security releases;
- model repository revision/license changes.

Production never auto-upgrades a model/runtime dependency merely because a newer mutable tag/revision exists.


---

## 59. Capability Fabric Observability & Economics

D10–D16 add required telemetry.

### Research

~~~text
search_provider_calls
source_fetch_attempts
browser_fetches
source_cache_hit/miss
source_refresh_count
download_bytes
evidence_claims_accepted/rejected
research_wall_seconds
research_cost_gbp
~~~

### Repository Intelligence

~~~text
repository_index_seconds
files/symbols/graph_edges
incremental_files_reindexed
lsp_health
repo_query_latency by strategy
semantic_index_hit/miss
stale_result_rejections
~~~

### Browser / CPU worker

~~~text
worker_boot_seconds
browser_start_seconds
build/test_seconds
worker CPU/RAM peak
worker billed seconds/cost
~~~

### Model cold start

~~~text
model_cache_hit/miss
model_download_bytes
model_download_seconds
artifact_verification_seconds
model_load_seconds
runtime_warmup_seconds
cold_start_total_seconds
~~~

### Context

~~~text
context_tokens_selected
exact/lexical/semantic/research retrieval counts
context_refresh_count
omitted optional items
compression count
ContextManifest build latency
~~~

### Storage economics

Track separately:

- temporary provider disk;
- optional persistent warm cache/volume;
- durable Control Plane BlobStore;
- model/download egress if billed;
- cache benefit measured as saved startup/billable time.

Persistent model cache is promoted only when measured savings exceed storage/complexity cost.

### Idle/termination optimization

ReverendBench may compare 5/7/10-minute or adaptive idle policy, but default remains 420 seconds until evidence changes it.

Scale-to-zero means provider-confirmed compute billing ends; optional storage charges remain visible separately.


---

## 60. Capability Cache Retention & Quotas

Operational quotas distinguish:

~~~text
durable evidence Blob storage
source acquisition cache
repository derived index
model cache
browser cache
build/package cache
temporary workspace
~~~

GC priority removes reconstructible caches before durable evidence/recovery material.

Metrics include cache bytes by class and eviction cause.

A retained SourceSnapshot referenced by Evidence/Decision/Requirement is a durable Blob root and is never evicted by ordinary web-cache pressure.

Optional warm provider volumes must not contain untracked authoritative workspace state or Secret material.


---

## 61. Derived-Service Placement & Control-Host Sizing

The original Hetzner CX33-class 4-vCPU/8-GB host remains a starting baseline, not a proof that every modernized capability fits there.

Measure separately:

~~~text
PostgreSQL/WAL
API/SSE
scheduler/recovery
Secret Broker
Blob metadata
SearXNG
Qdrant
repository indexes
language servers
research/document parsing
~~~

Authority services have reserved headroom.

If derived/reconstructible services pressure that reserve, move them to a CPU service/worker before upsizing or co-locating further workload.

Operational acceptance includes a sustained-load test proving API/PostgreSQL/recovery remain responsive during research/index/build activity.


---

## 62. Background Work & Artifact Retention Operations

Cloud v1 background execution is divided cleanly.

### Allowed system housekeeping

~~~text
backup / restore verification
recovery replication
provider inventory reconciliation
cost reconciliation
session/credential cleanup
health probes
cache garbage collection
derived-index cleanup
security update checks
~~~

### Not autonomous background work

~~~text
web research
Project replanning
Memory promotion
repository mutation
new model experiments
Agent Team execution
~~~

Those require a Run/benchmark Run or explicit administrative operation.

This avoids unowned spend and hidden state mutation.

### Browser/source Artifact quotas

Operations track and quota:

- retained SourceSnapshot bytes;
- screenshots;
- videos/traces;
- downloaded documents;
- temporary browser cache.

Sanitized retained test/research Artifacts follow Project retention policy. Disposable browser state is cleaned at Job/worker termination.
