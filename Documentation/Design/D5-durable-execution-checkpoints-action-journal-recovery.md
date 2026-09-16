# D5 — Durable Execution, Checkpoints, Action Journal & Recovery

> **Status:** DESIGN ACCEPTED FOR DEVELOPMENT  
> **Depends on:** A7, A12, D1, D4  
> **Purpose:** Define the exact application-level durability protocol for pause/resume, approvals, crashes, worker loss, Control Plane restart, and full control-host recovery.

---

## 1. Durability Invariant

Cloud v1 implements:

> **Compute is replaceable. Run state is durable.**

Recovery may not depend on:

- Python object memory;
- thread/process stacks;
- PIDs;
- open sockets;
- worker container identity;
- CUDA context;
- GPU VRAM;
- vLLM KV cache.

A durable Run is reconstructed from PostgreSQL, BlobStore, Git/workspace recovery material, Action Journal, and checkpoints.

---

## 2. Run Lifecycle v1

Canonical states:

~~~text
QUEUED
STARTING
RUNNING
PAUSE_REQUESTED
PAUSING
PAUSED
RESUME_QUEUED
RESUMING
AWAITING_APPROVAL
RECOVERING
RECOVERY_BLOCKED
COMPLETED
FAILED
CANCELLED
~~~

State authority is PostgreSQL.

Workers may report observations but do not own Run state.

---

## 3. Safe Action Boundary

The execution engine uses:

~~~text
prepare action
↓
persist ActionRecord intent
↓
mark STARTED when appropriate
↓
execute bounded action
↓
observe result
↓
persist ActionRecord result
↓
commit workflow/Job changes
↓
write checkpoint where policy requires
↓
safe interruption point
~~~

A normal pause waits for this safe boundary.

---

## 4. Action Classification

Every executable tool operation declares:

~~~text
side_effect_class
interruptibility
resume_strategy
approval_policy
checkpoint_policy
~~~

Initial side-effect classes:

~~~text
PURE_READ
REPEATABLE_COMPUTE
LOCAL_MUTATION
REMOTE_IDEMPOTENT
REMOTE_RECONCILABLE
IRREVERSIBLE_OR_HIGH_RISK
~~~

The class informs journal/recovery behavior.

---

## 5. ActionRecord v1

Fields are defined in D1.

Required creation:

- before external side effect;
- before local durable mutation whose duplicate application would matter;
- optional for pure read-only operations where no recovery ambiguity exists.

State machine:

~~~text
PLANNED
  ↓
STARTED
  ├── COMPLETED
  ├── FAILED
  ├── INTERRUPTED
  └── UNKNOWN
~~~

UNKNOWN is used when the system cannot prove whether the external effect happened.

---

## 6. Resume Strategies

### RESTART

Safe to repeat from prior durable state.

Examples:

- LLM inference;
- embedding;
- web fetch;
- tests;
- build.

### VERIFY_THEN_RETRY

Inspect external/local state before retry.

Examples:

- Git commit;
- Git push;
- PR creation;
- atomic file write.

### REBUILD

Reconstruct an environment rather than attempting in-place continuation.

Examples:

- uncertain package environment;
- disposable worker workspace.

### MANUAL_RECOVERY

Automatic reconciliation cannot prove a safe outcome.

Examples:

- ambiguous deployment;
- non-queryable third-party side effect.

---

## 7. Tool Recovery Registry

Create a registry keyed by:

~~~text
tool_name + operation
~~~

Each entry defines:

- resume_strategy;
- reconciler callable;
- safe interruption behavior;
- result verification;
- idempotency support.

No side-effecting tool is production-ready until its recovery class is registered and tested.

---

## 8. Checkpoint v1

RunCheckpoint contains logical recovery references rather than a memory snapshot.

Manifest includes at least:

~~~text
checkpoint_id
schema_version
run_id
project_id
owner_user_id
sequence
created_at
run_status_at_checkpoint

workflow refs
task graph ref
completed task IDs
pending task IDs
current task/job
agent state refs
TeamPlan refs

plan refs
ContextManifest refs
Memory refs

workspace ref
repository state ref

Artifact manifest ref
Evidence refs
Decision refs

budget state
retry state
Approval refs

last Action ID
Action Journal watermark

object hashes
complete flag
~~~

Large data is referenced, not copied.

---

## 9. Checkpoint Publication

Algorithm:

~~~text
build candidate manifest
↓
write all new BlobStore objects
↓
fsync / verify object hashes
↓
begin PostgreSQL transaction
↓
insert checkpoint complete=false
↓
validate references
↓
set complete=true
↓
advance runs.active_checkpoint_id
↓
insert CheckpointCommitted event
↓
commit
~~~

If commit fails, the checkpoint is not active.

Unreferenced content-addressed blobs may be garbage-collected later.

---

## 10. Checkpoint Frequency

Required checkpoints:

- after completed high-level Task;
- before normal pause completes;
- before authoritative host planned shutdown;
- after security-relevant approval decision where execution cursor changes;
- before selected high-risk operations where rollback/reconciliation warrants it;
- periodically during long Jobs with large recovery window.

Avoid checkpointing every model token/tool read.

Policy should balance recovery point objective and write cost.

---

## 11. Normal Pause

Sequence:

1. RUNNING → PAUSE_REQUESTED;
2. scheduler stops admitting new non-required actions for that Run;
3. current atomic action settles;
4. ActionRecord is persisted;
5. execution/workflow state commits;
6. complete checkpoint publishes;
7. active compute/tool leases release;
8. PAUSING → PAUSED;
9. queue slot becomes available.

No new GPU lease remains held merely because the Run is paused.

---

## 12. Run-Now Pre-emption

Cloud v1:

~~~text
MAX_ACTIVE_TOP_LEVEL_RUNS = 1
MAX_PREEMPTION_DEPTH = 1
~~~

Example:

~~~text
Run A RUNNING
↓
Run B run-now request
↓
A PAUSE_REQUESTED
↓
A safe checkpoint
↓
A RESUME_QUEUED
↓
B STARTING → RUNNING
↓
B terminal/pause
↓
A RESUMING → RUNNING
~~~

A third Run cannot recursively pre-empt B while A is already pre-empted.

---

## 13. Awaiting Approval

Approval wait is a durable zero-compute state.

Sequence:

~~~text
next action requires approval
↓
persist Approval
↓
settle current action
↓
checkpoint contains approval_ref + workflow cursor
↓
verify checkpoint
↓
release execution leases
↓
AWAITING_APPROVAL
~~~

No active GPU cost is attributed while no resource lease exists.

---

## 14. Approval Decision Resume

Approve endpoint:

- records human decision;
- does not execute action.

Then:

~~~text
AWAITING_APPROVAL
↓
RESUME_QUEUED
↓
scheduler grants fresh compute/tool context
↓
RESUMING
↓
revalidate:
  approval state
  expiry
  Run owner
  effective identity
  action fingerprint
  target/scope
  current policy
↓
execute normal Tool Broker path
~~~

If any security-relevant input changed, require a new Approval.

---

## 15. Worker Loss

Worker loss path:

~~~text
heartbeat expires / provider gone
↓
ComputeNode UNREACHABLE
↓
active lease EXPIRED/REVOKED
↓
Job execution interrupted
↓
classify current ActionRecord
↓
Run remains durable
↓
RECOVERING if needed
↓
replacement capacity
↓
new Job attempt / resume
~~~

No old worker can later submit authoritative success without current epoch/lease validation.

---

## 16. Backend Process Restart

On startup:

1. open PostgreSQL and BlobStore;
2. create new runtime_epoch_id;
3. acquire recovery-controller leadership;
4. invalidate stale worker sessions;
5. expire/revoke previous-epoch active leases;
6. locate non-terminal Runs;
7. inspect clean-shutdown marker/runtime metadata;
8. recover each Run by durable state;
9. release recovery leadership when stable.

---

## 17. Run Recovery Algorithm

For each non-terminal Run:

~~~text
load durable Run state
↓
select newest complete valid checkpoint
↓
verify manifest hash + referenced blobs
↓
reconstruct/verify workspace
↓
inspect Action Journal after checkpoint watermark
↓
reconcile STARTED / UNKNOWN actions
↓
classify state
├── AWAITING_APPROVAL + pending approval
│     → restore AWAITING_APPROVAL, no compute
├── PAUSED
│     → restore PAUSED, no compute
├── runnable interrupted work
│     → RECOVERING → RESUME_QUEUED
└── unresolved ambiguity
      → RECOVERY_BLOCKED
~~~

Do not jump directly from recovery to RUNNING.

All runnable recovery returns through scheduling.

---

## 18. UNKNOWN Action Reconciliation

Example Git push:

~~~text
ActionRecord = STARTED
local process died
remote may have accepted push
~~~

Reconciler:

1. query remote branch/ref;
2. compare expected commit;
3. if present, persist COMPLETED;
4. if absent and retry safe, retry using same idempotency intent;
5. if ambiguous, RECOVERY_BLOCKED.

Blind retry is prohibited.

---

## 19. Git Workspace Recovery

Checkpoint repository state includes:

~~~text
repository identity
workspace/worktree identity
Run branch
base commit
HEAD
index state where needed
uncommitted diff/blob refs
untracked-file manifest/hash
~~~

Implementation may use internal local refs:

~~~text
refs/reverend/checkpoints/<run-id>/<sequence>
~~~

They are local recovery primitives, not necessarily remote pushes.

---

## 20. Workspace Persistence Strategy

For disposable workers:

- no unique progress may exist only on worker disk at safe boundary;
- patch/artifact/Git state must be transferred back to durable storage;
- worker can be terminated after confirmation.

For persistent control-host local worktrees:

- worktree may remain on disk;
- checkpoint still records enough information to verify/reconstruct after host replacement.

---

## 21. Control Host Graceful Shutdown

Authoritative host shutdown is stronger than GPU drain.

Before shutdown:

1. stop new Run admission;
2. let active work reach safe boundaries;
3. checkpoint all non-terminal Runs;
4. flush Action Journal/events/cost records;
5. take consistent PostgreSQL backup;
6. verify BlobStore durability;
7. create RecoveryGeneration;
8. obtain required off-host replica ACK;
9. write CleanShutdownRecord;
10. stop services.

If required recovery ACK cannot be obtained, automatic shutdown is inhibited.

---

## 22. RecoveryGeneration v1

Contains:

~~~text
generation_number
created_at
PostgreSQL backup ref
RunCheckpoint refs
Action Journal watermark/snapshot ref
repository recovery refs
Artifact/Blob refs
encrypted Secret-store backup ref
object hashes
complete flag
~~~

Use monotonic generation number.

Do not select recovery truth only by timestamps.

---

## 23. Client Recovery Replicas

Registered recovery-enabled devices may store encrypted content-addressed recovery packages.

They are backup peers only.

Protocol:

~~~text
Control Plane creates complete generation
↓
encrypt/package
↓
send manifest + objects to authenticated recovery device
↓
device fsyncs
↓
device verifies hashes
↓
device ACKs generation/hash
~~~

A network send without durable ACK is not a replica.

---

## 24. Required Replication Policy

For planned authoritative host shutdown:

~~~text
latest RecoveryGeneration valid locally
+
at least 1 authorized off-host durable ACK
~~~

Two client ACKs preferred when both devices are available.

A12 allows future object-store backup; clients do not become authority.

---

## 25. CleanShutdownRecord

Persist:

~~~text
runtime_epoch_id
final_recovery_generation
completed_at
reason
~~~

On next boot, mismatch/absence triggers unclean recovery path.

---

## 26. RECOVERY_BLOCKED

When automatic reconciliation cannot prove safety:

- set Run state RECOVERY_BLOCKED;
- release expensive compute unless explicitly needed for investigation;
- persist RecoveryIssue Artifact/record.

UI must show:

- last valid checkpoint;
- ambiguous Action;
- known evidence;
- reason automation stopped;
- allowed human choices.

Possible choices:

~~~text
mark externally completed
retry
abort action and replan
cancel Run
~~~

Each human choice is itself audited/authorized.

---

## 27. Cancellation

Cancellation is not process kill.

Normal cancellation:

1. mark cancel requested;
2. stop new action admission;
3. settle current non-interruptible action;
4. journal/observe result;
5. release leases;
6. persist final checkpoint where useful;
7. transition cancelled.

Emergency stop may interrupt interruptible work immediately.

---

## 28. Recovery and Budgets

Recovery work may incur compute.

Rules:

- deterministic DB/journal reconciliation on persistent host is shared overhead;
- Run-specific replacement GPU/CPU recovery work is attributable to Run owner;
- hard budget may block expensive recovery, yielding RECOVERY_BLOCKED with explicit reason;
- unsafe action reconciliation is never skipped merely to save cost.

---

## 29. Retention

Suggested v1:

- keep all complete checkpoints for active Runs;
- after terminal Run, keep latest + Task-boundary checkpoints and journal required for audit;
- retain Action Journal according to Project history policy;
- garbage-collect unreferenced BlobStore objects only after mark-and-sweep over authoritative references;
- never delete data needed by active recovery generation.

Exact retention durations become configuration.

---

## 30. Fault Injection Suite

Required tests include controlled failure:

- after Action STARTED before effect;
- after effect before COMPLETED persistence;
- after COMPLETED before checkpoint;
- during checkpoint blob write;
- during checkpoint DB publish;
- during Git commit/push;
- during approval transition;
- during GPU inference;
- during provider stop;
- during PostgreSQL backup;
- after RecoveryGeneration local completion before remote ACK.

Expected state must be deterministic.

---

## 31. Recovery Objectives

Initial targets:

### Process/worker crash

Lose at most current atomic action; completed durable work remains.

### GPU worker loss

No authoritative state lost; replacement worker resumes from durable inputs.

### Control host loss

Restore to latest complete acknowledged RecoveryGeneration.

These are architectural RPO goals; Development should measure real RTO.

---

## 32. D5 Acceptance Tests

Must prove:

- normal pause releases compute;
- approval wait releases compute;
- approval survives restart without execution;
- inference crash restarts from prior durable state;
- Git push ambiguity reconciles remote first;
- stale lease loses authority;
- incomplete checkpoint never selected;
- corrupt newest checkpoint falls back safely if previous valid exists;
- unreconcilable action becomes RECOVERY_BLOCKED;
- worker filesystem is not sole copy of completed progress;
- fresh host restore succeeds without old GPU state.

---

## 33. Exit Condition

C6 is complete when deliberate process/worker faults cannot silently lose completed work or duplicate privileged side effects, pause/resume works through durable states, and the persistent Control Plane can be restored from a complete RecoveryGeneration.


---

## 34. Recursive Architecture Hardening — Recovery Authenticity and Bootstrap Recovery

The recursive review identified three durability gaps: recovery without a prior checkpoint, recovery-package authenticity, and approval/action atomicity.

### Recovery does not require a pre-existing checkpoint

A checkpoint is a recovery accelerator and consistency anchor, not a second source of truth.

If a non-terminal Run has no complete checkpoint — for example, a crash immediately after Run creation — Recovery Controller reconstructs from:

~~~text
PostgreSQL authoritative Run/Workflow/Task/Job state
+
Action Journal
+
durable Artifact/Blob references
+
Git/workspace state that has already been journaled
~~~

It then writes the first recovery checkpoint before resuming charge-bearing work.

If neither a valid checkpoint nor sufficient canonical durable state exists, the Run enters `RECOVERY_BLOCKED`; it is never guessed forward.

### Approval consumption and Action intent are atomic

For any action that consumes a single-use Approval:

~~~text
lock Approval
→ revalidate fingerprint / owner / identity / policy / expiry
→ create ActionRecord PLANNED
→ bind Approval.used_action_id
→ transition Approval APPROVED → USED
→ commit
→ perform external effect
~~~

The external effect occurs only after this transaction commits.

After a crash:

- `USED + PLANNED/STARTED` is recovered through the ActionRecord;
- a second executor cannot consume the same Approval;
- a changed action requires a new Approval.

### RecoveryGeneration authenticity

A SHA-256 manifest hash detects corruption but does not by itself prove authenticity.

Every complete RecoveryGeneration therefore contains:

~~~text
generation_number
manifest_hash
integrity_key_id
manifest_authenticator
~~~

where `manifest_authenticator` is a MAC/signature produced by dedicated recovery-integrity key material not writable by recovery clients.

Restore procedure must verify:

1. generation completeness;
2. object hashes;
3. manifest authenticator;
4. key identity;
5. generation monotonicity across available replicas.

A client storing an encrypted replica cannot forge an accepted recovery generation.

### Recovery replication freshness

D8 defines the operational replication interval. A recovery health alert fires when no off-host acknowledged generation exists inside the configured recovery-point target. A stale replica is explicitly reported as degraded recovery health rather than treated as current.

### Action idempotency

Where a tool supplies a stable idempotency key, the Action Journal enforces uniqueness in the action scope defined by D1. Retrying a recoverable effect reuses the existing ActionRecord whenever possible instead of creating parallel intents.


---

## 35. Recursive Audit Cycle 2 — Cancellation and Aggregate Waiting Semantics

### Safe cancellation lifecycle

For an active Run:

~~~text
RUNNING / PAUSE_REQUESTED / STARTING
→ CANCEL_REQUESTED
→ stop admitting new work
→ settle or safely interrupt current actions
→ CANCELLING
→ journal/reconcile effects
→ release leases
→ checkpoint/finalize
→ CANCELLED
~~~

The system must not expose `CANCELLED` while a non-interruptible external action or active paid lease still requires settlement.

Queued or already-safe zero-compute Runs may cancel directly after invariant checks.

### Approval and human input are Task-local first

An Approval or ClarificationRequest blocks the affected Task through `task_blockers`.

The entire Run enters:

~~~text
AWAITING_APPROVAL
or
AWAITING_INPUT
~~~

only when no useful independent Task can proceed and no active action remains.

This preserves internal parallelism without holding compute unnecessarily.

### Provider operations are recoverable actions

Action Journal coverage includes not only model-requested tools but also trusted control services that create external effects:

- provider provision/start/stop/terminate;
- billing-affecting external API calls;
- backup uploads;
- deployment mutations.

No subsystem is exempt from write-ahead recovery semantics merely because it is “internal control logic”.

### Recovery of a surviving worker

After Control Plane restart:

- prior-epoch leases remain invalid;
- worker may reconnect using D4 worker identity;
- scheduler may grant a fresh lease after Run/Job recovery;
- old in-flight result can never be retroactively accepted as current success unless explicit reconciliation proves it corresponds to the recovered attempt.
