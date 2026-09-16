# Reverend

**Specification in. Verified engineering work out.**

Reverend is a persistent autonomous software-engineering system designed to turn an engineering objective or accepted technical specification into implemented, tested, repaired, verified and reviewable software changes.

The project is evolving from a proven local AI engineering workstation into a private two-user Cloud platform with durable project intelligence, bounded Agent Teams, elastic model compute, repository-scale context, research/browser capabilities and explicit security, recovery and cost control.

> **Cloud v1 is a design target, not yet the current production implementation.**  
> The accepted local baseline is Reverend 0.4.0. Cloud Development begins with C0 after the pre-development Design closure is merged and validated.

---

## Why Reverend Exists

A large engineering task may require a relatively small number of high-value design decisions and a very large number of repetitive implementation iterations:

~~~text
inspect repository
→ localize change
→ edit code
→ build
→ test
→ observe failure
→ diagnose
→ repair
→ test again
→ verify
→ document
→ integrate
~~~

Reverend is designed to keep that long-running engineering loop on infrastructure you control, while preserving the option to use human or frontier-model intelligence where it has the highest leverage.

A common workflow is:

~~~text
Human + design intelligence
        ↓
accepted SpecificationPackage
        ↓
Reverend
        ↓
decompose
implement
compile/build
test
debug
repair
verify
document
integrate
        ↓
reviewable engineering result
~~~

A useful shorthand is:

> **GPT can design. Reverend builds.**

But Reverend is **not coupled to GPT, Codex, OpenAI, or any other frontier-model provider**. External design intelligence is optional and replaceable. Reverend also supports objective-driven Runs where it performs its own research, clarification and architecture before implementation.

---

## Product Model

Reverend separates four layers of responsibility:

~~~text
L0 — Human authority
      objectives • approvals • policy • final product intent

L1 — Design intelligence
      human / external frontier model / Reverend Architect
      research • architecture • contracts • acceptance criteria

L2 — Autonomous engineering
      Reverend
      decomposition • implementation • testing • repair • integration

L3 — Deterministic reality
      compilers • tests • benchmarks • simulations • Git • CI
~~~

The trust ordering is deliberate:

~~~text
Human / Project policy
> accepted SpecificationPackage
> normalized Requirements / Decisions / AcceptanceCriteria
> Reverend orchestration
> Agent/model proposals
> deterministic evidence decides implementation correctness
~~~

A model saying “done” is never sufficient.

---

## Specification-Driven Engineering

The preferred high-reliability workflow uses a versioned **SpecificationPackage** rather than one enormous prompt.

Conceptually:

~~~text
SpecificationPackage/
├── objective
├── requirements
├── non-goals
├── architecture
├── component contracts
├── data model
├── API contracts
├── security model
├── failure semantics
├── performance requirements
├── testing strategy
├── acceptance criteria
├── development plan
├── references
└── machine-readable contracts
~~~

Reverend validates and compiles the package into durable Project state:

~~~text
SpecificationPackage
→ Requirements
→ accepted Decisions
→ AcceptanceCriteria
→ interface / contract Artifacts
→ Run
→ Task DAG
~~~

A Run pins the exact accepted specification version and hash.

If the design changes, Reverend creates an explicit amendment/new version instead of silently drifting away from the accepted specification.

If Reverend becomes stuck or discovers a real architecture ambiguity, it emits an **EscalationArtifact** containing the relevant specification, attempts, deterministic failures, evidence and exact decision required. That escalation can go to the human, an external frontier model, or a Reverend Architect Specialist.

---

## Current Status

| Area | Status |
|---|---|
| Reverend 0.4.0 local workstation | Accepted baseline |
| Cloud Analysis A0–A12 | Complete |
| Cloud Design D0–D22 | Hardened, pre-C0 closure |
| Specification-driven design refinement | Integrated into Design |
| Cloud implementation | Next phase |
| Current local inference | Ollama |
| Cloud v1 primary runtime target | vLLM |
| Cloud v1 baseline workhorse | Qwen3.8-27B |
| Cloud v1 baseline GPU | RunPod Community A100 SXM 80 GB |
| Cloud v1 authoritative database | PostgreSQL |
| Top-level Run concurrency | 1 |
| GPU scale-to-zero | Required |

The accepted Reverend 0.4.0 release recorded **619 passing tests** with live local inference, research/search, sandbox, development, verification, memory and Workstation validation.

Cloud Development must preserve those reliability properties while replacing laptop-bound implementations.

---

# Cloud v1 Architecture

~~~text
Two authenticated developers
          │
          ▼
Thin GUI / CLI / IDE clients
          │
          ▼
Authenticated /api/v1 + SSE
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│             PERSISTENT REVEREND CONTROL PLANE              │
│                                                             │
│  PostgreSQL authority                                       │
│  Project / Specification / Run / Workflow / Task / Job      │
│  Executive Orchestrator                                     │
│  Agent / Team Runtime                                       │
│  Context Broker                                             │
│  Research Fabric                                            │
│  Repository Intelligence                                    │
│  Memory / Evidence / Artifacts                              │
│  Model Registry / Router                                    │
│  Tool / Policy / Secret Brokers                             │
│  Workflow Scheduler                                         │
│  Compute Scheduler                                          │
│  Capacity Controller                                        │
│  Recovery / Action Journal                                  │
│  Cost / Budgets / Observability                             │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
             authenticated capability workers
                           │
        ┌──────────────────┼───────────────────┐
        │                  │                   │
        ▼                  ▼                   ▼
 CPU build/test      Browser research      Model GPU
 index / LSP          frontend testing      vLLM
        │                  │                   │
        └──────────────────┼───────────────────┘
                           │
             future specialized workers
                           │
              scientific GPU / media GPU
~~~

---

## Persistent Brain, Disposable Muscle

The most important Cloud invariant is the separation between durable intelligence and replaceable compute.

### Persistent / authoritative

~~~text
PostgreSQL
Git / recovery refs
durable BlobStore
SpecificationPackages
Requirements / Decisions / AcceptanceCriteria
Artifacts / retained Evidence / Memory
Action Journal
RunCheckpoint / RecoveryGeneration
cost / audit / policy state
~~~

### Reconstructible / disposable

~~~text
CPU workers
Browser workers
GPU workers
model weights
vLLM KV / prefix cache
Qdrant indexes
Tree-sitter indexes
LSP sessions
browser caches
build/package caches
temporary worktrees
provider instances
~~~

Destroying every RunPod resource must cause **reconstruction work**, not Project loss.

A healthy Reverend installation can have:

~~~text
GPU workers = 0
~~~

---

# Project Intelligence

Reverend does not use one giant “memory database”.

Different information classes have different authority and lifetime.

~~~text
Authoritative Project State
    Requirements
    accepted Decisions
    SpecificationPackages
    policy

Execution State
    Runs
    Workflows
    Tasks
    Jobs
    Teams
    budgets
    approvals

Artifact Fabric
    implementation outputs
    test reports
    architecture packs
    verification reports

Evidence Fabric
    external source snapshots
    claims
    research evidence packs

Memory Fabric
    validated reusable failures/results/experiments/facts

Repository Intelligence
    files
    symbols
    references
    imports
    dependency/test/interface graphs
    diagnostics

Derived indexes
    lexical
    vectors
    Tree-sitter caches
    LSP state
~~~

Derived indexes accelerate retrieval. They are never Project truth.

---

# Context Broker

Agents do not receive the entire repository, chat history, memory store and web cache on every call.

Reverend compiles context progressively:

~~~text
1. system / security / policy
2. Task / Requirements / AcceptanceCriteria
3. explicit parent Artifacts
4. exact repository symbols / references / interfaces
5. retained Evidence
6. Project Memory
7. lexical / structural retrieval
8. semantic / hybrid retrieval
9. external research when information is missing or stale
10. optional interaction history
~~~

The Agent can issue a bounded **ContextRequest** for more information.

Large model context windows are **headroom**, not a target.

---

# Repository Intelligence

Reverend treats repository understanding as a first-class engineering capability.

The Cloud design evolves the existing Python codeintel subsystem into:

~~~text
RepositorySnapshot
├── Git / filesystem facts
├── current Python AST intelligence
├── Tree-sitter structural parsing
├── LSP / type-service adapters
│   ├── Pyright
│   ├── clangd
│   ├── TypeScript language service
│   └── future language adapters
├── dependency / interface graph
├── affected-test mapping
└── semantic fallback
~~~

Exact deterministic information is preferred over fuzzy retrieval:

~~~text
path
→ symbol
→ definition / references
→ dependency / test graph
→ lexical / structural search
→ semantic search
~~~

Every result is tied to an exact repository/worktree snapshot so stale indexes cannot silently describe newer code.

---

# Research Fabric

Reverend's existing SearXNG/Brave + restricted-fetch foundations are generalized into a persistent research subsystem.

~~~text
Research Coordinator
├── Search Broker
│   ├── SearXNG
│   ├── Brave
│   ├── GitHub
│   ├── Hugging Face
│   ├── academic providers
│   └── future domain providers
│
├── Fetch Broker
│   ├── structured APIs
│   ├── restricted HTTP
│   ├── documents / PDFs
│   └── Browser Worker
│
├── Source Registry
├── Source Cache
├── Evidence Extractor
├── Evidence Validator
└── Research Synthesizer
~~~

Research normally escalates:

~~~text
existing fresh Evidence
→ structured provider/API
→ search
→ restricted HTTP fetch
→ browser only when necessary
~~~

Search results are discovery. Retained claims cite exact **SourceSnapshots** with provenance and freshness.

External content remains untrusted data and cannot alter Reverend policy or tool authority.

---

## Research Teams

Agent Teams are useful when they partition work rather than duplicate it.

Example:

~~~text
Research Lead
├── Official Sources
├── Academic Literature
├── GitHub / Ecosystem
├── Benchmarks
├── Deployment / Economics
└── Adversarial / Counterevidence
        ↓
ResearchEvidencePack
~~~

Five logical research Agents do **not** require five GPUs.

HTTP/API/browser work can overlap while model inference shares or time-slices the same model runtime.

---

# Agent & Team Runtime

A Reverend Agent is:

> a bounded, policy-governed runtime instantiation of a versioned Specialist methodology assigned to one authoritative Task.

Agent is **not** synonymous with model, Task, process, or GPU.

~~~text
Run
→ Workflow
→ Task
→ AgentInstance
→ Job attempt
→ model / tools / capabilities
→ typed Artifacts
→ verification
~~~

Teams use the minimum sufficient number of Agents.

Supported Team strategies include:

~~~text
pipeline
parallel decomposition
sharded research
independent replication
adversarial review
~~~

The Control Plane DAG remains the only workflow authority.

---

# Model Fabric

Specialists request capabilities, not checkpoints.

~~~text
Specialist
→ ModelRequirement
→ eligible ModelProfiles
→ eligible DeploymentProfiles
→ Model Router
→ Compute Scheduler
→ InferenceRuntime
~~~

Initial Cloud baseline:

| Concern | Baseline |
|---|---|
| Provider | RunPod Community Cloud |
| GPU | A100 SXM 80 GB |
| Runtime | vLLM |
| Workhorse | Qwen3.8-27B |
| Reverend serving context | 64K |
| GPU lifecycle | provision on demand → idle grace → drain → terminate |

The baseline is a **benchmark target**, not a permanent binding.

ReverendBench may later promote:

- coding-specialized models;
- smaller control models;
- independent verifier models;
- embeddings / rerankers;
- vision models;
- quantized profiles;
- external API models where disclosure policy permits.

Model weights are reconstructible cache objects by default.

---

# Worker Capability Fabric

Cloud v1 separates execution by capability.

### Bounded Control-host sandbox

Tiny safe operations only.

### CPU build/test worker

~~~text
build
test
lint
dependency preparation
repository indexing
LSP/type services
document parsing
data transforms
~~~

### Browser Worker

Two policy modes:

~~~text
RESEARCH_BROWSER
FRONTEND_TEST_BROWSER
~~~

### Model GPU worker

~~~text
vLLM / SGLang
generation
embeddings / reranking where appropriate
vision/model inference
~~~

### Future accelerated workers

~~~text
scientific CUDA
CFD / FEA
simulation
image / 3D / video / audio
~~~

All specialized workers reuse the same compute/resource/lease/artifact/cost architecture rather than inventing separate schedulers.

---

# Security & Trust

Reverend is designed for a private two-user deployment, but remote compute still introduces real trust boundaries.

Key rules:

- immutable Run ownership;
- users cannot silently resume another user's Run under that user's credentials/budget;
- Secret Broker is privilege-separated from the normal application process;
- credentials are resolved only at bounded enforcement points;
- model/browser/CPU workers do not receive PostgreSQL, provider lifecycle or unrelated user credentials;
- Community Cloud is explicitly lower-trust;
- Project disclosure policy determines what private context may leave the trusted Control Plane;
- external model APIs require a separate disclosure decision;
- search-query text itself is treated as potential data disclosure;
- browser/fetch workers enforce SSRF/network policy;
- repository-provided LSP/plugins/parsers are not automatically trusted;
- model runtime prompt logging is disabled by default;
- active browser/HTML Artifacts cannot execute in the authenticated Reverend application origin.

Models propose actions. Trusted Reverend code decides what is permitted.

---

# Durable Execution & Recovery

A long-running autonomous system must survive ordinary and catastrophic failure.

Reverend does **not** rely on preserving:

~~~text
Python stack
process memory
CUDA state
GPU VRAM
KV cache
browser state
worker filesystem
~~~

Durability uses:

~~~text
authoritative PostgreSQL state
Git / workspace reconstruction refs
typed Artifacts
RunCheckpoints
Action Journal
RecoveryGenerations
off-host recovery replicas
off-host ActionIntent barrier for dangerous external effects
~~~

External side effects are write-ahead journalled.

Ambiguous effects are reconciled before retry.

If the system cannot prove whether a dangerous action happened, **RECOVERY_BLOCKED** is preferable to guessing.

---

# Cost & Scheduling

Reverend treats cost as architecture, not an afterthought.

Scheduling is split into:

~~~text
Workflow Scheduler
    what may logically run

Compute Scheduler
    where it can physically run

Capacity Controller
    whether infrastructure should exist

Execution Runtime
    performs the work
~~~

Budgets are hierarchical:

~~~text
Run
→ Team
→ Task
→ Agent
→ Job / operation
~~~

Paid compute is admitted before provisioning.

Costs distinguish:

- provider source cost;
- user/project allocation;
- startup/load overhead;
- useful lease time;
- idle grace;
- storage/cache cost;
- safety-recovery overrun.

Primary optimization target:

> **GBP per verified successful engineering Task**

—not tokens per second and not maximum Agent count.

---

# ReverendBench v2

ReverendBench evaluates the engineering organization, not just the model.

It compares:

~~~text
models
reasoning effort
context size
repository retrieval
Research Fabric strategies
single Agent vs Teams
browser workflows
worker placement
cache policy
idle grace
recovery
verification
security
~~~

Promotion follows:

~~~text
correctness
→ security/integrity
→ requirement satisfaction
→ independent verification
→ robustness
→ human intervention
→ maintainability
→ latency
→ cost
~~~

A cheaper configuration that fails acceptance does not win.

---

# Development Programme

Cloud v1 is implemented in ordered slices.

~~~text
C0  Contract package / migration skeleton

C1  PostgreSQL persistent Control Plane

C2  Remote identity / REST API / SSE

C3  Run / queue / workflow convergence

C4  Agent / Team / Context
    Research + Repository Intelligence facades

C5  Security / Git / secrets / approvals

C6  Durable execution / recovery

C7  Capability execution fabric
    CPU worker
    Browser Worker
    RunPod ephemeral Model GPU
    vLLM / baseline model
    cold-start / drain / scale-to-zero

C8  Economics / budgets / observability
    ReverendBench v2

C9  Full Cloud acceptance
~~~

**Development begins with C0, not with GPU provisioning.**

---

# Documentation

Canonical architecture lives in:

- [Analysis — A0–A12](Documentation/Analysis/)
- [Design Index — D0–D22](Documentation/Design/00-design-index.md)
- [Complete System Diagram](Documentation/Design/system-complete-mermaid-diagram.md)
- [Subsystem Diagrams](Documentation/Design/Diagrams/)

Key documents:

| Document | Scope |
|---|---|
| [A12](Documentation/Analysis/A12-cloud-architecture-acceptance.md) | accepted Cloud architecture |
| [D0](Documentation/Design/D0-system-contracts-and-codebase-boundaries.md) | system boundaries and contracts |
| [D1](Documentation/Design/D1-authoritative-domain-and-postgresql-schema.md) | PostgreSQL authority and schema |
| [D2](Documentation/Design/D2-api-auth-sse-and-client-contract.md) | API/auth/SSE/client contract |
| [D3](Documentation/Design/D3-agent-team-context-artifact-runtime.md) | Agent/Team runtime + specification-driven workflow |
| [D4](Documentation/Design/D4-scheduling-compute-worker-and-provider-protocol.md) | scheduling/worker/provider protocol |
| [D5](Documentation/Design/D5-durable-execution-checkpoints-action-journal-recovery.md) | durable execution and recovery |
| [D6](Documentation/Design/D6-security-secrets-git-approvals-and-emergency-controls.md) | security/secrets/Git/approvals |
| [D7](Documentation/Design/D7-model-profiles-routing-serving-and-reverendbench.md) | model profiles/routing |
| [D8](Documentation/Design/D8-observability-cost-budgets-operations-deployment.md) | operations/cost/budgets |
| [D9](Documentation/Design/D9-development-programme-migration-and-acceptance.md) | implementation programme |
| [D10](Documentation/Design/D10-research-retrieval-evidence-acquisition.md) | research, retrieval and evidence foundations |
| [D11](Documentation/Design/D11-legacy-to-cloud-migration-and-refactor-map.md) | 0.4.0 → Cloud migration/refactor map |
| [D12](Documentation/Design/D12-tool-policy-side-effect-and-recovery-registry.md) | tool policy, side effects and recovery registry |
| [D13](Documentation/Design/D13-client-operator-ux-state-contract.md) | client/operator UX state contract |
| [D14](Documentation/Design/D14-development-readiness-baseline-and-postgresql-test-strategy.md) | baseline, PostgreSQL tests and Development readiness |
| [D15](Documentation/Design/D15-capability-modernization-audit.md) | laptop → cloud capability audit |
| [D16](Documentation/Design/D16-research-fabric-and-web-context-acquisition.md) | Research Fabric |
| [D17](Documentation/Design/D17-repository-intelligence-and-code-context.md) | Repository Intelligence |
| [D18](Documentation/Design/D18-model-fabric-serving-and-optimization.md) | Model Fabric |
| [D19](Documentation/Design/D19-worker-capability-fabric-and-ephemeral-bootstrap.md) | Worker Capability Fabric |
| [D20](Documentation/Design/D20-context-broker-and-knowledge-retrieval-v2.md) | Context Broker v2 |
| [D21](Documentation/Design/D21-reverendbench-v2-and-adaptive-optimization.md) | ReverendBench v2 |
| [D22](Documentation/Design/D22-pre-development-architecture-closure.md) | pre-development closure |

Implementation should follow these contracts rather than inventing architecture ad hoc.

---

# Current Local Baseline

Reverend 0.4.0 remains the accepted local regression baseline.

Requirements:

- Python 3.11+
- Git
- Linux / WSL2
- Ollama for current local inference
- Linux sandbox support for untrusted execution

Install:

~~~bash
git clone <repository-url>
cd reverend

python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -e '.[dev]'
~~~

Start the current local Workstation:

~~~bash
.venv/bin/reverend gui
~~~

Default address:

~~~text
http://127.0.0.1:8765
~~~

The current Workstation is intentionally loopback-only. Do **not** make it internet-facing by changing the bind address.

Remote access is provided by the Cloud architecture, not by exposing the local Workstation.

---

# Validation

Run the Python test suite:

~~~bash
.venv/bin/python -m pytest -q
~~~

Portable final validation:

~~~bash
.venv/bin/python -m reverend.benchmarks.final_validation \
  --repository . \
  --skip-live \
  --report-root benchmarks/results/vnext/final-validation
~~~

Full live validation requires the supported local inference/search environment.

See:

- [Accepted local final validation](docs/current/release/final-acceptance.md)
- [Current documentation index](docs/README.md)

---

# Repository Structure

~~~text
Documentation/
├── Analysis/              Cloud architecture analysis A0–A12
└── Design/                Cloud implementation design D0–D22

src/reverend/
├── controlplane/          authoritative workflow foundations
├── development/           repository/worktree/engineering runtime
├── intelligence/          context/evidence/intelligence foundations
├── observability/         events/metrics/tracing
├── policy/                capability/tool policy
├── research/              accepted research foundations
├── runtime/               models/resources/providers
├── specialists/           Specialist definitions/runtime
├── ui/                    local client assets
└── workstation/           Reverend 0.4.0 compatibility mode

tests/
benchmarks/
config/
deploy/
docs/
~~~

Cloud Development extends these semantics rather than creating duplicate authority planes.

---

# Development Discipline

**main** is the stable integration branch.

Major work should follow:

~~~text
accepted main
→ narrow branch / worktree
→ implement one Design slice
→ deterministic tests
→ targeted validation
→ relevant full validation
→ review
→ merge
~~~

Rules:

- never weaken tests to make a change pass;
- never make workers/caches authoritative;
- never let model confidence override deterministic failure;
- never silently change an accepted SpecificationPackage;
- never introduce paid-provider behavior before the corresponding budget/recovery/security gate exists;
- preserve Reverend 0.4.0 regression behavior until an accepted Cloud replacement exists.

---

# Non-Goals for Cloud v1

Cloud v1 does not require:

- Kubernetes;
- a permanent GPU cluster;
- many simultaneous top-level Runs;
- dozens of production LLMs;
- one model per Specialist;
- a fully learned scheduler/router;
- indiscriminate web crawling;
- every scientific simulation engine;
- every media-generation backend;
- a universal knowledge-graph database.

The architecture leaves room for these capabilities later without making them prerequisites for a reliable first Cloud release.

---

# Project Direction

Reverend is being built as a **persistent autonomous engineering organization**, not merely a chatbot or code generator.

Its intended strengths are:

- specification-driven implementation;
- optional objective-driven research and design;
- persistent Project intelligence;
- repository-scale deterministic context;
- bounded specialist Agents and Teams;
- long-running implementation/debugging loops;
- strong testing and failure investigation;
- independent verification;
- secure human authority;
- durable recovery;
- elastic self-hosted model compute;
- explicit costs;
- replaceable models/providers;
- future scientific simulation and asset-generation capability.

The goal is not to maximize model size, prompt length or Agent count.

The goal is to maximize:

> **verified engineering value per unit of human attention, frontier-model usage and infrastructure cost.**
