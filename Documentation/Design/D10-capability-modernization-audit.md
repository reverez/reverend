# D10 — Capability Modernization Audit

> **Status:** DESIGN ACCEPTED FOR DEVELOPMENT  
> **Research snapshot:** 2026-09-16  
> **Depends on:** A12, D0–D9, accepted Reverend 0.4.0 local baseline  
> **Purpose:** Re-evaluate every laptop-era Reverend capability now that Cloud v1 has a persistent Control Plane, durable storage, elastic CPU/browser/GPU workers and replaceable model serving.

---

## 1. Executive Decision

The Cloud migration is incomplete if Reverend merely moves the existing Workstation onto a server.

The accepted modernization principle is:

> **Preserve proven semantics; replace machine-local implementations; add persistent intelligence services and elastic execution where the cloud changes what is technically or economically possible.**

Reverend Cloud v1 therefore gains a **Capability Fabric** beneath the Agent/Team runtime:

~~~text
Agent / AgentTeam
        │
        ▼
Context Broker + Tool Broker
        │
        ├── Repository Intelligence
        ├── Research Fabric
        ├── Project Knowledge / Memory
        ├── Model Fabric
        └── Execution Capability Fabric
              ├── bounded local sandbox
              ├── CPU build/test worker
              ├── browser worker
              ├── model GPU worker
              ├── accelerated-compute GPU profile
              └── media/asset GPU profile
~~~

The Capability Fabric contains **derived intelligence and replaceable execution**, not a second source of workflow authority.

---

## 2. Current Baseline Audit

### Research today

The repository already has:

- research/search.py with typed Brave/SearXNG query-to-web configuration;
- bounded search/fetch budgets;
- research/service.py with bubblewrap-isolated public fetch/search/image workers;
- deterministic source-authority/freshness metadata;
- public evidence persistence and provenance;
- accepted M17/M18 live search/fetch/image paths.

Decision: **KEEP + GENERALIZE**.

Cloud limitations:

- local SQLite-oriented persistence;
- static HTTP acquisition is the primary reader;
- browser automation is not a production research capability;
- no persistent multi-provider Research Fabric;
- source reuse/freshness invalidation is limited;
- research swarms do not partition evidence acquisition as a first-class Team strategy.

### Repository intelligence today

The existing codeintel subsystem already provides:

- repository scanning;
- file/language/build metadata;
- Python AST symbols/imports/calls;
- Python dependency graph;
- lexical/structural retrieval;
- bounded coding context.

Decision: **KEEP + GENERALIZE**.

Cloud limitations:

- structural intelligence is primarily Python-specific;
- no general Tree-sitter multi-language layer;
- no first-class LSP/type-service adapters;
- no durable commit/worktree index identity;
- no unified test/interface/dependency impact graph.

### Knowledge and retrieval today

The local Knowledge Fabric already proves:

- canonical state separate from vector index;
- lexical + dense + hybrid retrieval;
- BGE-M3 embeddings;
- Qdrant as reconstructible dense index;
- evidence/provenance gating;
- bounded context compilation.

Cloud keeps these semantics while moving authority to PostgreSQL/Artifact/Blob contracts.

### Model runtime today

Local Reverend already has:

- ModelSpec;
- logical model roles;
- resource scheduling;
- Ollama adapter;
- model-call budgets;
- independent verification.

Cloud generalizes this into:

~~~text
ModelRequirement
→ ModelProfile
→ DeploymentProfile
→ Model Router
→ Compute Scheduler
~~~

### Browser capability today

Playwright exists only in test/acceptance workflows.

Cloud introduces a real isolated Browser Worker for:

1. JavaScript-heavy research acquisition;
2. frontend/browser verification.

### Asset and scientific compute today

Image/asset and scientific/accelerated workloads exist only as partial or planned capabilities.

Cloud freezes their **worker/resource interfaces**, but does not require every renderer/simulator implementation before core Cloud v1 acceptance.

---

## 3. Capability Classification

| Capability | Decision | Cloud v1 direction |
|---|---|---|
| Control Plane DAG/state | KEEP + EXTEND | PostgreSQL authority |
| Specialist/Agent semantics | KEEP + EXTEND | dynamic Agents/Teams |
| fixed WorkerRole taxonomy | REPLACE | registry-driven capabilities |
| local Ollama implementation | KEEP compatibility | vLLM primary cloud adapter |
| static model-role binding | REPLACE | ModelRequirement routing |
| local resource broker | KEEP semantics | distributed leases/schedulers |
| SearXNG/Brave search | KEEP + GENERALIZE | SearchProvider |
| restricted HTTP fetch | KEEP + GENERALIZE | FetchProvider |
| production browser research | NEW | Browser Worker |
| source cache | NEW/GENERALIZE | persistent Source Registry/Snapshots |
| evidence provenance | KEEP + EXTEND | EvidenceClaim/EvidencePack |
| Python AST code intelligence | KEEP | one Repository Intelligence adapter |
| Tree-sitter index | NEW | language-neutral structural layer |
| LSP/type services | NEW | language-specific semantic layer |
| Qdrant | KEEP derived | hybrid semantic retrieval |
| Engineering Memory | KEEP + MIGRATE | Project-scoped PostgreSQL Memory |
| context compiler | KEEP + EXTEND | iterative demand-driven Context Broker |
| local worktrees | KEEP | worker-independent MutationScope/workspaces |
| build/test execution | GENERALIZE | CPU worker + bounded local sandbox |
| Playwright test fixture | GENERALIZE | Browser Test capability |
| GPU inference | REPLACE physical path | ephemeral Model GPU worker |
| model persistence | RECLASSIFY | reconstructible cache |
| GPU scientific compute | NEW capability profile | accelerator worker |
| media/render GPU | NEW capability profile | asset worker |
| benchmark framework | KEEP + EXPAND | ReverendBench v2 |
| client-side workflow state | REDUCE | projection only |

---

## 4. Capability Fabric Invariants

### CF-01 — Capability does not create authority

A SearchProvider, browser, LSP, vector index, model runtime or worker cannot mutate authoritative workflow state except through validated Control Plane commands/Artifacts.

### CF-02 — Derived indexes are disposable

Repository indexes, embeddings, search caches, browser caches, model weights and build outputs are reconstructible.

### CF-03 — Provenance crosses subsystem boundaries

Every context item returned from research/repository/memory services carries source identity, version/hash, trust, sensitivity and freshness.

### CF-04 — Exact knowledge outranks fuzzy retrieval

Authoritative objects, explicit dependencies, exact symbols/references and deterministic graph results are attempted before semantic similarity.

### CF-05 — Network/browser content is untrusted

Search results, pages, browser DOM and downloaded content remain untrusted data.

### CF-06 — Workers are capability-scoped

A worker advertises verified capabilities. GPU does not imply LLM inference, and browser does not imply general network/secret authority.

### CF-07 — Logical parallelism is not physical parallelism

A five-member Research Team may have concurrent HTTP tasks while model inference is serialized through one GPU.

### CF-08 — Cache is optimization only

Loss of source cache, vector index, model cache, browser cache or optional provider volume may increase latency but cannot destroy Project/Run correctness.

### CF-09 — Promotion is explicit

Research synthesis, repository summaries and model outputs do not become Requirements/Decisions/Memory merely because they were generated.

### CF-10 — Modernization is benchmarked

New intelligence layers are promoted by ReverendBench evidence.

---

## 5. New First-Class Logical Services

Cloud v1 Design now includes:

~~~text
Research Fabric
Repository Intelligence Service
Context Broker / Context Compiler
Model Registry / Router
Capability Registry
Worker / Compute Fabric
ReverendBench Registry
~~~

They may initially be modules within the modular monolith or worker processes. They do not require a microservice deployment.

---

## 6. Capability Registry

Conceptual contract:

~~~text
CapabilitySpec
├── capability_id
├── version
├── capability_family
├── input_contract
├── output_contract
├── resource_requirement_template
├── trust_requirement
├── side_effect_class
├── network_policy
├── recovery_policy
├── benchmark_profile
└── implementation adapters
~~~

Examples:

~~~text
research.search/v1
research.http_fetch/v1
research.browser_fetch/v1
repo.symbol_lookup/v1
repo.references/v1
repo.diagnostics/v1
execution.build/v1
execution.test/v1
browser.frontend_test/v1
inference.generate/v1
compute.cuda/v1
media.render/v1
~~~

A Specialist requests a capability; it does not choose the physical worker/provider.

---

## 7. Persistent vs Reconstructible Intelligence

### Durable

~~~text
Requirements
Decisions
MemoryRecords
Artifact metadata/content
Evidence source metadata/snapshots required by retained evidence
Run/Task/Job state
Action Journal
repository binding / commits
benchmark results
accepted model/profile registry state
~~~

### Reconstructible

~~~text
Qdrant collections
Tree-sitter index
symbol/reference caches
LSP cache/state
web search cache where source retention is not required
model weights
vLLM KV/prefix cache
browser profile/cache
build/test cache
package cache
temporary worktrees
~~~

Evidence snapshots referenced by durable Evidence Packs are promoted to durable BlobStore retention rather than left only in disposable cache.

---

## 8. Major Risks and Solutions

### One giant vector database

Failure: code, research, memory and conversation history flattened into similarity search.

Decision: vector retrieval is one derived candidate generator; authoritative/symbolic retrieval precedes it.

### Uncontrolled Agent swarms

Failure: more model calls without better coverage.

Decision: Teams use partitioned search/decomposition, minimum-sufficient-team policy and explicit synthesis.

### Browser becomes privileged remote shell

Decision: dedicated browser profiles, URL/network policy, no ambient Reverend credentials, task-specific allowed origins.

### Index staleness after edits

Decision: every repository result binds to RepositorySnapshot identity; mismatched snapshot is rejected.

### Model fleet complexity

Decision: begin with one workhorse; add profiles only when ReverendBench proves value.

### Oversized context

Decision: context stays demand-driven; 64K remains baseline until measured benefit justifies more.

### Research cache becomes stale authority

Decision: source-type freshness + source timestamp/hash + explicit refresh triggers.

---

## 9. Mandatory Modernized Capabilities for Core Cloud v1

Before C9:

1. persistent Project/Run knowledge authority;
2. query-to-web SearchProvider;
3. restricted static HTTP fetch;
4. Source Registry + retained evidence snapshots;
5. Repository Intelligence with exact file/symbol structure;
6. at least the accepted Python structural capability;
7. Context Broker using authority-first retrieval;
8. elastic model worker;
9. CPU build/test execution path that cannot threaten Control Plane availability;
10. Browser capability sufficient for frontend verification and JS-heavy research;
11. ReverendBench evaluation of retrieval/context/model/team choices.

Multi-language Tree-sitter/LSP breadth may expand incrementally.

Media generation and arbitrary scientific simulation are first-class extensibility targets, not mandatory C9 blockers unless selected Project acceptance requires them.

---

## 10. Development Effect

The original C0–C9 sequence remains valid.

Largest changes:

~~~text
C0
  add capability/research/repository/context contracts

C4
  Context Broker + Repository Intelligence + research interfaces

C7
  general Worker Capability Fabric
  not only RunPod/vLLM

C8
  research/browser economics, cache/cold-start telemetry,
  ReverendBench promotion data

C9
  whole-organization capability acceptance
~~~

D11–D17 freeze the detailed designs.

---

## 11. Exit Condition

Capability modernization is complete when every significant local-era subsystem has a Cloud disposition, persistent/reconstructible classification, trust boundary, worker placement, budget model and benchmark gate.
