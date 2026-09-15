# Reverend

**Reverend** is a local-first AI engineering and knowledge workstation evolving into a private, cloud-hosted autonomous development platform.

Its long-term goal is to provide **Codex-class and eventually beyond-Codex autonomous software engineering** through specialist agents, repository intelligence, durable execution, verification, memory, research, tool use, and dynamically allocated compute.

Reverend is not intended to be a generic chatbot.

The core execution model is:

```text
objective
→ understand
→ plan
→ decompose
→ execute
→ inspect
→ test
→ repair
→ independently verify
→ deliver reviewable artifacts
```

The project is currently transitioning from a validated single-machine system into a two-user cloud architecture with centrally hosted AI compute.

---

# Project Status

## Current Stable Baseline

**Release line:** Reverend `0.4.0`

The current `main` branch represents the stabilized local-first implementation.

The retained M6–M18 acceptance programme validated:

- **619 passing tests**
- live local inference
- `qwen3-coder:30b` STRONG_CODE residency
- FAST_GENERAL inference
- DEEP_REASON inference
- local SearXNG research
- searched-image acquisition
- sandbox validation
- autonomous development workflows
- isolated Git worktrees
- deterministic verification
- independent verification
- persistent engineering memory
- repository intelligence
- privacy modes
- browser Workstation
- artifact rendering
- evidence/provenance handling

The accepted architecture remains the foundation for the cloud programme.

## Current Cloud Programme

Reverend is now entering the:

> **Reverend Cloud Analysis Phase**

The objective is to redesign the infrastructure around:

- two authenticated developers;
- thin frontend/CLI clients;
- one authoritative Reverend control plane;
- centrally hosted models;
- cloud GPU compute;
- dynamic specialist-agent teams;
- durable long-running execution;
- pause/resume and crash recovery;
- resource-aware scheduling;
- per-user cloud-cost attribution;
- eventual elastic GPU provisioning.

The cloud architecture is **under analysis**.

Planned cloud features described in this README must not be interpreted as already implemented.

---

# Product Goal

The development subsystem is intended to automate increasingly large portions of software engineering.

The target experience is approximately:

```text
Human
  │
  │ objective + constraints
  ▼
Reverend
  │
  ├── understand repository
  ├── investigate requirements
  ├── research when required
  ├── design architecture
  ├── plan implementation
  ├── modify multiple files
  ├── use terminal/build tools
  ├── run tests
  ├── debug failures
  ├── repair implementation
  ├── perform security/performance review
  ├── independently verify results
  └── produce a reviewable branch / artifact set
```

Reverend should eventually support complete project construction rather than only isolated code completion.

Target workloads include:

- Python
- C++
- CUDA
- frontend/web systems
- APIs and backend services
- data systems
- AI/ML projects
- scientific software
- repository migrations
- testing
- deployment automation
- research-driven engineering
- simulation workflows
- asset-generation workflows

---

# Design Philosophy

Reverend follows several core principles.

## Models are resources, not agents

A specialist role must not be permanently tied to one model.

Incorrect:

```text
Architect = Model A
Developer = Model B
Verifier = Model C
```

Target:

```text
Agent Role
    ↓
Capability Requirements
    ↓
Model Router
    ↓
Compute Scheduler
    ↓
Best eligible model/runtime
```

Models can therefore evolve without redesigning Reverend.

---

## Agents are roles, not permanent processes

Reverend's specialist architecture describes capabilities such as:

```text
Researcher
Product Strategist
Systems Architect
Developer
Tester
Security Reviewer
Performance Specialist
Verifier
Failure Investigator
Deployment Specialist
```

A future runtime may instantiate zero, one, or several instances of each role depending on the task.

A simple problem may use:

```text
Developer
→ Verifier
```

A difficult problem may use:

```text
Engineering Lead
├── Repository Analyst
├── Systems Architect
├── Developer A
├── Developer B
└── Test Specialist

        ↓

Independent Assurance
├── Verifier
├── Security Reviewer
└── Failure Investigator
```

More hardware should enable **selective parallelism**, not uncontrolled agent spawning.

---

## Deterministic evidence outranks model confidence

A model declaring that work is correct does not make it correct.

Where applicable, Reverend prefers:

```text
tests
builds
linters
static analysis
benchmarks
simulations
repository state
external evidence
```

over subjective model confidence.

---

## Generated changes remain isolated

Development work occurs in isolated worktrees/workspaces.

The primary repository checkout is not silently modified.

AI-generated changes must pass required verification before they can become integration candidates.

Automatic merging into protected branches is not part of the current architecture.

---

## Durable state must not depend on live compute

The future cloud architecture follows the principle:

> **Compute is replaceable. Run state is durable.**

Reverend must not depend on preserving:

- Python process memory
- GPU VRAM
- CUDA state
- model KV cache
- open sockets
- temporary containers

to recover a development run.

---

# Current Architecture

The current stable system can be summarized as:

```text
USER
  │
  ▼
WORKSTATION / CLI
  │
  ▼
OBJECTIVE INTAKE
  │
  ▼
EXECUTIVE ORCHESTRATION
  │
  ├── task planning
  ├── workflow state
  ├── policies
  ├── resource control
  └── specialist routing
  │
  ▼
CONTEXT / MEMORY
  │
  ├── repository intelligence
  ├── project memory
  ├── engineering memory
  ├── evidence
  └── knowledge retrieval
  │
  ▼
MODEL ROUTING
  │
  ├── fast/general
  ├── coding
  ├── reasoning
  ├── critic
  └── embedding
  │
  ▼
TOOLS / WORKSPACE
  │
  ├── filesystem
  ├── Git
  ├── shell
  ├── build
  ├── tests
  ├── research
  └── isolated worktrees
  │
  ▼
VERIFICATION
  │
  ├── acceptance
  ├── tests
  ├── regression
  ├── static analysis
  ├── security
  └── independent verification
  │
  ▼
DELIVERY
```

---

# Current Model Runtime

The current accepted logical model roles are:

| Role | Current model | Purpose |
|---|---|---|
| FAST_GENERAL | `qwen3.5:4b` | general low-cost inference |
| ROUTER | `qwen3.5:4b` | request classification/routing |
| FAST_CODE | `qwen2.5-coder:7b` | inexpensive code work |
| STRONG_CODE | `qwen3-coder:30b` | repository-scale coding |
| DEEP_REASON | `deepseek-r1:8b` | difficult reasoning |
| CRITIC | `deepseek-r1:8b` | independent critique |
| EMBED | `bge-m3:latest` | semantic retrieval |

These are **current runtime defaults**, not the final Reverend Cloud model fleet.

The Cloud Analysis Phase will research and benchmark replacement or additional models before future hardware is selected.

---

# Current Compute Model

The accepted implementation currently targets Linux / WSL2 and local inference through Ollama.

Reverend already contains foundations for:

- model profiles
- model health
- ResourceRequests
- ResourceLeases
- GPU serialization
- RAM/VRAM accounting
- residency management
- hardware inspection
- scheduling
- queue wait metrics

The current architecture intentionally serializes heavyweight inference unless hardware evidence demonstrates safe concurrency.

---

# Reverend Cloud Target Architecture

The current design direction separates persistent control infrastructure from expensive GPU compute.

```text
          CLIENTS

    Developer A        Developer B
        │                  │
        ├──── GUI / CLI ───┤
        │                  │
        └──── HTTPS ───────┘
                │
                ▼

       REVEREND CONTROL PLANE

     Authentication / Identity
                │
          Project / Run API
                │
          Executive Runtime
                │
       Workflow / Task Fabric
                │
      Context / Memory Fabric
                │
       Agent / Team Runtime
                │
         Model Router
                │
        Compute Governor
                │
        ┌───────┴─────────┐
        ▼                 ▼

   CONTROL COMPUTE      GPU COMPUTE
   persistent/cheap     elastic/expensive

   state                LLM inference
   DB                   vision
   Git                  assets
   queue                simulation
   artifacts
   orchestration
   accounting
```

The precise deployment topology remains under analysis.

---

# Two-User Operating Model

The initial cloud deployment targets:

```text
one private Reverend installation
two authenticated developers
one authoritative control plane
one active top-level run initially
```

Each run has immutable ownership.

Conceptually:

```text
Run
├── run_id
├── owner_user_id
├── project_id
├── objective
├── workflow_state
├── resource budget
├── workspace
├── Git identity
└── checkpoint history
```

The user viewing a run is not necessarily the user who owns the run.

Run ownership determines:

- Git identity
- user-scoped credentials
- approvals where policy requires owner approval
- compute-cost attribution
- audit attribution

---

# Frontend / Backend Boundary

## Client responsibilities

The frontend/CLI may provide:

- authentication UX
- conversation/run interface
- project selection
- run creation
- run queue
- live execution activity
- agent/team visualization
- pause/resume controls
- approval UI
- artifact inspection
- compute status
- model status
- resource usage
- cost dashboards
- settings

The client does **not** own authoritative execution state.

Disconnecting the client must not terminate a running Reverend job.

## Backend responsibilities

The Reverend backend owns:

- authentication authority
- users/projects/runs
- orchestration
- workflow DAG
- agent execution
- resource allocation
- context compilation
- memory
- tools
- model routing
- compute routing
- workspaces
- Git
- secrets
- verification
- checkpointing
- recovery
- billing/accounting
- infrastructure lifecycle

SSH remains an administrative interface, not the Reverend application protocol.

---

# Future Specialist Organisation

Reverend currently organizes intelligence conceptually into several major domains.

## Discovery / Product

Potential specialist roles include:

- Research Intelligence
- Stakeholder Intelligence
- Product Strategy
- UX / Accessibility Intelligence

## Engineering

Potential roles include:

- Systems Architect
- Repository Analyst
- Coding Intelligence
- Test Engineering
- Integration
- Dependency / Migration Intelligence
- Performance Intelligence

## Assurance

Potential roles include:

- Independent Verification
- Security Review
- Performance Validation
- Adversarial Critic
- Failure Investigation

## Capability / Production

Future capability workers may include:

- image generation
- 3D / Blender workflows
- ComfyUI
- audio
- simulation
- CFD / FEA workloads
- isolated testbeds
- deployment automation
- external applications
- additional tool bridges

These are logical capabilities.

They do not imply that every run launches every specialist.

---

# Agent Teams and Swarms

The future runtime is expected to support dynamically formed teams.

Conceptually:

```text
AgentTeam
├── objective
├── leader
├── members
├── task DAG
├── artifact namespace
├── context policy
├── compute budget
├── concurrency budget
├── verification policy
└── termination policy
```

Example research team:

```text
Research Lead
├── Official Documentation Researcher
├── Academic Researcher
├── Ecosystem Researcher
└── Competitor Researcher

        ↓

Evidence Synthesis

        ↓

Independent Critic
```

Example engineering team:

```text
Engineering Lead
├── Repository Analyst
├── Architect
├── Developer
└── Test Specialist

        ↓

Integration

        ↓

Independent Verification
```

Swarm execution must remain bounded.

Reverend should instantiate the **minimum sufficient team** rather than maximizing the number of agents.

---

# Context and Memory Architecture

Scaling the number of agents must not mean replicating the entire project context into every model invocation.

The target model separates:

```text
AUTHORITATIVE PROJECT STATE
        │
        ├── repository
        ├── requirements
        ├── verified decisions
        └── trusted facts

SHARED ARTIFACT SPACE
        │
        ├── plans
        ├── evidence packs
        ├── patches
        ├── reports
        └── verification results

AGENT WORKING CONTEXT
        │
        └── task-specific bounded context

EXPERIENCE MEMORY
        │
        ├── historical successes
        ├── failures
        ├── benchmarks
        └── strategies
```

Agents should primarily communicate through typed artifacts rather than unbounded shared conversations.

Examples include:

```text
ResearchEvidencePack
ArchitectureDecision
ImplementationPlan
PatchArtifact
TestReport
PerformanceReport
SecurityReport
FailureReport
VerificationReport
```

---

# Scheduling and Resource Architecture

Future Reverend scheduling separates:

```text
WORKFLOW SCHEDULING
```

from:

```text
COMPUTE SCHEDULING
```

The Workflow Scheduler determines which tasks are logically executable.

The Compute Scheduler determines which of those tasks can physically execute.

Example:

```text
Research A      CPU / network
Research B      CPU / network
Code indexing   CPU
Build           CPU
Test suite      CPU
Developer       GPU
Verifier        waiting for GPU
```

Logical agent concurrency therefore does not require equivalent model concurrency.

---

# Resource Hierarchy

The future resource model is expected to support hierarchical budgets:

```text
Run Budget
    ↓
Team Budget
    ↓
Task Budget
    ↓
Agent Budget
    ↓
Model / Tool Lease
```

A resource request may include:

```text
CPU
RAM
GPU
VRAM
context requirement
model capability
expected runtime
maximum duration
priority
maximum cost
```

This architecture will later support both resource optimization and per-user billing.

---

# Model Fabric

The target Model Fabric will select models by capability rather than hardcoded role/model relationships.

Conceptually:

```text
Agent
  │
  ▼
ModelRequirement
  │
  ├── coding quality
  ├── reasoning quality
  ├── context requirement
  ├── vision requirement
  ├── tool calling
  ├── latency
  ├── cost ceiling
  └── trust policy
  │
  ▼
Model Router
  │
  ▼
Provider / Runtime
```

Potential runtime technologies under analysis include:

- Ollama
- vLLM
- SGLang
- other self-hosted inference runtimes where justified

No final Reverend Cloud model/runtime selection has been frozen.

---

# Compute Fabric

The future Compute Fabric should treat machines as interchangeable nodes.

```text
ComputeNode
├── node_id
├── provider
├── CPU
├── RAM
├── GPU
├── VRAM
├── storage
├── runtimes
├── health
├── current leases
└── cost profile
```

Possible future node types include:

```text
persistent control node
48 GB GPU worker
80 GB GPU worker
96 GB GPU worker
141 GB GPU worker
asset-generation worker
simulation worker
```

Actual hardware will be selected only after model research and benchmarking.

---

# Durable Execution

Long-running development must survive:

- browser disconnects
- worker crashes
- backend restarts
- GPU termination
- planned pause
- cloud shutdown
- compute replacement

The target run lifecycle includes states such as:

```text
QUEUED
STARTING
RUNNING

PAUSE_REQUESTED
PAUSING
PAUSED

RESUME_QUEUED
RESUMING

AWAITING_APPROVAL

RECOVERING
RECOVERY_BLOCKED

COMPLETED
FAILED
CANCELLED
```

---

# Checkpointing

Checkpoints capture logical application state, not machine memory.

A future checkpoint may reference:

```text
run
objective
task DAG
completed tasks
pending tasks
agent state
plan
context references
memory references
workspace
repository
branch
HEAD
uncommitted changes
artifacts
evidence
decisions
remaining budgets
retries
pending approvals
last completed action
```

The system should be capable of reconstructing a run on fresh compute.

---

# Action Journal

External side effects require stronger durability than ordinary model reasoning.

The planned action-journal model is:

```text
persist intent
    ↓
STARTED
    ↓
perform action
    ↓
observe result
    ↓
persist result
    ↓
COMPLETED
```

Possible action states include:

```text
PLANNED
STARTED
COMPLETED
FAILED
INTERRUPTED
UNKNOWN
```

After a crash, unknown actions must be reconciled before blind retries.

Examples:

```text
git push
→ inspect remote before retry

file write
→ inspect workspace

tests
→ rerun

LLM inference
→ restart

deployment
→ verify target environment
```

---

# Security Model

Reverend is designed around explicit authority boundaries.

Important principles include:

- authenticated users
- immutable run ownership
- project-scoped authority
- isolated workspaces
- explicit tool permissions
- server-side secrets
- encrypted persistent state
- restricted model context
- safe network policies
- non-root agent execution
- explicit approvals for dangerous operations
- no credentials returned to the browser
- no infrastructure credentials exposed to models
- deterministic verification before integration

---

# Git and GitHub Identity

Each Reverend user may have their own GitHub authority.

A run's GitHub identity is derived from:

```text
run
 ↓
run.owner
 ↓
owner GitHub identity
```

not whichever user is currently viewing the UI.

Expected policy direction:

| Operation | Default target policy |
|---|---|
| commit to isolated run branch | automatic |
| push isolated run branch | automatic |
| create pull request | automatic |
| push directly to protected branch | approval |
| merge | approval |
| force push | approval |
| delete repository | prohibited |

Exact policies remain subject to the Cloud Analysis Phase.

---

# Cloud Cost and Accounting

The target cloud architecture must be affordable for a two-developer project.

Reverend should eventually record resource usage by:

```text
user_id
project_id
run_id
agent_id
compute node
GPU model
model
start time
end time
GPU seconds
CPU time
storage
estimated cost
actual cost
```

Costs will be divided conceptually into:

## Shared fixed costs

Examples:

- control-plane hosting
- domain
- shared durable storage
- backups

## Variable costs

Examples:

- GPU runtime
- project-specific cloud storage
- paid external APIs where enabled

Variable compute costs should be attributable to the owner of the run that consumed them.

All user-facing financial analysis for the initial deployment will be performed in **GBP (£)**.

---

# Benchmarking Philosophy

Public model benchmarks are useful for candidate selection but do not determine Reverend's final model fleet.

The final decision should use Reverend-specific engineering workloads.

Evaluation should include:

```text
task completion
build success
test success
repair rounds
human intervention
wall-clock time
context usage
GPU time
cost
```

A core economic metric is expected to be:

```text
£ per verified successful engineering task
```

rather than only tokens per second or benchmark score.

Candidate models may be evaluated on complete project-building tasks.

---

# Reverend Cloud Analysis Programme

Cloud implementation does not begin until the major architectural questions have been investigated.

## A0 — Baseline & Requirements Freeze

Audit current Reverend and freeze:

- terminology
- accepted behaviour
- architectural invariants
- current limitations
- migration scope

---

## A1 — Codex-Class Product Definition

Define measurable autonomous development requirements for Reverend to reach and eventually exceed Codex-style engineering workflows.

---

## A2 — Client / Server & Two-User Architecture

Define:

- frontend/backend boundary
- authenticated identities
- projects
- run ownership
- queueing
- approvals
- API contracts
- live event transport
- remote access

---

## A3 — Agent Cognitive Runtime

Define:

- `AgentSpec`
- `AgentInstance`
- role catalogue
- permissions
- context rules
- budgets
- completion
- escalation
- model-independent specialist execution

---

## A4 — Agent Teams, Swarms & Parallelism

Define:

- `AgentTeam`
- team leadership
- task decomposition
- dynamic specialist creation
- bounded subagents
- logical parallelism
- disagreement handling
- minimum-sufficient-team selection

---

## A5 — Context, Memory & Agent Communication

Define:

- authoritative state
- project/run memory
- agent working context
- shared artifacts
- experience memory
- compression
- retrieval
- provenance
- typed communication

---

## A6 — Scheduling, Compute & Resource Architecture

Define:

- Workflow Scheduler
- Compute Scheduler
- ComputeNode
- ResourceRequest
- ResourceLease
- CPU/RAM/GPU/VRAM allocation
- concurrency
- pre-emption
- hierarchical budgets
- resource recovery

---

## A7 — Durable Execution, Pause/Resume & Recovery

Define:

- run lifecycle
- safe interruption
- checkpoints
- action journal
- recovery
- pause/resume
- crash reconciliation
- machine-independent continuation

---

## A8 — Security, Identity, Git & Secrets

Define:

- authentication
- authorization
- run ownership
- GitHub identity
- secrets
- worker authentication
- model trust
- approvals
- emergency control

---

## A9 — Model Requirements & Model Research

Determine requirements and candidates for:

- router
- researchers
- research synthesis
- architect
- fast developer
- primary developer
- critic/verifier
- failure investigator
- vision
- embedding
- reranking
- asset generation
- maximum-quality escalation

Research will use current model sources and independent benchmark evidence.

---

## A10 — Hardware, Runtime & Cloud Topology

Map candidate models onto:

- GPU VRAM
- system RAM
- CPU
- context
- runtime
- quantisation
- storage
- network

Evaluate cloud GPU classes and inference runtimes.

---

## A11 — Economics, Billing & Architecture Selection

Calculate:

- GPU cost
- persistent infrastructure
- storage
- backup
- idle overhead
- per-user attribution
- budget limits
- cost per successful task

Select the preferred Reverend Cloud v1 configuration.

---

## A12 — Cloud Architecture Acceptance

Perform the final cross-system review.

The architecture is accepted only when frontend and backend can be implemented independently against stable contracts and all major subsystems agree.

A12 produces the implementation programme.

---

# What Is Not Yet Implemented

The following should currently be treated as **target architecture**, not accepted production functionality:

- full remote cloud inference
- elastic RunPod provisioning
- dynamic multi-agent swarms
- cloud GPU fleet routing
- remote worker registration
- hierarchical cloud budgets
- per-user GPU billing
- durable cross-machine pause/resume
- distributed Action Journal recovery
- PostgreSQL-backed cloud control plane
- cloud secrets service
- client/server production authentication
- cloud cost dashboards
- multiple GPU-node scheduling
- Codex-class end-to-end project automation
- automatic asset-generation scheduling

Do not implement these opportunistically outside the analysis/implementation programme without an architecture decision.

---

# Current Installation

The stable Reverend implementation currently targets Linux / WSL2.

Requirements:

- Python 3.11+
- Git
- Ollama
- Linux sandbox capabilities
- sufficient RAM/VRAM for selected local models

Clone and install:

```bash
git clone <repository-url>
cd reverend

python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -e '.[dev]'
```

Optional reference support:

```bash
.venv/bin/pip install -e '.[dev,reference]'
```

Check the installed version:

```bash
.venv/bin/reverend --version
```

Expected current release line:

```text
reverend 0.4.0
```

---

# Runtime Configuration

Important current settings include:

```text
AI_DATA_ROOT
REVEREND_RUNTIME_CONFIG
REVEREND_STATE_KEY_FILE
OLLAMA_HOST
QDRANT_URL
QDRANT_COLLECTION
```

Example:

```json
{
  "data_root": "/home/you/.local/share/reverend",
  "ollama_host": "http://127.0.0.1:11434"
}
```

Credentials must not be committed to the repository.

---

# Starting the Current Workstation

```bash
.venv/bin/reverend gui
```

Default:

```text
http://127.0.0.1:8765
```

The current stable Workstation remains loopback-oriented.

It should not simply be exposed publicly by changing the bind address.

Remote/cloud access will be introduced through the Cloud architecture programme.

---

# Current Development Workflow

Trusted development currently follows approximately:

```text
request
→ trust check
→ isolated Git worktree
→ repository analysis
→ structured plan
→ bounded implementation
→ deterministic verification
→ bounded repair
→ independent verification
→ result
```

Lower-level CLI access remains available:

```bash
.venv/bin/reverend dev implement \
  --project /path/to/repository \
  --request 'Implement the requested change.' \
  --acceptance 'Relevant tests pass.' \
  --json
```

Generated changes should be reviewed before integration.

---

# Research and Evidence

Reverend separates evidence into classes such as:

```text
PERSONAL
PROJECT
REFERENCE
FRESH
```

Retrieved public content is treated as data, not as trusted instructions.

Network usage remains policy controlled.

The self-hosted SearXNG path is available for current public-web research.

---

# Privacy

Current Workstation modes include:

```text
Normal
Private
Ephemeral
```

Persistent Workstation data can use authenticated encryption.

Loss of the state encryption key intentionally makes protected state unrecoverable.

Backups must therefore include both data and appropriately protected recovery-key material.

---

# Validation

Run the full Python suite with:

```bash
.venv/bin/python -m pytest -q
```

Current final validation:

```bash
.venv/bin/python -m reverend.benchmarks.final_validation \
  --repository . \
  --report-root benchmarks/results/vnext/final-validation
```

Portable-only validation:

```bash
.venv/bin/python -m reverend.benchmarks.final_validation \
  --repository . \
  --skip-live \
  --report-root benchmarks/results/vnext/final-validation
```

Portable validation does not certify real model/search/runtime behaviour.

---

# Repository Structure

Important areas currently include:

```text
benchmarks/
config/
deploy/
docs/
fixtures/
scripts/
src/reverend/
tests/
```

Major runtime areas include:

```text
src/reverend/controlplane/
src/reverend/development/
src/reverend/intelligence/
src/reverend/observability/
src/reverend/policy/
src/reverend/research/
src/reverend/runtime/
src/reverend/specialists/
src/reverend/ui/
src/reverend/workstation/
```

Cloud work should extend existing subsystem authority rather than creating duplicate control planes.

---

# Development Discipline

`main` is the canonical stable integration branch.

Major work should:

```text
branch from accepted main
→ implement narrow scope
→ add deterministic tests
→ run targeted validation
→ run full portable validation
→ perform live validation when required
→ review
→ integrate
```

Do not silently weaken existing security, verification or authority boundaries while implementing cloud functionality.

---

# Immediate Next Step

The project is currently in the **Analysis Phase**.

Implementation should not begin with GPU provisioning or model installation.

The immediate sequence is:

```text
A0
Baseline & Requirements Freeze

↓
A1
Codex-Class Product Definition

↓
A2–A8
Runtime / client-server / agents / memory /
scheduling / recovery / security architecture

↓
A9
Model Research

↓
A10
Hardware + Runtime + Cloud Selection

↓
A11
Economics + Billing

↓
A12
Architecture Acceptance

↓
Implementation Programme
```

The first active architectural task is:

> **A0 — establish the exact current Reverend baseline, accepted invariants, terminology, migration scope and known limitations before redesigning the runtime.**

---

# Long-Term Direction

Reverend is intended to evolve from:

```text
single-user
local workstation
fixed model roles
single-machine compute
```

into:

```text
private shared AI engineering platform
        │
        ├── specialist intelligence
        ├── dynamic agent teams
        ├── persistent engineering memory
        ├── repository understanding
        ├── research
        ├── autonomous implementation
        ├── independent assurance
        ├── durable execution
        ├── elastic model compute
        ├── simulation
        ├── asset generation
        └── deployment automation
```

while retaining the principles that made the original system reliable:

> **bounded autonomy, explicit authority, durable evidence, isolated execution, deterministic verification, measurable performance, and human control over consequential integration.**
