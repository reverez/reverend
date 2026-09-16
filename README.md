# Reverend

**Reverend** is a persistent AI software-engineering system designed to turn high-level objectives into researched, implemented, tested and independently verified project changes.

The current stable implementation is **Reverend 0.4.0**, a local-first Linux/WSL2 engineering workstation. The Cloud architecture has completed its Analysis and Design phases and is ready to enter staged Development.

> Cloud v1 is a **design target**, not yet the current production implementation.

---

## Current Status

| Area | Status |
|---|---|
| Local Reverend 0.4.0 | Accepted baseline |
| Cloud Analysis A0–A12 | Complete / accepted |
| Cloud Design D0–D17 | Complete / ready for Development |
| Cloud implementation | Next phase |
| Current local inference | Ollama-based |
| Accepted Cloud v1 inference target | vLLM + Qwen3.8-27B |
| Accepted Cloud v1 baseline GPU | RunPod Community A100 SXM 80 GB |
| Accepted Cloud v1 authoritative DB | PostgreSQL |

The historical accepted local validation recorded **619 passing tests** together with live local inference, research/search, sandbox, development, verification, memory and Workstation checks. Development must continue to preserve those reliability and safety properties.

---

## Cloud v1 Architecture

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
Persistent Reverend Control Plane
          │
          ├── PostgreSQL authoritative state
          ├── Project / Run / Workflow / Task / Job
          ├── Agent / Team runtime
          ├── Context / Memory / Artifacts
          ├── Policy / Approvals / Secrets / Git
          ├── Workflow Scheduler
          ├── Compute Scheduler
          ├── Capacity Controller
          ├── Recovery
          └── Cost / Observability
          │
          ▼
Authenticated disposable execution workers
          │
          ├── CPU sandbox execution
          └── RunPod GPU workers
                └── vLLM
                      └── Qwen3.8-27B baseline
~~~

Cloud v1 keeps the Control Plane available even when GPU worker count is zero.

Initial accepted operating profile:

- private installation for two authenticated developers;
- one active top-level Run;
- bounded internal Agent/Job parallelism;
- persistent CPU-oriented Control Plane;
- PostgreSQL authoritative state;
- RunPod Community Cloud Pods for GPU execution;
- A100 SXM 80 GB initial GPU;
- vLLM initial cloud inference runtime;
- Qwen3.8-27B initial workhorse;
- 64K initial serving context;
- GPU provisioning on demand and scale-to-zero after idle grace.

These deployment choices remain replaceable behind stable interfaces.

---

## Core Invariants

Reverend development must preserve these rules:

- **One authoritative workflow state:** clients, models, workers and caches never become competing sources of truth.
- **Immutable Run ownership:** user-scoped Git identity, approvals, secrets and variable cost follow the Run owner.
- **Models propose; Reverend executes:** model output never creates authority.
- **Compute is replaceable:** Run recovery does not depend on Python memory, GPU VRAM, CUDA state or KV cache.
- **Typed collaboration:** Agents communicate durable work through typed Artifacts and structured control signals.
- **Selective context:** repository/history/memory are compiled per Task instead of copied wholesale into every prompt.
- **Verification outranks confidence:** deterministic failures block integration regardless of model claims.
- **Secrets remain at enforcement boundaries:** raw credentials are never normal model/client state.
- **Minimum sufficient parallelism:** more Agents are created only when useful.
- **Costs are attributable:** paid execution is traceable to immutable resource and Run ownership events.

---

## Documentation

The architecture is defined in two stages:

- [Analysis phase — A0–A12](Documentation/Analysis/)
- [Design phase — implementation contracts and development plan](Documentation/Design/00-design-index.md)

The final accepted architecture is:

- [A12 — Cloud Architecture Acceptance](Documentation/Analysis/A12-cloud-architecture-acceptance.md)

The Design specification covers:

~~~text
D0  System contracts and codebase boundaries
D1  PostgreSQL authoritative domain model
D2  API, authentication, SSE and client contract
D3  Agent, Team, context and Artifact runtime
D4  Scheduling, workers, RunPod and vLLM protocol
D5  Checkpoints, Action Journal and recovery
D6  Security, secrets, Git and approvals
D7  Model profiles, routing and ReverendBench
D8  Observability, costs, budgets and operations
D9  Development programme and acceptance gates
D10 Research, retrieval and evidence acquisition
D11 Legacy-to-Cloud migration/refactor map
D12 Tool policy, side-effect and recovery registry
D13 Client/operator UX state contract
D14 Development readiness and PostgreSQL test strategy
~~~

Implementation should follow these contracts rather than recreating architecture ad hoc.

Design change control:
- [Architecture Decision Records](Documentation/Design/Decisions/README.md)
- [Development baseline records](Documentation/Design/Baselines/README.md)

---

## Development Programme

Cloud v1 is implemented in ordered slices:

~~~text
C0  Contract package / migration skeleton
C1  PostgreSQL persistent Control Plane
C2  Remote identity / API / SSE
C3  Run / queue / workflow convergence
C4  Agent / Team / Context runtime
C5  Security / Git / secrets / approvals
C6  Durable execution / recovery
C7  Compute fabric / RunPod / vLLM
C8  Economics / budgets / operational UX
C9  Full Cloud acceptance
~~~

Development begins with **C0**, not GPU provisioning.

See [D9 — Development Programme](Documentation/Design/D9-development-programme-migration-and-acceptance.md).

---

## Current Local Installation

Requirements:

- Python 3.11+
- Git
- Linux / WSL2
- Ollama for the current local inference path
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

The current Workstation is intentionally loopback-only. Do not expose it publicly by changing its bind address. Remote access is implemented through the Cloud design.

---

## Validation

Run the current Python test suite:

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

See [docs/current/release/final-acceptance.md](docs/current/release/final-acceptance.md) for the accepted local baseline.

---

## Repository Structure

~~~text
Documentation/
├── Analysis/       accepted Cloud architecture research
└── Design/         Cloud v1 implementation specification

src/reverend/
├── controlplane/
├── development/
├── intelligence/
├── observability/
├── policy/
├── research/
├── runtime/
├── specialists/
├── ui/
└── workstation/

tests/
benchmarks/
config/
deploy/
~~~

Cloud Development should extend the existing subsystem authority rather than create duplicate control planes.

---

## Development Discipline

main remains the stable integration branch.

Major changes should follow:

~~~text
accepted main
→ narrow branch/worktree
→ implement one design slice
→ deterministic tests
→ targeted validation
→ relevant full validation
→ review
→ merge
~~~

Paid provider/model validation is introduced only when the corresponding Development phase requires it.

---

## Project Direction

Reverend is evolving from a local AI workstation into a private shared autonomous engineering platform with:

- research and evidence;
- persistent project intelligence;
- specialist Agents and bounded Teams;
- repository-scale implementation;
- deterministic testing and repair;
- independent assurance;
- durable long-running execution;
- elastic model compute;
- simulation and asset-generation extensibility;
- auditable cost and human authority.

The goal is not to maximize model size or Agent count.

The goal is to maximize **verified engineering value** while keeping authority, security, durability and cost explicit.


---

## Cloud Product Interaction

The accepted Cloud product is a **cloud-only shared autonomous engineering service**.

Developer devices are thin clients: they render the browser/desktop GUI, submit chat/commands/uploads and display server results. Production Cloud does not rely on laptop inference, embeddings, builds, sandboxes, indexing, media generation, scheduling, authoritative state or disaster-recovery replicas.

The primary interaction model is:

~~~text
You / teammate
      ↓
ChatGPT-style Reverend client
      ↓
accepted BuildSpecification
      ↓
single globally active Run
      ↓
autonomous implementation / test / repair / verification
      ↓
Artifacts + repository changes
~~~

External reasoning tools such as ChatGPT may be used manually to create high-quality specifications, but Reverend Cloud v1 has **no automatic frontier-model API dependency**.

Two developers share the system while one top-level Run remains active globally. A higher-priority queued project uses safe checkpointed pre-emption: current work is made durable, the Run yields to `RESUME_QUEUED`, the higher-priority Run executes, and the interrupted Run can later resume.

### Developer Asset Studio

Cloud v1 also includes a developer-oriented Media/Asset Fabric:

- raster image generation and reference editing through an eligible media model profile;
- asset variants, background removal, resize/crop and web optimization;
- SVG/icon generation;
- deterministic charts and diagrams;
- browser-render/screenshot feedback for real UI implementation.

Audio, video and generative 3D are intentionally outside Cloud v1.

See:

- [D15 — Conversation, Specification & Priority Handoff](Documentation/Design/D15-conversation-specification-and-priority-handoff.md)
- [D16 — Developer Media & Asset Studio](Documentation/Design/D16-developer-media-and-asset-studio.md)
- [ADR-001](Documentation/Design/Decisions/ADR-001-cloud-only-client-and-cloud-recovery.md)
- [ADR-002](Documentation/Design/Decisions/ADR-002-conversation-specification-and-priority-handoff.md)
- [ADR-003](Documentation/Design/Decisions/ADR-003-developer-media-asset-fabric.md)


### Cold-start model policy

Cloud v1 treats model weights as **reconstructible worker state**, not persistent authority.

Default cold start:

~~~text
provision disposable worker
→ boot pinned Reverend runtime image
→ hydrate exact pinned model revision from approved upstream repository
→ verify model artifact manifest
→ load runtime
→ smoke-test
→ READY
~~~

Paid persistent model storage is disabled by default. Reverend measures hydration time/cost and may later recommend persistent caching only when repeated cold starts make it economically superior.

Developer laptops are not required model sources. Personal local copies may be kept for archival convenience, but normal Cloud startup never waits for a user's Wi-Fi upload.

See [D17 — Model Hydration, Cold Start & Cache Economics](Documentation/Design/D17-model-hydration-cold-start-and-cache-economics.md) and [ADR-004](Documentation/Design/Decisions/ADR-004-ephemeral-model-hydration-and-cache-economics.md).
