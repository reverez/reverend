# A12 — Cloud Architecture Acceptance

> **Programme:** Reverend Cloud Analysis  
> **Milestone:** A12  
> **Status:** ACCEPTED  
> **Owner:** akurkar07  
> **Acceptance snapshot:** 2026-09-16  
> **Inputs:** A0–A11 accepted analysis artifacts  
> **Document purpose:** Reconcile the complete Cloud Analysis programme, resolve cross-milestone conflicts, freeze the Reverend Cloud v1 architecture and hand implementation a stable programme.

---

## 1. Acceptance Decision

Reverend Cloud v1 is accepted for implementation.

The accepted system is:

> **A persistent, inexpensive, server-authoritative Control Plane serving two authenticated developers, with one active top-level Run, bounded agent/team execution, PostgreSQL-backed durable state, policy-mediated tools/secrets/Git, and authenticated disposable GPU workers provisioned on demand through the Compute Scheduler / Capacity Controller.**

The initial implementation profile is:

    clients:
    thin GUI / CLI / IDE integration

    persistent authority:
    Hetzner Cloud CX33 baseline
    x86
    4 vCPU
    8 GB RAM
    80 GB NVMe
    PostgreSQL

    GPU provider:
    RunPod Community Cloud Pods

    baseline GPU:
    A100 SXM 80 GB

    inference runtime:
    vLLM

    baseline workhorse:
    Qwen/Qwen3.8-27B

    initial serving context:
    64K

    top-level Run concurrency:
    1

    GPU lifecycle:
    provision on demand
    drain / stop after idle grace
    zero-GPU is a normal healthy state

Implementation may replace the provider/GPU/model profile later through the accepted abstractions, but may not redefine identity, authority, durability, lifecycle or accounting semantics without a new architecture decision.

---

## 2. A0–A11 Acceptance Matrix

All Cloud Analysis inputs required by A12 are available and accepted.

| Milestone | Accepted A12 input |
|---|---|
| A0 | baseline, migration direction, one authority per concern, durable-state invariants |
| A1 | Codex-class product definition, measurable autonomous engineering objectives |
| A2 | two-user client/server boundary, Projects, immutable Run ownership, queue/API/SSE |
| A3 | AgentSpec / AgentInstance, bounded model-independent cognitive runtime |
| A4 | AgentTeam, bounded dynamic teams, minimum-sufficient parallelism |
| A5 | authoritative state vs memory/context, typed artifact communication, provenance |
| A6 | Workflow Scheduler vs Compute Scheduler, ComputeNode, ResourceRequest/Lease |
| A7 | Run lifecycle, checkpoints, Action Journal, pause/recovery, approval-wait release |
| A8 | authentication, authorization, Git identity, secrets, workers, Community-worker trust class, approvals, emergency control |
| A9 | capability-based ModelRequirements and current model candidate research |
| A10 | persistent Control Plane + disposable compute, RunPod/vLLM direction, hardware tiers and selected Community A100 SXM note |
| A11 | economics, billing, PostgreSQL decision, exact initial Cloud v1 deployment profile |

No analysis milestone remains a blocker to starting the Design/Implementation programme.

---

## 3. Canonical Authority Hierarchy

A12 freezes the following authority hierarchy:

    authenticated human
          │
          ▼
    Project / Run API
          │
          ▼
    AUTHORITATIVE CONTROL PLANE
          │
          ├── Project
          ├── Run
          ├── Workflow
          ├── Task
          ├── Job
          ├── Event
          ├── Artifact
          ├── Approval
          ├── RunCheckpoint
          ├── ActionRecord
          └── CostEvent
          │
          ▼
    cognitive specialist layer
          │
          ├── AgentSpec
          ├── AgentInstance
          └── AgentTeam
          │
          ▼
    policy-mediated execution
          │
          ├── Model Router
          ├── Tool Broker
          ├── Secret Broker
          ├── Workflow Scheduler
          ├── Compute Scheduler
          └── Capacity Controller
          │
          ▼
    replaceable execution resources
          │
          ├── CPU workers
          ├── GPU workers
          ├── inference runtimes
          └── external services

The Control Plane is authoritative for workflow truth.

Models, clients, workers, caches, model servers and provider state are not.

---

## 4. Canonical Object Graph

### Human / Project layer

    User
    ├── AuthSession / Device
    ├── GitHubIdentity
    └── ProjectMember

    Project
    ├── repository identity
    ├── membership
    ├── project policy
    └── Runs

### Execution layer

    Run
    ├── immutable owner_user_id
    ├── Workflows
    ├── approvals
    ├── checkpoints
    ├── recovery state
    ├── budgets
    ├── cost lineage
    └── project-scoped external authority

    Workflow
    └── Tasks
        └── Jobs

### Cognitive layer

    Task / Job
    ├── Specialist / AgentSpec
    ├── AgentInstance
    ├── AgentTeam where needed
    ├── ContextRequest
    ├── ModelRequirement
    └── typed artifacts / control signals

### Physical execution layer

    Job
    ├── ResourceRequest
    ├── ResourceLease
    ├── ComputeNode
    ├── InferenceRuntime / executor
    └── ActionRecords

### Evidence / history layer

    Artifact
    Evidence
    Decision
    Event
    Memory
    Provenance
    Verification
    CostEvent

These concepts may have different persistence schemas, but they must not duplicate authority.

---

## 5. Identity and Ownership

Cloud v1 has two configured human users.

Every private request has an authenticated principal.

A request body cannot create or change identity.

For every Run:

    owner_user_id

is immutable after creation.

The following derive from Run ownership where applicable:

- Git/GitHub identity;
- user-scoped secrets;
- approval routing;
- audit attribution;
- variable cost attribution.

A viewer is not an owner.

Opening another user's Run never changes its authority.

---

## 6. Client / Server Boundary

Clients contain:

- GUI;
- CLI;
- IDE integration;
- authentication session;
- presentation state/cache;
- approval interaction.

Clients do not own:

- Run state;
- queue order;
- Project authority;
- workflow progress;
- checkpoints;
- billing truth;
- secrets;
- provider credentials.

Closing a client does not cancel an active Run.

The authoritative backend remains available while GPU worker count is zero.

---

## 7. Network/API Boundary

Cloud v1 external API namespace:

    /api/v1/...

Mandatory properties:

- authenticated principal;
- bounded request bodies;
- server-side authorization;
- idempotency keys for retriable mutating commands;
- durable event sequence/cursor;
- presentation-safe event payloads;
- no raw secrets;
- no private chain-of-thought.

Live presentation transport:

> **Server-Sent Events for Cloud v1.**

WebSockets may be introduced later only for a concrete bidirectional-streaming need.

Initial remote access should prefer a private network such as Tailscale plus HTTPS and Reverend authentication.

Private networking is defence in depth, not a replacement for application auth.

SSH remains administrative only.

---

## 8. Frozen Contract Versions

Implementation starts from the following Cloud v1 contract versions.

| Contract | Frozen version |
|---|---|
| REST API | v1 |
| live Event envelope | v1 |
| Run lifecycle schema | v1 |
| RunCheckpoint manifest | v1 |
| ActionRecord / Action Journal | v1 |
| RecoveryGeneration manifest | v1 |
| Approval schema | v1 |
| CostEvent / RateSnapshot | v1 |
| AgentSpec / AgentInstance persisted contract | v1 |
| typed Artifact envelope | v1 |

Rules:

- additive backward-compatible fields may remain within v1;
- changing the meaning of an existing field is a breaking change;
- breaking semantics require an explicit version/migration;
- persisted old objects must remain readable or be migrated deliberately.

C0 must turn these architecture-level version labels into concrete schema definitions and compatibility tests before frontend/backend implementation diverges.

---

## 9. Persistent Control Plane

The Control Plane stays online independently of GPU workers.

Initial A11 baseline:

    Hetzner CX33
    4 vCPU
    8 GB RAM
    80 GB NVMe
    x86
    EU region

Responsibilities:

- authentication/session state;
- Project / Run APIs;
- Control Plane authority;
- Executive Orchestrator;
- Agent / Team runtime coordination;
- Context / Memory coordination;
- Workflow Scheduler;
- Compute Scheduler;
- Capacity Controller;
- Provider Registry;
- Policy / approvals / secret broker;
- events and observability;
- cost ledger;
- durable authoritative metadata.

The Control Plane is not an expensive GPU worker.

---

## 10. Database Decision

A12 resolves the previously open SQLite/PostgreSQL question.

> **Reverend Cloud v1 uses PostgreSQL for authoritative cloud state.**

Rationale:

- independent API/scheduler/worker-facing services;
- transactional Run/queue/approval/checkpoint/action/cost coordination;
- durable idempotency;
- safer multi-process write topology;
- cleaner recovery/backup semantics;
- future distributed growth without redefining authority.

SQLite remains supported for local compatibility/development mode.

Redis is **not required** for Cloud v1.

If introduced later, Redis may accelerate ephemeral coordination/cache/pub-sub, but may not become the sole authority for durable Run state.

---

## 11. Workflow Scheduling vs Compute Scheduling

A6 separation is frozen.

### Workflow Scheduler

Decides:

> what work is logically ready?

Inputs include:

- DAG dependencies;
- policy;
- Project/Run state;
- budgets;
- approvals;
- prior artifacts/results.

### Compute Scheduler

Decides:

> where may an admitted Job execute?

Inputs include:

- ResourceRequest;
- trust;
- ModelRequirement;
- ComputeNode health;
- runtime support;
- VRAM/RAM/CPU capacity;
- residency;
- cost/budget;
- locality.

### Capacity Controller

Decides:

> should infrastructure be started, stopped or replaced?

It alone holds cloud-provider lifecycle authority.

---

## 12. Top-Level Run Policy and Internal Parallelism

Cloud v1 policy:

    MAX_ACTIVE_TOP_LEVEL_RUNS = 1

This means one Run has active top-level scheduling ownership at a time.

It does **not** mean the active Run is single-threaded.

Within that Run, independent work may overlap subject to A6 admission:

- research;
- indexing;
- builds/tests;
- CPU tools;
- inference;
- independent verification.

Physical concurrency remains bounded by available resources and conflict policy.

The resource architecture must not hard-code one-Run forever; the product policy may be changed later without redefining ResourceRequest/Lease semantics.

---

## 13. Agent Runtime

A Specialist is not a model checkpoint.

A3/A4 canonical flow:

    Task
    ↓
    Specialist / AgentSpec
    ↓
    AgentInstance
    ↓
    delegated authority + context + budget
    ↓
    ModelRequirement
    ↓
    Job(s)
    ↓
    typed artifacts / control signal

Agent authority is delegated by Reverend policy.

Model output cannot create authority.

Dynamic Agent/Team creation is bounded by:

- parent budget;
- fan-out limits;
- Task DAG rules;
- authority;
- expected marginal value;
- termination conditions.

Unbounded recursive swarms are rejected.

---

## 14. AgentTeam and Parallelism

AgentTeam is a bounded organisational construct, not a licence to spawn arbitrary work.

Canonical properties:

- objective;
- members;
- Team plan;
- Task dependency graph;
- Team budget;
- termination condition;
- escalation policy.

Minimum-sufficient-Team principle:

> Add cognitive branches only when expected information/engineering value exceeds compute and coordination cost.

Independent assurance may use information isolation where correlated reasoning would undermine verification.

---

## 15. Context, Memory and Communication

A5 distinctions are frozen.

Separate:

    authoritative Project / Run state
    shared typed artifacts
    Project / experience memory
    Agent working context
    interaction history

Agents communicate durable work primarily through typed artifacts and structured control messages.

Canonical Agent-to-Agent path:

    Agent A
    ↓
    Artifact / control signal
    ↓
    Control Plane lineage
    ↓
    Task B
    ↓
    Context Compiler
    ↓
    Agent B

Free-form permanent swarm chat is not canonical.

Summaries are derived/lossy and retain source references.

Unverified model text cannot silently become authoritative Project truth.

---

## 16. Model Architecture

A9 capability-based routing is frozen.

    Specialist / Task
    ↓
    ModelRequirement
    ↓
    eligible ModelProfiles
    ↓
    Model Router
    ↓
    InferenceRuntime
    ↓
    ComputeNode

No permanent architecture rule may say:

    role X = model Y forever

A11's Qwen3.8-27B selection is an initial deployment profile, not a semantic binding.

---

## 17. Initial Model / GPU Profile

Initial production-quality baseline:

    Provider:
    RunPod Community Cloud Pods

    GPU:
    A100 SXM 80 GB

    Runtime:
    vLLM

    Model:
    Qwen/Qwen3.8-27B

    Serving context:
    64K initial

The first cost-down experiment:

    RTX A6000 48 GB
    +
    validated quantised Qwen3.8-27B
    or another A9 workhorse

Premium/headroom profile:

    RTX Pro 6000 96 GB

Frontier-scale models are benchmark/escalation infrastructure, not baseline Cloud v1 capacity.

---

## 18. GPU Worker Lifecycle

Zero GPU workers is a healthy state.

Canonical lifecycle:

    runnable GPU Job
    ↓
    no eligible worker
    ↓
    Capacity Controller
    ↓
    RunPod provider adapter
    ↓
    provision/start Pod
    ↓
    authenticated worker registration
    ↓
    runtime/model health
    ↓
    ResourceLease
    ↓
    Job
    ↓
    release
    ↓
    idle grace
    ↓
    DRAINING
    ↓
    STOP / TERMINATE

Initial idle grace:

    5–10 minutes

as configurable Design policy.

Raw vLLM/SGLang ports are private and never the public Reverend interface.

---

## 19. ComputeNode / ResourceLease

ComputeNode is the physical capacity abstraction.

It records capabilities such as:

- CPU;
- RAM;
- GPU/VRAM;
- runtime support;
- health;
- trust;
- resident models;
- active leases.

ResourceRequest describes required capacity/capability.

ResourceLease is:

- atomic;
- time-bounded;
- Job-owned;
- non-transferable;
- heartbeated;
- revocable;
- idempotently releasable.

A stale lease from a previous runtime epoch never grants new authority after recovery.

---

## 20. CPU Execution

CPU execution is first-class.

Examples:

- Git;
- compilation;
- tests;
- static analysis;
- repository search;
- indexing;
- file processing.

The scheduler must not keep an expensive GPU alive merely because a Run is doing CPU-only work.

Small bounded CPU execution services may initially be co-located on the persistent host only when isolation/resource limits prove they cannot threaten the Control Plane.

Heavy or untrusted workloads should use a separate schedulable CPU worker.

The logical separation is frozen even if initial physical deployment co-locates selected low-risk services.

---

## 21. Security and Trust

A8 is authoritative for Cloud security.

Core invariant:

> **Identity creates authority; model output never does.**

Authentication and authorization are separate.

Authorization remains default-deny.

Relevant scope dimensions include:

- user;
- Project;
- Run;
- repository;
- branch;
- worker;
- secret;
- provider.

Models, workers and clients cannot grant themselves broader authority.

### Community Cloud execution trust

The accepted GPU baseline is RunPod Community Cloud.

A8 classifies this as a lower-infrastructure-assurance worker class than dedicated/single-tenant infrastructure. The Community worker is therefore:

- disposable and non-authoritative;
- limited to task-scoped workspace/context;
- authenticated with short-lived worker authority;
- excluded from GitHub/provider/control-plane/master-key secrets;
- ineligible for Jobs whose `trust_requirement` demands stronger infrastructure.

Reverend accepts the additional shared-host / noisy-neighbour / potential side-channel risk for normal project workloads in exchange for lower cost.

Highly sensitive, regulated or policy-restricted workloads must use a stronger deployment class such as Secure Cloud or another dedicated/single-tenant worker.

---

## 22. Secret Architecture

Secrets are server-side references.

Application state stores references rather than plaintext values.

Privileged flow:

    Agent proposes action
    ↓
    Tool Broker
    ↓
    Policy Engine
    ↓
    approval / scope / Run-owner check
    ↓
    Secret Broker
    ↓
    bounded host action

The model receives the result, not raw credentials.

No raw GitHub/provider/session/private-key material appears in:

- prompts;
- browser state;
- SSE;
- logs;
- ordinary artifacts.

---

## 23. Git / GitHub Identity

Each user has server-side GitHub identity binding(s).

For user-scoped Git operations:

    Run
    ↓
    immutable owner_user_id
    ↓
    configured GitHub identity
    ↓
    Tool Broker
    ↓
    Git/GitHub operation

Viewer identity never changes push identity.

Routine Run-branch actions may be automatic.

Default-branch mutation, PR merge, force-push and other dangerous integration actions follow A8 approval policy.

Repository-native protection remains authoritative where stronger.

---

## 24. Approval Semantics

Approval is durable bounded authority, not inline execution.

When approval is required:

    running action settles at safe boundary
    ↓
    Approval request persisted
    ↓
    RunCheckpoint persisted
    ↓
    compute/tool leases released
    ↓
    AWAITING_APPROVAL

While waiting:

- no exclusive GPU lease;
- another Run may use compute according to queue policy;
- a GPU worker may drain/stop;
- waiting time is £0 active compute.

On approval:

    decision persisted
    ↓
    RESUME_QUEUED
    ↓
    fresh lease
    ↓
    approval fingerprint / identity / scope revalidated
    ↓
    action executes through normal Tool Broker path

Stale, expired or changed approvals cannot authorise a different action.

---

## 25. Durable Execution

A7 canonical safe loop:

    prepare action
    ↓
    persist ActionRecord intent
    ↓
    execute
    ↓
    observe
    ↓
    persist result
    ↓
    commit authoritative workflow state
    ↓
    checkpoint
    ↓
    safe interruption point

Pause/resume is application-level.

Cloud v1 does not depend on preserving:

- Python object memory;
- process stack;
- open socket;
- GPU VRAM;
- CUDA context;
- KV cache.

---

## 26. Action Journal

Every side-effecting operation receives an identity before execution.

States include:

    PLANNED
    STARTED
    COMPLETED
    FAILED
    INTERRUPTED
    UNKNOWN

Crash after an external side effect but before local completion persistence creates UNKNOWN.

Recovery reconciles the external world before retry.

Arbitrary third-party side effects are not assumed exactly-once.

---

## 27. Recovery

On worker loss:

    ComputeNode unhealthy
    ↓
    leases invalidated
    ↓
    affected Job interrupted/recoverable
    ↓
    authoritative Control Plane remains online
    ↓
    checkpoint/journal reconciliation
    ↓
    replacement capacity if needed
    ↓
    fresh lease
    ↓
    resume

Ambiguous unreconcilable state becomes RECOVERY_BLOCKED.

The system does not guess.

---

## 28. Resolution: A7 "VPS Shutdown" vs A10 Disposable Workers

A7 was written while the architecture still considered a single VPS carrying more of the system.

A10 later separated:

    persistent authoritative Control Plane
    from
    disposable GPU workers

A12 resolves the wording as follows.

### Routine GPU-worker scale-to-zero

A GPU worker contains no unique authoritative state.

Before routine drain/termination it must:

- settle/interrupt work safely;
- persist required ActionRecord/result state;
- ensure valuable workspace progress has durable representation;
- release leases.

It does **not** require a complete off-site Control Plane disaster-recovery generation merely to stop an otherwise disposable GPU worker.

### Persistent Control Plane shutdown/replacement

A7's stronger RecoveryGeneration / off-VPS durability rule applies to infrastructure carrying authoritative state.

For planned shutdown/replacement of the persistent authority:

- PostgreSQL/state backup must be consistent;
- checkpoints/journal/artifacts required for recovery must be durable;
- off-host/client recovery requirements must pass.

This interpretation removes the apparent conflict without weakening durability.

---

## 29. Client Recovery Peers

Developer clients may retain authenticated encrypted recovery replicas.

They are:

- disaster-recovery peers;
- backup targets;
- restore sources.

They are **not**:

- authoritative databases;
- schedulers;
- provider lifecycle controllers;
- independent writers of Run truth.

The persistent Control Plane remains authoritative while online.

---

## 30. Storage Authority

Cloud v1 authoritative categories:

- identity / membership;
- Project / Run metadata;
- Workflow / Task / Job;
- immutable events;
- approvals;
- RunCheckpoint manifests;
- Action Journal;
- memory/decision metadata;
- secret metadata/encrypted values;
- cost ledger;
- recovery metadata.

Large files may live in content-addressed/object/filesystem storage.

GPU-local model weights and caches are reconstructible.

Worker-local workspace state must never be the only copy of valuable progress.

---

## 31. Billing and Cost Attribution

A11 objects:

    PowerSession
    ComputeLeaseUsage
    CostEvent
    RateSnapshot

Variable resource use is attributed through durable ownership lineage.

Initial policy:

| Cost | Attribution |
|---|---|
| active Run GPU lease | 100% Run owner |
| Run-specific external paid API | 100% Run owner |
| separately provisioned Run CPU worker | 100% Run owner |
| persistent Control Plane | 50/50 |
| shared backups/storage | 50/50 |
| unattributable boot/warm-up/idle/drain overhead | 50/50 |
| PAUSED / AWAITING_APPROVAL without lease | £0 active compute |

Primary optimisation metric:

> **£ per verified successful engineering task**

Displayed live costs are estimated until provider reconciliation.

---

## 32. Budget Enforcement

Budget hierarchy:

    User
    ↓
    Run
    ↓
    Team
    ↓
    Task
    ↓
    Agent
    ↓
    Job / model / tool

Soft limits warn.

Hard limits block the next charge-bearing action at a safe boundary.

A budget limit does not interrupt an unsafe external side effect halfway through.

---

## 33. Verification and Integration

Deterministic verification outranks model confidence.

Canonical integration flow:

    implementation
    ↓
    deterministic tests/checks
    ↓
    independent verification
    ↓
    policy/security/performance gates as required
    ↓
    integration approval
    ↓
    push / PR / merge

A model cannot self-declare a failed deterministic check acceptable.

Implementer and final verifier remain logically independent.

---

## 34. Observability

Important state transitions and privileged actions are durable/traceable.

At minimum record lineage sufficient to answer:

- which user;
- which Project/Run;
- which Team/Task/Agent/Job;
- which model/runtime/node;
- which tool/action;
- which approval;
- which resource lease;
- which artifact/evidence;
- which cost.

Telemetry should distinguish:

- queue wait;
- provisioning;
- model load;
- inference;
- tool execution;
- GPU lease time;
- provider billed time;
- idle/drain overhead;
- verification result;
- estimated/actual cost.

---

## 35. Cross-Milestone Conflict Resolution

A12 explicitly resolves the material conflicts found during final review.

### Conflict 1 — full-stack GPU VPS vs persistent Control Plane

Earlier A11 framework:
one metered GPU VPS for everything.

Later A10:
persistent CPU Control Plane + disposable compute.

**Resolution:** A10/A11 final topology wins. Persistent Control Plane is accepted.

### Conflict 2 — client wakes provider vs server-held provider authority

Earlier migration discussion allowed clients to wake the VPS directly.

A8/A10:
provider credentials are infrastructure authority.

**Resolution:** clients submit work to persistent Reverend; Capacity Controller owns provider lifecycle credentials.

### Conflict 3 — SQLite vs PostgreSQL

A0/A10:
open.

**Resolution:** PostgreSQL is Cloud v1 authoritative database. SQLite stays local compatibility mode.

### Conflict 4 — one active Run vs parallel agents/jobs

A2:
one active top-level Run.

A4/A6:
bounded logical/physical parallelism.

**Resolution:** one active top-level Run, internal independent Jobs may overlap when scheduler/policy/resources permit.

### Conflict 5 — exact model selection vs model-independent Agents

A3/A9:
Agent identity is model-independent.

A11:
Qwen3.8-27B selected as initial workhorse.

**Resolution:** Qwen is a deployment profile, not Agent semantic identity. Model Router remains capability-based.

### Conflict 6 — A7 full-host recovery condition vs routine GPU shutdown

**Resolution:** strong off-host RecoveryGeneration requirement applies to authoritative Control Plane shutdown/replacement; disposable GPU workers drain after durable execution state is synchronised.

### Conflict 7 — recovery clients vs authoritative server

A7:
clients can hold recovery replicas.

A0/A2/A10:
server/control plane is authoritative.

**Resolution:** recovery peers are backup replicas only, never active authority.

### Conflict 8 — Secure Cloud vs Community Cloud baseline

Earlier A11/A12:
RunPod Secure Cloud + A100 PCIe 80 GB.

Final deployment choice:
RunPod Community Cloud + A100 SXM 80 GB.

**Resolution:** Community Cloud is the accepted normal GPU tier. It is explicitly classified as lower-assurance shared-host infrastructure under A8. Community workers remain disposable, secret-minimised and task-scoped; Jobs requiring stronger trust use a stronger deployment class.

No unresolved conflict remains that blocks Design/Implementation.

---

## 36. Rejected Cloud v1 Architecture Choices

A12 rejects requiring:

- one full-stack expensive GPU VPS as authority;
- client-held provider lifecycle credentials;
- user identity as a cosmetic dropdown;
- client-authoritative Run state;
- model-created permissions;
- model-visible raw secrets;
- Docker socket exposure to untrusted Agents;
- worker-local unique project state;
- process/VRAM/KV snapshots as recovery foundation;
- unrestricted recursive Agent swarms;
- one model per Specialist;
- one GPU per Agent;
- hidden unlimited runtime queues;
- permanent frontier-scale GPU capacity;
- speculative GPU overcommit;
- Redis as mandatory authority;
- Kubernetes as a Cloud v1 dependency;
- automatic integration that bypasses verification/approval;
- billing that cannot reconcile to provider usage.

---

## 37. End-to-End Acceptance Scenarios

Implementation must eventually pass all of the following.

### E2E-01 — Two-user identity isolation

Both developers authenticate separately, can access permitted shared Projects, and cannot impersonate each other by request payload.

### E2E-02 — Run owner / Git identity

User A starts a Run. User B views it. Commits/pushes remain bound to A's configured external identity.

### E2E-03 — One active top-level Run

A is active. B submits another Run. B remains queued until policy permits execution/pre-emption.

### E2E-04 — Safe pre-emption

A reaches a safe checkpoint, releases compute, B runs, then A resumes from RESUME_QUEUED.

### E2E-05 — Client disconnect

A browser/laptop disconnects; active execution continues server-side.

### E2E-06 — GPU scales from zero

A GPU Job becomes READY with zero GPU workers. Capacity Controller provisions an authenticated RunPod worker and the Job acquires a fresh ResourceLease.

### E2E-07 — GPU worker loss

Worker disappears. Lease invalidates. Control Plane stays online. Job recovers on replacement capacity.

### E2E-08 — Crash during inference

Recovery restarts inference from durable prior state; it does not restore CUDA/KV process memory.

### E2E-09 — Crash during Git push

ActionRecord is STARTED, remote accepted the push, local completion was not recorded. Recovery verifies remote state before retry.

### E2E-10 — Ambiguous side effect

Outcome cannot be proven. Run enters RECOVERY_BLOCKED and human receives bounded choices.

### E2E-11 — Approval releases compute

Approval request/checkpoint becomes durable, Run enters AWAITING_APPROVAL, compute releases, GPU may scale to zero, approval later resumes via scheduler/fresh lease.

### E2E-12 — Secret isolation

Policy/Tool/Secret Broker performs a Git/provider action without raw credential appearing in model/browser/logs.

### E2E-13 — Cost attribution

Pre-emption and resume accurately attribute active leases to the corresponding immutable Run owners.

### E2E-14 — Budget boundary

Run reaches hard budget; current safe action completes; next paid action is blocked.

### E2E-15 — Verification before integration

Deterministic failure blocks integration regardless of model confidence.

### E2E-16 — Persistent Control Plane at zero GPU

All GPU workers stop. Login, queue, history, approvals, cost view and worker provisioning remain available.

### E2E-17 — Control Plane disaster recovery

Persistent host is lost; PostgreSQL/checkpoint/artifact/secret recovery material reconstructs the authoritative system without relying on old GPU-worker state.

### E2E-18 — Context/provenance integrity

Agent B consumes a typed artifact/derived context from Agent A with source lineage; unverified free-form conversation is not promoted to Project truth.

### E2E-19 — Agent Team bounded expansion

A Team requests another specialist; orchestrator checks DAG, budget, authority and marginal value before creating work.

### E2E-20 — Cost-down model promotion

48 GB deployment profile is not promoted until ReverendBench and cost metrics satisfy the A11 promotion rule.

### E2E-21 — Community worker trust isolation

A Community A100 SXM worker is provisioned for an ordinary Run. It receives only the bounded workspace/context and short-lived worker authority required for the Job. Attempts to access GitHub credentials, provider lifecycle credentials, Control Plane database credentials, secret-store keys or unrelated Project data fail.

### E2E-22 — Stronger-trust workload rejected from Community placement

A Job declares a trust requirement stronger than `COMMUNITY_CLOUD_WORKER`. The Compute Scheduler refuses the Community node and waits/provisions an eligible stronger deployment class rather than silently weakening policy.

---

## 38. Implementation Programme

A12 replaces the earlier provisional implementation ordering with the reconciled Cloud v1 sequence.

### C0 — Contract package / migration skeleton

Freeze concrete schemas for:

- User / Device / Project / ProjectMember;
- Run / Approval;
- AgentSpec / AgentInstance / AgentTeam;
- ResourceRequest / ResourceLease / ComputeNode;
- RunCheckpoint / ActionRecord;
- Event / Artifact envelope;
- CostEvent / RateSnapshot.

Deliver schema-version constants, migration tests and architectural-invariant tests.

### C1 — Persistent Control Plane foundation

Deliver:

- Hetzner-compatible deployment;
- PostgreSQL;
- canonical Control Plane persistence;
- service health/readiness;
- backup/restore baseline;
- migration from overlapping local stores/projections.

### C2 — Remote identity / API / events

Deliver:

- authenticated users/devices;
- Project membership;
- /api/v1;
- idempotency;
- SSE replay;
- thin-client-compatible endpoints.

### C3 — Run / queue / workflow convergence

Deliver:

- durable top-level Run;
- immutable owner;
- Run → Workflow linkage;
- ACTIVE / RESUME_NEXT / NORMAL policy;
- one-active-Run enforcement;
- convergence on one workflow authority.

### C4 — Agent / Team / Context runtime

Deliver:

- AgentSpec / AgentInstance;
- Specialist Registry evolution;
- AgentTeam bounds;
- typed control messages/artifacts;
- Context Broker/Compiler rules;
- budget delegation.

### C5 — Security / Git / secrets / approvals

Deliver:

- user GitHub identities;
- server-side Secret Broker;
- worker/service identity;
- policy scopes;
- approval records/fingerprints;
- Tool Broker enforcement;
- emergency controls.

### C6 — Durable execution / recovery

Deliver:

- RunCheckpoint v1;
- Action Journal v1;
- pause/resume;
- AWAITING_APPROVAL release;
- stale-lease invalidation;
- reconciliation;
- RECOVERY_BLOCKED;
- Control Plane backup/recovery.

### C7 — Compute fabric / RunPod / vLLM

Deliver:

- ComputeNode Registry;
- ResourceRequest/Lease generalisation;
- Capacity Controller;
- RunPod ComputeProvider;
- authenticated GPU worker;
- vLLM runtime adapter;
- A100 SXM Community/Qwen baseline profile;
- drain/scale-to-zero;
- cold-start telemetry.

### C8 — Economics / budgets / client operational UX

Deliver:

- PowerSession;
- ComputeLeaseUsage;
- CostEvent / RateSnapshot;
- provider reconciliation;
- user/Run budgets;
- queue/agent/approval/cost/recovery UI.

### C9 — Full Cloud acceptance

Run:

- full regression suite;
- security suite;
- fault-injection recovery;
- provider lifecycle tests;
- live model ReverendBench;
- billing reconciliation;
- all E2E scenarios above.

Cloud becomes the primary deployment only after C9.

---

## 39. Implementation Branch Discipline

The existing repository discipline remains:

- current main as branch base;
- one narrow workstream per branch/worktree;
- no direct implementation on main;
- review before merge;
- targeted CI;
- full relevant CI before integration;
- live provider/model validation when behaviour depends on real infrastructure.

Architecture documents are not a substitute for implementation evidence.

---

## 40. Operational Readiness Gates

Before Cloud v1 becomes the primary Reverend environment:

1. both users authenticate independently;
2. Project/Run ownership tests pass;
3. both GitHub identities are tested on isolated branches;
4. PostgreSQL restore is tested from a blank replacement control host;
5. client/off-host recovery material is validated;
6. secret redaction tests pass;
7. RunPod Community A100 SXM provisioning/stop/replacement is verified;
8. zero-GPU Control Plane availability is verified;
9. A100 SXM/Qwen/vLLM deployment passes ReverendBench minimum gates;
10. Community-worker isolation tests prove no GitHub/provider/DB/master-key authority is present;
11. scheduler trust-placement tests reject Community nodes for stronger-trust Jobs;
12. A6000 cost-down profile remains disabled until benchmark admission;
13. Action Journal fault injection passes;
14. approval-wait release/restart passes;
15. provider billing and cost ledger reconcile within defined tolerance;
16. hard budget enforcement passes;
17. deterministic verification blocks unsafe integration.

---

## 41. Deferred Post-v1 Capabilities

The architecture represents but does not require:

- multiple simultaneous top-level Runs;
- several GPU nodes;
- RunPod Serverless;
- SGLang as production primary;
- multi-GPU frontier serving;
- public multi-tenant accounts;
- enterprise SSO;
- Kubernetes;
- multi-region Control Plane;
- external object-store recovery replica;
- advanced fair-share scheduling;
- KV-cache migration;
- automatic large swarm scaling;
- permanently resident frontier models.

These additions must extend canonical identities/contracts rather than create new sources of truth.

---

## 42. Final Frozen Invariants

### A12-I01 — One workflow authority

Run/Workflow/Task/Job truth belongs to the authoritative Control Plane.

### A12-I02 — Authenticated human identity

Clients never self-assert another user's authority.

### A12-I03 — Immutable Run owner

User-scoped Git/secrets/cost authority derives from owner_user_id.

### A12-I04 — Models do not own authority

Models propose; Reverend policy/tool infrastructure executes.

### A12-I05 — Compute is replaceable

No critical Run progress depends on one worker/process/GPU.

### A12-I06 — One active top-level Run in v1

Internal bounded parallel work remains allowed.

### A12-I07 — Durable action semantics

External effects are journalled and uncertain outcomes reconciled.

### A12-I08 — Typed collaboration

Durable Agent collaboration uses artifacts/control signals with provenance.

### A12-I09 — Context is selective

Repository/history/memory are not blindly copied into prompts.

### A12-I10 — Verification outranks confidence

Testable claims are tested; failed deterministic gates block integration.

### A12-I11 — Persistent authority, disposable expensive compute

The Control Plane survives GPU scale-to-zero.

### A12-I12 — PostgreSQL is Cloud v1 authority store

SQLite remains local compatibility, not the Cloud write topology.

### A12-I13 — Secrets stay at enforcement boundaries

Raw secrets do not enter model/client state.

### A12-I14 — Billing is attributable and reconcilable

Costs map to immutable resource/provider events and explicit shared policy.

### A12-I15 — Model identity is deployable configuration

Qwen3.8-27B is the initial workhorse, not a permanent semantic role binding.

### A12-I16 — Recovery replicas do not become authority

Client/off-host replicas restore the Control Plane; they do not compete with it.

### A12-I17 — Community compute is lower-assurance and bounded

Community Cloud workers receive only task-scoped data and short-lived execution authority. They never become a credential, database or workflow authority, and stronger-trust Jobs require a stronger deployment class.

---

## 43. A12 Decision Record

    MILESTONE:
    A12 — Cloud Architecture Acceptance

    STATUS:
    ACCEPTED

    PRODUCT:
    private two-user autonomous engineering system

    CLIENTS:
    thin / non-authoritative

    CONTROL PLANE:
    persistent CPU infrastructure
    Hetzner CX33 baseline

    CLOUD DATABASE:
    PostgreSQL

    TOP-LEVEL RUNS:
    one active in v1

    COGNITIVE RUNTIME:
    bounded AgentSpec / AgentInstance / AgentTeam

    COMMUNICATION:
    typed artifacts + structured control messages

    SCHEDULING:
    Workflow Scheduler
    +
    Compute Scheduler
    +
    Capacity Controller

    GPU PROVIDER:
    RunPod Community Cloud Pods

    BASELINE GPU:
    A100 SXM 80 GB

    INFERENCE:
    vLLM

    BASELINE MODEL:
    Qwen3.8-27B

    CONTEXT:
    64K initial serving profile
    selective A5 context architecture

    DURABILITY:
    PostgreSQL + checkpoints + Action Journal + backups/recovery peers

    SECURITY:
    authenticated humans/workers
    fail-closed policy
    server-side secrets
    Tool Broker enforcement

    GIT:
    immutable Run-owner identity

    BILLING:
    immutable cost ledger
    variable cost → Run owner
    fixed/shared overhead → explicit two-user policy

    GPU IDLE:
    scale to zero

    KUBERNETES:
    not required

    REDIS:
    not required

    IMPLEMENTATION:
    C0 may begin

---

## Final Acceptance Invariant

> Reverend Cloud v1 is accepted only as the architecture defined across A0–A12 after this reconciliation: one durable server-side authority, authenticated immutable human/Run identity, bounded cognitive agents, selective typed context, policy-mediated tools/secrets, recoverable application state, schedulable replaceable compute and auditable economics. No client, model, worker, cache, provider or recovery replica may create a competing source of truth for ownership, workflow state, authority, completed work, external side effects or cost.


---

## Post-Acceptance Refinement — Capability & Ephemeral Worker Freeze

> **Status:** Accepted Design refinement. It preserves A12 authority, security, durability and economics invariants.

A12 now explicitly freezes the default Cloud v1 execution posture:

~~~text
PERSISTENT:
  Control Plane
  PostgreSQL
  Git/recovery refs
  durable BlobStore Artifacts
  Action Journal
  Project intelligence metadata

DISPOSABLE / RECONSTRUCTIBLE:
  model GPU workers
  CPU workers
  browser workers
  model weights
  runtime caches
  repository indexes
  browser caches
  temporary worktrees
~~~

### Default model GPU

~~~text
class:
  EPHEMERAL_GPU_WORKER

provider baseline:
  RunPod Community

GPU baseline:
  A100 SXM 80 GB

runtime baseline:
  vLLM

workhorse baseline:
  Qwen3.8-27B

serving profile:
  64K initial

provider-local persistent state:
  optional cache only
~~~

### New accepted capability fabrics

Cloud v1 Design includes:

~~~text
Research Fabric
Repository Intelligence Service
Context Broker v2
Model Fabric
Worker Capability Fabric
ReverendBench v2
~~~

These are subordinate to the existing Control Plane authority.

### Knowledge acquisition

Reverend does not choose between “local database” and “web scraping”.

It uses an authority-first hierarchy:

~~~text
authoritative Project state
→ explicit Artifacts
→ Repository Intelligence
→ retained Evidence
→ Memory
→ derived lexical/vector retrieval
→ Research Fabric acquisition
~~~

Research Fabric may use structured APIs, search, restricted HTTP and a disposable browser worker.

### Worker taxonomy

Core Design distinguishes:

~~~text
bounded Control-host sandbox
CPU build/test/index worker
Browser research/test worker
Model GPU worker
accelerated scientific GPU profile
media/asset GPU profile
~~~

The last two are extensibility contracts and need not block core C9 unless a selected v1 acceptance workload requires them.

### Final acceptance principle

Cloud v1 is not accepted merely because remote Qwen inference works.

Acceptance must prove the organization can:

- gather/retain evidence;
- understand repositories;
- compile bounded context;
- use isolated browser/CPU/model workers;
- recover from worker/cache loss;
- scale model GPU from zero back to zero;
- verify outputs;
- attribute cost;
- preserve all A12 authority/security invariants.
