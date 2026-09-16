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
AWAITING_INPUT
RECOVERING
RECOVERY_BLOCKED
CANCEL_REQUESTED
CANCELLING
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


---

## 36. Recursive Audit Cycle 4 — Recovery Key Hierarchy and Rollback Protection

### Recovery key hierarchy

A recoverable encrypted Secret store requires recoverable key material without placing plaintext master keys in the RecoveryGeneration.

Cloud v1 uses:

~~~text
Secret Data Encryption Key (S-DEK)
  held only by Secret Broker helper

Recovery Integrity signing/MAC key (R-IK)
  held only by recovery/secret privilege boundary

Recovery recipient public keys / operator recovery public key
  used to wrap S-DEK and R-IK recovery material
~~~

RecoveryGeneration contains only:

- encrypted secret rows;
- wrapped key envelopes for authorized recovery recipients;
- integrity public metadata/key IDs;
- authenticated manifest.

It never contains plaintext S-DEK/R-IK.

At least one tested recovery recipient must be able to unwrap the required key material before a RecoveryGeneration is declared disaster-recovery healthy.

### Restore ceremony

Fresh-host restore requires:

1. choose the highest valid acceptable generation from available replicas;
2. verify manifest signature/MAC before trusting object refs;
3. compare generation numbers across available peers to detect stale rollback;
4. unwrap recovery key envelopes using authorized operator/device recovery credential;
5. restore Secret Broker key material directly into its protected OS boundary;
6. restore PostgreSQL/BlobStore;
7. create a new runtime epoch;
8. rotate worker/session credentials as required;
9. perform functional health checks before resuming Runs.

A lower generation is used only when every newer generation is provably corrupt/unavailable, and that rollback is explicitly logged and operator-confirmed.

### Recovery-key test

C6/C9 fault tests include a blank-host restore in which no original host key file exists. A backup is not accepted as complete if it can restore rows/blobs but cannot restore the secrets needed for authorized external actions.


---

## 37. Recursive Audit Cycle 5 — Budget-Independent Safety Cleanup

Hard budget exhaustion stops new productive charge-bearing work, but it cannot prevent mandatory reconciliation required to make the system safe.

Examples:

- determining whether a privileged external Action occurred;
- stopping/terminating an orphan paid provider resource;
- persisting a final checkpoint/journal result;
- restoring integrity after a partial provider lifecycle operation.

A bounded system `safety_recovery_reserve` may therefore be used after user hard-budget exhaustion.

Rules:

- only recovery/cleanup operations classified by trusted code are eligible;
- no model-generated “continue work” request can access the reserve;
- every use emits a SAFETY_RECOVERY_OVERRUN CostEvent/audit Event;
- once safe state is reached, the Run remains budget-blocked until a human increases budget or cancels.

This prevents a budget limit from becoming a resource-leak or duplicate-side-effect vulnerability.


---

## 38. Recursive Audit Cycle 7 — Durable Controls and Post-Restore Security Reset

### Emergency/maintenance state is durable

Recovery restores D1 `execution_controls` before schedulers admit work.

An ACTIVE STOP/MAINTENANCE control remains active after restart; rebooting the backend is never a way to clear an emergency stop.

### Shutdown inhibitors

Graceful host shutdown and worker drain consult D1 `shutdown_inhibitors` plus active leases/Actions.

Recovery clears stale inhibitors only after reconciling their owning Action/Job or expiry policy. It never deletes an inhibitor just because its original process disappeared.

### Human-session reset after disaster restore

A full control-host disaster restore revokes every restored active human AuthSession before the API becomes ready.

Reason:

- the restored database may predate a logout/session revocation;
- accepting restored sessions could resurrect authority that was revoked after the recovery point.

Device registrations may remain, but interactive users must establish fresh sessions.

### External credential revalidation after stale restore

If the recovered generation is older than current external credential state, GitHub/provider integrations may fail closed until credentials are revalidated/rotated.

Reverend never assumes a recovered encrypted token is still externally valid merely because decryption succeeded.


---

## 39. Recursive Audit Cycle 8 — Checkpoint Journal-Watermark Correctness

`journal_high_watermark` is a per-Run commit-safe cursor from D1, not the maximum value observed from a PostgreSQL identity sequence.

Checkpoint publication must not claim watermark N while any Action with sequence <= N can still be uncommitted.

Required flow:

~~~text
settle/reconcile required Actions
→ obtain per-Run journal sequence state consistently
→ publish checkpoint watermark
→ recovery later scans committed ActionRecords with sequence > watermark
~~~

Parallel Agent Tasks may create Actions, but ActionRecord sequence assignment is serialized only for the short journal insert transaction.

Fault injection must cover two concurrent Action inserts where the second attempts to commit before the first; checkpoint/recovery must still observe a valid total order.


---

## 40. Recursive Audit Cycle 10 — Run Recovery vs System Recovery

Recovery performs two related but distinct journal passes.

### System journal recovery

Using the RecoveryGeneration `global_action_high_watermark`, reconcile post-generation SYSTEM/PROJECT/RUN ActionRecords such as:

- orphan provider provisioning/stopping;
- backup/replication uploads;
- secret/key rotation;
- infrastructure maintenance;
- external deployment effects.

This occurs before normal scheduler admission when unresolved actions could leak cost or authority.

### Run journal recovery

For each RunCheckpoint, use the Run's `run_sequence` watermark to reconstruct/reconcile Run-local work.

A system Action is never hidden merely because no Run existed to own it.

### Control-host readiness gate

If a SYSTEM-scoped UNKNOWN action can cause unsafe duplicate external effect or ongoing paid resource leakage, Control Plane may serve read/status APIs but productive scheduler readiness remains blocked until the action is reconciled or explicitly moved to an authorized recovery-blocked operator state.


---

## 41. Recursive Audit Cycle 11 — Git TOCTOU Recovery

For a protected Git/GitHub Action, the ActionRecord reconciliation metadata includes:

~~~text
repository identity
source commit
target ref
expected target head
provider request/idempotency correlation where available
observed result commit/ref
~~~

Recovery behavior:

1. query current remote state;
2. if remote equals the recorded successful result, mark COMPLETED;
3. if remote remains at the expected precondition and retry is safe, retry through the same bounded Action intent;
4. if remote moved to an unrelated/new state, do not guess whether a retry is safe;
5. mark conflict/recovery-blocked or replan according to operation semantics.

This prevents crash recovery from overwriting valid work that landed after the original approval.


---

## 42. Recursive Audit Cycle 12 — Catastrophic-Host-Loss External-Effect Barrier

### Why RecoveryGeneration cadence alone is insufficient

Suppose:

~~~text
RecoveryGeneration G acknowledged off-host
↓
local ActionRecord says “push commit X”
↓
GitHub push succeeds
↓
Control Plane host is permanently lost
↓
restore G
~~~

If the Action intent existed only on the lost host, the restored system could believe the push was never attempted and repeat/replan from stale state.

Therefore externally visible, non-trivially-repeatable actions use D1's `OFF_HOST_INTENT_ACK` barrier.

### Execution protocol

~~~text
create PLANNED ActionRecord
→ include complete reconciliation identity
→ authenticate/encrypt compact RecoveryActionIntent
→ replicate to required durable off-host target
→ receive durable ACK
→ mark barrier satisfied
→ perform external effect
→ reconcile/persist COMPLETED/FAILED/UNKNOWN locally
→ later full RecoveryGeneration subsumes the delta
~~~

A full RecoveryGeneration is not required before every Git push.

### Disaster restore protocol

Before normal Run recovery:

1. restore latest valid RecoveryGeneration;
2. enumerate every configured recovery target;
3. authenticate and import valid ActionIntent deltas newer than the generation watermark;
4. deduplicate by Action ID/digest;
5. reject conflicting/tampered envelopes;
6. reconcile each imported external intent against real provider/Git state;
7. only then permit scheduler/productive execution.

If a delta proves an action was intended but external outcome is unknowable, restore enters the appropriate recovery-blocked state instead of replaying blindly.

### Availability behavior

If an action requires OFF_HOST_INTENT_ACK and no target can ACK:

- the action does not execute;
- the affected Task receives a durable recovery-replication blocker;
- unrelated safe work may continue;
- UI/operations expose degraded recovery availability.

Durability policy is fail-closed.

### Provider/control-service actions

The same barrier applies to SYSTEM-scoped provider/deployment side effects when duplicate provisioning or forgotten paid resources could survive host loss.

Provider-side idempotency/tags are additional reconciliation evidence, not a substitute unless the Tool Recovery Registry explicitly proves the restored system can deterministically derive and query the same operation identity.


---

## 2026-09-16 Cloud-Only Recovery and Priority Yield Extension

ADR-001 replaces the Cloud v1 production preference for client-device RecoveryGeneration replicas.

### Off-host recovery target

Cloud v1 requires an authenticated encrypted **cloud/off-host recovery target** behind the recovery/BlobStore abstraction.

Developer laptops are not required recovery peers.

A valid production RecoveryGeneration is healthy only when:

~~~text
local authoritative generation complete
+
encrypted off-host object copy complete
+
manifest/hash verification complete
+
durable recovery-target ACK recorded
~~~

Client availability is irrelevant to this condition.

The system must support authoritative-host restore while every user client is offline.

### Priority yield checkpoint

ADR-002/D15 reuses the existing safe-pre-emption lifecycle.

Before yielding the globally active Run to a higher-priority queued Run:

1. stop admitting new nonessential Jobs for the yielding Run;
2. allow unsafe/non-interruptible ActionRecord operations to settle/reconcile;
3. persist valuable repository/workspace state;
4. publish required Artifacts;
5. create a complete RunCheckpoint;
6. release charge-bearing leases where safe;
7. transition the Run to `RESUME_QUEUED`;
8. allow the selected queued Run to start.

Unvalidated workspace progress may be persisted on a Run-owned worktree/branch or patch Artifact. Priority handoff never requires merging or pushing unverified work to a protected branch.

### Restore semantics

Conversation/Message/BuildSpecification/MediaAsset records are included in normal PostgreSQL/BlobStore recovery according to retention policy.

No recovery procedure may require reconstructing authoritative data from a browser cache.
