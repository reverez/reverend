# A0 — Baseline & Requirements Freeze

> **Programme:** Reverend Cloud Analysis  
> **Milestone:** A0  
> **Status:** ACCEPTED  
> **Owner:** Backend / systems track  
> **Document purpose:** Establish the authoritative starting point for Reverend Cloud, classify the current system, identify migration risks, and freeze architectural invariants that every later milestone must respect.  
> **Important:** This is an analysis-phase report, not the final implementation design. Concrete schemas, module layouts, database choices, APIs, and migration code belong to the Design Phase after A12.

---

## 1. Executive Summary

Reverend Cloud should **evolve the existing Reverend system rather than replace it**.

The current repository already contains several of the correct semantic abstractions for a future distributed autonomous engineering platform:

- explicit `Workflow`, `Task`, `Job`, `Event`, and `Artifact` concepts;
- a versioned specialist system;
- bounded context compilation;
- evidence and provenance handling;
- engineering memory;
- isolated development worktrees;
- deterministic and independent verification;
- resource requests and leases;
- model profiles and local scheduling;
- observability foundations.

The central architectural problem is not lack of structure. It is that these abstractions were originally developed around a **single-user, single-machine, local-inference operating model**.

The accepted migration principle is therefore:

> **Preserve sound semantic contracts. Replace or generalize machine-local implementations only where the cloud architecture requires it.**

The most important A0 finding is that Reverend currently has **overlapping state and orchestration authorities**. The cloud architecture must converge those into one canonical Control Plane before distributed execution is considered trustworthy.

---

## 2. Baseline Being Preserved

At the time this analysis programme began, Reverend was treated as a stable local-first engineering workstation baseline, with the existing project documentation describing the system as Reverend `0.4.0`.

The accepted baseline included:

- local Linux / WSL2 operation;
- Ollama-based local inference;
- executive orchestration;
- specialist contracts;
- autonomous software-development workflows;
- research and evidence collection;
- repository intelligence;
- engineering memory;
- bounded context compilation;
- isolated Git worktrees;
- deterministic verification;
- independent verification;
- resource scheduling;
- model routing;
- Workstation UI/API;
- observability and benchmark scaffolding.

A previously accepted validation baseline recorded:

```text
619 tests passed
```

together with live checks covering:

- general local inference;
- deep reasoning inference;
- strong-code model residency;
- SearXNG research;
- searched-image acquisition;
- sandbox behaviour.

A0 does **not** claim that these exact model choices or local deployment assumptions must survive. It treats them as the regression baseline from which the cloud system evolves.

---

## 3. Repository Areas Relevant to A0

The baseline audit focused on the architectural areas most likely to become cloud authorities:

```text
src/reverend/controlplane/
src/reverend/runtime/
src/reverend/specialists/
src/reverend/development/
src/reverend/intelligence/
src/reverend/research/
src/reverend/workstation/
src/reverend/observability/
deploy/vps/
docs/
tests/
```

Representative implementation seams considered during the analysis included:

```text
controlplane/models.py
controlplane/store.py

runtime/models.py
runtime/providers.py
runtime/resources.py
runtime/scheduler.py
runtime/leased_scheduler.py
runtime/hardware.py
runtime/policy.py

specialists/models.py
specialists/registry.py
specialists/context.py

development/engine.py
development/worktrees.py

autonomy.py

workstation/server.py
workstation/context.py
workstation/store.py
```

The exact repository layout may continue to evolve. The Design Phase should re-audit the live tree before code migration begins.

---

## 4. Current Architectural Strengths

### 4.1 Generic Control Plane

The existing Control Plane already defines explicit workflow entities such as:

```text
Workflow
Task
Job
Event
Artifact
```

with typed lifecycle states, dependency handling, cycle prevention, immutable events, and artifact lineage.

This is the strongest existing candidate for Reverend's future authoritative workflow state.

**A0 classification:** `KEEP + EXTEND`.

---

### 4.2 Versioned Specialist Runtime

The current specialist layer already captures concepts such as:

- specialist identity;
- version;
- methodology binding;
- context policy;
- tool policy;
- required capabilities;
- typed input artifacts;
- typed output artifacts;
- authority profile;
- independent-verifier restrictions.

This is conceptually close to the future Agent architecture defined later in A3.

**A0 classification:** `KEEP + EXTEND HEAVILY`.

---

### 4.3 Resource Request / Lease Semantics

The local resource layer already contains several semantics worth preserving:

- CPU allocation;
- RAM allocation;
- GPU requirement;
- estimated VRAM;
- atomic request admission;
- Job-owned leases;
- priority;
- priority aging;
- heartbeat;
- lease expiry;
- lease revocation;
- idempotent release;
- GPU exclusivity;
- guarded same-model sharing.

These semantics remain useful even after the local machine is replaced by a distributed compute fabric.

**A0 classification:** `KEEP SEMANTICS; GENERALIZE IMPLEMENTATION`.

---

### 4.4 Development Safety Plane

The current development architecture already distinguishes:

```text
model reasoning
```

from:

```text
authoritative repository mutation
```

and provides:

- isolated worktrees;
- pinned base commits;
- guarded mutation;
- deterministic verification;
- independent verification.

This is a major architectural strength.

**A0 classification:** `KEEP`.

---

### 4.5 Evidence, Context, and Memory Foundations

The repository already distinguishes useful information classes rather than treating all data as one blob:

- research evidence;
- provenance;
- engineering memory;
- bounded context;
- artifact validation;
- artifact promotion;
- verification evidence.

A5 later formalizes these distinctions.

**A0 classification:** `KEEP + UNIFY SEMANTICS`.

---

## 5. Major Architectural Debt Discovered

### 5.1 Overlapping State Authorities

The most important A0 finding is that several subsystems currently contain task-, run-, or workflow-like state.

#### Control Plane store

Conceptually owns:

```text
workflows
tasks
jobs
events
artifacts
```

#### Development database

Contains domain records such as:

```text
projects
tasks
task_runs
task_steps
artifacts
verifications
model_runs
decisions
experiments
```

#### Workstation store

Contains:

```text
conversations
messages
jobs
authoritative_tasks
```

The Workstation's `authoritative_tasks` also contains concepts such as:

- objective;
- authoritative specification;
- acceptance criteria;
- decisions;
- completed steps;
- current step;
- remaining steps;
- checkpoint.

On a single machine, these overlaps are manageable because the system can coordinate them tightly. In a distributed system with:

- API processes;
- workers;
- GPU nodes;
- two users;
- pause/resume;
- remote recovery;

the overlaps can create conflicting answers to the question:

> **Which record is actually authoritative?**

### A0 decision

There must be:

> **One canonical workflow/run lifecycle authority.**

The generic Control Plane is the preferred future authority.

Other stores may remain for:

- domain metadata;
- telemetry;
- indexes;
- projections;
- caches;
- history;

but they must not independently govern workflow truth.

---

### 5.2 Overlapping Orchestration Concepts

Current orchestration-like components include:

- generic Control Plane DAG;
- fixed autonomy software workflow;
- worker orchestration;
- development engine;
- Workstation authoritative-task logic.

The cloud migration must not add another competing scheduler on top.

### A0 decision

Future architecture converges toward:

```text
ONE workflow authority
ONE dependency model
MULTIPLE execution strategies
```

not:

```text
control scheduler
agent scheduler
cloud scheduler
RunPod scheduler
development scheduler
```

all independently changing project state.

---

### 5.3 Single-Provider Runtime Coupling

`ModelSpec` already records provider/runtime-related information, but the current execution architecture remains effectively centered around one provider/runtime path.

Future cloud execution requires:

```text
ProviderRegistry
```

or an equivalent abstraction capable of multiple inference backends.

A0 does not define that API. It only freezes the requirement that the current single-provider assumption must not remain architectural truth.

---

### 5.4 Local Security Boundary

The existing Workstation and inference policy are deliberately local-first.

For example, the current system uses loopback-only trust assumptions and local inference restrictions.

Cloud support must not be achieved by simply weakening those checks.

### A0 decision

Remote inference must introduce **new explicit trust classes**, not mutate `LOCAL_ONLY` into a permissive mode.

A8 owns the final trust model.

---

### 5.5 Single-Node Resource Universe

Current hardware discovery naturally assumes:

```text
this machine
```

and often a local GPU device.

The semantic resource model remains useful, but the physical implementation must later support:

```text
ComputeNodeRegistry
```

with authenticated multiple workers.

A6 defines the distributed scheduling semantics.

---

## 6. Canonical Authority Model

A0 freezes the following conceptual architecture:

```text
HUMAN / CLIENT
      │
      ▼
EXPERIENCE PLANE
      │
      ▼
AUTHORITATIVE CONTROL PLANE
Workflow / Task / Job / Artifact
      │
      ▼
COGNITIVE SPECIALIST LAYER
      │
      ▼
EXECUTION / TOOL LAYER
      │
      ▼
MODEL + COMPUTE FABRIC
      │
      ▼
PHYSICAL INFRASTRUCTURE
```

Cross-cutting concerns:

```text
Context / Memory
Evidence / Provenance
Security / Policy
Verification / Assurance
Observability
```

This abstraction hierarchy must survive all later design work.

---

## 7. Current Component Classification

| Current subsystem / concept | A0 direction |
|---|---|
| Executive orchestration concept | KEEP + EXTEND |
| Generic Control Plane | KEEP + EXTEND HEAVILY |
| Workflow / Task / Job DAG | KEEP |
| immutable Event model | KEEP |
| Artifact lineage / provenance | KEEP |
| versioned SpecialistSpec / registry | KEEP + EXTEND HEAVILY |
| context policies | KEEP + EXTEND |
| evidence gating | KEEP |
| Engineering Memory | KEEP + EXTEND |
| repository intelligence | KEEP + EXTEND |
| development safety plane | KEEP |
| Git worktree isolation | KEEP |
| deterministic verification | KEEP |
| independent verifier | KEEP |
| security / integration promotion gates | KEEP |
| ResourceRequest / ResourceLease | KEEP + EXTEND |
| ModelSpec | KEEP + EXTEND |
| current logical model-role concept | KEEP CONCEPTUALLY |
| current fixed role taxonomy | REVISIT IN A9 |
| current model checkpoints | REPLACEABLE |
| single provider registry | GENERALIZE / REPLACE |
| Ollama | KEEP AS ONE RUNTIME |
| local `fcntl` scheduling | LOCAL SAFETY ONLY; NOT DISTRIBUTED AUTHORITY |
| local hardware discovery | GENERALIZE |
| `LOCAL_ONLY` policy | KEEP AS A TRUST MODE |
| remote inference support | NEW |
| loopback Workstation | KEEP FOR LOCAL MODE |
| remote client/server API | NEW VIA A2 |
| overlapping task stores | CONSOLIDATE |
| SQLite | OPEN — topology dependent |
| PostgreSQL | OPEN — topology dependent |
| VPS systemd scaffold | KEEP AS DEPLOYMENT SCAFFOLD |
| cloud GPU provisioning | NEW |
| AgentTeam / swarm runtime | NEW IN A4 |
| per-user accounting | NEW VIA A11 |

---

## 8. Frozen Architectural Invariants

### I-01 — One authoritative workflow state

One canonical source owns:

```text
Workflow
Task
Job
Run lifecycle
```

truth.

---

### I-02 — One authority per concern

Caches, projections, domain stores, and UI stores must not silently become competing authorities.

---

### I-03 — Models are replaceable resources

A Specialist is not equivalent to a particular checkpoint.

---

### I-04 — Compute is replaceable

Loss of any of the following must eventually be recoverable:

```text
GPU
worker
container
model process
compute host
```

---

### I-05 — Durable state outranks runtime memory

Critical progress may not exist only inside:

```text
Python RAM
CUDA state
VRAM
KV cache
shell process state
```

---

### I-06 — Typed communication over free-form swarm chatter

Durable collaboration uses typed artifacts and structured control signals.

---

### I-07 — Bounded autonomy

Every autonomous loop has:

- budget;
- retry limit;
- termination condition;
- authority.

---

### I-08 — Minimum sufficient parallelism

More hardware does not automatically imply more Agents.

---

### I-09 — Deterministic verification outranks model confidence

When a claim can be tested, test it.

---

### I-10 — Implementer and verifier remain logically independent

Final assurance cannot collapse into developer self-approval.

---

### I-11 — Execution authority is mediated

Models propose actions.

Reverend's policy, tool, sandbox, and execution layers perform them.

---

### I-12 — Provenance survives subsystem boundaries

Research, decisions, code, tests, and verification remain traceable.

---

### I-13 — Generated output is not evidence by default

Model synthesis and source evidence remain different epistemic classes.

---

### I-14 — Context is selective and budgeted

Do not solve scaling by putting all repository/history/memory data into every prompt.

---

### I-15 — Remote capability expands trust policy rather than weakening it

Cloud support must preserve local security invariants.

---

### I-16 — Existing abstractions get first right of extension

Before creating a new subsystem, ask whether an existing authoritative subsystem can own the responsibility cleanly.

---

### I-17 — Clients are non-authoritative

The server/control plane owns durable state.

---

### I-18 — Expensive operations are attributable

Resource usage must eventually trace:

```text
User
→ Project
→ Run
→ Team
→ Task
→ Agent
→ Job
→ Resource
```

---

## 9. Explicitly Not Frozen by A0

A0 intentionally does not decide:

- exact Agent types;
- exact AgentSpec schema;
- number of Agents;
- Team/swarm hierarchy;
- context implementation;
- memory database;
- scheduler algorithm;
- database engine;
- Redis;
- vLLM vs SGLang;
- RunPod topology;
- exact GPU;
- exact model fleet;
- exact API;
- exact remote auth method;
- billing formula.

These are downstream decisions.

---

## 10. Migration Risks Carried Forward

| Risk | Why it matters | Downstream milestone |
|---|---|---|
| state fragmentation | multiple stores can disagree after distribution | A2 / A7 / Design |
| orchestration proliferation | duplicated scheduling authority becomes unrecoverable | A3 / A4 / A6 |
| provider/runtime coupling | cloud model routing becomes brittle | A9 / A10 |
| local-only security assumptions | remote inference can accidentally weaken isolation | A8 |
| single-host compute assumptions | local locks/VRAM logic do not scale across workers | A6 / A10 |

---

## 11. Acceptance Criteria

A0 is complete because the architecture can now state:

1. what Reverend is today;
2. which current semantics deserve preservation;
3. which subsystem should become authoritative;
4. which local assumptions must be generalized;
5. what later milestones are allowed to change;
6. what all future architecture must never violate.

---

## 12. Design-Phase Implications

The Design Phase must include a concrete migration plan that:

- converges workflow truth onto one authority;
- preserves compatibility while old stores are retired or converted to projections;
- generalizes resource management behind node/provider interfaces;
- keeps existing regression tests meaningful;
- introduces cloud functionality without weakening local security;
- avoids rewriting stable deterministic components for aesthetic reasons.

---

## 13. A0 Decision Record

```text
MILESTONE:
A0 — Baseline & Requirements Freeze

STATUS:
ACCEPTED

PRIMARY DECISION:
Evolve the existing Reverend architecture rather than replace it.

CANONICAL FUTURE AUTHORITY:
Generic Reverend Control Plane.

MIGRATION STRATEGY:
Preserve sound semantic contracts.
Replace/generalize machine-local implementations only where necessary.

PRIMARY ARCHITECTURAL DEBT:
1. overlapping persistent state authorities
2. overlapping orchestration paths
3. single-provider runtime assumptions
4. local-only trust assumptions
5. single-node compute coordination

PERMANENT PRINCIPLES:
typed state
bounded autonomy
mediated tools
selective context
deterministic verification
independent assurance
durable provenance
replaceable models
replaceable compute
one authority per concern
```
