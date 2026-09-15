# A4 — Agent Teams, Swarms & Parallelism

> **Programme:** Reverend Cloud Analysis  
> **Milestone:** A4  
> **Status:** ACCEPTED  
> **Owner:** Backend / systems track  
> **Document purpose:** Define how multiple A3 Agents cooperate, how Team and swarm execution are represented, how logical parallelism is created, how conflicts are resolved, and how Reverend prevents multi-agent execution from degenerating into expensive redundant chatter.  
> **Important:** This report defines analysis-level semantics. Exact database schemas, scheduler algorithms, TeamPlan formats, and APIs belong to the Design Phase.

---

## 1. Executive Decision

Reverend's canonical multi-agent abstraction is:

> **`AgentTeam`**

A “swarm” is **not** a separate authority or parallel orchestration system. It is a **Team execution strategy** used when several Agents should work in parallel, independently, or over partitioned subproblems.

This decision deliberately avoids introducing overlapping concepts such as:

```text
Team
Swarm
Crew
Squad
Committee
Council
Collective
```

as separate core abstractions.

The architecture should remain:

```text
Executive Orchestrator
        ↓
Control Plane DAG
        ↓
AgentTeam
        ↓
Tasks / Agents
```

not:

```text
Control Plane
+ swarm scheduler
+ team scheduler
+ worker scheduler
+ agent society
```

---

## 2. Why Teams Are Necessary

A1 requires Reverend to build and evolve entire projects.

A sufficiently complex project should not be represented as:

```text
one gigantic Agent
  ↓
research
  ↓
architecture
  ↓
backend
  ↓
frontend
  ↓
tests
  ↓
security
  ↓
verification
```

because this creates several problems:

- context size grows without bound;
- specialist methodologies become diluted;
- independent verification disappears;
- independent work is forced to run serially;
- one Agent becomes the failure domain for the entire project;
- strong models are wasted on trivial subtasks;
- every project becomes one enormous transcript;
- parallel hardware cannot be used intelligently.

A Team architecture lets Reverend decompose work into coherent cognitive responsibilities while preserving one authoritative Control Plane.

---

## 3. Why More Agents Are Not Automatically Better

A4 explicitly rejects “agent count” as the optimization target.

Bad pattern:

```text
Task received
   ↓
spawn 20 Agents
   ↓
all discuss the task
   ↓
vote on answer
```

This tends to create:

- duplicated work;
- token explosion;
- correlated mistakes;
- integration overhead;
- context replication;
- difficult debugging;
- unclear responsibility;
- unpredictable cost.

The accepted principle is:

> **Minimum Sufficient Team**

For any objective, Reverend should use the smallest number of Agents expected to materially improve verified success.

---

## 4. Canonical Terminology

```text
AGENT
One A3 cognitive Specialist instance.

TEAM
A bounded set of Agent/Task assignments cooperating toward a shared objective.

TEAM PLAN
The dependency structure describing Team work.

TEAM COORDINATOR
Deterministic infrastructure that tracks Team membership, Tasks, dependencies,
budgets, completion and cancellation.

TEAM LEAD
Optional cognitive Specialist that performs synthesis, technical leadership,
review, or adjudication.

SWARM
A Team strategy in which multiple Agents perform parallel, partitioned,
replicated, or adversarial work.

EXECUTIVE ORCHESTRATOR
Global authority that creates Teams, changes workflow topology and controls
dynamic decomposition.
```

A crucial distinction:

```text
TeamCoordinator ≠ TeamLead
```

The Coordinator is infrastructure.

The Lead may be an LLM-powered Agent.

---

## 5. Team Coordinator Must Be Deterministic

The Team Coordinator should own deterministic Team lifecycle concerns such as:

- membership;
- child Task references;
- dependency readiness;
- budget accounting;
- completion bookkeeping;
- cancellation propagation;
- Team result collection.

It does **not** decide software architecture or product strategy.

Example:

```text
Architect Agent:
"Backend, frontend and test-harness work can proceed independently."

        ↓

ArchitectureDecision artifact

        ↓

Executive Orchestrator:
creates Team + Tasks

        ↓

Team Coordinator:
tracks those Tasks deterministically
```

This maintains the A3 rule that deterministic infrastructure should not be unnecessarily turned into an Agent.

---

## 6. AgentTeam Semantic Contract

A future Team should conceptually be able to represent:

```text
AgentTeam
├── team_id
├── project_id
├── run_id
├── parent_task_id
├── objective
│
├── team_strategy
├── member_task_ids
├── leader_agent_id?
│
├── dependency graph
├── input artifact refs
├── output contract
│
├── budget envelope
├── concurrency envelope
├── authority scope
│
├── completion policy
├── failure policy
├── disagreement policy
└── provenance
```

The exact Python/database schema is intentionally deferred.

---

## 7. Teams Remain Subordinate to the Control Plane

A Team does not create its own authoritative workflow store.

Example:

```text
Workflow
│
├── Task: Architecture
│
└── Task: Implement Application
     │
     └── Team E17
          ├── Task: Backend
          ├── Task: Frontend
          └── Task: Test Harness
```

The child work remains normal Control Plane Tasks.

A Team is grouping, coordination, budgeting, and completion metadata over authoritative Tasks.

This preserves A0's:

> **one workflow authority**

rule.

---

## 8. Dynamic Team Formation

Reverend should not permanently operate with a large fixed “staff roster” of active Agents.

Instead, the Executive Orchestrator should derive the minimum necessary organisation from the objective.

Conceptual formation decision:

```text
Can one Specialist reliably complete the Task?
  ├─ YES → one Agent
  └─ NO
       ↓
Can the work be decomposed into independently useful subtasks?
  ├─ NO → stronger / more appropriate single Agent
  └─ YES
       ↓
Will multi-Agent execution likely justify coordination cost?
  ├─ NO → sequential Specialists
  └─ YES → AgentTeam
```

This keeps the system economical and easier to reason about.

---

## 9. Decomposition Quality Requirements

Parallel execution only helps when decomposition is good.

Each child Task should have:

- a clear objective;
- bounded input;
- expected output;
- known dependencies;
- limited overlap;
- acceptance criteria.

Bad decomposition:

```text
Developer A:
work on backend

Developer B:
improve backend

Developer C:
also review/fix backend while editing it
```

Better decomposition:

```text
Developer A:
implement authentication service contract

Developer B:
implement session repository

Developer C:
implement API adapter

Integration Task:
combine against defined interfaces
```

A4 therefore treats **decomposition quality** as a prerequisite for useful parallelism.

---

## 10. Canonical Team Strategies

A4 defines several execution patterns without creating separate orchestration systems.

### 10.1 Pipeline

Different Specialists perform different stages sequentially.

```text
Research
  ↓
Architecture
  ↓
Development
  ↓
Verification
```

The current Reverend autonomy workflow already resembles this pattern.

---

### 10.2 Parallel Decomposition

Different Agents work on independent subcomponents.

```text
              Architecture
                   │
        ┌──────────┼──────────┐
        ▼          ▼          ▼
     Backend    Frontend    Tests
        │          │          │
        └──────────┼──────────┘
                   ▼
              Integration
```

This is central to full-project development.

---

### 10.3 Sharded Swarm

Several same-family Agents cover distinct partitions of a broader problem.

Example:

```text
Research Team
├── Official Documentation Researcher
├── Academic Literature Researcher
├── Implementation / Repository Researcher
└── Ecosystem / Failure-Report Researcher
          │
          ▼
       Synthesis
```

This is useful because each Agent explores a different search space.

---

### 10.4 Independent Replication

Several Agents independently tackle the same hard question.

```text
Investigator A ─┐
Investigator B ─┼──► comparison / adjudication
Investigator C ─┘
```

This should be used selectively for:

- difficult debugging;
- threat modeling;
- high-uncertainty architecture;
- adversarial review;
- hard research.

It should not be Reverend's default pattern.

---

## 11. Research Swarms

Research parallelizes well because search space can often be partitioned.

Preferred pattern:

```text
Research Objective
      │
      ├── official sources
      ├── academic literature
      ├── implementations
      └── ecosystem / community evidence
             │
             ▼
         Synthesis Agent
             │
             ▼
          EvidencePack
```

Researchers do not need each other's full working context.

They publish evidence artifacts.

The Synthesizer consumes the durable outputs.

This minimizes context replication and keeps provenance clear.

---

## 12. Engineering Teams Require Stronger Isolation

Parallel research is relatively safe.

Parallel code mutation is not.

Accepted engineering pattern:

```text
ArchitectureDecisionPack
         │
         ▼
Engineering Team
   ┌─────┼───────────┐
   ▼     ▼           ▼
Backend Frontend    Tests
Agent   Agent       Agent
   │     │           │
isolated isolated  isolated
scope    scope      scope
   └─────┼───────────┘
         ▼
     Integration
         ↓
     Verification
```

Parallel mutating Agents should not edit one shared worktree without explicit conflict-control semantics.

---

## 13. Mutation Scope and Ownership

A4 accepts the concept of explicit mutation scopes.

Examples:

```text
Backend Agent:
  src/server/**
  tests/server/**

Frontend Agent:
  frontend/**
  tests/ui/**
```

These scopes may be represented as:

- paths;
- components;
- repositories;
- branches;
- worktrees;
- interface boundaries.

The exact enforcement mechanism belongs to Design.

The principle is:

> **Parallel mutation requires isolated or explicitly non-conflicting mutation scopes.**

---

## 14. Interface-First Parallelism

Parallel development becomes more reliable when interfaces are stabilized first.

Example:

```text
Frontend
   ↕
API contract
   ↕
Backend
```

If both sides are changing the interface independently, parallelism may increase rework.

A4 therefore accepts the direction:

> **Interface stability should influence whether implementation work is parallelized.**

---

## 15. Integration Is First-Class Work

Parallel work introduces integration risk.

Integration is not simply:

```text
git merge
```

It may need to inspect:

- API contracts;
- configuration;
- shared dependencies;
- data schemas;
- build systems;
- runtime assumptions;
- cross-component tests.

The existing Reverend Integration stage should therefore remain and be generalized.

---

## 16. Team Leads

A Team may optionally have a cognitive Lead.

Examples:

```text
Research Lead
Engineering Lead
Assurance Lead
```

A Team Lead may:

- review member artifacts;
- identify missing work;
- synthesize results;
- propose follow-up Tasks;
- produce Team-level artifacts.

A Team Lead may **not**:

- grant permissions;
- bypass budgets;
- spawn unlimited Agents;
- change global Run authority;
- replace the Executive Orchestrator.

---

## 17. Not Every Team Needs a Lead

A simple parallel decomposition such as:

```text
Backend
Frontend
Tests
```

may already be sufficiently structured by the Executive Orchestrator and Team Coordinator.

Adding a Lead would create:

- another context compilation;
- another model call;
- another synthesis step;
- more cost.

Therefore:

> **Team Lead is optional and must be justified by cognitive value.**

---

## 18. Organisational Hierarchy Without Recursive Authority

Large projects may be represented hierarchically:

```text
Run
├── Discovery Team
│   ├── Research
│   └── Product
│
├── Engineering Team
│   ├── Backend
│   ├── Frontend
│   └── Tests
│
└── Assurance Team
    ├── Verification
    ├── Security
    └── Performance
```

This is useful for:

- observability;
- budgeting;
- grouping;
- artifact lineage.

However, A4 rejects recursive autonomous orchestration such as:

```text
Agent creates Team
Team Lead creates subteam
subteam creates another scheduler
...
```

Topology changes remain centrally authorized.

---

## 19. Logical vs Physical Parallelism

A4 defines **logical parallelism**.

A6 later determines **physical concurrency**.

Example:

```text
A, B, C, D
all independent and logically READY
```

A4 says all four may run.

A6 may decide:

```text
A + B RUNNING
C + D waiting
```

because only two resource slots exist.

This separation is fundamental.

---

## 20. Control Plane DAG Remains Canonical

The current Control Plane already supports:

- dependencies;
- cycle prevention;
- readiness;
- dependency completion checks.

These semantics remain the canonical dependency model.

The Team runtime must use the Control Plane DAG.

It must not invent a separate “swarm DAG” authority.

---

## 21. Dynamic DAG Expansion

A1 requires replanning.

A Team may discover new dependency work.

Example:

```text
Development
   ↓
unknown OAuth behavior
   ↓
BLOCKED
   ↓
Research Task inserted
   ↓
EvidencePack produced
   ↓
Development resumes
```

The original history remains.

The DAG evolves through explicit decisions rather than silent mutation.

---

## 22. Agent Communication Is Artifact-Based

Rejected pattern:

```text
10 Agents
all in one shared conversation
all read each other's chain-of-thought
```

Accepted pattern:

```text
Agent A → Artifact A
Agent B → Artifact B
Agent C → Artifact C
             ↓
       Synthesizer / Integrator
```

A5 defines the information architecture in detail.

A4 freezes the **communication topology**.

---

## 23. Fan-Out and Fan-In

A4 requires both.

### Fan-out

One upstream artifact feeds several Tasks.

```text
ArchitectureDecision
├── Backend Task
├── Frontend Task
└── Test Task
```

### Fan-in

Several outputs feed one downstream Task.

```text
BackendArtifact ─┐
FrontendArtifact ├──► Integration
TestArtifact ────┘
```

This is the canonical multi-Agent dataflow.

---

## 24. Team Completion

A Team does not succeed merely because all Agents stopped.

The Team has an output contract.

Examples:

```text
ResearchTeam
must produce:
EvidencePack

EngineeringTeam
must produce:
IntegratedImplementation
+ verification-ready workspace
```

Possible semantic completion policies include:

```text
ALL_REQUIRED
FIRST_VALID
SYNTHESIS_REQUIRED
SUFFICIENT_COVERAGE
```

Exact enum and semantics belong to Design.

For most cognitive swarms, `SYNTHESIS_REQUIRED` is likely safest.

---

## 25. Majority Voting Is Not Authoritative

Three models agreeing does not make a claim true.

They may share:

- training biases;
- prompt assumptions;
- missing evidence;
- common hallucination patterns.

Preferred disagreement resolution hierarchy:

1. deterministic tests;
2. measurements;
3. benchmarks;
4. source/evidence comparison;
5. independent critique;
6. specialist adjudication;
7. human decision where genuinely necessary.

Voting can be a signal.

It is not final truth.

---

## 26. Disagreement Classification

### Empirical disagreement

Example:

```text
Approach A is faster than B.
```

Resolve with:

- benchmark;
- simulation;
- test.

### Evidence disagreement

Inspect:

- source quality;
- provenance;
- freshness;
- conflicting source sets.

### Design trade-off

Pass alternatives to an Architect/Adjudicator against explicit criteria.

### Requirement ambiguity

Escalate to Product/human where consequential.

### Subjective preference

Use project policy/defaults when possible.

---

## 27. Adjudicator Pattern

For unresolved cognitive disagreement:

```text
Architect A ─┐
             ├── Architecture Adjudicator
Architect B ─┘
```

But do not instantiate adjudicators automatically for every difference.

The Executive Orchestrator should evaluate whether the expected value justifies the extra cost.

---

## 28. Independent Replication and Information Isolation

If independent analysis is requested, Agents should not read each other's intermediate hypotheses before producing their own outputs.

Otherwise:

```text
independent replication
```

turns into:

```text
anchored consensus
```

This is especially important for:

- root-cause analysis;
- adversarial security;
- difficult verification;
- architecture alternatives.

---

## 29. Model Diversity Hypothesis

A4 carries forward a hypothesis for A9:

> **Different model families may reduce correlated failure in independent branches or Developer/Verifier pairs.**

This is not a permanent rule.

It must be benchmarked.

---

## 30. Assurance Teams

Assurance is well-suited to parallel specialization.

Example:

```text
Implementation
   │
   ├── Verification
   ├── Security
   └── Performance
           │
           ▼
    Integration / final gate
```

These Agents should inspect different dimensions independently.

They should not coordinate merely to make their reports agree.

---

## 31. Failure Propagation

A local failure should not automatically invalidate unrelated successful work.

Example:

```text
Backend → complete
Frontend → complete
Tests → runtime failure
```

Expected behavior:

- preserve successful artifacts;
- retry/replace the failing Test Task;
- block only dependent Integration;
- avoid restarting everything.

However, if an upstream architecture assumption is invalid, dependent branches may need cancellation/replanning.

Failure propagation follows dependency semantics.

---

## 32. Cancellation Scope

Useful conceptual scopes:

```text
cancel Job
cancel Agent assignment
cancel Task
cancel Team
cancel Run
```

The wider the scope, the more downstream work is affected.

A7 defines durable pause/cancel/recovery semantics.

---

## 33. Team Budgets

Budget hierarchy:

```text
RunBudget
  ├── ResearchTeamBudget
  ├── EngineeringTeamBudget
  └── AssuranceTeamBudget
```

Teams delegate budget to member Tasks/Agents.

They do not have authority to consume the Run's entire remaining budget without explicit delegation.

A6 defines the physical resource/accounting hierarchy.

---

## 34. Adaptive Team Size

Do not hard-code:

```text
research swarm = 5 Agents
engineering Team = 4 Agents
```

Team size depends on:

- problem breadth;
- decomposability;
- uncertainty;
- expected information gain;
- coordination overhead;
- budget;
- available compute.

---

## 35. Marginal-Value Principle

A useful conceptual policy:

> **Add another Agent only when expected additional value exceeds expected compute and coordination cost.**

This may initially be heuristic.

It is still the correct optimization target.

---

## 36. Team Expansion

A Team member may discover that additional work is required.

Flow:

```text
Agent
  ↓
Dependency / Expansion Request
  ↓
Team Coordinator records
  ↓
Executive Orchestrator evaluates
  ↓
policy + budget + DAG check
  ↓
new Task / Team member if approved
```

No unrestricted self-recruitment.

---

## 37. Team Contraction

Optional branches may be cancelled when their expected value becomes too low.

Example:

```text
Researcher A finds a definitive official answer.

Researchers B/C are still exploring redundant weak sources.
```

If Team policy allows:

```text
cancel optional branches
```

This matters for cloud cost control.

---

## 38. Speculative / Experimental Branches

Reverend may deliberately test alternatives.

Example:

```text
Optimization A
Optimization B
      ↓
Benchmark
      ↓
Select validated result
```

This is particularly valuable when:

- uncertainty is high;
- outcome is objective;
- consequence is significant;
- budget permits.

Competing full implementations should be rare because they double implementation cost.

---

## 39. Team Observability

A Team should eventually expose:

```text
objective
strategy
members
dependency graph
running Tasks
completed Tasks
blocked Tasks
budget spent
budget remaining
artifacts
Team result
```

This is a direct requirement for Kirk's A2 frontend.

Example UI projection:

```text
Engineering Team — 67%

✓ API Developer
● Frontend Developer
✓ Test Framework
○ Integration

Elapsed: 18m
GPU spend: ...
```

Exact UI is out of scope.

---

## 40. Provenance Hierarchy

Every artifact should remain attributable through:

```text
Run
 ↓
Team
 ↓
Task
 ↓
Agent
 ↓
Job
 ↓
Artifact
```

This supports:

- debugging;
- security review;
- benchmarking;
- billing;
- project history.

---

## 41. Team Plans Are Versioned

Plans can change:

```text
TeamPlan v1
  ↓
new evidence
  ↓
ReplanDecision
  ↓
TeamPlan v2
```

The old plan remains historical evidence.

This supports A1's durable replanning requirement.

---

## 42. Whole-Project Organisational Example

```text
                       EXECUTIVE ORCHESTRATOR
                                │
                                ▼
                            PROJECT DAG
                                │
             ┌──────────────────┼──────────────────┐
             ▼                  ▼                  ▼
      DISCOVERY TEAM        PRODUCT           ARCHITECTURE
             │                  │                  │
      ┌──────┼──────┐           │                  │
      ▼      ▼      ▼           │                  │
official academic ecosystem     │                  │
research research research      │                  │
      └──────┼──────┘           │                  │
             ▼                  │                  │
         EvidencePack            │                  │
             └───────────────────┼──────────────────┘
                                 ▼
                         ArchitectureDecision
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
                 Backend      Frontend      Tests
                    │            │            │
                    └────────────┼────────────┘
                                 ▼
                            Integration
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
                 Verify       Security    Performance
                    └────────────┼────────────┘
                                 ▼
                         Final Assurance
```

This is an available organisational vocabulary, not a requirement to instantiate every box.

---

## 43. Small-Project Example

The same architecture must collapse efficiently:

```text
"Fix this parser bug."
```

into:

```text
Developer
   ↓
Verifier
```

No research swarm.

No Team Lead.

No unnecessary committee.

---

## 44. Rejected “Agent Society” Architecture

A4 explicitly rejects a primary design in which Agents:

- freely message each other;
- independently recruit more Agents;
- negotiate authority;
- negotiate budgets;
- vote as the truth mechanism;
- maintain private long-lived societies;
- run independent nested schedulers.

Reverend should be a **managed organisation**.

Agents provide cognition.

The Control Plane provides governance.

---

## 45. Benchmark Hypotheses Carried Forward

These are not frozen truths:

### H1
Specialized Teams outperform one general Agent on B4/B5 whole-project work.

### H2
Partitioned research gives better evidence per £ than redundant identical search.

### H3
Cross-family verification reduces correlated failure.

### H4
Interface-first parallel engineering reduces integration failures.

### H5
Speculative implementations can improve difficult engineering success when objective evaluation exists.

These require ReverendBench evidence.

---

## 46. Frozen A4 Requirements

```text
A4-01
AgentTeam is Reverend's canonical multi-Agent abstraction.

A4-02
Swarm is a Team strategy, not a separate authority.

A4-03
Executive Orchestrator owns Team creation and topology changes.

A4-04
Team Coordinator is deterministic infrastructure.

A4-05
Team Lead is optional cognitive Specialist.

A4-06
All Team work remains authoritative Control Plane Tasks.

A4-07
Teams are dynamically formed from task requirements.

A4-08
Minimum sufficient Team is the default policy.

A4-09
Parallelism requires useful decomposition and explicit dependencies.

A4-10
Control Plane DAG remains the canonical dependency model.

A4-11
Logical parallelism is separate from physical concurrency.

A4-12
Parallel mutating Agents require isolated mutation scopes.

A4-13
Integration is a first-class Task.

A4-14
Substantive communication is artifact-based.

A4-15
Fan-out / fan-in artifact flow must be supported.

A4-16
Same-role swarms are allowed where partitioning or replication is justified.

A4-17
Independent replication preserves information independence until result publication.

A4-18
Majority voting is not authoritative verification.

A4-19
Evidence/tests/benchmarks are preferred disagreement-resolution methods.

A4-20
Assurance Specialists remain independent.

A4-21
Failure propagation follows dependency semantics.

A4-22
Teams operate under delegated bounded budgets.

A4-23
Agents and Team Leads cannot recursively spawn without Executive approval.

A4-24
TeamPlan revisions remain provenance-tracked.

A4-25
Team size is adaptive.

A4-26
Optional work may be cancelled when marginal value no longer justifies cost.

A4-27
Speculative branches are supported when objectively evaluable and budget-justified.

A4-28
Team activity is observable and attributable.

A4-29
Organisational hierarchy may exist without recursive workflow authority.

A4-30
Uncontrolled recursive Agent-society architecture is rejected.
```

---

## 47. Current-Code Migration Classification

| Current construct | Direction |
|---|---|
| Control Plane DAG | CANONICAL — KEEP / EXTEND |
| task dependencies | KEEP |
| cycle prevention | KEEP |
| readiness calculation | KEEP / GENERALIZE |
| fixed software autonomy DAG | GENERALIZE DYNAMICALLY |
| sequential `WorkerOrchestrator` | ABSORB / REPLACE |
| hard worker-count constants | REMOVE AS ARCHITECTURAL CONSTANT |
| central budget principle | KEEP |
| typed worker results | KEEP THROUGH ARTIFACTS |
| no recursive delegation | KEEP IN STRONGER FORM |
| Verification/Security branches | KEEP / GENERALIZE |
| Integration stage | KEEP + EXPAND |
| fixed worker plans | REPLACE WITH TEAM PLANS |
| free-form swarm dialogue | REJECT |
| concurrent shared-worktree mutation | REJECT |
| AgentTeam runtime | NEW |

---

## 48. Design-Phase Implications

The Design Phase must define concrete interfaces for:

- `AgentTeam`;
- TeamPlan and revisions;
- Team Coordinator;
- Team strategy;
- Team budget;
- fan-out/fan-in;
- mutation scopes;
- Team completion policy;
- expansion requests;
- disagreement/adjudication flow;
- Team telemetry.

The design must reuse the existing Control Plane DAG instead of creating a parallel swarm state machine.

---

## 49. A4 Decision Record

```text
MILESTONE:
A4 — Agent Teams, Swarms & Parallelism

STATUS:
ACCEPTED

CORE ABSTRACTION:
AgentTeam

SWARM:
A Team execution strategy for sharded, replicated, adversarial or parallel work.

GLOBAL AUTHORITY:
Executive Orchestrator + Control Plane

TEAM COORDINATION:
Deterministic Team Coordinator

COGNITIVE LEADERSHIP:
Optional Team Lead Specialist

PRIMARY WORK MODEL:
Control Plane dependency DAG

PARALLELISM:
Logical first.
Physical execution is decided by A6.

COMMUNICATION:
Typed artifacts with fan-out / fan-in.

MUTATION:
Parallel developers use isolated mutation scopes and explicit integration.

FORMATION POLICY:
Minimum sufficient Team.

DISAGREEMENT:
Evidence/test/benchmark first.
Adjudication when necessary.
Voting is non-authoritative.

REJECTED:
Uncontrolled recursive Agent society.
```
