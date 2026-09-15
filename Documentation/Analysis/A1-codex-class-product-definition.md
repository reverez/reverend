# A1 — Codex-Class Product Definition

> **Programme:** Reverend Cloud Analysis  
> **Milestone:** A1  
> **Status:** ACCEPTED  
> **Owner:** Backend / systems track  
> **Document purpose:** Define the product-level capabilities Reverend must ultimately provide before choosing Agent internals, models, GPUs, or cloud topology.  
> **Important:** This is a product/architecture requirements report. It intentionally avoids lower-level implementation choices reserved for A3–A10 and the Design Phase.

---

## 1. Executive Product Definition

Reverend should become:

> **A persistent autonomous software-engineering organisation capable of creating and evolving complete development projects with minimal human orchestration.**

The user should primarily supply:

- desired outcome;
- requirements;
- constraints;
- high-consequence approvals.

Reverend should dynamically assemble the reasoning, research, architecture, engineering, testing, verification, and production capabilities needed to turn that objective into a working project.

The system is therefore not just:

```text
user
→ one coding model
→ shell
→ code
```

The intended model is:

```text
human objective
      ↓
Executive Orchestrator
      ↓
Project / requirement model
      ↓
dynamic specialist organisation
      ↓
research / architecture / engineering / assurance
      ↓
tools + execution
      ↓
verified project
```

The LLMs provide intelligence.

> **Reverend provides organisation, governance, memory, tooling, execution, and assurance.**

---

## 2. Greenfield and Brownfield Scope

Reverend must support both major software-engineering modes.

### 2.1 Greenfield

Example:

```text
"Build an application that does X with constraints A, B and C."
```

The system should be able to:

1. interpret the objective;
2. identify important ambiguity;
3. derive requirements and acceptance criteria;
4. research missing information;
5. design architecture;
6. create repository structure;
7. choose/configure dependencies;
8. implement components;
9. build tests;
10. debug failures;
11. repair;
12. integrate;
13. document;
14. verify;
15. produce a reviewable deliverable.

The target is a real project, not a generated code snippet.

---

### 2.2 Brownfield

Example:

```text
"Add distributed worker support to this repository."
```

Reverend should:

1. map the repository;
2. understand relevant modules and symbols;
3. inspect existing contracts and tests;
4. locate change surfaces;
5. preserve existing behavior where required;
6. implement isolated modifications;
7. run builds/tests;
8. repair integration failures;
9. independently verify acceptance;
10. return reviewable Git changes.

Brownfield engineering requires project-scale repository reasoning, not merely file-at-a-time generation.

---

## 3. Human Role

The normal human role should resemble:

> **Product owner / director**

rather than:

> manual project manager for every engineering step.

The interaction goal is approximately:

```text
Human:
"Build X under constraints Y and Z."

Reverend:
- asks only important clarifying questions;
- investigates;
- decomposes;
- researches;
- plans;
- executes;
- tests;
- repairs;
- verifies;
- asks for approval only when required;
- returns the result.
```

The user should not need to manually orchestrate:

```text
open file
edit file
run test
fix test
inspect diff
repeat
```

for ordinary work.

---

## 4. Dynamic Workflow Requirement

A single fixed pipeline cannot represent all engineering work.

### Tiny bug

```text
Developer
   ↓
Verifier
```

### Medium feature

```text
Architect
   ↓
Developer
   ↓
Tests
   ↓
Verifier
```

### Full application

```text
Research
  ↓
Product
  ↓
Architecture
  ↓
┌─────────┬──────────┬─────────┐
Backend   Frontend   Tests
└─────────┴──────────┴─────────┘
             ↓
         Integration
             ↓
┌─────────┬──────────┬─────────┐
Verify   Security   Performance
└─────────┴──────────┴─────────┘
```

### A1 decision

> **Workflow topology must be derived from the objective rather than hard-coded globally.**

The mechanism is defined later in A3/A4.

---

## 5. Meaning of “Almost Autonomous”

For normal trusted engineering work, Reverend should be able to perform the following without the user explicitly ordering each step.

| Area | Required behavior |
|---|---|
| understanding | interpret objective, constraints, repository |
| requirements | derive and persist requirements / acceptance |
| research | investigate APIs, libraries, standards, papers, current facts |
| product | resolve scope, non-goals and trade-offs |
| architecture | design system/component architecture |
| planning | decompose into dependency-aware work |
| repository | create/map repository structure |
| implementation | modify project across many files |
| tools | use shell, compilers, build tools, package managers |
| dependencies | select/configure dependencies |
| tests | create and execute tests |
| debugging | diagnose from evidence |
| repair | bounded iterative correction |
| integration | combine parallel work safely |
| security | identify relevant risks |
| performance | benchmark/optimize where required |
| verification | independent acceptance evaluation |
| documentation | create useful project documentation |
| Git | isolated worktrees/branches and reviewable changes |
| persistence | resume long-running projects |
| delivery | produce usable project outputs |

This is the baseline interpretation of **Codex-class engineering capability** for Reverend.

---

## 6. “Beyond Codex” Product Direction

Reverend's intended differentiator is not simply a larger coding model.

The system should develop:

> **persistent project intelligence plus specialised organisational intelligence.**

For a long-running project, Reverend should know:

- why architecture decisions were made;
- which approaches failed;
- which experiments were run;
- what benchmarks showed;
- what requirements remain;
- what components are risky;
- what assumptions changed;
- what the repository currently means.

This makes Reverend closer to a persistent engineering organisation attached to a project than a disposable chat session.

---

## 7. Project Is Longer-Lived Than Run

A central A1 distinction:

```text
Project ≠ Run
```

Example:

```text
Project: AstraFlow Web

Run 1: create backend
Run 2: add visualization
Run 3: optimize CUDA path
Run 4: repair regression
Run 5: add deployment
```

Persistent project-level intelligence may include:

- requirements;
- accepted decisions;
- architecture history;
- experiments;
- benchmarks;
- failures;
- repository intelligence;
- policies.

A Run is one episode of execution inside that longer-lived project.

---

## 8. Requirements Must Survive Long Execution

Project requirements cannot live only inside an initial user prompt.

Reverend needs durable notions of:

```text
objective
constraints
requirements
acceptance criteria
decisions
non-goals
```

Every downstream Task should ultimately be traceable to these.

This prevents goal drift across dozens of Agent/model calls.

---

## 9. Dynamic Research

Research must be callable whenever a knowledge gap appears.

Example:

```text
Developer
  ↓
unknown external API behavior
  ↓
BLOCKED
  ↓
Research Task
  ↓
EvidencePack
  ↓
Developer resumes
```

The intended behavior is:

```text
identify gap
→ research
→ evaluate evidence
→ publish evidence
→ continue engineering
```

not guessing.

---

## 10. Dynamic Replanning

Projects rarely execute exactly as planned.

If Reverend discovers:

- incompatible dependency;
- invalid architecture;
- unavailable API;
- failed benchmark;
- test revealing design flaw;

then it must be capable of changing future work.

```text
Plan v1
   ↓
new evidence
   ↓
recorded decision
   ↓
Plan v2
```

History remains visible.

The system must not silently rewrite what happened.

---

## 11. Specialist Intelligence Is a Product Requirement

Specialisation exists because engineering work uses different methodologies.

Examples:

- Researcher;
- Systems Architect;
- Developer;
- Test Engineer;
- Security Reviewer;
- Performance Engineer;
- Product Specialist;
- UX Specialist;
- Failure Investigator;
- Verifier.

A Specialist should differ in:

- methodology;
- context;
- tools;
- authority;
- outputs;
- success criteria;
- model capability requirement.

A1 freezes **specialisation as a requirement**, not the exact catalogue.

---

## 12. Dynamic Teams / Swarms Are a Requirement

Large projects may require:

```text
Research Lead
├── API Researcher
├── Academic Researcher
└── Ecosystem Researcher
```

or:

```text
Engineering Team
├── Backend
├── Frontend
├── Tests
└── Integration
```

However:

> **Swarming is an optimization strategy, not the default mode.**

Use one Agent when one Agent is enough.

A4 defines the minimum-sufficient-team model.

---

## 13. Logical Parallelism

Independent work should be representable concurrently:

```text
Architecture complete
        │
┌───────┼─────────┐
▼       ▼         ▼
Backend Frontend  Tests
└───────┼─────────┘
        ▼
   Integration
```

A1 requires logical parallelism.

A6 decides whether the hardware can run it physically in parallel.

---

## 14. Repository Understanding Is First-Class

Brownfield project-scale development cannot be implemented as arbitrary prompt stuffing.

Reverend must maintain useful structured knowledge of:

```text
files
modules
symbols
dependencies
interfaces
tests
build systems
configuration
Git history
documentation
architecture
recent changes
```

This repository intelligence should be reusable across Specialists.

---

## 15. Self-Correction

Autonomy must be feedback-driven:

```text
attempt
 ↓
observe
 ↓
verify
 ↓
failure?
 ├─ no → continue
 └─ yes
      ↓
   diagnose
      ↓
   repair
      ↓
   rerun
```

Every repair loop remains bounded.

If repeated attempts fail, Reverend should:

- escalate intelligence;
- change strategy;
- request missing context;
- request human input;
- fail transparently.

It must never silently declare success.

---

## 16. Non-Code Project Outputs

Whole-project creation may require:

- documentation;
- diagrams;
- images/icons;
- 3D models;
- generated data;
- deployment files;
- simulation results;
- configuration;
- assets.

Therefore Project/Artifact semantics must be broader than source code.

Exact production systems can be introduced incrementally.

---

## 17. Human Intervention Boundaries

Human input is appropriate when:

### Material ambiguity exists

Example:

```text
"Build authentication."
```

where local credentials vs OAuth changes the product significantly.

### Consequential authority is required

Examples:

- deploy production;
- merge protected branch;
- delete data;
- incur substantial cloud cost;
- use sensitive credentials.

### Reverend cannot safely continue

After bounded attempts, the system may report:

```text
two viable architectures have materially different consequences
```

and request a decision.

Routine engineering should not produce repeated unnecessary approval prompts.

---

## 18. Autonomy Modes

The product should eventually support policy levels equivalent to:

```text
SUPERVISED
STANDARD
HIGH AUTONOMY
```

Exact names/UI are A2/Design decisions.

The architectural requirement is simply:

> approval behavior is policy-configurable.

---

## 19. Observable Autonomy

The user should be able to understand:

- what Reverend is doing;
- why it is doing it;
- which Team/Agent is active;
- which Task/Job is running;
- what is complete;
- what is blocked;
- what remains;
- what decisions were made;
- what resources are being consumed;
- what approvals are pending.

Autonomy must not imply opacity.

---

## 20. Completion Definition

Reverend does not equate:

```text
model stopped generating
```

with:

```text
Task complete
```

Completion requires relevant combinations of:

```text
requirements evaluated
acceptance criteria evaluated
deterministic tests passed
required assurance completed
no blocking Tasks remain
deliverables available
```

The Control Plane determines completion.

---

## 21. Quality Priority Ordering

Accepted priority ordering:

1. correctness;
2. safety and integrity;
3. requirement satisfaction;
4. maintainability;
5. robustness;
6. performance where required;
7. development speed;
8. compute efficiency / cost.

Cost matters, but not at the expense of silently broken results.

---

## 22. Codex-Class Capability Is Not UI Parity

A1 does **not** require Reverend to look like Codex.

The goal is capability parity/superiority in:

- repository engineering;
- long-running project work;
- tool use;
- debugging;
- repair;
- testing;
- full project creation;
- verification.

Kirk's frontend can expose these capabilities differently.

---

## 23. Core Product Thesis

The accepted conceptual formula is:

```text
strong model(s)
+
excellent engineering harness
+
specialist organisation
+
persistent project intelligence
+
dynamic orchestration
+
deterministic tools
+
independent verification
+
elastic compute
```

The system should obtain more reliable engineering value from a model than exposing that model through a plain chat interface.

---

## 24. Benchmark Classes

A1 defines project difficulty classes:

| Class | Typical task |
|---|---|
| B1 — Surgical Change | bug fix / small modification |
| B2 — Feature Development | multi-file feature |
| B3 — Subsystem Development | API/service/module |
| B4 — Full Project | complete repository from high-level spec |
| B5 — Complex Evolving Project | research + architecture + parallel components + revisions |

The strategic target is **strong B4/B5 performance**.

A model performing well only on B1 does not meet Reverend's long-term goal.

---

## 25. Ultimate Product Benchmark

A representative benchmark should resemble:

```text
"Create a production-quality application that does X.

Requirements:
A
B
C

Constraints:
D
E

You may research where necessary.
Do not ask me questions unless a decision is genuinely blocking."
```

Then evaluate whether Reverend independently:

- researches;
- architects;
- creates repository;
- implements;
- tests;
- debugs;
- repairs;
- documents;
- verifies;
- produces a usable deliverable.

This is more representative than isolated coding prompts.

---

## 26. Frozen A1 Requirements

```text
P-01
Reverend supports complete greenfield project creation.

P-02
Reverend supports repository-scale brownfield development.

P-03
The user primarily supplies objectives, constraints and consequential approvals.

P-04
Project workflows are dynamically decomposed.

P-05
Specialist intelligence is first-class.

P-06
Complex work can form dynamic specialist Teams.

P-07
Independent work supports logical parallelism.

P-08
Project intelligence persists across Runs.

P-09
Requirements and acceptance criteria remain durable throughout execution.

P-10
Research is dynamically callable when knowledge gaps appear.

P-11
Reverend supports bounded self-correction and repair.

P-12
Reverend supports dynamic replanning.

P-13
Code and non-code deliverables are first-class artifacts.

P-14
Consequential operations remain under explicit human authority.

P-15
Routine engineering proceeds without unnecessary interruption.

P-16
Autonomous execution remains observable.

P-17
Completion is determined by acceptance and verification rather than model confidence.

P-18
B4/B5 full-project performance is the strategic benchmark target.

P-19
The model fleet remains replaceable.

P-20
Reverend optimizes organisation around models rather than exposing models as the product.
```

---

## 27. Explicitly Outside A1

A1 deliberately does not define:

- exact Specialist list;
- AgentSpec schema;
- number of Agents;
- Team hierarchy;
- context engine;
- memory database;
- scheduler;
- models;
- GPUs;
- cloud provider;
- runtime;
- API;
- billing.

Those are derived downstream.

---

## 28. Design-Phase Implications

The Design Phase must turn these product requirements into:

- explicit Project / Requirement contracts;
- Run and Task semantics;
- approval policies;
- observability events;
- Team decomposition mechanisms;
- benchmark suites;
- acceptance gates.

Design must not reinterpret the product target downward into a simple coding assistant.

---

## 29. A1 Decision Record

```text
MILESTONE:
A1 — Codex-Class Product Definition

STATUS:
ACCEPTED

PRODUCT:
Persistent autonomous software-engineering organisation.

PRIMARY USER INTERACTION:
Objective + constraints + consequential approvals.

PRIMARY OUTPUT:
Verified, reviewable, functioning project or project change.

TARGET:
Codex-class autonomous engineering plus:
- dynamic specialist organisation
- persistent project intelligence
- integrated research
- multi-Agent teamwork
- selective parallelism
- independent assurance
- durable long-project execution
- non-code production capability

HUMAN ROLE:
Product owner / director.

REVEREND ROLE:
Researcher + architect + engineering organisation + execution harness + verifier.

STRATEGIC BENCHMARK:
Whole-project B4/B5 success, not isolated code generation.
```
