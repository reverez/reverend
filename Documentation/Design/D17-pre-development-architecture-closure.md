# D17 — Pre-Development Architecture Closure

> **Status:** PRE-DEVELOPMENT GATE CANDIDATE — FINAL CONSISTENCY / CI REQUIRED  
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


---

## 14. Capability Modernization Recursive Audit Findings

A fresh pass over D10–D16 identified and closed the following design gaps before Development:

1. **Search-query exfiltration:** private repository facts could leak through externally submitted queries. D11/D15 now require QueryDisclosurePolicy.
2. **Browser subresource SSRF:** protecting only top-level URLs is insufficient. Browser policy now covers every subresource, redirect, WebSocket and service worker.
3. **Private source-cache cross-scope reuse:** canonical URL alone is not a safe cache key for future authenticated providers. Source cache now has access partitions.
4. **Tree-sitter/LSP supply chain:** repository-defined parser/server plugins could become code execution. Only pinned Reverend-approved adapters are permitted.
5. **Vector index isolation:** filtering unauthorized Project results after global ranking is insufficient. Project scope is applied before ranking.
6. **Community-worker model credentials:** private model registry tokens must not be placed on lower-trust workers. Use public artifacts, pre-stage, short-lived object capabilities or stronger trust.
7. **Warm-volume contamination:** provider-local cache reuse may carry stale Project data. Warm storage is cache-only, validated and not a workspace authority.
8. **Model baseline fit assumption:** the accepted A100/Qwen/64K profile remains a target until C7 live fit/throughput validation promotes it.
9. **Evidence/cache retention confusion:** durable source snapshots referenced by evidence are protected from ordinary cache GC.

After these patches, these issues are no longer open architecture blockers.


---

## 15. Capability Modernization Recursive Audit — Cycle 2

A second pass found and closed additional laptop-to-server gaps:

1. **Unreproducible build environment:** workers can no longer assume developer-laptop toolchains; D14 adds ExecutionEnvironmentSpec and bounded dependency acquisition.
2. **Browser policy only at application layer:** D11/D6 now require OS/network egress enforcement as a second boundary.
3. **Frontend browser connectivity:** D14 defines task-scoped private TestEndpoint instead of publicly exposing development servers.
4. **Control host overload:** 4-vCPU/8-GB remains a baseline, but derived services must move off-host/queue when authority-service reserves would be violated.

These are now part of the C7/C8 acceptance surface.


---

## 16. Capability Modernization Recursive Audit — Cycle 3

A third pass closed asynchronous/distributed capability races:

1. **Late capability results:** D3/D15 now require Job-attempt + snapshot/policy revalidation before current-state use.
2. **Browser TestEndpoint authorization:** D14/D1 now require lease-bound authenticated private routes; opaque routing alone is not authority.
3. **Frontend credential bleed:** browser tests use explicit test-only credentials by default rather than copying real human sessions.

These prevent stale research/index/browser/model results from mutating newer execution state.


---

## 17. Capability Modernization Recursive Audit — Cycle 4

A fourth pass closed persistent-server behavior that could otherwise create hidden authority or data exposure:

1. **Background autonomous work:** D10/D14/D8 now forbid unowned background research/Agents; only operational housekeeping runs outside normal Run authority.
2. **Private research credential confusion:** D11/D6 separate authenticated research capabilities from Run-owner Git credentials.
3. **Browser Artifact confidentiality:** screenshots/traces/downloads inherit Project/source sensitivity and use sanitized bounded retention.
4. **Unbounded web mirroring:** source retention is policy/evidence driven; cache is not a permanent mirror.

No new Project truth is created merely because the Control Plane is always online.


---

## 18. Capability Modernization Recursive Audit — Cycle 5

A fifth pass closed additional production-scale and tool-boundary gaps:

1. **Credentialed SearchProvider secrets:** credential-bearing search is now a trusted Secret-Broker-backed adapter operation.
2. **Research fanout abuse:** per-origin/provider rate/concurrency policy is explicit.
3. **Evidence quote fabrication:** EvidenceClaim spans/quotes must structurally resolve against the exact retained SourceSnapshot.
4. **LSP configuration escape:** compiler/plugin/driver/plugin settings are sanitized; richer execution moves to explicit CPU capability.
5. **Uncommitted repository snapshot durability:** retained repository context cannot outlive the only reconstructible copy of its source state.
6. **Large Artifact bottleneck:** BlobStore now permits object-backed, object-scoped direct upload so future simulation/media output does not depend on Control Plane RAM/local disk.
7. **Internal resource cost confusion:** measured CPU usage is distinguished from actual payable provider cost.

These close the main remaining capability-layer architecture gaps found in the fifth pass.


---

## 19. Capability Modernization Recursive Audit — Cycle 6

A sixth pass closed confidentiality ambiguity around the selected Community GPU baseline:

1. **Sensitivity was not enough to determine placement.** D1/D6/D15 now separate data sensitivity from versioned Project disclosure policy.
2. **Community use is explicit.** Safe default rejects PROJECT_PRIVATE until Project owner opts in; ordinary engineering deployments can use an explicit Community preset.
3. **External API remains separate.** Community opt-in never implies permission to send the same data to an external model API.
4. **Inference logging:** model runtime prompt/body logging is disabled by default.
5. **Derived indexes remain sensitive even when reconstructible.**

This makes the economic Community baseline compatible with an explicit, auditable confidentiality decision rather than a silent assumption.
