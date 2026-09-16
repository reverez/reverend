# Reverend Cloud v1 — Design Specification Index

> **Phase:** Design  
> **Status:** READY FOR DEVELOPMENT  
> **Accepted architecture input:** Documentation/Analysis/A12-cloud-architecture-acceptance.md  
> **Repository baseline:** main@cc45be4780374b70d9b09fd041c7217d6b890331  
> **Purpose:** Turn the accepted A0–A12 architecture into concrete implementation contracts without changing the accepted authority, durability, security, scheduling, model, or cost semantics.

---

## 1. Design-Phase Objective

The Analysis phase answered **what Reverend Cloud v1 must be**.

The Design phase answers:

> **Exactly which persisted objects, interfaces, state transitions, services, worker protocols, security boundaries, deployment profiles, migrations, and acceptance tests should development implement?**

This folder is therefore the authoritative pre-development technical plan.

It is intentionally more concrete than Documentation/Analysis while remaining implementation-language compatible with the existing Python codebase.

The implementation team may refine code structure where necessary, but it must not change a frozen A12 invariant without an explicit architecture decision.

---

## 2. Canonical Cloud v1 Target

Reverend Cloud v1 is designed as:

~~~text
Two authenticated developers
        │
        ▼
Thin GUI / CLI / IDE clients
        │
        ▼
Authenticated /api/v1 Control API + SSE
        │
        ▼
Persistent Reverend Control Plane
        │
        ├── PostgreSQL authoritative state
        ├── Project / Run / Workflow / Task / Job
        ├── Agent / Team runtime coordination
        ├── Context / Memory / Artifact fabric
        ├── Policy / Approval / Secret brokers
        ├── Workflow Scheduler
        ├── Compute Scheduler
        ├── Capacity Controller
        ├── Cost ledger / budgets
        └── Observability
        │
        ▼
Authenticated disposable execution fabric
        │
        ├── CPU sandbox workers
        └── RunPod GPU workers
              └── vLLM
                    └── Qwen3.8-27B baseline
~~~

Initial accepted deployment profile:

| Concern | Cloud v1 baseline |
|---|---|
| Control host | Hetzner CX33-class x86 host |
| Control host resources | 4 vCPU / 8 GB RAM / 80 GB NVMe baseline |
| Authoritative DB | PostgreSQL |
| Top-level Run concurrency | 1 |
| GPU provider | RunPod Community Cloud Pods |
| Baseline GPU | A100 SXM 80 GB |
| Inference runtime | vLLM |
| Baseline workhorse | Qwen/Qwen3.8-27B |
| Initial model context | 64K |
| Live client events | SSE |
| Primary API | REST/JSON under /api/v1 |
| GPU idle behavior | drain and scale to zero |
| Redis | not required |
| Kubernetes | not required |

These are deployment defaults, not permanent semantic bindings.

---

## 3. Design Documents

| Document | Scope | Primary development output |
|---|---|---|
| D0 | system boundaries, code/package plan, contract/version policy | repository/module skeleton |
| D1 | authoritative domain model and PostgreSQL schema | migrations + repositories |
| D2 | authentication, REST API, idempotency, SSE and client contract | cloud API server |
| D3 | Agent, Team, context, artifact and memory runtime | cognitive runtime |
| D4 | schedulers, ComputeNode, worker protocol, RunPod and vLLM | compute fabric |
| D5 | Run lifecycle, checkpointing, Action Journal and recovery | durable execution |
| D6 | security, secrets, Git/GitHub, approvals and emergency controls | enforcement plane |
| D7 | model profiles, routing, serving and ReverendBench | model fabric |
| D8 | observability, budgets, billing, operations and deployment | operations plane |
| D9 | migration waves, branch discipline, testing and development gates | implementation programme |

### Architecture diagrams

The visual architecture map is maintained under [`Documentation/Design/Diagrams/`](./Diagrams/README.md).

- `00-system-overview.mmd` provides a compact system map.
- `system-complete-mermaid-diagram.mmd` preserves the complete architecture.
- `Subsystems/` contains one focused Mermaid file per numbered architecture subsystem for practical viewing.

Recommended reading order:

~~~text
D0
 ↓
D1 ── D2
 ↓      ↓
D3 ── D4
 ↓      ↓
D5 ── D6
  \    /
   D7
    ↓
   D8
    ↓
   D9
~~~

---

## 4. Frozen Design Principles

The following are non-negotiable implementation constraints inherited from A12.

### One authority per concern

PostgreSQL-backed Control Plane state is authoritative for Run / Workflow / Task / Job truth.

No client, model, worker, cache, provider, recovery replica, or UI state may become a competing authority.

### Authenticated immutable ownership

Every Run has immutable owner_user_id.

User-scoped Git identity, secrets, approvals, audit attribution, and variable costs derive from that owner where relevant.

### Model output never creates authority

Models may propose actions.

Trusted Reverend enforcement code decides whether the action is allowed, whether approval is required, and which secret/credential is resolved.

### Durable application state, disposable compute

Reverend recovers from persisted application state, not preserved Python memory, process stacks, CUDA state, VRAM, or KV cache.

### Typed collaboration

Durable Agent collaboration occurs through typed artifacts and structured control messages.

### Deterministic verification outranks model confidence

A failing deterministic gate blocks integration even when a model claims success.

### Minimum sufficient parallelism

Cloud capacity is used to accelerate useful independent work, not to maximize Agent count.

### Cost attribution is event-derived

Billing/accounting is derived from immutable resource/provider events and explicit shared-cost policy.

---

## 5. Contract Version Set

Development begins with the following semantic versions:

~~~text
REST API                       v1
SSE Event Envelope             v1
Run Lifecycle                  v1
RunCheckpoint                  v1
ActionRecord / Action Journal  v1
RecoveryGeneration             v1
Approval                       v1
Artifact Envelope              v1
AgentSpec / AgentInstance      v1
ComputeNode                    v1
ResourceRequest / Lease        v1
CostEvent / RateSnapshot       v1
Worker Registration Protocol   v1
~~~

Rules:

1. additive optional fields may stay within v1;
2. changing an existing field's meaning is breaking;
3. persisted records must remain readable;
4. breaking changes require explicit migration/versioning;
5. network clients must reject unsupported major versions cleanly.

---

## 6. Persistence Rule

Authoritative structured state goes to PostgreSQL.

Large immutable payloads use a BlobStore abstraction.

Cloud v1 initial BlobStore may be filesystem-backed on persistent control infrastructure, but every durable blob is content-addressed and included in backup/recovery policy.

Reconstructible state includes:

- embeddings;
- search indexes;
- model weights;
- runtime cache;
- worker caches;
- build output;
- KV cache.

Reconstructible state must not be required to determine project truth.

---

## 7. Runtime Rule

The persistent server may initially run several logical services in one Python deployment for simplicity, but those services must preserve explicit boundaries.

Cloud v1 logical services:

~~~text
API Service
Auth / Identity Service
Control Plane Service
Workflow Scheduler
Agent / Team Runtime
Context / Artifact / Memory Services
Policy / Tool / Secret Brokers
Compute Scheduler
Capacity Controller
Cost Ledger
Recovery Service
~~~

Physical co-location does not erase authority boundaries.

This allows development to begin as a modular monolith while retaining a clean path to process separation later.

---

## 8. Development Compatibility Rule

Existing Reverend 0.4.0 local functionality is a regression baseline.

Local mode remains supported while Cloud v1 is built.

The migration should therefore prefer:

~~~text
new cloud interface
    ↓
adapter over existing semantic contract
    ↓
gradual replacement of local implementation
~~~

rather than deleting working subsystems before equivalent cloud behavior exists.

Examples:

- current ControlPlaneStore semantics migrate to PostgreSQL repositories;
- current SpecialistSpec evolves rather than being discarded;
- current ResourceRequest / ResourceLease semantics generalize;
- Ollama remains a local inference adapter;
- current loopback Workstation remains a compatibility client until /api/v1 is ready.

---

## 9. Source Layout Direction

The Design phase recommends extending the existing repository rather than creating one giant cloud package.

Target module direction:

~~~text
src/reverend/
├── api/                    # new cloud API / SSE surface
├── controlplane/           # canonical workflow authority
├── persistence/            # PostgreSQL + migrations + blob storage
├── specialists/            # AgentSpec / AgentInstance / Team contracts
├── intelligence/           # cognitive runtime / context / model requirements
├── runtime/                # compute nodes, leases, inference/compute adapters
├── policy/                 # authorization and capability policy
├── security/               # identity, sessions, secrets, worker credentials
├── development/            # repo/worktree/coding execution
├── observability/          # events/metrics/tracing/redaction
├── workstation/            # existing local compatibility mode
└── ui/                     # current client assets
~~~

Exact file names are specified by the focused design documents.

---

## 10. Development Entry Gate

Development may begin when:

- all design documents in this folder are present;
- README points to the accepted Analysis and Design specifications;
- no Design document contradicts A12;
- C0 contract work can be implemented without inventing missing authority rules;
- schema/state-machine acceptance tests are specified;
- migration order is explicit.

This document set is intended to satisfy that gate.

---

## 11. Canonical Source Priority

When implementation questions conflict, resolve them in this order:

1. A12 accepted invariants;
2. this Design specification;
3. accepted A0–A11 analysis details;
4. current code semantics where compatible;
5. implementation convenience.

Implementation convenience never overrides a frozen authority/security/durability rule.

---

## 12. Change Control During Development

If development discovers a necessary design correction:

1. record the issue;
2. determine whether it changes an A12 invariant;
3. if not, update the relevant Design document and tests;
4. if yes, create an explicit architecture decision before implementation;
5. never silently encode a contradictory behavior only in code.

---

## 13. Development Exit Definition

The Design phase is successful only if the Development phase can work in narrow branches with concrete contracts and objective acceptance gates.

The final Cloud v1 implementation is not accepted until D9/C9 verifies the full E2E matrix inherited from A12.
