# D9 — Development Programme, Migration & Acceptance Gates

> **Status:** DESIGN ACCEPTED FOR DEVELOPMENT  
> **Depends on:** A12, D0–D8  
> **Purpose:** Convert the Design specification into an ordered development programme that preserves the Reverend 0.4.0 baseline, prevents parallel teams from inventing incompatible contracts, and defines objective gates for Cloud v1 acceptance.

---

## 1. Development Objective

Development must transform the accepted local Reverend system into the Cloud v1 architecture without losing the reliability properties already validated in 0.4.0.

The implementation strategy is:

> **contract first, authority convergence second, remote execution third, optimization last.**

Do not begin by provisioning GPUs or replacing all existing model code.

The high-risk parts of the architecture are identity, state authority, durability, side-effect recovery, and security. Those contracts must exist before expensive compute is introduced.

---

## 2. Baseline Preservation

The accepted local baseline remains a regression reference:

~~~text
Reverend 0.4.0
local Workstation
local Ollama
isolated worktrees
deterministic verification
independent verification
Engineering Memory
research/evidence
resource scheduling
619-test accepted historical baseline
~~~

Later commits may have changed the exact current test count, so Development must run the live repository suite rather than assert 619 as the current count.

Cloud development must not silently weaken:

- fail-closed sandboxing;
- evidence provenance;
- independent verification;
- isolated repository mutation;
- bounded context;
- secret redaction;
- deterministic acceptance gates.

---

## 3. Branch Discipline

Use one narrow workstream per branch/worktree.

Recommended branch naming:

~~~text
cloud/c0-contracts
cloud/c1-postgres
cloud/c2-api-auth
cloud/c3-run-queue
cloud/c4-agent-context
cloud/c5-security
cloud/c6-recovery
cloud/c7-compute
cloud/c8-economics-ui
cloud/c9-acceptance
~~~

Each branch:

1. starts from current accepted main;
2. changes only its declared scope;
3. includes tests;
4. runs targeted validation;
5. rebases/updates before merge where needed;
6. receives review;
7. merges only after required upstream contracts are on main.

Do not stack long-lived unmerged dependency chains when a smaller integration slice can land first.

---

## 4. Contract-First Rule

Before two developers implement opposite sides of an interface, merge the shared contract first.

Examples:

~~~text
API schemas
worker protocol
Run state machine
Artifact envelope
AgentSpec
ResourceRequest / Lease
Approval
ActionRecord
CostEvent
~~~

This prevents frontend/backend or Control Plane/worker divergence.

---

## 5. C0 — Contract Package & Migration Skeleton

### Goal

Represent all frozen Cloud v1 contracts in executable Python/schema form without changing production behavior.

### Deliverables

- schema/version constants;
- RunStatus;
- queue class;
- Approval state;
- ActionRecord state/resume strategy;
- AgentSpec evolution;
- AgentInstance/AgentTeam contracts;
- ModelRequirement/ModelProfile/DeploymentProfile;
- ComputeNode;
- ResourceRequest/ResourceLease distributed shapes;
- CostEvent/RateSnapshot;
- Event v1 envelope;
- RunCheckpoint/RecoveryGeneration manifest types;
- PostgreSQL migration harness skeleton;
- BlobStore interface;
- contract compatibility tests.

### Existing-code principle

Do not remove current ModelRole, SQLite ControlPlaneStore or local ResourceBroker yet.

Add adapters/deprecation path.

### C0 gate

- current tests pass;
- new contract tests pass;
- object schema versions explicit;
- no network/provider dependency;
- Analysis/Design invariants represented in tests.

---

## 6. C1 — Persistent Control Plane Foundation

### Goal

Make PostgreSQL + BlobStore the Cloud authoritative state while keeping local mode available.

### Deliverables

- psycopg3 persistence layer;
- D1 migrations;
- users/Projects/Runs;
- Workflow/Task/Job PostgreSQL repositories;
- immutable event store;
- Artifact metadata;
- requirements/decisions/memory state;
- FileBlobStore;
- transaction/transition services;
- advisory leader locks;
- backup/restore baseline;
- cloud configuration.

### Migration strategy

Do not delete SQLite stores.

Introduce:

~~~text
local mode → current SQLite adapters
cloud mode → PostgreSQL repositories
~~~

Then progressively redirect cloud services.

### C1 gate

- blank PostgreSQL creates/migrates cleanly;
- one-active-Run DB invariant holds under concurrency test;
- owner immutability test passes;
- event immutability passes;
- backup restores into blank DB;
- current local suite remains green.

---

## 7. C2 — Remote Identity, API & Events

### Goal

Make Reverend remotely usable by two explicit authenticated humans without changing execution semantics yet.

### Deliverables

- FastAPI application;
- user provisioning;
- Argon2id or approved equivalent credential flow;
- server-side sessions;
- browser CSRF;
- CLI bearer sessions;
- Project membership;
- /api/v1 Project/Run/queue read/write contracts;
- idempotency records;
- SSE replay;
- system/status;
- UI/API client adapter layer.

### Compatibility

The current loopback Workstation remains usable.

Cloud UI may initially expose only Run/Project/control-plane features while development execution still uses existing backend adapters.

### C2 gate

- two users cannot impersonate each other;
- membership authorization works;
- duplicate Run POST is idempotent;
- SSE reconnect catches up;
- client disconnect leaves durable server work intact;
- secrets/tokens absent from logs/events.

---

## 8. C3 — Run, Queue & Workflow Convergence

### Goal

Make top-level Run the single cloud scheduling unit and eliminate competing workflow authority.

### Deliverables

- RunService;
- Run lifecycle transition service;
- one-active-Run enforcement;
- ACTIVE / RESUME_NEXT / NORMAL queue;
- Run → Workflow linkage;
- immutable owner;
- pause/resume command plumbing;
- run-now pre-emption request;
- current Workstation/development state mapped into projections/adapters;
- queue/status UI projection.

### State convergence

The cloud path must stop creating independent authoritative Task state inside Workstation.

Existing local stores can remain local-mode history/projections.

### C3 gate

- only one top-level Run active under concurrent submissions;
- viewer cannot alter owner;
- Run status survives process restart;
- Task/Job state derives from canonical Control Plane;
- queue ordering stable under restart;
- pre-emption depth cannot exceed one.

---

## 9. C4 — Agent, Team & Context Runtime

### Goal

Replace fixed-worker assumptions with versioned bounded Agents/Teams while preserving proven specialists.

### Deliverables

- SpecialistSpec vNext fields;
- ModelRequirement;
- AgentInstance;
- AgentTeam/TeamPlan;
- Team Coordinator;
- Context Broker;
- generalized Context Compiler;
- ContextManifest;
- typed Artifact schemas;
- structured control signals;
- MemoryProposal/promotion;
- mutation scopes;
- Integration Task;
- Agent/Team budget delegation.

### Migration

Map existing WorkerRole/model_role into compatibility ModelRequirements.

Reuse current specialist methodologies.

### C4 gate

- simple Task can run one Agent;
- complex plan can form bounded Team;
- Team uses Control Plane Tasks;
- verifier cannot mutate implementation;
- mandatory context cannot be omitted;
- conflicting mutation scopes do not execute concurrently;
- Agent budget stops bounded loop;
- typed Artifact lineage is preserved.

---

## 10. C5 — Security, Git, Secrets & Approvals

### Goal

Make privileged Cloud behavior safe before remote workers exist.

### Deliverables

- extended PermissionEvaluator scopes;
- GitHubIdentity;
- Secret Broker;
- secret encryption/master-key procedure;
- Tool Broker;
- Git/GitHub adapters using Run-owner credential;
- Approval service/fingerprint;
- STOP_RUN / STOP_PROJECT / STOP_GLOBAL;
- worker/service identity primitives;
- audit events;
- expanded redaction;
- sandbox cloud-hardening tests.

### C5 gate

- viewer cannot push using own identity from another owner's Run;
- model cannot access raw credentials;
- Git push uses owner identity;
- Approval binds exact action/identity/target;
- changed action invalidates Approval;
- secret seeded in test never appears in logs/API/SSE;
- global stop blocks new model/tool work;
- sandbox cannot access DB/secret/Docker surfaces.

---

## 11. C6 — Durable Execution & Recovery

### Goal

Make execution independent of process/worker lifetime before paid GPU execution is introduced.

### Deliverables

- RunCheckpoint v1;
- checkpoint publication;
- Action Journal;
- Tool Recovery Registry;
- safe pause;
- AWAITING_APPROVAL / AWAITING_INPUT aggregate zero-compute behavior;
- CANCEL_REQUESTED / CANCELLING safe cancellation;
- RESUME_QUEUED;
- runtime epochs;
- stale lease/session invalidation;
- RECOVERING / RECOVERY_BLOCKED;
- Git workspace recovery;
- RecoveryGeneration;
- client recovery peer protocol;
- clean shutdown marker;
- fault-injection framework.

### C6 gate

Run required fault-injection cases.

Must prove:

- no duplicate Git push after crash;
- inference restart safe;
- incomplete checkpoint ignored;
- paused Run survives restart;
- approval wait survives restart;
- ambiguous action blocks instead of guessing;
- blank replacement host can restore latest complete RecoveryGeneration.

---

## 12. C7 — Compute Fabric, RunPod & vLLM

### Goal

Move model inference off user laptops and make GPU capacity disposable.

### Deliverables

- ComputeNode Registry;
- distributed ResourceRequest/Lease;
- Workflow/Compute Scheduler integration;
- Capacity Controller;
- RunPod adapter;
- bootstrap credential;
- worker session/heartbeat;
- long-poll assignment protocol;
- vLLM worker adapter;
- pinned Qwen3.8-27B/A100 SXM/64K DeploymentProfile;
- provider/model health layers;
- idle drain/scale-to-zero;
- cold-start metrics;
- Model Registry and ReverendBench admission.

### Development order inside C7

~~~text
fake provider + fake worker
↓
local remote-worker protocol
↓
real RunPod lightweight worker
↓
real vLLM container
↓
pinned Qwen profile
↓
one full Job
↓
idle drain
↓
fault/replacement
~~~

Do not debug scheduler, provider, model and recovery simultaneously on the first live attempt.

### C7 gate

- zero-GPU to successful inference end-to-end;
- raw vLLM not public;
- Community worker receives no protected secret;
- trust requirement can reject Community node;
- worker loss recovers;
- stale worker result rejected;
- GPU stops after idle grace;
- persistent API remains ready with zero GPU;
- ReverendBench baseline result captured.

---

## 13. C8 — Economics, Budgets & Operational UX

### Goal

Make Cloud operation understandable and financially bounded.

### Deliverables

- PowerSession;
- ComputeLeaseUsage;
- CostEvent/RateSnapshot service;
- provider billing reconciliation;
- GBP estimates;
- owner attribution;
- shared 50/50 fixed/transient policy;
- user/Run budgets;
- reservation accounting;
- budget warnings/blocking;
- cost API;
- queue/Agent/approval/recovery/cost UI;
- operational dashboards;
- backup timers/runbooks.

### C8 gate

- one Run's variable GPU cost maps to correct owner;
- shared overhead split deterministic;
- pause/approval wait has zero active lease cost;
- hard budget blocks next charge-bearing action;
- provider actual reconciles with estimate;
- UI distinguishes estimate vs actual;
- backup/recovery health visible.

---

## 14. C9 — Full Cloud Acceptance

### Goal

Prove Cloud v1 as one system.

### Required validation layers

- all Python tests;
- PostgreSQL contract/integration tests;
- browser/API tests;
- security/adversarial tests;
- recovery fault injection;
- live RunPod lifecycle;
- live vLLM/Qwen inference;
- ReverendBench;
- cost reconciliation;
- backup/blank-host restore.

Cloud becomes primary only when all mandatory gates pass.

---

## 15. A12 E2E Acceptance Matrix

| A12 scenario | Primary implementation phase |
|---|---|
| E2E-01 two-user identity isolation | C2/C5 |
| E2E-02 Run owner / Git identity | C3/C5 |
| E2E-03 one active top-level Run | C3 |
| E2E-04 safe pre-emption | C3/C6 |
| E2E-05 client disconnect | C2/C3 |
| E2E-06 GPU scales from zero | C7 |
| E2E-07 GPU worker loss | C6/C7 |
| E2E-08 crash during inference | C6/C7 |
| E2E-09 crash during Git push | C5/C6 |
| E2E-10 ambiguous side effect | C6 |
| E2E-11 approval releases compute | C5/C6/C7 |
| E2E-12 secret isolation | C5/C7 |
| E2E-13 cost attribution | C8 |
| E2E-14 budget boundary | C8 |
| E2E-15 verification before integration | C4/C9 |
| E2E-16 Control Plane at zero GPU | C7 |
| E2E-17 Control Plane disaster recovery | C6/C9 |
| E2E-18 context/provenance integrity | C4 |
| E2E-19 bounded Team expansion | C4 |
| E2E-20 cost-down model promotion | C7/C8 |
| E2E-21 Community worker isolation | C5/C7 |
| E2E-22 stronger-trust workload rejection | C5/C7 |

C9 runs all scenarios together.

---

## 16. Parallel Development Opportunities

After shared contracts land, two developers can work in parallel.

Examples:

### After C0

Developer A:

~~~text
PostgreSQL persistence
~~~

Developer B:

~~~text
FastAPI schemas/client API layer
~~~

### After C3

Developer A:

~~~text
Agent/Context runtime
~~~

Developer B:

~~~text
Security/Secret Broker scaffolding
~~~

### After C6

Developer A:

~~~text
RunPod/worker/provider fabric
~~~

Developer B:

~~~text
cost/operational UI
~~~

Parallel work must stay on interface-stable boundaries.

---

## 17. Pull Request Scope

A PR should generally implement one coherent contract slice.

Good:

~~~text
Add Run table and state transition service
Add SSE replay cursor
Add worker bootstrap registration
Add Action Journal for Git operations
~~~

Bad:

~~~text
Implement cloud architecture
~~~

Small PRs make invariant review and rollback possible.

---

## 18. Required PR Evidence

Each PR description should contain:

~~~text
Scope
Design document/section
Architecture invariants touched
Tests added
Commands run
Migration effect
Security effect
Recovery effect
Cost/provider effect if applicable
Known deferred work
~~~

For provider/model behavior, include live evidence only when actually run.

---

## 19. Test Pyramid

### Unit

- validation;
- state transitions;
- capability policy;
- cost math;
- context admission.

### PostgreSQL integration

- transactions;
- concurrent Run admission;
- idempotency;
- event immutability;
- advisory leadership.

### Component

- API auth/SSE;
- Agent runtime;
- worker protocol;
- Secret Broker;
- checkpoint/action recovery.

### Fault injection

- kill process;
- drop worker heartbeat;
- crash around side effects;
- corrupt incomplete checkpoint.

### Live

- RunPod;
- vLLM;
- model;
- billing.

Do not replace deterministic lower-level tests with expensive live E2E only.

---

## 20. Feature Flags

Use explicit configuration/feature gates during migration.

Examples:

~~~text
cloud_api_enabled
postgres_controlplane_enabled
agent_runtime_v1_enabled
remote_gpu_enabled
cost_enforcement_enabled
~~~

Flags are migration tools, not permanent architectural forks.

Once Cloud v1 is accepted, retire obsolete flags deliberately.

---

## 21. Local Compatibility

Until C9:

- local Workstation remains supported;
- Ollama local mode remains supported;
- local SQLite path remains usable;
- existing CLI continues where compatible.

Do not force incomplete cloud dependencies on users who run local 0.4.0 behavior.

After C9, a separate architecture decision can determine the long-term default mode.

---

## 22. Data Migration Strategy

Private two-user deployment allows a conservative migration.

Recommended:

1. create clean Cloud PostgreSQL;
2. seed configured users;
3. register Projects explicitly;
4. import only validated long-lived Project facts/decisions/artifacts where useful;
5. keep old SQLite Workstation/development DBs as read-only archive initially;
6. do not bulk-convert overlapping Task histories into new authority without clear mapping.

Preserving integrity is more important than copying every old row.

---

## 23. Dependency Changes

Add new runtime dependencies only in the phase that uses them.

Expected additions:

~~~text
FastAPI / Pydantic / Uvicorn
psycopg 3
Argon2 implementation
HTTP client for provider/worker APIs
~~~

Pin security-sensitive dependencies appropriately.

Avoid large framework additions unrelated to frozen Design.

---

## 24. Configuration Migration

Extend .env.example only when the corresponding feature lands.

Never commit real provider/GitHub/session keys.

Development must document:

- required settings;
- safe defaults;
- local testing behavior;
- production-only requirements.

---

## 25. Documentation Maintenance

As code lands:

- update relevant Design status only when behavior exists;
- do not rewrite Analysis history;
- add operational runbooks;
- keep README concise;
- link detailed behavior to Documentation/Design;
- document any explicit architecture deviation through decision record.

---

## 26. Security Review Gates

C2:

- authentication/session/CSRF review.

C5:

- policy/secrets/Git/Approval review.

C7:

- worker trust/provider boundary review.

C9:

- end-to-end adversarial review.

No provider credential enters a model/worker by accident during prototyping.

---

## 27. Recovery Review Gates

Any new side-effecting tool added during development must declare:

- side-effect class;
- recovery strategy;
- Action Journal behavior;
- idempotency/reconciler;
- pause semantics.

If those are missing, the tool is not safe for autonomous Cloud execution.

---

## 28. Cost Review Gates

Any new paid provider/service must declare:

- native rate source;
- RateSnapshot integration;
- attribution policy;
- budget admission;
- reconciliation method.

No hidden paid calls outside the cost ledger.

---

## 29. Performance Gate

Do not optimize prematurely.

First prove:

- correctness;
- durability;
- security;
- verification.

Then benchmark:

- API latency;
- scheduling wait;
- cold start;
- model load;
- inference;
- GPU utilization;
- context;
- GBP per verified Task.

Optimization must preserve acceptance quality.

---

## 30. 48 GB Cost-Down Promotion

After A100 baseline works:

1. create 48GB DeploymentProfile;
2. benchmark quantized Qwen/North/Nemotron candidates;
3. run representative B1–B5 subset;
4. compare verification/human intervention;
5. compare provider billed cost;
6. promote only if D7/A11 gate passes.

Do not change baseline solely because hourly price is lower.

---

## 31. Code Review Checklist

Reviewers should ask:

~~~text
Does this create another source of truth?
Can a client/model/worker self-assert authority?
Can this lose state on process/GPU loss?
Can it duplicate an external side effect?
Does it leak a secret?
Does it bypass verification?
Does it silently weaken trust?
Is resource/cost attributable?
Does local compatibility remain intact where required?
Are transitions/events transactional?
~~~

---

## 32. Definition of Done for a Development Slice

A slice is done only when:

- code implemented;
- contract tests added;
- targeted tests pass;
- existing relevant regression tests pass;
- migration docs/config updated;
- security/recovery implications handled;
- observability added;
- no known architecture contradiction;
- PR reviewed/merged.

Provider-dependent slice also requires appropriately scoped live validation.

---

## 33. C9 Cloud Definition of Done

Cloud v1 is accepted when:

- C0–C8 merged;
- full test suite passes;
- all A12 E2E scenarios pass;
- live A100/vLLM/Qwen baseline passes ReverendBench gates;
- zero-GPU Control Plane remains functional;
- blank-host recovery succeeds;
- worker/community trust isolation passes;
- Secret Broker/redaction tests pass;
- Git owner identity passes;
- provider billing reconciles within policy tolerance;
- hard budgets work;
- deterministic verification blocks invalid integration;
- README/status updated to Cloud v1 implemented only after evidence exists.

Until then, README must describe Cloud v1 as Design/Development target, not implemented production behavior.

---

## 34. Immediate Development Kickoff Checklist

Before opening C0 branch:

- [ ] Design docs D0–D9 merged to main.
- [ ] README points to Design index.
- [ ] main is clean/stable.
- [ ] current Python suite run and result recorded.
- [ ] PostgreSQL test strategy agreed.
- [ ] both developers use current main as branch base.
- [ ] no real RunPod/GitHub credentials placed in repo.
- [ ] C0 issue/PR scope contains only contracts/migration skeleton.
- [ ] A12 invariants available to reviewers.
- [ ] live paid-provider work deferred until C7.

---

## 35. Final Development Invariant

> Development succeeds by implementing the accepted contracts in progressively verifiable slices. It must not exchange architectural integrity for speed: one server-side authority, immutable human/Run ownership, bounded cognitive execution, typed provenance, mediated secrets/tools, recoverable side effects, replaceable compute and auditable costs remain true at every intermediate milestone.


---

## 36. Recursive Architecture Hardening — Phase Safety Gates

The recursive review found that the original C0–C9 order was sound but needed stricter negative gates so partially implemented Cloud stages cannot accidentally expose unfinished authority.

### C1 negative gate

PostgreSQL may become the Cloud state backend in C1, but no remote mutation endpoint is considered production-capable until C2 authentication/authorization exists.

### C2 negative gate

C2 remote APIs may create/control Projects and Runs, but Cloud autonomous privileged execution remains disabled.

Specifically, until C5:

- no user-scoped Git credential may be resolved;
- no protected external mutation may execute;
- no Secret Broker plaintext may enter a general application path.

### C4 negative gate

C4 Agent/Team execution may exercise deterministic read-only/sandboxed capabilities needed for tests, but it must not enable unmediated production side effects.

All privileged tool calls must either:

- fail closed; or
- remain behind the existing local accepted enforcement path

until C5 Tool Broker/Secret Broker/Approval enforcement is complete.

### C5/C6 coupling gate

A side-effecting Cloud tool is not enabled merely because C5 authorizes it.

It also requires its D5 Action Journal recovery strategy and reconciler from C6.

Therefore production enablement condition is:

~~~text
authorization implemented
AND
secret boundary implemented
AND
Action Journal semantics implemented
AND
recovery reconciler tested
~~~

### C7 paid-compute gate

No real paid provider provisioning is enabled until:

- C5 worker/provider credential isolation passes;
- C6 stale-epoch and worker-loss recovery passes;
- D8 RateSnapshot + PowerSession + budget reservation minimum path exists.

C8 may complete the full economics UX/reconciliation plane later, but C7 live paid tests require the minimum cost safety path first.

### C9 architecture-audit gate

Before Cloud v1 acceptance, repeat the recursive documentation/implementation audit from:

~~~text
identity
→ Project/Run authority
→ workflow/Agents/context
→ tools/security
→ durability/recovery
→ scheduling/workers/models
→ economics/operations
→ end-to-end acceptance
~~~

The gate passes only when:

- no unresolved architecture contradiction is known;
- all identified flaws have an owner and are either fixed or explicitly deferred outside Cloud v1;
- a fresh audit pass finds no new Cloud-v1-blocking flaw.

This means “zero known blocking flaws”, not a claim that defects are mathematically impossible.


---

## 37. Recursive Audit Cycle 2 — Additional Acceptance Gates

Development must add explicit tests for the Cycle-2 fixes:

### Lifecycle

- active cancellation visibly passes through CANCEL_REQUESTED/CANCELLING;
- no paid lease or non-interruptible Action remains when CANCELLED is committed;
- human clarification uses AWAITING_INPUT rather than Approval;
- one blocked Team member does not suspend unrelated runnable work;
- Run enters aggregate waiting state only when no useful work remains.

### Worker/control restart

- consumed bootstrap does not strand a surviving worker after Control Plane restart;
- worker identity reconnect issues a new epoch session;
- old epoch leases/results remain invalid;
- compromised/revoked worker identity cannot reconnect.

### Provider reconciliation

- crash after provider accepts provisioning but before local completion does not create a duplicate paid worker;
- scale-to-zero verifies provider billing state;
- cost ledger distinguishes provider PowerSession time from Run lease time.

### Security

- malicious URL cannot reach loopback/private/link-local/cloud metadata destinations;
- redirect/DNS rebinding cannot bypass the fetch policy;
- credential-bearing arbitrary Git remote is rejected;
- active HTML/SVG Artifact cannot execute in Reverend application origin.

### Provenance

- ContextManifest Artifact exists for model-backed Jobs;
- model invocation links Task/Agent/Job/deployment/node/context;
- cross-Project Memory is denied even if semantic retrieval ranks it highest.


---

## 38. Recursive Audit Cycle 3 — CPU, Revocation and Repository Tests

Add the following mandatory pre-C9 acceptance coverage:

- Project membership can be revoked without deleting historical Run ownership;
- disabled Run owner causes safe pause and blocks new privileged actions;
- revoked GitHub credential never falls back to another user's identity;
- Project repository change does not retarget an existing Run;
- Run base commit remains pinned through recovery;
- oversized/untrusted CPU Job is not executed inline in the authority process;
- local sandbox resource admission preserves configured Control Plane headroom;
- if no safe CPU executor exists, Job remains queued/blocked explicitly;
- ModelProfile/DeploymentProfile semantic mutation after use is rejected in favor of a new versioned profile;
- RateSnapshot/BenchmarkResultSet history is immutable.


---

## 39. Recursive Audit Cycle 5 — Authority, Queue and Safety Tests

Mandatory tests:

- Project member can read another member's Run but cannot resume/run-now it by default;
- Project owner emergency-stop does not imply authority to resume using another owner's credentials;
- repeated run-now requests cannot starve an existing RESUME_NEXT chain;
- ordinary client cannot choose arbitrary queue priority;
- queued-Run quota prevents unbounded queue flooding;
- production application DB role cannot ALTER/DROP schema or hard-delete immutable history;
- migration role is not used by runtime API/scheduler;
- hard budget stops productive work but still permits narrowly classified safety cleanup;
- STOP_GLOBAL blocks new productive actions while allowing provider termination, lease release and journal reconciliation.


---

## 40. Recursive Audit Cycle 6 — Confidentiality and Leadership Tests

Mandatory coverage:

- scheduler/capacity/recovery advisory lock uses a dedicated connection and controller stops on connection loss;
- failover cannot create duplicate provider action without reconciliation;
- SSE stream closes/filters after user/session/membership revocation;
- Event/SSE schema rejects seeded secret/raw-header/raw-environment fields;
- Artifact sensitivity propagates through summary/derivation;
- mandatory RESTRICTED context is never sent to a Community worker or external API;
- semantic retrieval cannot downgrade sensitivity;
- Git credential is absent from remote URL, argv, logs and committed config;
- production storage/security deployment verifies intended at-rest encryption/firewall/service ownership assumptions.


---

## 41. Recursive Audit Cycle 7 — Policy/Control/Restore Tests

Mandatory tests:

- Project policy update creates a new version and stale Approval fingerprint fails;
- Project owner is not implicitly SYSTEM_ADMIN;
- at least one active SYSTEM_ADMIN lockout invariant is enforced;
- STOP_GLOBAL/MAINTENANCE survives backend restart;
- restarting server cannot clear Run/Project emergency stop;
- stale shutdown inhibitor is reconciled, not blindly cleared;
- migration activates durable maintenance/inhibitor state;
- full disaster restore revokes all restored human sessions before API readiness;
- recovered external credential is revalidated/fails closed if provider rejects it.


---

## 42. Recursive Audit Cycle 8 — Replay-Ordering Tests

Mandatory PostgreSQL concurrency tests:

- Event transaction A obtains the next cursor and pauses before commit;
- Event transaction B cannot publish a higher cursor that becomes replay-visible first;
- rollback of A does not leave an authoritative advanced cursor;
- SSE reconnect after concurrent Event writes returns every authorized Event exactly once or at-least-once according to client application semantics, never silently missing one due to allocation order;
- per-Run Action Journal watermark cannot advance past an uncommitted earlier Action;
- checkpoint recovery scans every committed post-watermark Action.


---

## 43. Recursive Audit Cycle 9 — Idempotency, Lineage and Ledger Tests

Mandatory tests:

- two concurrent Run-create requests with same Idempotency-Key create exactly one Run;
- same key/different body conflicts;
- crashed IN_PROGRESS idempotency record reconciles to existing resource without duplication;
- Artifact parent self/cycle/cross-Project linkage is rejected;
- Approval with mismatched Run/Project or wrong-owner external identity is rejected;
- worker cannot bill another user by forging lineage;
- ComputeLeaseUsage derives immutable Run owner/project;
- shared SOURCE_COST allocated 50/50 sums correctly without double-counting system cost;
- self-hosted model tokens do not create a second payable GPU charge;
- duplicate worker result retry is idempotent; conflicting second result is rejected.
