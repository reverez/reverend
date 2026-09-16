# D17 — Pre-Development Architecture Closure

> **Status:** PRE-DEVELOPMENT GATE PASSED AT DESIGN LEVEL  
> **Date:** 2026-09-16  
> **Depends on:** A12, D0–D16  
> **Purpose:** Reconcile the recursive hardening audit, ephemeral-worker refinement and capability modernization into one final pre-development gate.

---

## 1. Closure Statement

Reverend's pre-development architecture has now undergone three layers:

~~~text
A0–A12
Architecture Analysis

D0–D9
Concrete Cloud Design

recursive hardening + D10–D16
failure/safety/capability modernization
~~~

The implementation target is no longer “the local Reverend running on a bigger computer”.

It is:

> **a persistent autonomous engineering organization with server-authoritative durable state, Project intelligence, bounded dynamic Agent Teams and replaceable capability workers.**

---

## 2. Final Logical Architecture

~~~text
Users
  │
Thin clients
  │
Authenticated API/SSE
  │
Persistent Control Plane
  ├── PostgreSQL authority
  ├── Artifact / Blob / Git durability
  ├── Project / Run / Workflow / Task / Job
  ├── Executive Orchestrator
  ├── Agent / Team runtime
  ├── Context Broker
  ├── Research Fabric
  ├── Repository Intelligence
  ├── Memory / Evidence
  ├── Tool / Policy / Secret Brokers
  ├── Workflow Scheduler
  ├── Compute Scheduler
  ├── Capacity Controller
  ├── Model Registry / Router
  ├── Cost / Observability
  └── Recovery
       │
       ▼
Replaceable Capability Workers
  ├── CPU build/test/index
  ├── Browser research/test
  ├── Model GPU
  ├── accelerated scientific compute
  └── media/asset GPU
~~~

---

## 3. Persistent Authority vs Derived Capability

### Persistent authority

~~~text
PostgreSQL
Git authoritative/recovery refs
durable BlobStore Artifacts
Action Journal
RunCheckpoints / RecoveryGeneration
Requirements / Decisions / Memory
Evidence snapshots referenced by retained Evidence
cost/audit state
~~~

### Replaceable / derived

~~~text
Agent process state
models
workers
browser profiles
Qdrant indexes
Tree-sitter indexes
LSP sessions
model weights
KV/prefix cache
build caches
temporary worktrees
web cache
provider instances
~~~

Deleting all workers/caches must not delete the Project.

---

## 4. Capability Modernization Decisions

### Research

Accepted:

~~~text
SearchProvider
+ structured provider APIs
+ restricted HTTP
+ browser escalation
+ SourceRegistry/SourceSnapshot
+ EvidenceClaim/EvidencePack
~~~

Current SearXNG/Brave/fetch implementation is migrated, not discarded.

### Repository intelligence

Accepted:

~~~text
current Python codeintel
+ versioned RepositorySnapshot
+ Tree-sitter multi-language structural layer
+ LSP/type-service adapters
+ dependency/test/interface graph
+ semantic fallback
~~~

### Model fabric

Accepted:

~~~text
one baseline workhorse first
dynamic ModelRequirement routing
ephemeral on-demand weights
vLLM optimization only after measurement
coding/small/verifier profiles added by benchmark evidence
~~~

### Worker fabric

Accepted mandatory core profiles:

~~~text
bounded control-host sandbox
CPU build/test worker path
Browser Worker
Model GPU worker
~~~

Interfaces reserved for:

~~~text
accelerated scientific compute
media/asset GPU
~~~

### Context

Accepted:

~~~text
authority/exact first
semantic later
web only for missing/stale information
iterative ContextRequest
typed ContextManifest
~~~

### Optimization

Accepted:

~~~text
ReverendBench v2
whole-organization comparisons
GBP / verified successful engineering Task
~~~

---

## 5. Ephemeral GPU Freeze

Default model GPU worker:

~~~text
provider:
  RunPod Community baseline

GPU:
  A100 SXM 80 GB baseline

runtime:
  vLLM

workhorse:
  Qwen3.8-27B baseline

context:
  64K Reverend profile

storage:
  approximately 200 GB temporary container target
  optional approximately 10 GB warm cache target
  no authoritative provider-local state

lifecycle:
  zero → provision → bootstrap → load → READY
  → work → idle grace → drain → durability gate → terminate
~~~

Exact capacities/prices remain deployment configuration.

Correctness must not depend on persistent RunPod storage.

---

## 6. Canonical Knowledge Acquisition

When an Agent needs context:

~~~text
Context Broker
│
├── PostgreSQL authoritative Project state
├── Git / Repository Intelligence
├── retained Artifacts/Evidence
├── Project Memory
├── derived lexical/vector indexes
└── Research Fabric
     ├── search
     ├── structured APIs
     ├── restricted HTTP
     └── browser
~~~

Reverend therefore uses both persistent/local Project intelligence and on-demand external acquisition.

It does not continuously scrape the internet into one giant database.

---

## 7. Revised Development Mapping

The original C0–C9 programme remains the outer sequence.

### C0 — Contracts

Add:

~~~text
CapabilitySpec
WorkerProfile
StorageProfile
BootstrapSpec
ResearchRequest/SourceSnapshot/EvidenceClaim
RepositorySnapshot/RepositoryQuery
ContextNeed
benchmark capability metadata
~~~

### C1 — Persistence

Add source/evidence/repository-index metadata and durable BlobStore retention rules.

### C2 — API

Expose bounded research/repository/capability status only where UI needs it.

### C3 — Run convergence

No material change.

### C4 — Cognitive + Knowledge Runtime

Implement:

~~~text
Agent/Team
Context Broker
Repository Intelligence facade
Research Fabric facade
Memory/Evidence integration
typed ContextRequest
~~~

### C5 — Security

Apply:

~~~text
network/SSRF policy
browser policy
repository index isolation
source prompt-injection boundary
sensitivity-aware placement
~~~

### C6 — Durability

Ensure retained Evidence/workspace/capability outputs survive worker loss.

### C7 — Capability Execution Fabric

Sub-order:

~~~text
C7A fake provider/worker protocol
C7B CPU worker
C7C Browser Worker
C7D RunPod ephemeral Model GPU
C7E vLLM + baseline model
C7F cold-start/cache/drain/termination
C7G capability-worker loss/replacement
~~~

CPU/browser order may move around GPU integration if contracts remain stable.

### C8 — Economics / Operations / Optimization

Add:

- source/cache/storage accounting;
- cold-start/download metrics;
- Research/Browser cost;
- ReverendBench v2 registry/reporting;
- idle/cache optimization.

### C9 — Full Acceptance

Exercise:

- two-user authority;
- Research Fabric;
- repository intelligence;
- context integrity;
- browser worker;
- CPU worker;
- zero-to-GPU-to-zero lifecycle;
- worker loss/recovery;
- benchmark/verification gates.

---

## 8. Development Non-Goals

Do not block Cloud v1 core on:

- Kubernetes;
- many simultaneous top-level Runs;
- permanent multi-GPU cluster;
- every simulation engine;
- every media generator;
- dozens of production LLMs;
- a learned scheduler/router;
- indiscriminate open-web crawling;
- a universal knowledge-graph database.

Interfaces should allow these later.

---

## 9. Remaining Non-Blocking Choices

Development/benchmark evidence may choose:

- exact CPU worker hosting/provider;
- Qdrant deployment mode;
- first Tree-sitter language set;
- exact LSP versions/adapters;
- exact browser worker hosting profile;
- optional object-store vendor;
- model-cache persistence economics;
- secondary/coding/verifier model winners;
- 48 GB cost-down winner;
- final idle-grace policy;
- exact source freshness TTLs.

Interfaces and safety constraints are frozen.

---

## 10. Architecture Blocker Definition

A blocker is a known issue that forces Development to invent or contradict architecture around:

- authority;
- identity;
- security/trust;
- durability/recovery;
- side effects;
- worker/provider lifecycle;
- Project knowledge/provenance;
- model/context semantics;
- cost attribution.

Implementation details that vary behind frozen interfaces are not blockers.

---

## 11. Required Pre-C0 Checklist

Before C0 begins:

- D0–D17 present on main;
- Design index updated;
- A10–A12 ephemeral refinement reconciled;
- D4/D7/D8/D9 reference new capability documents;
- system diagram includes Research/Repository/Worker Capability Fabric;
- README explains persistent Control Plane + disposable workers;
- CI green after documentation changes;
- Development issues reference the new Design documents;
- no real provider credentials in repository;
- main clean/stable.

---

## 12. Final Pre-Development Invariants

1. one authoritative workflow state;
2. immutable human/Run ownership;
3. models propose, trusted code executes;
4. durable state outlives compute;
5. zero GPU is healthy;
6. worker caches are never authority;
7. external evidence is provenance-bound and untrusted;
8. repository intelligence is snapshot-bound and derived;
9. exact/authority retrieval precedes fuzzy retrieval;
10. context is selected, not dumped;
11. Teams use minimum sufficient parallelism;
12. privileged side effects are journalled/recoverable;
13. secrets remain at privilege boundaries;
14. Community compute is lower trust;
15. deterministic verification outranks model claims;
16. costs derive from durable resource/provider lineage;
17. optimization is benchmark-driven;
18. new capabilities fit common worker/tool/artifact contracts instead of creating new authority planes.

---

## 13. Exit Condition

Development may enter C0 when documentation reflects D10–D17 consistently and a final documentation/CI pass finds no known unresolved Cloud-v1-blocking architecture contradiction.

This means **zero known blockers after repeated review**, not a claim that implementation can never reveal another defect.
