# A5 — Context, Memory & Agent Communication

> **Programme:** Reverend Cloud Analysis  
> **Milestone:** A5  
> **Status:** ACCEPTED  
> **Owner:** Backend / systems track  
> **Document purpose:** Define Reverend's information architecture: what is authoritative, what counts as evidence or memory, what an Agent receives, and how Agents/Teams communicate without creating context explosion.  
> **Important:** This document defines semantic information domains. Exact storage engines, database schemas, embedding systems, cache implementations, and retrieval algorithms belong to the Design Phase.

---

## 1. Executive Decision

Reverend does **not** have one giant memory.

It has distinct information classes with different:

- authority;
- lifetime;
- scope;
- provenance;
- truth status;
- retrieval policy.

Agents receive **temporary compiled projections** of these information domains.

They do not receive the entire Reverend state by default.

The canonical information architecture is:

```text
1. AUTHORITATIVE PROJECT STATE
2. AUTHORITATIVE EXECUTION STATE
3. ARTIFACT FABRIC
4. EVIDENCE FABRIC
5. MEMORY FABRIC
6. RECONSTRUCTIBLE INDEX / RETRIEVAL STATE
7. EPHEMERAL AGENT CONTEXT
```

This distinction is one of the most important foundations of the entire Cloud architecture.

---

## 2. Existing Reverend Foundations

The current repository already contains useful pieces of this architecture.

### Workstation Context Compiler

Existing behavior includes concepts such as:

- non-evictable system/task/request layers;
- token safety margin;
- reserved output tokens;
- layer-specific caps;
- clipping;
- omission telemetry;
- failure if authoritative content cannot fit safely.

Optional layers already include concepts similar to:

```text
checkpoint
evidence
project context
memory context
recent history
retrieved history
summary
```

### Engineering Memory

Current typed memory includes:

```text
FACT
DECISION
EXPERIMENT
FAILURE
RESULT
USER_CONSTRAINT
```

and metadata such as:

- project scope;
- source;
- evidence;
- task;
- commit;
- model;
- confidence;
- expiry;
- archival.

### Evidence System

Current intelligence/research infrastructure distinguishes evidence trust/source classes such as:

```text
PERSONAL
PROJECT
REFERENCE
FRESH
```

and uses provenance/relevance gating.

### Control Plane Artifacts

Artifacts already contain useful semantics including:

- producer Job;
- parent artifacts;
- content hash;
- provenance;
- validation state;
- promotion state.

A5 unifies these semantics rather than replacing them with one generic vector database.

---

## 3. Why One “Memory” Store Is Dangerous

Current Reverend has multiple places that can look memory-like:

- Control Plane artifacts;
- Engineering Memory;
- Workstation task state;
- conversation history;
- repository indexes;
- research evidence;
- checkpoints;
- knowledge registries.

These are not equally authoritative.

If everything is flattened into:

```text
vector database
```

then Reverend can retrieve:

- stale decisions;
- unverified hypotheses;
- conversation comments;
- old failures;
- current requirements;

as if they were equivalent.

A5 therefore freezes semantic separation before retrieval implementation.

---

## 4. Authoritative Project State

Project State answers:

> **What is this project currently supposed to be?**

Examples:

```text
project identity
repository identity
project membership

current requirements
hard constraints
acceptance criteria
non-goals

accepted architecture decisions
accepted product decisions

active interface contracts
project policy
active configuration
```

This is not ordinary memory.

A current requirement should not require semantic search to be “remembered.”

---

## 5. Requirements Become First-Class Durable State

A1 established that long projects must resist goal drift.

Future semantics should therefore support durable requirement identity.

Conceptually:

```text
Requirement
├── requirement_id
├── project_id
├── statement
├── source
├── status
├── priority
├── acceptance_refs
├── version
└── supersedes?
```

The exact schema is Design work.

The semantic requirement is frozen.

---

## 6. Accepted Decisions Become First-Class

Important architecture/product decisions should have durable identity and supersession.

Example:

```text
ADR-14

Decision:
Use PostgreSQL for authoritative run state.

Reason:
multiple independent writers required.

Supersedes:
ADR-09
```

Normal Agent context should retrieve the current accepted decision.

Historical decisions remain available for audit.

---

## 7. Authoritative Execution State

Execution State answers:

> **Where is this Run currently up to?**

Examples:

```text
Workflow
Task DAG
Task states
Jobs
Team assignments
pending approvals
budgets
leases
checkpoint refs
retry counters
blocked dependencies
```

The Control Plane is authoritative.

A checkpoint or current step is not automatically permanent Project knowledge.

This distinction is essential for A7 recovery.

---

## 8. Artifact Fabric

Artifacts are durable outputs of work.

Examples:

```text
EvidencePack
ProductDecisionPack
ArchitectureDecisionPack
RepositoryLocalization
ImplementationPatch
TestReport
SecurityAssessment
PerformanceReport
FailureAnalysis
VerificationReport
AssetArtifact
```

Each artifact should preserve:

```text
artifact id
artifact type/schema version
producer
parent artifacts
project/run/team/task/job lineage
content hash
provenance
validation state
promotion state
created time
```

---

## 9. Artifact Content Is Conceptually Immutable

If an architecture proposal changes:

```text
ArchitectureDecisionPack v1
```

does not silently mutate.

Instead:

```text
v1
 ↓ superseded by
v2
```

This preserves reproducible history.

---

## 10. Artifact ≠ Authoritative State

An Architect generating:

```text
ArchitectureDecisionPack
```

does not automatically make it Project truth.

Expected flow:

```text
generated artifact
   ↓
review / validation / policy
   ↓
promotion
   ↓
accepted Project decision
```

The existing validation/promotion distinction should survive.

---

## 11. Evidence Fabric

Evidence is information whose value depends on its source and provenance.

Useful semantic classes remain:

### PERSONAL

- user-provided document;
- private specification;
- private note.

### PROJECT

- repository file;
- Git history;
- test result;
- benchmark result;
- project documentation.

### REFERENCE

- stable manual;
- textbook;
- standard;
- archived technical reference.

### FRESH

- current vendor documentation;
- release announcement;
- current web research;
- fresh academic paper.

The exact retrieval tools can change.

The semantic classes remain valuable.

---

## 12. Evidence Provenance Must Survive End-to-End

Relevant evidence should retain metadata such as:

```text
claim / span
source
source class
retrieved time
authority
support type
content reference/hash
freshness metadata
```

Provenance should survive:

```text
retrieval
 → selection
 → context
 → Agent artifact
 → downstream artifact
```

---

## 13. Generated Synthesis Is Not Evidence

Example:

```text
Researcher reads 5 papers
   ↓
produces summary
```

The summary is:

```text
GENERATED SYNTHESIS
```

The papers remain:

```text
EVIDENCE
```

A downstream Architect can consume both.

But Reverend must never silently transform:

```text
model said X
```

into:

```text
source proves X
```

---

## 14. Memory Fabric

Memory answers:

> **What useful historical information should Reverend preserve so future work does not have to rediscover it?**

Canonical semantic record types should include:

```text
FACT
DECISION
EXPERIMENT
FAILURE
RESULT
USER_CONSTRAINT
HYPOTHESIS
```

`HYPOTHESIS` is especially important because unverified conclusions must not become Facts.

---

## 15. Memory Is Not Automatically Truth

Example:

```text
HYPOTHESIS:
GPU synchronization may be causing instability.

support:
FailureAnalysis #81

status:
unverified
```

must not later become:

```text
FACT:
GPU synchronization causes instability.
```

Type and provenance survive retrieval.

---

## 16. Memory Promotion

Preferred flow:

```text
Agent
 ↓
MemoryProposal
 ↓
memory policy / validation
 ↓
accepted memory record
```

Agents do not directly dump arbitrary model thoughts into durable memory.

---

## 17. Memory Scope

Useful scopes include:

```text
USER
PROJECT
GLOBAL / EXPERIENCE
```

### Project Memory

Examples:

- AstraFlow solver failed under configuration X;
- dependency Y was rejected;
- benchmark Z improved performance;
- project API contract changed.

### Global Experience Memory

Examples:

- recurring CMake failure pattern;
- reusable migration lesson;
- cross-project testing strategy.

Global promotion should be stricter because project-specific conclusions may not generalize.

---

## 18. Memory Lifetime

Records may support states such as:

```text
ACTIVE
ARCHIVED
SUPERSEDED
EXPIRED
```

Historical records remain inspectable.

They should not pollute normal current context after supersession.

---

## 19. Event Log vs Artifact vs Memory vs Project State

A5 freezes these distinctions:

```text
EVENT LOG
"What happened?"

ARTIFACT
"What was produced?"

MEMORY
"What is worth remembering for later?"

PROJECT STATE
"What is currently authoritative?"
```

These are different questions.

Reverend needs all four.

---

## 20. Reconstructible Index / Retrieval State

Examples:

```text
embeddings
vector indexes
lexical indexes
symbol indexes
repository maps
semantic caches
reranking caches
model caches
```

These are **derived state**.

If lost:

```text
Reverend may be slower while rebuilding
```

but Reverend should not forget:

- requirements;
- accepted decisions;
- artifact history;
- evidence provenance.

---

## 21. Vector Database Is Not “The Memory”

Rejected architecture:

```text
Everything
  ↓
one vector database
  ↓
nearest 20 chunks
  ↓
every Agent
```

This loses:

- authority;
- provenance;
- scope;
- freshness;
- epistemic status;
- lifetime.

Vector retrieval remains useful.

It operates inside a typed information architecture.

---

## 22. Ephemeral Agent Context

A3 Agents receive a temporary Job-specific `ContextEnvelope`.

Conceptually:

```text
ContextEnvelope
├── system / security constraints
├── Task objective
├── acceptance criteria
├── Specialist methodology
│
├── required upstream artifacts
├── selected Project State
├── selected repository context
├── selected Evidence
├── selected Memory
├── execution / checkpoint information
└── provenance references
```

This is constructed for:

```text
one Agent
one Task
one Job
one model context window
```

---

## 23. Context Is a Projection, Not a Store

Canonical direction:

```text
Durable stores
    ↓
retrieval / selection
    ↓
Context Broker
    ↓
Context Compiler
    ↓
ContextEnvelope
```

Agents do not “write to context.”

They publish:

- artifacts;
- control signals;
- memory proposals.

Context is regenerated when needed.

---

## 24. Context Priority Hierarchy

### Tier 0 — Non-Evictable Authority

```text
system constraints
security constraints
Task objective
hard requirements
acceptance criteria
```

### Tier 1 — Required Task Inputs

```text
required parent artifacts
interface contracts
current relevant workspace/repository state
```

### Tier 2 — High-Value Support

```text
selected evidence
relevant accepted decisions
relevant Project Memory
```

### Tier 3 — Optional Support

```text
older history
background references
summaries
global experience
```

### Tier 4 — Omit First

```text
low-relevance history
redundant context
weakly related Memory
```

If Tier 0 cannot fit safely:

> **do not silently truncate authority**

Use a larger eligible model/context, or fail/escalate.

---

## 25. Large Context Windows Do Not Remove Selection

Even a 256K or 1M model window has costs:

- prefill latency;
- KV memory;
- VRAM;
- monetary cost;
- attention noise.

Therefore:

> **Context size is a budget to use intelligently, not a target to fill.**

---

## 26. Role-Specific Context

Different Specialists need different information.

### Researcher

May need:

- research question;
- prior evidence;
- source policy.

### Developer

Needs:

- requirements;
- architecture/interface artifact;
- relevant files/symbols;
- tests;
- recent failures.

### Security Reviewer

Needs:

- architecture;
- trust boundaries;
- implementation/diff;
- dependency information.

### Verifier

Needs:

- requirements;
- acceptance criteria;
- implementation;
- observed evidence;
- tests.

But does not need private Developer persuasion.

---

## 27. Independent Assurance Context Isolation

Verifier context should generally include:

```text
objective
requirements
acceptance criteria
implementation
tests
observable evidence
relevant architecture
```

and avoid unnecessary:

```text
developer confidence
private failed reasoning
developer's preferred interpretation
```

This preserves independent review.

---

## 28. Agent-to-Agent Communication

Default flow:

```text
Agent A
  ↓
Artifact A
  ↓
Control Plane records lineage
  ↓
Task B references Artifact A
  ↓
Context Compiler extracts relevant representation
  ↓
Agent B
```

Agent B does **not** need Agent A's full conversation transcript.

---

## 29. Free-Form Shared Agent Chat Is Rejected as Canonical

Rejected pattern:

```text
Agent A ↔ Agent B ↔ Agent C ↔ Agent D
```

with arbitrary durable natural-language conversation.

Problems:

- unbounded context;
- weak provenance;
- hidden dependencies;
- difficult recovery;
- hard-to-reproduce results;
- unclear truth status.

Lightweight structured control messages are allowed.

---

## 30. Structured Control Messages

Examples:

```text
DependencyRequest
ContextRequest
ClarificationRequest
ApprovalRequest
EscalationRequest
ConflictNotice
CompletionSignal
```

These are small typed Control Plane messages.

They are not free-form Team chat.

---

## 31. Reference Over Copying

If several Agents need the same artifact:

```text
ArchitectureDecision #32
   ├── ref → Backend Task
   ├── ref → Frontend Task
   └── ref → Test Task
```

Do not create three durable copies.

Each Context Compiler retrieves the appropriate representation.

---

## 32. Artifact Representations

A large artifact may support:

```text
canonical full artifact
compact summary
indexed sections
selected slices
```

The canonical artifact remains the source.

Summaries are derived and lossy.

---

## 33. Summaries Retain Source References

A Summary should preserve:

```text
source refs
producer
compiler/summarizer version
created time
```

If a critical decision depends on exact wording:

```text
retrieve original source
```

rather than relying on the summary.

---

## 34. Progressive Context Compression

Preferred order:

```text
deduplicate
   ↓
select relevant items
   ↓
select relevant spans
   ↓
use compact representations
   ↓
summarize lower-value history
   ↓
omit lowest-value material
```

Blind clipping is a last resort.

---

## 35. Repository Context

Developer context should usually include:

```text
repository map
relevant symbols
relevant files/spans
interfaces
affected tests
dependency information
Git state/diff
```

not:

```text
entire repository text
```

Repository intelligence remains distinct from generic Memory.

---

## 36. Progressive Repository Disclosure

Preferred pattern:

```text
Repository Map
   ↓
symbol/file localization
   ↓
relevant slices
   ↓
Agent requests additional file/context if needed
```

This makes long projects scalable.

---

## 37. ContextRequest Does Not Bypass Policy

An Agent requesting:

```text
all environment files and secrets
```

does not automatically receive them.

Admission still considers:

- authority;
- sensitivity;
- provider trust;
- task relevance;
- token budget.

---

## 38. Secrets Are Outside Normal Context and Memory

Examples:

```text
API keys
GitHub credentials
SSH keys
cloud provider tokens
cookies
```

should not be stored in ordinary:

- memory;
- artifact text;
- conversation history;
- model context;

unless a tightly controlled operation requires a scoped secret capability.

A8 owns the final secret architecture.

---

## 39. Trust-Aware Context

Future context items should be classifiable by:

```text
scope
trust class
sensitivity
provenance
authority
freshness
```

Then Context admission can ask:

```text
Is this Agent allowed to see it?
Is this inference provider allowed to receive it?
```

This becomes critical when execution can occur on private cloud or external APIs.

---

## 40. Conversation History Is Not Project Truth

A casual chat message does not automatically become:

```text
authoritative requirement
```

If a conversation introduces an important constraint, Reverend should promote it into:

- Project State;
- accepted Memory;
- decision artifact;

as appropriate.

Otherwise it remains interaction history.

---

## 41. Workstation State Migration

A0 identified overlapping Workstation authoritative-task state.

Useful information should move to canonical owners:

```text
requirements / accepted decisions
→ Project State

workflow / completed / current step
→ Control Plane

checkpoint
→ Execution / Recovery State
```

The Workstation becomes a presentation/client layer over those authorities.

---

## 42. Memory Retrieval Must Be Authority-Aware

Future retrieval scoring may consider:

```text
task relevance
semantic similarity
lexical similarity
memory type
scope
current/superseded status
provenance
authority
freshness
```

An old FAILURE record should not outrank a current accepted DECISION merely because its embedding is closer.

---

## 43. Temporal Validity

Some information is stable:

```text
Project uses C++20.
```

Some is time-sensitive:

```text
Dependency X is currently version 4.2.
```

Records should support:

- validity;
- supersession;
- expiry;

where appropriate.

---

## 44. Contradictions Are Not Silently Collapsed

If Reverend has:

```text
Decision A:
Use SQLite

Decision B:
Use PostgreSQL
```

then current retrieval should normally understand:

```text
B supersedes A
```

rather than return both as equally current.

Historical A remains available for audit.

Similarly, conflicting external evidence should remain explicitly conflicting until resolved.

---

## 45. Memory Deduplication

Swarm execution increases duplicate-memory risk.

Bad:

```text
five Researchers
→ five copies of "library X is deprecated"
```

Better:

```text
one canonical Memory/Evidence claim
with multiple supporting references
```

Exact deduplication algorithm is deferred.

---

## 46. Memory Writes Should Be Sparse

The Control Plane already records events.

Memory should not become a second event log.

Long-term Memory should store future-useful conclusions such as:

- decision;
- failure lesson;
- experiment result;
- durable project fact;
- persistent user constraint.

Routine execution details stay in Run/Task/Artifact history.

---

## 47. Global Experience Learning

Cross-project learning should use controlled promotion:

```text
failure / result
   ↓
validated lesson
   ↓
ExperienceMemory proposal
   ↓
promotion
```

Not:

```text
Agent fails once
→ writes global rule
→ every future project obeys it
```

This avoids uncontrolled self-modification.

---

## 48. Context Caching

Some derived context representations may be reusable.

Examples:

```text
repository map
architecture summary
stable requirements summary
```

But derived caches must record source versions/hashes.

Conceptually:

```text
DerivedRepresentation
├── source IDs
├── source hashes
├── compiler version
└── generated representation
```

If sources change:

```text
cache becomes stale
```

---

## 49. Prefix/KV Cache Is Not Durable State

A9/A10 may use inference prefix caching for performance.

But:

```text
KV cache
```

remains disposable compute state.

The information architecture must reconstruct Agent context without it.

This preserves A0's replaceable-compute invariant.

---

## 50. Team Communication Across Milestones

A4 Team flow becomes:

```text
Discovery Team
  ↓
EvidencePack

Product Team
  ↓
ProductDecisionPack

Architecture
  ↓
ArchitectureDecisionPack

Engineering Team
  ↓
Implementation artifacts

Assurance Team
  ↓
Verification artifacts
```

The internal Team transcripts do not need to follow the project forever.

---

## 51. Artifact Lineage as Project Knowledge Graph

Without building a special graph-database product immediately, Reverend already naturally creates:

```text
Requirement
   ↓
Evidence
   ↓
Architecture Decision
   ↓
Implementation
   ↓
Test Report
   ↓
Verification
```

This lineage is more valuable than an undifferentiated vector store.

Future impact analysis can potentially answer:

```text
Requirement R8 changed.
What downstream work depends on it?
```

through explicit references.

---

## 52. Context Manifest

A useful future concept:

```text
ContextManifest
├── context_id
├── agent_id
├── job_id
├── broker/compiler version
├── source refs[]
├── selected sections[]
├── omitted refs[]
├── token estimates
├── actual provider tokens
├── trust/sensitivity decision
└── content hash
```

This supports observability and reproducibility without requiring indefinite storage of every full prompt.

---

## 53. Broker vs Compiler

A5 preserves two distinct responsibilities.

### Context Broker

```text
WHAT information is eligible and relevant?
```

Responsible for:

- retrieval;
- ranking;
- filtering;
- scope;
- relevance;
- evidence/memory selection.

### Context Compiler

```text
HOW does the selected information fit one invocation?
```

Responsible for:

- authority ordering;
- formatting;
- token admission;
- compression;
- provider-specific envelope construction.

The current strongest compiler lives under Workstation code; the future canonical compiler should become shared runtime/intelligence infrastructure.

---

## 54. Recovery Implications

A7 should preserve durable references to:

- Task state;
- artifact state;
- Project State;
- Memory references;
- workspace state;
- context source references where useful.

It does **not** need to preserve:

- live KV cache;
- hidden model reasoning;
- in-process retrieval objects.

A new worker can reconstruct the ContextEnvelope.

---

## 55. Swarm Scalability Implication

This A5 architecture is what makes A4 feasible.

Ten Researchers should not create:

```text
10 × entire project state
+
10 × all previous Agent transcripts
```

Instead:

```text
each gets narrow ContextEnvelope
each produces artifacts
Synthesizer reads relevant outputs
```

The total information topology stays bounded.

---

## 56. Context Economics

Every call has:

```text
input tokens
+
output tokens
+
KV cache / VRAM
+
latency
+
monetary cost
```

Context optimization therefore affects both reasoning quality and cloud economics.

A6/A9/A10/A11 can consume context telemetry.

---

## 57. Retrieval Is Demand-Driven

Preferred pattern:

```text
initial compact context
   ↓
Agent identifies uncertainty
   ↓
ContextRequest / lookup
   ↓
specific additional material
```

This is more scalable than preloading everything.

Context expansion is still bounded by Agent budget.

---

## 58. Benchmark Hypotheses

### H1
Artifact-based Agent communication gives better B4/B5 performance per £ than shared long transcripts.

### H2
Hybrid lexical + semantic retrieval outperforms pure vector retrieval for Project Memory.

### H3
Persistent Project Memory reduces repeated investigation and repair.

### H4
Role-specific context policies improve quality over one global policy.

### H5
Verifier context isolation reduces correlated errors.

### H6
Progressive repository disclosure reduces token cost without lowering success.

These require later measurement.

---

## 59. Frozen A5 Requirements

```text
A5-01
Reverend does not model all persistent information as one generic memory store.

A5-02
Project State, Execution State, Artifacts, Evidence, Memory, Derived Indexes,
and Agent Context are distinct domains.

A5-03
Accepted requirements and decisions are first-class durable state.

A5-04
Control Plane remains authoritative for execution state.

A5-05
Artifacts are immutable/versioned and provenance-tracked.

A5-06
Generated artifacts require validation/promotion before becoming authoritative where applicable.

A5-07
Evidence retains source/trust/provenance semantics end-to-end.

A5-08
Generated synthesis is not automatically evidence.

A5-09
Memory records are typed and provenance-backed.

A5-10
HYPOTHESIS remains distinct from FACT.

A5-11
Agents propose Memory; policy governs durable promotion.

A5-12
Memory is scoped.

A5-13
Global experience requires stricter promotion than Project Memory.

A5-14
Memory supports supersession, expiry, and archival.

A5-15
Indexes and embeddings are reconstructible derived state.

A5-16
An Agent receives a temporary ContextEnvelope per Job.

A5-17
Context is a projection over durable state, not authority itself.

A5-18
System constraints, Task objective, hard requirements, and acceptance criteria are non-evictable.

A5-19
If authoritative context cannot fit, Reverend escalates/fails rather than silently truncating it.

A5-20
Large model windows do not eliminate selective retrieval.

A5-21
Context policy is role-specific.

A5-22
Independent assurance may use intentionally isolated context.

A5-23
Agents communicate substantive results primarily through typed artifacts.

A5-24
Free-form shared Agent chat is non-canonical.

A5-25
Structured control messages are permitted.

A5-26
Shared artifacts are referenced rather than duplicated.

A5-27
Summaries retain source references.

A5-28
Repository context uses progressive localization.

A5-29
Context access is constrained by authority, sensitivity, and trust.

A5-30
Secrets are not ordinary Memory/Context.

A5-31
Inference-provider trust participates in context admission.

A5-32
Conversation history does not automatically become Project truth.

A5-33
Event history, artifacts, Memory, and Project State remain distinct.

A5-34
Long-term Memory writes are sparse and future-useful.

A5-35
Context expansion / retrieval loops are budget-bounded.

A5-36
Context decisions are observable and benchmarkable.

A5-37
Context Broker and Context Compiler remain distinct responsibilities.

A5-38
Canonical Context Compiler becomes shared infrastructure.

A5-39
Team communication uses artifact fan-out/fan-in with provenance.

A5-40
Agent context can be reconstructed on fresh compute from durable sources.
```

---

## 60. Current-Code Migration Classification

| Current construct | Direction |
|---|---|
| Workstation Context Compiler V2 | KEEP SEMANTICS; GENERALIZE |
| Specialist ContextPolicy | KEEP + EXTEND |
| ContextBroker | KEEP + EXTEND |
| mandatory context layers | KEEP |
| token reserve / safety margin | KEEP |
| layer-specific token caps | GENERALIZE BY ROLE |
| Control Plane artifacts | CANONICAL — KEEP + EXTEND |
| artifact parent lineage | KEEP |
| validation/promotion | KEEP |
| evidence classes | KEEP + EXTEND |
| research provenance | KEEP |
| Engineering Memory | KEEP SEMANTICS; INTEGRATE |
| current FTS5-only retrieval | IMPLEMENTATION DETAIL |
| missing HYPOTHESIS memory type | ADD LATER |
| Workstation authoritative Task state | DECOMPOSE INTO CANONICAL OWNERS |
| conversation history | KEEP AS INTERACTION HISTORY |
| repository/vector indexes | KEEP AS RECONSTRUCTIBLE DERIVED STATE |
| one generic vector-memory store | REJECT |
| shared Agent scratchpad | REJECT |
| mandatory full prompt persistence | REJECT |
| ContextManifest | NEW |
| structured requirements/decisions | EXTEND / NEW PROJECT STATE |

---

## 61. Design-Phase Implications

The Design Phase must define:

- Project State schema;
- Requirement/Decision semantics;
- Artifact schemas/versioning;
- Evidence references;
- MemoryProposal and promotion;
- Memory scopes/lifetime;
- index rebuild semantics;
- Context Broker interface;
- Context Compiler interface;
- ContextManifest;
- role-specific context policies;
- provider-trust-aware filtering;
- repository progressive disclosure;
- secret references.

The implementation should not place all these semantics behind a single generic “memory retrieval” API.

---

## 62. A5 Decision Record

```text
MILESTONE:
A5 — Context, Memory & Agent Communication

STATUS:
ACCEPTED

CORE PRINCIPLE:
Reverend information is typed by authority, provenance, scope, and lifetime.
It is not one giant memory.

CANONICAL DOMAINS:
1. Project State
2. Execution State
3. Artifact Fabric
4. Evidence Fabric
5. Memory Fabric
6. Derived Index / Retrieval State
7. Ephemeral Agent Context

AGENT INPUT:
Job-specific ContextEnvelope

AGENT COMMUNICATION:
Typed artifacts + structured control signals

MEMORY:
Sparse, typed, scoped, provenance-backed, promotable.

CONTEXT:
Selected projection of Reverend state, not a source of truth.

REPOSITORY:
Progressive localization and retrieval.

SECRETS:
Outside ordinary Memory/Context.

RECOVERY:
Reconstruct context from durable references rather than preserving live model state.

REJECTED:
- giant universal vector store
- shared Agent scratchpad
- unrestricted shared Team chat
- whole repository in every prompt
- conversation history as Project truth
```
