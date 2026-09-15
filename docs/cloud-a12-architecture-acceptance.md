# A12 — Reverend Cloud Architecture Acceptance & Implementation Programme

**Status:** acceptance contract complete; final architecture acceptance remains conditional on A0–A11 dependency artifacts  
**Programme:** Reverend Cloud Analysis Phase  
**Baseline:** main@a2d4194153976b1bc9f21212d72874e0b0e6e757  
**Inputs currently available on this branch:** A2, A7, A8, A11  
**Purpose:** cross-system consistency review, architecture freeze criteria and implementation programme

## Objective

A12 is the point where Reverend stops accumulating independent cloud ideas and decides whether the architecture is coherent enough to implement.

The acceptance rule is intentionally strict:

> **Frontend and backend teams must be able to implement independently against stable contracts, and every authority, durability, resource and cost boundary must agree on the same object identities and state transitions.**

A12 does not accept an architecture because a diagram looks plausible.

It accepts only a contract set that can survive implementation without each subsystem inventing incompatible meanings for User, Project, Run, Agent, Job, Lease, Checkpoint, Secret, Artifact or Cost.

## Current acceptance position

The repository already has a validated local-first baseline with:

- durable Control Plane Workflow/Task/Job/Event/Artifact state;
- explicit capability/permission policy;
- ResourceRequest/ResourceLease semantics;
- isolated Git worktrees;
- fail-closed untrusted execution sandboxing;
- encrypted workstation state;
- model routing and measured runtime/resource state;
- deterministic verification and independent verification;
- observability traces.

The Cloud Analysis Phase introduces a new distributed boundary above that baseline.

The current branch freezes four major cloud contracts:

- **A2:** remote two-user client/server and Run ownership;
- **A7:** durable execution, pause/resume, Action Journal and recovery;
- **A8:** authentication, authorization, Git identity and secrets;
- **A11:** billing/accounting and the selected Cloud v1 deployment topology.

These four contracts are internally compatible.

However, A12 must **not** declare final architecture acceptance until the remaining analysis milestones have published their authoritative outputs, especially A3–A6 and A9–A10.

The correct current state is therefore:

~~~text
A12 CONTRACT = COMPLETE
FINAL CLOUD ARCHITECTURE = CONDITIONALLY ACCEPTABLE
FINAL FREEZE = BLOCKED ON REMAINING ANALYSIS INPUTS
~~~

This is deliberate, not a documentation failure.

## Canonical cloud object graph

All analysis milestones must converge on one object hierarchy.

~~~text
User
 ├── Device/AuthSession
 ├── GitHubIdentity
 └── Project membership

Project
 └── Run
      ├── Workflow
      │    └── Task
      │         └── Job
      │              ├── AgentInstance
      │              ├── ResourceRequest
      │              ├── ResourceLease
      │              ├── ActionRecord
      │              └── Artifact
      │
      ├── Checkpoint history
      ├── Approval records
      ├── Cost events
      └── Workspace / Git state

ComputeNode
 ├── runtime/model inventory
 ├── active leases
 └── provider cost profile

Secret
 └── referenced by policy-controlled actions
~~~

No implementation milestone may create a second competing concept for the same authority.

## Canonical identity rules

### Human authority

User.user_id is the stable human identity.

### Project authority

Project.project_id is independent of local filesystem paths.

### Run authority

Run.run_id and Run.owner_user_id define the top-level execution and billing owner.

owner_user_id is immutable.

### Workflow execution

The existing Control Plane hierarchy remains canonical beneath a Run:

~~~text
Workflow → Task → Job
~~~

### Resource authority

A ResourceLease belongs to a schedulable Job/Run context and is valid only for the current runtime epoch.

### External authority

User-scoped credentials are resolved from:

~~~text
Run.owner_user_id
~~~

never the current viewer.

## Stable cross-system invariants

The final Cloud architecture is acceptable only if every milestone preserves the following.

### I1 — Server authority

The client is never authoritative for execution state.

### I2 — Authenticated identity

A client cannot become another user merely by selecting a name or submitting a different user_id.

### I3 — Immutable Run ownership

A Run has exactly one initiating owner.

### I4 — Model-independent authority

Model output cannot create permissions, credentials, approvals or resource authority.

### I5 — One active top-level Run in v1

Cloud v1 schedules one top-level Run at a time and allows that Run to use effectively the full allocatable VPS.

### I6 — Workflow/compute separation

Logical task readiness and physical resource availability are different scheduling decisions.

### I7 — Durable Run state

Run continuation does not depend on a live Python process, GPU allocation, KV cache or VPS.

### I8 — Side-effect reconciliation

An externally visible action with unknown crash outcome is verified before retry.

### I9 — Isolated development

Generated development remains in an isolated Run/task workspace until verification/integration policy allows promotion.

### I10 — Secret non-exposure

Clients, models and untrusted workspaces never receive raw infrastructure/user credentials unless a specifically trusted client-side credential is intentionally required for lifecycle control.

### I11 — Verification before promotion

Deterministic and independent verification remain stronger than model confidence.

### I12 — Cost attribution

Material variable compute cost maps to the Run owner; shared overhead follows explicit policy.

### I13 — Disposable compute

The selected GPU VPS may be stopped/replaced without destroying authoritative Run state.

### I14 — Recoverable shutdown

Automatic shutdown requires a durable recovery generation and at least one acknowledged authorised off-VPS replica.

### I15 — Versioned contracts

Remote API/event/checkpoint formats are versioned and migrations are explicit.

## Cloud v1 deployment accepted direction

Subject to A9/A10 choosing an actual compatible instance, the preferred topology is:

~~~text
                 Developer A Client
                 ├── GUI / CLI
                 ├── auth/device identity
                 ├── lifecycle control
                 └── encrypted recovery peer
                         │
                         │
                 Developer B Client
                 ├── GUI / CLI
                 ├── auth/device identity
                 ├── lifecycle control
                 └── encrypted recovery peer
                         │
              ┌──────────┴──────────┐
              │ provider start/stop │
              │ + Reverend HTTPS    │
              ▼                     │
       ┌───────────────────────────────┐
       │      Metered Reverend VPS     │
       │                               │
       │ network edge / auth           │
       │ Control API + SSE             │
       │ Run Queue                     │
       │ Control Plane                 │
       │ Policy / Approval             │
       │ Context / Memory              │
       │ Agent runtime                 │
       │ Scheduler / Resource Broker   │
       │ Tool Broker / Secrets         │
       │ Checkpoint / Action Journal   │
       │ Workspace / Git               │
       │ Model runtime                 │
       │ Observability / Cost ledger   │
       └───────────────────────────────┘
~~~

No mandatory always-on control server is required for the initial two-user deployment.

A future persistent control-plane + elastic GPU fleet remains an allowed evolution because the object contracts do not assume the Control API and ComputeNode are permanently co-located.

## Network/API acceptance boundary

A2's versioned contract is the minimum external surface:

~~~text
/api/v1/auth/...
/api/v1/me
/api/v1/projects/...
/api/v1/runs/...
/api/v1/queue
/api/v1/approvals/...
/api/v1/events/stream
/api/v1/system/status
~~~

Requirements:

- authenticated principal on every non-bootstrap private API request;
- bounded request bodies;
- idempotency keys on retriable mutating commands;
- durable event sequence/cursor;
- presentation-safe events;
- no chain-of-thought;
- no secret material;
- explicit API schema version.

The current loopback Workstation API is not itself the final cloud API.

## Storage acceptance boundary

The final implementation may initially use SQLite or migrate selected state to PostgreSQL, but the **logical authorities** are fixed.

Authoritative categories:

~~~text
identity/project/run metadata
Control Plane workflow/task/job
immutable events
approvals
checkpoints/manifests
Action Journal
secret metadata
cost events
recovery generations
~~~

Large objects may be external files/content-addressed blobs.

A12 does not require one physical database technology for every category.

It does require transactional/durable semantics appropriate to each authority.

If SQLite remains for Cloud v1, implementation must prove safe single-server access patterns, backup consistency and schema migration behaviour.

If PostgreSQL is introduced, migration must preserve the same logical contracts.

## Agent/runtime acceptance boundary

A3/A4 must fit beneath the existing Run/Workflow/Task hierarchy.

Required compatibility:

~~~text
AgentSpec
→ describes role/capabilities/context/resource needs

AgentInstance
→ belongs to bounded task/job execution

AgentTeam
→ belongs to a Run/Workflow
→ has bounded membership/concurrency/budget
~~~

Agents must not become independent principals with unlimited durable authority.

A team may request work. It does not bypass:

- Policy Engine;
- Resource Broker;
- Tool Broker;
- verification;
- Run budget;
- human approval.

## Context/memory acceptance boundary

A5 must preserve the separation:

~~~text
authoritative project/run state
shared typed artifacts
agent working context
experience memory
~~~

No model invocation should require copying the entire project or every agent conversation.

Checkpoint reconstruction may reference context/memory artifacts, but recovery must not turn unverified model text into authoritative state.

## Scheduling acceptance boundary

A6 must distinguish:

~~~text
Workflow Scheduler
~~~

from:

~~~text
Compute Scheduler
~~~

Cloud v1 policy:

~~~text
one active top-level Run
~~~

does not mean only one logical Task/Agent object may exist.

The active Run may contain logical parallelism, but actual model/compute concurrency is admitted only if the selected A10 hardware/runtime demonstrates it is safe and economically useful.

A11's whole-machine policy takes precedence over speculative multi-user partitioning.

## Model/hardware acceptance boundary

A9/A10 must not hardwire human/agent role identity directly to one model.

Expected contract:

~~~text
Agent/Task
↓
ModelRequirement
↓
Model Router
↓
Runtime/Provider
↓
ComputeNode + ResourceLease
~~~

A12 final freeze requires measured evidence for:

- primary coding capability;
- verifier/critic path;
- context requirement;
- VRAM/RAM fit;
- expected load/residency behaviour;
- throughput;
- task success;
- cost per verified successful task.

No final hardware acceptance may rely only on public leaderboard scores.

## Git/integration acceptance boundary

Development flow:

~~~text
Run owner
↓
isolated branch/worktree
↓
agent edits
↓
tests/verification
↓
candidate artifact
↓
integration approval policy
↓
push/PR/merge using Run-owner GitHub identity
~~~

The current isolated-worktree invariant remains.

Cloud v1 must never use whichever viewer happens to be online as the push identity.

## Recovery acceptance boundary

A7 defines:

~~~text
safe action
↓
durable ActionRecord
↓
checkpoint
↓
optional pause/shutdown
↓
fresh worker/machine
↓
verify/reconcile
↓
resume
~~~

Required recovery scenarios are part of A12 end-to-end acceptance and are listed below.

## Security acceptance boundary

A8 is authoritative for:

- user/device authentication;
- capability authorization;
- GitHub identity;
- server-side secrets;
- worker identity;
- approval enforcement;
- emergency controls;
- recovery-peer authentication.

A system is not accepted if a model or untrusted repository can access provider/GitHub credentials merely because the Run needs them.

## Billing acceptance boundary

A11 defines:

~~~text
PowerSession
ComputeLeaseUsage
CostEvent
RateSnapshot
~~~

The system must separately know:

- how long the provider billed the machine;
- which Run held compute;
- which user owned that Run;
- which cost is shared overhead;
- whether displayed cost is estimated or reconciled actual.

## Final end-to-end acceptance scenarios

The Cloud implementation programme must eventually pass at least the following scenarios.

### E2E-01 — Two-user identity isolation

1. Developer A authenticates.
2. Developer B authenticates separately.
3. both can inspect an authorised shared Project.
4. neither can impersonate the other by editing a request body.
5. audit events identify the correct principal.

### E2E-02 — Run ownership and Git identity

1. A starts Run A.
2. B opens Run A as a viewer.
3. Run A commits/pushes an isolated branch.
4. commit/push authority remains A's configured GitHub identity.
5. B's viewing session never changes ownership.

### E2E-03 — Exclusive Run queue

1. A starts a long Run.
2. B submits another Run.
3. only one top-level Run holds the exclusive compute lease.
4. B's Run remains queued.
5. queue state is visible to both clients.

### E2E-04 — Safe pre-emption

1. A's Run is active.
2. B requests run-now.
3. A reaches a safe checkpoint.
4. A releases compute and becomes RESUME_QUEUED.
5. B runs.
6. when B finishes, A resumes before normal queued work.

### E2E-05 — Client disconnect

1. a Run is active.
2. its owner's browser/client disconnects.
3. execution continues.
4. reconnecting client restores live state from durable API/events.

### E2E-06 — Crash during LLM inference

1. checkpoint N is complete.
2. inference starts.
3. worker/VPS dies.
4. recovery uses checkpoint N.
5. inference is restarted rather than attempting to restore GPU/KV process state.

### E2E-07 — Crash during Git push

1. ActionRecord is STARTED.
2. remote accepts commit.
3. VPS dies before COMPLETED is persisted.
4. recovery queries remote GitHub state.
5. action is marked complete without blind duplicate push.

### E2E-08 — Ambiguous external action

1. side effect starts.
2. system crashes.
3. provider cannot prove outcome.
4. Run becomes RECOVERY_BLOCKED.
5. human receives bounded recovery choices.

### E2E-09 — Automatic idle deallocation

1. all Runs complete.
2. queues are empty.
3. idle grace expires.
4. final recovery generation is produced.
5. at least one client ACKs durable replica.
6. provider deallocates VPS.
7. compute billing stops according to provider state.

### E2E-10 — Wake and resume

1. VPS is off.
2. user resumes a paused Run.
3. client starts provider instance.
4. Reverend reaches /ready.
5. checkpoint is restored.
6. Run reacquires a fresh compute lease and continues.

### E2E-11 — Complete VPS replacement

1. previous VPS/storage is unavailable.
2. a replacement machine is provisioned.
3. authorised client supplies latest complete recovery generation.
4. hashes are verified.
5. state/workspace is reconstructed.
6. non-terminal Run becomes recoverable without relying on old process state.

### E2E-12 — Secret isolation

1. Run needs GitHub credential.
2. model proposes push.
3. Policy/Tool Broker authorizes action.
4. credential is injected at enforcement point.
5. model output, event stream, logs and browser contain no raw token.

### E2E-13 — Cost attribution across pre-emption

1. A runs for interval X.
2. B pre-empts for interval Y.
3. A resumes for interval Z.
4. active compute cost maps to A for X+Z and B for Y.
5. paused time is not charged to A as active compute.

### E2E-14 — Budget boundary

1. Run approaches hard budget.
2. current atomic action completes safely.
3. next paid action is blocked.
4. Run surfaces budget/approval state rather than silently exceeding limit.

### E2E-15 — Verification before integration

1. developer agent produces changes.
2. deterministic checks fail.
3. integration is blocked.
4. model confidence cannot override verification.
5. corrected candidate must pass required gates before merge approval.

## Architecture dependency checklist

Final A12 status may change to ACCEPTED only when each analysis artifact answers the following.

| Milestone | Required A12 input |
| --- | --- |
| A0 | frozen baseline, terminology and migration scope |
| A1 | measurable Codex-class product/quality targets |
| A2 | client/server, users, Run/API/event contracts |
| A3 | AgentSpec/AgentInstance contract |
| A4 | AgentTeam/swarm/concurrency contract |
| A5 | context/memory/artifact communication contract |
| A6 | workflow/compute scheduler and resource hierarchy |
| A7 | checkpoint/action-journal/recovery contract |
| A8 | authentication/policy/secrets/Git authority |
| A9 | measured candidate model requirements/results |
| A10 | hardware/runtime/provider topology evidence |
| A11 | economics, billing and selected v1 topology |

Missing or contradictory input blocks final acceptance.

## Conflict checks before final freeze

A12 must explicitly reject the architecture if any milestone proposes:

- two meanings for Run or Job;
- a second unrelated permission system;
- model-created authority;
- client-authoritative Run state;
- Git identity based on viewer rather than owner;
- checkpoints that require live GPU/process state;
- resource leases surviving runtime epochs without reacquisition;
- cloud secrets entering model prompts;
- unbounded recursive agents;
- automatic merging that bypasses verification/approval policy;
- billing that cannot be reconciled to provider time;
- an always-on expensive GPU requirement without measured justification.

## Versioning policy

Cloud contracts require independent schema versions for:

- REST API;
- event envelope;
- checkpoint manifest;
- Action Journal record;
- recovery generation;
- agent/artifact typed contracts where externally persisted.

Backward-compatible additive fields may remain within a major version.

Breaking semantics require an explicit migration and version increment.

"Same JSON shape but changed meaning" is not an acceptable migration strategy.

## Implementation programme

After A12 final acceptance, implementation should proceed in dependency order rather than attempting the full cloud system at once.

### C0 — Contract package and schema freeze

Deliver:

- shared Python/types or schema package for User/Project/Run/Approval/Checkpoint/ActionRecord/CostEvent;
- API/event schema definitions;
- schema-version constants;
- migration-test harness;
- architectural invariant tests.

No remote UI rewrite should precede this contract package.

### C1 — Remote identity and transport

Deliver:

- HTTPS/private-network server boundary;
- authenticated User/Device sessions;
- /api/v1/me;
- project membership;
- REST command/query transport;
- SSE live event stream;
- idempotency keys.

Acceptance focus: E2E-01 and client reconnect.

### C2 — Top-level Run and queue

Deliver:

- durable Run table/model;
- immutable owner;
- Run → Workflow linkage;
- ACTIVE / RESUME_NEXT / NORMAL queue;
- one-active-Run enforcement;
- exclusive top-level compute lease integration.

Acceptance focus: E2E-02/03.

### C3 — Git identity, secrets and approvals

Deliver:

- user GitHub identity registration;
- encrypted secret store;
- Secret Broker;
- policy scopes;
- approval records/UI contract;
- isolated branch push/PR path using Run owner.

Acceptance focus: E2E-02/12/15.

### C4 — Durable execution

Deliver:

- general RunCheckpoint;
- Action Journal;
- tool recovery metadata;
- PAUSE/RESUME states;
- safe-point coordinator;
- recovery manager;
- stale-lease invalidation.

Acceptance focus: E2E-04/06/07/08.

### C5 — Client recovery and VPS lifecycle

Deliver:

- client Recovery Agent;
- device-authenticated encrypted replication;
- recovery generations;
- clean-shutdown marker;
- provider start/stop/status integration;
- idle detector and drain protocol;
- wake/resume UX.

Acceptance focus: E2E-09/10/11.

### C6 — Cloud model/runtime integration

Deliver using A9/A10:

- selected inference runtime;
- selected model fleet;
- ComputeNode profile;
- measured ResourceRequests;
- startup/residency controls;
- health/readiness checks.

Do not implement speculative multi-node scheduling before this single-node path is accepted.

### C7 — Cost ledger and budgets

Deliver:

- PowerSession;
- ComputeLeaseUsage;
- CostEvent;
- rate snapshots;
- per-user dashboard;
- provider reconciliation;
- run/user budgets.

Acceptance focus: E2E-13/14.

### C8 — Thin client migration

Deliver:

- client no longer assumes local filesystem/service authority;
- authenticated project/run UX;
- queue display;
- pause/resume;
- approvals;
- live agents/events;
- recovery/lifecycle status;
- cost views.

The client consumes stable C0/C1 contracts rather than importing backend internals.

### C9 — Full Cloud acceptance

Run:

- full portable test suite;
- security regression suite;
- recovery/fault-injection suite;
- provider lifecycle tests;
- live model engineering benchmarks;
- billing reconciliation test;
- all E2E scenarios above.

Only then may the local-first baseline be considered superseded for the cloud deployment.

## Implementation branch discipline

The repository's existing workflow remains applicable:

- no direct development on main;
- narrow branches/worktrees;
- current main as base;
- review before merge;
- green targeted and full CI;
- real-provider/live-model smoke where behaviour depends on them.

Cloud implementation should avoid multiple branches editing the same central state models before C0 contract freeze.

## Required test classes

The implementation programme should add permanent regression suites for:

~~~text
identity/auth
run ownership
project membership
API idempotency
SSE replay
queue/exclusive Run
pause/resume
checkpoint corruption fallback
Action Journal reconciliation
stale lease recovery
Git identity
secret redaction
worker authority
recovery peer authentication
VPS lifecycle
replacement-machine recovery
cost attribution
budget enforcement
verification/integration policy
~~~

Fault injection is mandatory for A7 implementation quality. Happy-path unit tests alone cannot validate durability claims.

## Operational readiness gates

Before the cloud deployment becomes the primary Reverend environment:

1. backups/recovery are tested from a blank replacement machine;
2. both users can authenticate independently;
3. both GitHub identities are tested on isolated branches;
4. secret redaction tests pass;
5. provider stop/deallocate behaviour is verified against billing state;
6. recovery peers have storage quota/retention configured;
7. one client may be offline without preventing ordinary operation;
8. there is a manual provider/admin recovery procedure if both clients are unavailable;
9. the selected model/runtime passes A9/A10 live workload gates;
10. cost dashboards distinguish estimated from actual charges.

## Deferred post-v1 capabilities

The accepted contracts intentionally leave room for, but do not require:

- always-on cheap control plane;
- multiple concurrent top-level Runs;
- multiple GPU nodes;
- elastic worker fleets;
- multi-region recovery;
- Kubernetes;
- model KV-cache migration;
- advanced fair-share scheduling;
- public multi-tenant accounts;
- enterprise SSO;
- external object-store recovery replica;
- automatic dynamic swarm scaling beyond A4 bounds.

These features must extend the canonical identities rather than replace them.

## Final acceptance procedure

When A0–A11 are all available:

1. attach/reference every milestone artifact;
2. resolve terminology conflicts against the canonical object graph;
3. run the conflict checklist;
4. fill A11's numeric provider/model selection table from A9/A10 evidence;
5. freeze the selected model/runtime/hardware combination;
6. freeze API/event/checkpoint schema versions for implementation v1;
7. confirm all E2E scenarios are implementable without undefined authority;
8. change this document's status from conditional to ACCEPTED;
9. start C0.

Until those steps occur, implementation may prototype isolated mechanisms but must not treat the overall Cloud architecture as final production truth.

## A12 conclusion

The A2/A7/A8/A11 contracts form a coherent backbone:

~~~text
authenticated user
↓
immutable Run owner
↓
durable server queue/control plane
↓
bounded agent/workflow execution
↓
exclusive metered compute
↓
policy-controlled tools/secrets/Git
↓
checkpoint + Action Journal
↓
verification
↓
cost attribution
↓
idle deallocation + recoverable restart
~~~

No contradiction was found among these four assigned analysis areas.

The remaining risk is not within those contracts; it is integration with the still-required agent/team/context/scheduler/model/hardware analyses.

## Frozen A12 acceptance invariant

> Reverend Cloud is ready for implementation only when every subsystem agrees on the same durable identities, authority flow, lifecycle and resource semantics. No client, model, worker, provider or recovery mechanism may create a second source of truth for Run ownership, permissions, completed work, external side effects or cost.
