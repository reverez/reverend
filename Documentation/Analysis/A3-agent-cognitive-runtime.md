# A3 — Agent Cognitive Runtime

> **Programme:** Reverend Cloud Analysis  
> **Milestone:** A3  
> **Status:** ACCEPTED  
> **Owner:** Backend / systems track  
> **Document purpose:** Define the canonical semantics of one Reverend Agent so that later Team, context, scheduler, model, and hardware architecture can be built on a stable cognitive primitive.  
> **Important:** This report defines semantics, not the final Python classes. Exact schemas and module placement belong to the Design Phase.

---

## 1. Executive Definition

A Reverend Agent is:

> **A bounded, policy-governed runtime instantiation of a versioned Specialist methodology, assigned to one explicit Control Plane Task, operating over selected context and mediated tools, using dynamically selected intelligence and compute, and producing typed artifacts or structured control signals.**

This definition intentionally separates:

- the cognitive methodology;
- the logical work;
- the model;
- the physical machine.

The architecture must never collapse these into one object.

---

## 2. Canonical Terminology

```text
SPECIALIST
Reusable, versioned definition of a cognitive expert / methodology.

AGENT
One runtime instantiation of a Specialist assigned to a Task.

TASK
Authoritative unit of work in the Control Plane DAG.

JOB
One execution attempt for the Task/Agent assignment.

EXECUTOR
Runtime mechanism that performs the Job.

COMPUTE WORKER
Physical or virtual machine/process supplying compute.

MODEL
Replaceable intelligence resource used by the Agent.
```

Therefore:

```text
Agent ≠ model
Agent ≠ Task
Agent ≠ Job
Agent ≠ GPU worker
```

Example:

```text
Task:
"Design authentication architecture"
        ↓
SpecialistSpec:
systems_architect@v3
        ↓
AgentInstance:
ag_781
        ↓
Job:
attempt #2
        ↓
Model Router:
resolves eligible reasoning model
        ↓
Compute Scheduler:
resolves worker/node
```

---

## 3. Current Reverend Foundations

The current repository already contains several useful ideas that A3 generalizes rather than discards.

Relevant current concepts include:

- `WorkerTask`;
- `WorkerExecution`;
- bounded worker budgets;
- fixed worker roles;
- `SpecialistSpec`;
- `SpecialistRegistry`;
- methodology binding;
- context policies;
- tool policies;
- typed artifact inputs/outputs;
- independent verifier restriction;
- central orchestration.

Current worker philosophy already includes important rules:

```text
workers exchange validated state
workers do not recursively delegate
orchestrator controls budgets
verification is separately scheduled
```

These principles survive.

---

## 4. SpecialistSpec Is the Reusable Definition

The `SpecialistSpec` concept becomes the canonical reusable cognitive contract.

Future semantics should conceptually include:

```text
SpecialistSpec
├── specialist_id
├── version
├── name
├── role_family
│
├── methodology_ref
├── model_requirements
├── context_requirements
├── tool_capability_ceiling
├── authority_ceiling
│
├── accepted_input_artifacts
├── produced_output_artifacts
│
├── default_budget_policy
├── completion_contract
├── verification_requirements
├── escalation_policy
├── risk_class
└── metadata
```

The exact dataclass/Pydantic/database representation is intentionally deferred.

---

## 5. Specialists Are Methodologies, Not Personas

Bad architecture:

```text
"You are a world-class systems architect.
Think carefully."
```

Accepted architecture:

```text
systems_architecture_v3

1. establish current system
2. derive requirements
3. freeze invariants
4. identify authority/state ownership
5. enumerate alternatives
6. identify coupling
7. model failure cases
8. evaluate migration
9. analyze trade-offs
10. produce decision artifact
```

Similarly:

### Security methodology

```text
assets
→ actors
→ trust boundaries
→ attack surfaces
→ abuse paths
→ severity
→ mitigation
```

### Failure investigation methodology

```text
symptom
→ reproduce
→ isolate
→ competing hypotheses
→ evidence
→ root cause
→ corrective action
```

### A3 decision

Specialisation comes primarily from:

- methodology;
- context;
- tools;
- authority;
- success conditions;
- artifact contracts;

not pseudo-human personality prompting.

---

## 6. Methodology Versioning

Specialist methodologies must be independently versioned:

```text
systems_architecture_v1
systems_architecture_v2
systems_architecture_v3
```

This allows Reverend to improve its own engineering harness independently from model releases.

Benchmark example:

```text
same model
same Task
same tools
methodology v3 vs v4
```

This measures system-level intelligence rather than model intelligence.

---

## 7. AgentInstance

A `SpecialistSpec` is reusable.

An `AgentInstance` represents one concrete assignment.

Conceptually:

```text
AgentInstance
├── agent_id
├── specialist_id
├── specialist_version
│
├── project_id
├── run_id
├── task_id
├── team_id?
│
├── mission
├── constraints
├── acceptance_refs
│
├── effective_authority
├── budget_envelope
├── context_scope
└── creation_metadata
```

An AgentInstance is **not** another workflow database.

Its execution remains subordinate to the Control Plane.

---

## 8. Task → Agent → Job Relationship

Canonical hierarchy:

```text
Workflow / Run
      ↓
Task
      ↓ assigned
AgentInstance
      ↓ attempt
Job
```

Retry example:

```text
Architect Agent
   ├── Job 1 → runtime failure
   ├── Job 2 → weak-model failure
   └── Job 3 → stronger model → success
```

The logical Agent assignment can remain stable while Job attempts change.

---

## 9. Agent Lifecycle Does Not Become a Competing Authority

A0 prohibits duplicate authorities.

Agent-facing status can exist:

```text
ASSIGNED
WAITING
RUNNING
BLOCKED
COMPLETED
FAILED
CANCELLED
```

but should be derived from authoritative Task/Job state.

The Control Plane owns truth.

---

## 10. Model Independence

The current direct relationship:

```text
SpecialistSpec
→ ModelRole
```

is too rigid for Cloud Reverend.

The future semantic relationship is:

```text
SpecialistSpec
→ ModelRequirement
```

Example:

```text
Systems Architect requires:
  reasoning = high
  coding = medium
  structured_output = strong
  context >= task requirement
  tool_calling = optional
  vision = false
  trust >= required classification
  latency = non_interactive acceptable
```

The Specialist does not say:

```text
use model X forever
```

---

## 11. Model Resolution Per Job

Future flow:

```text
AgentInstance
   ↓
ModelRequirement
   ↓
Model Router
   ↓
eligible model candidates
   ↓
quality / cost / availability / trust
   ↓
resolved model for this Job
```

The Job records the actual model/runtime for provenance.

This cleanly separates:

```text
logical intelligence requirement
```

from:

```text
physical model implementation
```

---

## 12. Model Escalation Across Attempts

Example:

```text
Developer Agent
  Job 1
    ↓
  economical coder
    ↓
  verification failure
    ↓
  EscalationRequest
    ↓
  Job 2
    ↓
  stronger model
```

No new Agent identity is required.

This is essential for cost-aware routing.

---

## 13. Compute Independence

An Agent must never own:

```text
gpu = A100
```

Instead:

```text
Agent
 ↓
Job
 ↓
ModelRequirement
 ↓
resolved model
 ↓
ComputeRequirement
 ↓
Compute Scheduler
 ↓
ComputeNode
```

A3 therefore freezes:

> **Agent identity is independent of physical hardware identity.**

---

## 14. Authority Ceiling

A Specialist declares the maximum authority it could ever need.

Example:

```text
Developer maximum:
  repo.read
  repo.propose_edit
  test.request
  build.request
```

Effective authority is:

```text
Specialist ceiling
∩ Task policy
∩ Project policy
∩ User authority
∩ Environment policy
```

A prompt cannot elevate its own permissions.

---

## 15. Models Never Receive Infrastructure Authority

Models may propose:

```text
ToolRequest(
  capability="test.run",
  command="pytest ..."
)
```

but must not directly possess:

- cloud API keys;
- GitHub tokens;
- root shell;
- SSH keys;
- deployment credentials;
- secrets.

Canonical flow:

```text
MODEL
  ↓ proposes
AGENT RUNTIME
  ↓
POLICY / TOOL BROKER
  ├── allow → sandboxed executor
  └── deny  → structured denial
  ↓
ToolResult
```

---

## 16. Bounded Cognitive Loop

One Agent may need several reasoning/tool cycles.

```text
ContextEnvelope
     ↓
Inference
     ↓
Need tool?
 ├─ yes
 │   ↓
 │ ToolRequest
 │   ↓
 │ Policy / Tool Broker
 │   ↓
 │ ToolResult
 │   ↓
 │ Inference
 │
 └─ no
     ↓
Typed result
```

Terminal conditions include:

- completion;
- blocked;
- failure;
- budget exhaustion;
- approval required;
- cancellation.

---

## 17. Inner Loop vs Outer Loop

### Agent Runtime — inner loop

Responsible for:

- reasoning;
- requesting bounded tools;
- consuming observations;
- producing Task result.

### Executive Orchestrator — outer loop

Responsible for:

- creating Tasks;
- selecting Specialists;
- forming Teams;
- changing DAG topology;
- replanning;
- escalation;
- Run completion.

An Agent is not a recursive Executive Orchestrator.

---

## 18. Delegation Rule

An Agent may discover missing work:

```text
"I need current API behavior before implementation can continue."
```

It should emit:

```text
DependencyRequest
type: research
reason: external API behavior unknown
desired_output: EvidencePack
```

The Executive Orchestrator decides whether to:

- create a new Task;
- create/expand a Team;
- reject due to budget;
- request human input.

Agents do not freely spawn arbitrary subagents.

---

## 19. Context Is Supplied, Not Hoarded

Canonical flow:

```text
Task
+
Specialist ContextPolicy
+
Project State
+
upstream artifacts
+
Evidence
+
Memory
+
workspace/repository state
       ↓
Context Broker
       ↓
Context Compiler
       ↓
ContextEnvelope
       ↓
Agent
```

Agents receive a bounded view.

If more information is needed, they issue a structured `ContextRequest`.

A5 defines the detailed information architecture.

---

## 20. Typed Artifacts Are the Primary Communication Mechanism

Examples:

```text
ResearchEvidencePack
ProductDecisionPack
ArchitectureDecisionPack
RepositoryLocalization
ImplementationArtifact
TestPlan
TestReport
SecurityAssessment
PerformanceReport
FailureAnalysis
VerificationReport
```

Artifacts retain:

- schema;
- producer;
- parents;
- provenance;
- validation;
- content hash.

This is more reliable than passing Agent conversation transcripts between Specialists.

---

## 21. Structured Control Signals

Alongside domain artifacts, Agents produce compact control outcomes.

Examples:

```text
COMPLETE

BLOCKED:
  missing_context

BLOCKED:
  dependency_required

BLOCKED:
  approval_required

ESCALATION_REQUESTED

FAILED:
  malformed_output

FAILED:
  tool_failure
```

The Executive Orchestrator consumes these signals.

The Agent does not directly rewrite the project DAG.

---

## 22. Completion Contract

Every Specialist declares what “finished” means.

Example:

```text
Systems Architect completion:
- requirements addressed
- invariants explicit
- state ownership explicit
- alternatives considered
- failure semantics defined
- migration impact described
- artifact validates
```

A model reaching end-of-generation does not satisfy completion by itself.

---

## 23. Artifact Inputs and Outputs Are Contractual

A Specialist can declare:

```text
required inputs
optional inputs
accepted input artifact types
output artifact types
```

Example:

```text
Developer requires:
  ArchitectureDecisionPack
  AcceptanceContract
  RepositoryLocalization

Developer produces:
  ImplementationArtifact
  DevelopmentResult
```

Invalid handoffs should be rejected before expensive inference where possible.

---

## 24. Evidence-Aware Reasoning

A conclusion is not evidence merely because a Specialist generated it.

An architecture artifact may reference:

```text
EvidencePack #123
```

but remains generated analysis.

This preserves the evidence distinction frozen in A0/A5.

---

## 25. Independent Assurance

The current verifier restriction should be strengthened rather than removed.

An independent verifier should ideally have:

- no mutation authority over the implementation;
- a fresh Job;
- explicit acceptance criteria;
- subject artifacts as input;
- no private implementer scratch reasoning;
- an independent completion contract.

A9 later considers whether model-family diversity improves independence.

---

## 26. Private Reasoning Is Not Authoritative State

Do not persist hidden model reasoning as project truth.

Durable state should contain:

- decisions;
- evidence;
- artifacts;
- observations;
- tool outputs;
- test results;
- structured summaries;
- failures;
- measured metrics.

This improves privacy, reproducibility, and verifier independence.

---

## 27. Agent Budgets

Every Agent execution operates within explicit bounds.

Conceptual dimensions:

```text
max_model_calls
max_generated_tokens
max_context_tokens
max_tool_calls
max_wall_time
max_retries
max_compute_cost
max_dependency_requests
```

A6 defines the hierarchical resource model.

---

## 28. Budget Hierarchy

Agent budgets are delegated from larger scopes:

```text
Run Budget
   ↓
Team Budget
   ↓
Task Budget
   ↓
Agent Budget
   ↓
Job / model / tool budget
```

An Agent cannot spend resources that were not delegated to it.

---

## 29. Structured Escalation

Possible escalation reasons:

```text
model incapable
context insufficient
dependency missing
tool unavailable
verification rejected
repeated structured-output failure
risk exceeds authority
ambiguity requires human
```

An `EscalationRequest` should state:

- reason;
- supporting evidence;
- requested capability change;
- expected benefit.

The outer orchestrator decides.

---

## 30. Specialist Composition

Avoid hundreds of rigid hard-coded role classes.

A Specialist can be composed from:

```text
role family
+
methodology
+
authority
+
context profile
+
model requirement
+
artifact contract
```

Example:

```text
ROLE FAMILY:
Architecture

METHODOLOGY:
systems_architecture_v3

AUTHORITY:
proposal_only

CONTEXT:
architecture_profile

MODEL REQUIREMENT:
deep_reasoning

OUTPUT:
ArchitectureDecisionPack
```

This allows project-specific Specialists without changing the runtime architecture.

---

## 31. Specialist Registry Becomes Canonical

The current fixed `WorkerRole` enum is too rigid for the target system.

Future direction:

```text
SpecialistRegistry
```

becomes the authoritative catalogue.

It may contain:

- built-in Specialists;
- versioned methodologies;
- project-specific Specialists;
- future plugin Specialists.

`WorkerRole` becomes compatibility/deprecation architecture.

---

## 32. Role Families

Useful high-level families:

```text
DISCOVERY
PRODUCT
ARCHITECTURE
ENGINEERING
ASSURANCE
OPERATIONS
CREATIVE / PRODUCTION
MEMORY / KNOWLEDGE
```

These are useful for organisation/UI without freezing every exact Specialist.

---

## 33. Not Everything Should Be an Agent

Deterministic services should remain deterministic.

Do **not** turn the following into Agents merely because the system is “agentic”:

- Model Router;
- Context Broker;
- Scheduler;
- Resource Broker;
- Artifact Store;
- Git manager;
- Secret manager;
- Policy Engine;
- cost accountant;
- vector database.

Create an Agent only when cognitive methodology adds value.

---

## 34. Memory Curator Safety

If Reverend uses a cognitive Memory Curator:

```text
Memory Curator
   ↓
MemoryProposal artifact
   ↓
policy / validation
   ↓
Memory store
```

not:

```text
model thinks something
→ directly writes permanent authoritative memory
```

This preserves epistemic quality.

---

## 35. Agent Observability

Each Job should expose sufficient telemetry for debugging, benchmarking, frontend display, and billing.

Conceptually:

```text
agent_id
specialist_id/version
task_id
team_id
resolved model
runtime
compute node
context size
model calls
tool calls
artifacts
start/end
stop reason
tokens
cost
verification result
```

Agent identity is stable technical identity, not pseudo-human personality.

---

## 36. Failure Classification

Useful semantic failure categories include:

```text
MODEL_FAILURE
TOOL_FAILURE
CONTEXT_FAILURE
SCHEMA_FAILURE
AUTHORITY_DENIED
BUDGET_EXHAUSTED
DEPENDENCY_FAILURE
VERIFICATION_FAILURE
RUNTIME_FAILURE
```

Different classes should drive different responses.

Examples:

```text
SCHEMA_FAILURE
→ bounded retry

MODEL_FAILURE
→ model escalation

CONTEXT_FAILURE
→ ContextRequest

AUTHORITY_DENIED
→ policy/human path

VERIFICATION_FAILURE
→ Failure Investigator / repair workflow
```

---

## 37. Efficiency Rules

A3 freezes several economic/cognitive principles.

### Cheapest sufficient intelligence

Use the smallest/cheapest eligible model that satisfies quality requirements.

### Deterministic work before LLM work

Examples:

- symbol lookup;
- dependency graph;
- test discovery;
- Git diff;
- build diagnostics.

### Reuse artifacts

A Developer consumes the accepted architecture artifact instead of regenerating architecture.

### Avoid context replication

Each Specialist receives task-relevant information.

### Avoid redundant debate

Multiple Agents analyze the same issue only when uncertainty or independence justifies it.

---

## 38. Long-Running Agent Identity

A durable Agent identity must not depend on:

- KV cache;
- open model stream;
- Python object;
- worker process.

If the GPU dies:

```text
AgentInstance remains logically meaningful
```

and a future Job can reconstruct context from durable state.

This is a key A7 integration point.

---

## 39. Project-Specific Specialists

Future projects should be able to define domain Specialists without changing the core runtime.

Example:

```text
AstraFlow CFD Validation Specialist

methodology:
  conservation checks
  residual checks
  nozzle-flow invariants
  grid convergence

tools:
  simulator
  plots
  validation scripts

output:
  CFDValidationPack
```

This is simply another versioned `SpecialistSpec`.

---

## 40. Benchmarking Specialist Quality

Because a Specialist is more than a model, Reverend can benchmark:

```text
same model
same Task
different methodology
```

or:

```text
same Specialist
different model
```

This lets the system distinguish:

```text
model intelligence
```

from:

```text
Reverend harness intelligence
```

---

## 41. Canonical Agent Runtime Flow

```text
CONTROL PLANE TASK
        │
        ▼
SELECT SPECIALIST
        │
        ▼
CREATE AGENT INSTANCE
        │
        ▼
RESOLVE EFFECTIVE AUTHORITY
        │
        ▼
COMPILE CONTEXT
        │
        ▼
RESOLVE MODEL REQUIREMENT
        │
        ▼
REQUEST COMPUTE
        │
        ▼
CREATE JOB ATTEMPT
        │
        ▼
┌─────────────────────────────┐
│ BOUNDED AGENT LOOP          │
│                             │
│ inference                   │
│   ↓                         │
│ tool needed? ── yes ──┐     │
│   │                   │     │
│   no                  ▼     │
│   │              policy     │
│   │                   │     │
│   │                tool     │
│   │                   │     │
│   └────────────── observation│
└──────────────┬──────────────┘
               │
               ▼
        TYPED ARTIFACTS
               +
        CONTROL SIGNAL
               │
               ▼
        SCHEMA / POLICY GATE
               │
               ▼
        CONTROL PLANE
          │    │     │
          ▼    ▼     ▼
       next   retry  complete
```

---

## 42. Current-Code Migration

| Current construct | Future direction |
|---|---|
| `SpecialistSpec` | CANONICAL — EXTEND |
| `SpecialistRegistry` | CANONICAL — EXTEND |
| `ContextPolicy` | KEEP; A5 generalizes |
| `ContextBroker` | KEEP; A5 generalizes |
| methodology binding | KEEP + FORMAL VERSIONING |
| typed artifact I/O | KEEP |
| authority profile | EXTEND |
| independent-verifier guard | KEEP / GENERALIZE |
| direct `model_role` binding | REPLACE SEMANTICALLY WITH MODEL REQUIREMENT |
| `WorkerRole` | COMPATIBILITY / DEPRECATE |
| static worker policy maps | REPLACE WITH REGISTRY/POLICY RESOLUTION |
| `WorkerTask` | ABSORB INTO CONTROL PLANE TASK + AGENT ASSIGNMENT |
| `WorkerExecution` | EVOLVE INTO JOB RESULT + ARTIFACTS + CONTROL SIGNAL |
| `WorkerBudget` | KEEP CONCEPT; A6 GENERALIZES |
| hard `MAX_WORKERS` | REMOVE AS ARCHITECTURAL CONSTANT |
| sequential `WorkerOrchestrator` | ABSORB INTO A4/A6 |
| worker adapters | TEMPORARY COMPATIBILITY |

---

## 43. Frozen A3 Requirements

```text
A3-01
A Specialist is a reusable, versioned cognitive methodology contract.

A3-02
An Agent is a runtime instantiation of a Specialist assigned to a Task.

A3-03
Task and Job lifecycle remain authoritative in the Control Plane.

A3-04
Agent status is subordinate to Control Plane state.

A3-05
Agents are not permanently bound to a model.

A3-06
Specialists declare model capability requirements.

A3-07
Model selection occurs at Job execution time.

A3-08
Agents are independent of physical compute identity.

A3-09
Specialists declare authority ceilings.

A3-10
Effective authority is resolved by policy.

A3-11
Models never receive direct infrastructure authority.

A3-12
Tool actions are mediated by Reverend.

A3-13
Agent cognition/tool loops are bounded.

A3-14
Executive Orchestrator owns outer workflow topology.

A3-15
Agents may request dependencies but not recursively spawn freely.

A3-16
Context is compiled and bounded externally.

A3-17
Typed artifacts are the primary substantive inter-Agent communication.

A3-18
Agent completion is determined by a completion contract.

A3-19
Independent assurance cannot mutate the artifact it verifies.

A3-20
Private reasoning is not authoritative project state.

A3-21
Every Agent operates under an explicit budget.

A3-22
Escalation is structured and orchestrator-controlled.

A3-23
Specialist definitions are registry-driven.

A3-24
Deterministic services are not unnecessarily modeled as Agents.

A3-25
Agent execution is observable and attributable.

A3-26
Agent durable identity survives model/compute replacement.

A3-27
Project-specific Specialist definitions are supported.

A3-28
Specialist methodologies are independently versionable and benchmarkable.
```

---

## 44. Explicitly Outside A3

A3 does not define:

- Team/swarm mechanics;
- Team hierarchy;
- exact context engine;
- memory architecture;
- compute scheduler;
- concrete model fleet;
- GPU topology;
- recovery state machine;
- auth system.

Those belong to A4, A5, A6, A7, A8, A9, and A10.

---

## 45. Design-Phase Implications

The Design Phase must produce concrete contracts for:

- `SpecialistSpec`;
- `AgentInstance`;
- model requirements;
- authority resolution;
- control signals;
- Agent budget;
- Agent telemetry;
- compatibility migration from `WorkerRole`;
- lifecycle projection from Task/Job state;
- tool request/result interfaces.

The implementation should avoid introducing a second state authority for Agents.

---

## 46. A3 Decision Record

```text
MILESTONE:
A3 — Agent Cognitive Runtime

STATUS:
ACCEPTED

CORE DEFINITION:
Agent = bounded runtime instantiation of a versioned Specialist assigned to an authoritative Control Plane Task.

SPECIALIST DEFINES:
methodology
inputs / outputs
authority ceiling
context requirements
model capability requirements
tool capabilities
budget defaults
completion contract
verification / escalation policy

AGENT DOES NOT OWN:
workflow topology
model identity
GPU identity
infrastructure credentials
unbounded delegation
authoritative project state

PRIMARY COMMUNICATION:
typed artifacts + structured control signals

EXECUTION:
bounded cognition/tool loop

OUTER CONTROL:
Executive Orchestrator + Control Plane

PRIMARY MIGRATION:
SpecialistSpec becomes canonical.
WorkerRole / WorkerOrchestrator become compatibility mechanisms and are eventually absorbed.
```
