# A7 — Durable Execution, Pause/Resume & Recovery

**Status:** analysis contract  
**Programme:** Reverend Cloud Analysis Phase  
**Baseline:** `main@a2d4194153976b1bc9f21212d72874e0b0e6e757`  
**Depends on:** A2 run identity/queue contract; A6 workflow/compute scheduling contract  
**Scope:** run lifecycle, safe interruption, checkpoints, action journal, pause/resume, crash reconciliation and machine-independent continuation

## Objective

Make long-running Reverend work independent of any one Python process, worker, GPU allocation or VPS lifetime.

The required invariant is:

> **Compute is replaceable. Run state is durable.**

A browser disconnect, worker crash, planned pre-emption, VPS shutdown or replacement machine must not silently discard already completed Reverend work.

## Baseline audit

The current code already contains several useful foundations.

### Durable authoritative task state

`src/reverend/workstation/store.py` persists encrypted:

- conversations;
- messages;
- jobs;
- authoritative tasks.

SQLite runs in WAL mode and durable modes encrypt sensitive text fields.

### Existing task checkpoint

`src/reverend/workstation/task_state.py` already defines a bounded `chat_continuation` checkpoint with:

- reason;
- source job ID;
- logical role;
- output budget;
- continuation count;
- bounded partial response.

The current checkpoint is valuable, but it only reconstructs a bounded chat continuation. It is not sufficient to reconstruct an arbitrary multi-step cloud engineering Run.

### Durable Control Plane

`src/reverend/controlplane/store.py` persists generic Workflow, Task, Job, Event and Artifact state and enforces explicit state transitions. Events are immutable.

Current statuses do not include cloud-level pause/resume/recovery states.

### Resource leases

`src/reverend/runtime/resources.py` already models expiring resource leases with heartbeat, release, expiry and revocation. The current broker is process-local memory, so a process or machine restart loses active lease state. That is acceptable only if cloud recovery treats all pre-crash leases as stale.

### Isolated worktrees

`src/reverend/development/worktrees.py` creates per-task Git worktrees from pinned base commits. This is a strong basis for durable workspace recovery.

The missing layer is a top-level durable Run lifecycle plus application-aware checkpoints and external-side-effect reconciliation.

## Decision summary

A7 freezes the following v1 decisions:

1. pause/resume is implemented at the Reverend workflow level, not by freezing Linux processes or GPU memory;
2. every top-level Run has durable lifecycle state;
3. checkpoints are application state, not VM/process snapshots;
4. safe interruption normally occurs after an observed atomic action;
5. every externally visible side effect uses a write-ahead Action Journal;
6. an interrupted action is reconciled according to typed recovery semantics before retry;
7. paused Runs retain their workspace and release compute;
8. pre-empted Runs enter `RESUME_QUEUED` and normally resume before ordinary queued work;
9. Cloud v1 limits pre-emption depth to one;
10. stale resource leases never survive a machine/process recovery as active authority;
11. recovery may reconstruct a Run on fresh compatible compute;
12. critical recovery generations are replicated off the VPS, initially to authenticated Reverend clients;
13. `AWAITING_APPROVAL` is a durable non-compute state: once the approval request and checkpoint are durable at a safe boundary, the Run releases execution leases;
14. an approval decision never executes the blocked action directly: the Run returns through `RESUME_QUEUED`, reacquires fresh compute and revalidates the approval before continuing.

## Run lifecycle

A2's top-level Run gains the following state machine:

```text
QUEUED
  ↓
STARTING
  ↓
RUNNING
  │
  ├── pause requested
  │       ↓
  │  PAUSE_REQUESTED
  │       ↓
  │    PAUSING
  │       ↓
  │     PAUSED
  │       ↓
  │  RESUME_QUEUED
  │       ↓
  │    RESUMING
  │       └──────────────→ RUNNING
  │
  ├── crash / uncertain restart
  │       ↓
  │   RECOVERING
  │       ├── safe → RESUME_QUEUED
  │       └── ambiguous → RECOVERY_BLOCKED
  │
  ├── approval required
  │       ↓
  │  checkpoint + release leases
  │       ↓
  │  AWAITING_APPROVAL
  │       ├── approved → RESUME_QUEUED → RESUMING → RUNNING
  │       ├── rejected → replan/terminal by workflow policy
  │       └── expired  → new approval required if action remains necessary
  │
  └── terminal
          ├── COMPLETED
          ├── FAILED
          └── CANCELLED
```

Run state is authoritative server state.

A worker's process state is not.

## Safe execution boundary

The target atomic loop is:

```text
prepare action
↓
persist ActionRecord intent
↓
execute action
↓
observe result
↓
persist ActionRecord result
↓
commit authoritative workflow state
↓
write durable checkpoint
↓
safe interruption point
```

A normal pause request waits until the next safe interruption point.

The execution engine may define smaller or larger atomic actions by tool type, but the boundary must be explicit.

## Pause modes

### Normal pause

Default user action:

```text
Pause after current safe action
```

Sequence:

1. transition `RUNNING → PAUSE_REQUESTED`;
2. prevent admission of a new non-required action;
3. allow the current atomic action to settle;
4. persist result/reconciliation state;
5. write checkpoint;
6. verify checkpoint durability;
7. release compute/tool leases;
8. transition to `PAUSED`.

Normal pause must not interrupt a non-interruptible external side effect midway.

### Immediate/emergency interruption

A separate emergency operation may stop interruptible work immediately.

Examples that are normally safe to terminate:

- LLM generation;
- tests;
- builds;
- read-only research fetches.

The current action becomes `INTERRUPTED` or `UNKNOWN` according to whether the system can prove no side effect occurred.

Recovery then follows the tool's resume strategy.

Emergency interruption is not the default pre-emption path.

## Awaiting human approval

`AWAITING_APPROVAL` is a blocked durable Run state, not an active compute state.

A Run enters it only after the current atomic action has settled at a safe boundary. The transition is:

```text
RUNNING
↓
approval required for next bounded action
↓
persist Approval request
↓
write complete Run checkpoint containing approval_ref + workflow cursor
↓
verify durability
↓
release compute/tool execution leases
↓
AWAITING_APPROVAL
```

While a Run is `AWAITING_APPROVAL`:

- it does not hold the exclusive top-level compute lease;
- it does not count as `ACTIVE`, `RESUME_NEXT` or `NORMAL` runnable queue work;
- its workspace, checkpoint, Approval record and other durable state remain retained;
- another Run may acquire the VPS and execute;
- the VPS may enter idle grace and deallocate if no runnable work remains and the normal A7 recovery-replication gates pass.

The approval itself is durable authority, not an execution trigger.

### Approval decision

When an authorized human approves:

1. persist the Approval decision;
2. verify the approval is still unexpired and bound to the same Run, owner/external identity, action fingerprint, target/resource scope and policy;
3. write/advance durable state so the decision survives a crash;
4. transition `AWAITING_APPROVAL → RESUME_QUEUED`;
5. let the scheduler acquire a fresh compute lease;
6. transition through `RESUMING`;
7. immediately revalidate the approval before the side effect executes.

The approval API must not execute the privileged action inline and must not bypass the scheduler.

If the proposed action, target, effective external identity or other security-relevant parameters changed while the Run was waiting, the previous approval is stale and cannot be reused. A new Approval is required.

If an approval is rejected, the rejection is persisted. The workflow may then replan/continue via `RESUME_QUEUED` when useful, or become terminal according to workflow policy.

If an approval expires before use, it grants no authority. If the action is still required, a new Approval must be requested.

### Restart while awaiting approval

A clean or unclean restart must preserve a still-pending approval block.

If the latest valid checkpoint and durable Approval record show:

```text
Run = AWAITING_APPROVAL
Approval = PENDING
```

recovery restores `AWAITING_APPROVAL` without acquiring compute.

If a durable approval/rejection decision exists, recovery processes that decision through the normal queue/state-machine path. It must not execute the action directly during recovery.

## Pre-emption policy

Initial Cloud v1:

```text
MAX_ACTIVE_TOP_LEVEL_RUNS = 1
MAX_PREEMPTION_DEPTH = 1
```

Example:

```text
Run A running
↓
Run B requests "run now"
↓
A pauses at safe point
↓
A = RESUME_QUEUED
B = RUNNING
↓
B completes
↓
A = RESUMING
↓
A = RUNNING
```

If A is already paused by B and Run C is submitted, C enters the normal queue. B is not recursively pre-empted.

This prevents indefinite interruption stacks.

## Checkpoint contract

A cloud checkpoint is an immutable manifest describing one recoverable Run generation.

```text
RunCheckpoint
├── checkpoint_id
├── schema_version
├── run_id
├── project_id
├── owner_user_id
├── sequence
├── created_at
├── run_status_at_checkpoint
├── workflow_refs
├── task_graph_ref
├── completed_task_ids
├── pending_task_ids
├── current_task_id
├── current_job_id
├── agent_state_refs
├── plan_ref
├── context_refs
├── memory_refs
├── workspace_ref
├── repository_state_ref
├── artifact_manifest_ref
├── evidence_refs
├── decision_refs
├── budget_state
├── retry_state
├── approval_refs
├── last_action_id
├── journal_high_watermark
├── object_hashes
└── complete
```

Large content is referenced by immutable IDs/hashes rather than copied into every checkpoint.

### What a checkpoint must not depend on

A valid checkpoint must not require preservation of:

- Python object memory;
- thread stacks;
- process IDs;
- open sockets;
- CUDA state;
- GPU VRAM;
- model KV cache;
- temporary container IDs.

Those are recomputable/transient state.

## Checkpoint creation rules

Create a durable checkpoint:

- after each completed high-level task;
- after important safe action boundaries;
- before planned pause;
- before graceful VPS shutdown;
- before selected risky/irreversible operations;
- after approvals that alter execution authority;
- periodically during long tasks where individual actions are lengthy.

The implementation may coalesce low-value checkpoints, but it must never create an unbounded recovery window.

## Atomic checkpoint commit

Checkpoint publication uses a two-phase application rule:

```text
build checkpoint candidate
↓
write referenced objects
↓
fsync / durable DB commit as applicable
↓
verify hashes
↓
publish checkpoint manifest as complete
```

A checkpoint manifest is not eligible for recovery until `complete=true` is durably committed.

Filesystem-backed objects should use temporary-write + fsync + atomic rename where practical.

Keep multiple generations. Recovery should be able to fall back from checkpoint N to N-1 if validation fails.

## Action Journal

Every side-effecting tool action receives an immutable identity before execution.

```text
ActionRecord
├── action_id
├── run_id
├── job_id
├── actor
├── tool
├── operation
├── arguments_digest
├── idempotency_key
├── state
├── started_at
├── finished_at
├── result_ref
├── resume_strategy
└── reconciliation_metadata
```

States:

```text
PLANNED
STARTED
COMPLETED
FAILED
INTERRUPTED
UNKNOWN
```

Required sequence:

```text
persist PLANNED/STARTED
↓
perform external effect
↓
observe
↓
persist COMPLETED or FAILED
```

If the machine dies after the external effect but before result persistence, the action is recovered as `UNKNOWN`, never assumed failed.

## Tool recovery classes

Each tool operation declares interruption/recovery semantics.

| Operation | Normal pause behaviour | Crash recovery |
| --- | --- | --- |
| LLM inference | interruptible | restart from prior checkpoint |
| embedding/rerank | interruptible | repeat |
| web search/fetch | interruptible | repeat if policy allows |
| tests | interruptible | rerun |
| build/compiler | interruptible | rerun |
| file read | interruptible | reread |
| structured file write | finish atomic write | inspect/hash then reapply if needed |
| package install | defer pause where possible | verify environment, rebuild if uncertain |
| Git commit | defer briefly | inspect HEAD/object |
| Git push | do not interrupt casually | inspect remote before retry |
| PR creation | verify provider result | query remote before retry |
| deployment | policy-specific | verify target state or block |
| DB migration | transactional/non-interruptible | DB-specific recovery |

The contract uses at least:

```text
RESTART
VERIFY_THEN_RETRY
REBUILD
MANUAL_RECOVERY
```

as resume strategies.

## Git workspace recovery

Git should carry code-state durability rather than Reverend inventing another version-control format.

Checkpoint repository state records:

```text
repository identity
worktree identity
branch
base commit
HEAD
index state if relevant
uncommitted diff/object reference
untracked-file manifest/hash
```

Optional internal local refs may represent checkpointed code state:

```text
refs/reverend/checkpoints/<run-id>/<sequence>
```

They are recovery implementation details and do not need to be pushed to GitHub.

Paused worktrees remain present while the local VPS disk remains available.

If the worker process is recreated, a fresh worker attaches to the same verified workspace.

If the VPS is replaced, the workspace is reconstructed from replicated Git/checkpoint data.

## Resource lease recovery

Resource leases are runtime authority, not durable entitlement.

On restart:

1. all leases belonging to the previous runtime epoch are considered stale;
2. the new runtime never trusts an old heartbeat timestamp as permission to use compute;
3. recovering Runs reacquire fresh leases;
4. leaked process-local broker capacity therefore cannot survive reboot.

The durable Run may remember what resources it previously requested, but not claim that the old lease is still active.

## Recovery algorithm

On unclean startup:

```text
start durable stores
↓
detect previous runtime was not cleanly stopped
↓
expire/revoke stale runtime leases
↓
find non-terminal Runs
↓
select newest valid checkpoint + durable Run/Approval state
↓
verify checkpoint/object hashes
↓
verify/reconstruct workspace
↓
inspect Action Journal after checkpoint watermark
↓
reconcile STARTED/UNKNOWN actions
↓
classify durable lifecycle state
├── AWAITING_APPROVAL + pending Approval → restore AWAITING_APPROVAL, no compute lease
├── PAUSED                               → restore PAUSED, no compute lease
├── runnable/interrupted work            → RECOVERING → RESUME_QUEUED
└── ambiguous/unsafe                     → RECOVERY_BLOCKED
↓
rebuild transient model/context state only when the Run becomes runnable
```

A recovered runnable Run normally returns to the queue rather than directly bypassing scheduling. A Run durably blocked on human approval remains blocked and does not acquire compute merely because the server restarted.

## Recovery-blocked contract

When an action outcome cannot be proven safely:

```text
Run.status = RECOVERY_BLOCKED
```

The human-facing recovery record must state:

- last durable checkpoint;
- ambiguous action;
- known evidence;
- why automatic reconciliation failed;
- allowed operator choices.

Possible choices may include:

- mark externally completed;
- retry;
- abort action and replan;
- cancel Run.

The system must not silently guess.

## Planned VPS shutdown

A graceful shutdown is just a controlled recovery boundary.

Before compute deallocation:

1. stop admitting new active work;
2. reach safe boundaries;
3. checkpoint every non-terminal Run;
4. persist queue order;
5. flush action journal/event state;
6. replicate critical recovery state off the VPS;
7. write a clean-shutdown record;
8. only then allow provider deallocation.

A Run in `AWAITING_APPROVAL` does not by itself block graceful deallocation once its Approval record, checkpoint and required recovery generation are durable. Approving while the VPS is off first wakes Reverend; the decision is then persisted and the Run re-enters scheduling.

The exact provider lifecycle implementation belongs to A10/A11, but A7 defines what "safe to power off" means.

## Off-VPS recovery replicas

The initial two-user deployment may use the developers' Reverend clients as recovery peers.

```text
Reverend VPS
   ├── encrypted recovery replica → Developer A client
   └── encrypted recovery replica → Developer B client
```

A recovery peer stores content-addressed encrypted objects and checkpoint manifests.

Critical recovery data includes:

- checkpoint manifests/objects;
- Action Journal generations;
- required Control Plane state backup;
- project/repository recovery objects;
- important artifact manifests;
- encrypted configuration/secret-store backup where A8 permits it.

Rebuildable model weights, dependency caches and temporary build output do not need to be replicated by default.

### Durability levels

```text
LOCAL_ONLY
ONE_CLIENT_REPLICA
TWO_CLIENT_REPLICAS
```

Graceful automatic VPS shutdown requires at minimum:

```text
latest critical recovery generation
= valid locally
+ acknowledged by >= 1 authorised off-VPS recovery peer
```

When both clients are reachable, two replicas are preferred.

A network send is not an acknowledgement. The recovery peer ACKs only after durable local write and hash verification.

A8 owns peer authentication/encryption/key management.

## Recovery generation

A recovery generation is broader than one Run checkpoint.

```text
RecoveryGeneration
├── generation_number
├── created_at
├── control_plane_backup_ref
├── run_checkpoint_refs
├── journal_ref
├── repository_refs
├── artifact_refs
├── secret_backup_ref
├── object_hashes
└── complete
```

Use a monotonic generation number. Do not select recovery truth only by wall-clock time.

If the VPS local disk is stale or lost, query available recovery peers and choose the highest complete valid generation.

## Clean-shutdown record

Persist:

```text
CleanShutdownRecord
├── runtime_epoch
├── final_recovery_generation
├── completed_at
└── reason
```

Absence/mismatch at next boot triggers unclean recovery.

## Recovery objectives

Initial targets:

### Worker/process crash

Lose at most the current atomic action.

### Full VPS loss

Lose at most the interval since the latest acknowledged off-VPS recovery generation.

Where replication is available after every important checkpoint, the two targets converge.

## Migration from current implementation

| Current | Cloud target |
| --- | --- |
| encrypted local task/job rows | durable top-level Run + Control Plane state |
| `chat_continuation` checkpoint | general immutable RunCheckpoint |
| process-local cancellation/checkpoint state | server durable lifecycle |
| process-local ResourceBroker leases | fresh leases per runtime epoch |
| task Git worktree | Run/workflow referenced recoverable workspace |
| no Action Journal | write-ahead side-effect journal |
| restart means local app restart | machine-independent reconstruction |
| local disk only | client-backed off-VPS recovery generations |

The current chat continuation checkpoint should remain as a specialised artifact/state component inside the broader checkpoint model rather than being discarded.

## Non-goals for A7

A7 does not require:

- serialising Python process memory;
- CRIU as a core dependency;
- preserving GPU VRAM;
- preserving model KV cache;
- live-migrating CUDA contexts;
- exactly-once semantics from third-party APIs that do not provide them;
- simultaneous active top-level Runs;
- recursive pre-emption.

## Acceptance gates

A7 analysis is complete when implementation can satisfy all of the following:

1. every non-terminal Run has durable lifecycle state;
2. normal pause waits for a safe boundary;
3. paused Runs release compute;
4. paused workspaces remain recoverable;
5. pre-empted Runs enter `RESUME_QUEUED`;
6. pre-emption depth is bounded to one in v1;
7. checkpoint manifests are immutable/versioned/hash-verified;
8. checkpoints do not depend on live process/GPU state;
9. side-effecting actions are journalled before execution;
10. `UNKNOWN` actions are reconciled before retry;
11. stale leases are invalid after runtime restart;
12. a Run can continue on fresh compatible compute;
13. unclean startup automatically enters recovery;
14. ambiguous recovery fails into `RECOVERY_BLOCKED`;
15. graceful VPS shutdown requires a valid recovery generation;
16. at least one authorised off-VPS replica acknowledges critical state before automatic shutdown;
17. `AWAITING_APPROVAL` releases compute after its Approval request and checkpoint are durable;
18. an approval-blocked Run does not prevent another Run from acquiring the exclusive compute lease;
19. approval decisions resume through `RESUME_QUEUED` and a fresh lease rather than executing inline;
20. restart preserves a pending `AWAITING_APPROVAL` state without spuriously requeueing it;
21. a stale, expired or action-mismatched Approval cannot authorize execution.

## Frozen A7 invariant

> A Reverend Run may stop between safe atomic actions without losing completed work. Recovery reconstructs authoritative application state from durable checkpoints and reconciles uncertain external effects before continuing; it never depends on preserving a particular process, GPU allocation or machine.
