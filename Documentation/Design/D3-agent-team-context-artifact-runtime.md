# D3 — Agent, Team, Context & Artifact Runtime

> **Status:** DESIGN ACCEPTED FOR DEVELOPMENT  
> **Depends on:** A3, A4, A5, A9, A12, D1  
> **Purpose:** Define the concrete cognitive runtime that turns authoritative Tasks into bounded Specialist execution without introducing new workflow authority.

---

## 1. Core Runtime Model

Canonical flow:

~~~text
Control Plane Task
      ↓
Specialist selection
      ↓
AgentInstance creation
      ↓
effective authority + budget
      ↓
Context Broker
      ↓
Context Compiler
      ↓
ModelRequirement
      ↓
Job attempt
      ↓
bounded inference/tool loop
      ↓
typed Artifact(s) + control signal
      ↓
validation / workflow transition
~~~

Task/Job remain authoritative lifecycle state.

AgentInstance is a durable assignment identity, not a second scheduler.

---

## 2. AgentSpec Evolution

Extend existing SpecialistSpec rather than replacing it.

Target semantic contract:

~~~text
SpecialistSpec
├── id
├── version
├── name
├── role_family
├── methodology_binding
├── model_requirement
├── context_policy
├── tool_policy
├── required_capabilities
├── input_artifact_types
├── output_artifact_types
├── authority_profile
├── default_budget_policy
├── completion_contract
├── verification_policy
├── escalation_policy
├── independent_verifier
└── metadata
~~~

The current model_role field becomes a compatibility mapping during migration.

New code reasons from ModelRequirement.

---

## 3. ModelRequirement Contract

Recommended structure:

~~~json
{
  "reasoning": "high",
  "coding": "high",
  "repository_reasoning": "high",
  "tool_use": "required",
  "structured_output": "required",
  "vision": "optional",
  "min_context_tokens": 65536,
  "trust_requirement": "COMMUNITY_CLOUD_WORKER",
  "latency_class": "normal",
  "cost_class": "normal"
}
~~~

Fields are requirements, not concrete checkpoint names.

A weaker fallback may not silently violate them.

---

## 4. AgentInstance Contract

Persisted assignment:

~~~text
AgentInstance
├── agent_instance_id
├── run_id
├── task_id
├── team_id?
├── specialist_id
├── specialist_version
├── mission
├── effective_authority
├── budget_envelope
├── context_scope
├── created_at
└── closed_at?
~~~

No primary Agent status enum is required.

Presentation status derives from:

- Task status;
- latest Job status;
- blocked dependency/approval state.

---

## 5. Specialist Resolution

The Executive Orchestrator selects a Specialist based on:

- Task kind/objective;
- required Artifact outputs;
- authority needed;
- risk;
- existing Team role;
- eligible model capabilities;
- Project policy.

An LLM may propose a Specialist/Team plan, but trusted orchestration validates it.

---

## 6. Agent Budget

Recommended budget envelope:

~~~json
{
  "max_model_calls": 8,
  "max_input_tokens": 250000,
  "max_output_tokens": 32000,
  "max_tool_calls": 24,
  "max_wall_seconds": 1800,
  "max_retries": 2,
  "max_dependency_requests": 3,
  "max_cost_gbp": 2.0
}
~~~

Values vary by Specialist/Task.

Hierarchy:

~~~text
Run
→ Team
→ Task
→ Agent
→ Job / operation
~~~

A child may consume only delegated capacity.

---

## 7. Effective Authority

Compute effective authority as:

~~~text
Specialist ceiling
∩ Task policy
∩ Project policy
∩ Run owner authority
∩ current emergency state
∩ environment/provider trust
~~~

The Agent cannot widen authority through output.

Effective authority is revalidated before privileged tool execution.

---

## 8. Context Domains

The runtime distinguishes:

~~~text
Project State
Execution State
Artifacts
Evidence
Memory
Repository Intelligence
Derived Indexes
Conversation / Interaction History
~~~

The Agent never receives a generic “all memory” stream.

---

## 9. ContextItem

Recommended internal contract:

~~~text
ContextItem
├── item_id
├── layer
├── source_type
├── source_ref
├── representation
├── authority
├── trust_class
├── sensitivity
├── freshness
├── priority
├── mandatory
├── estimated_tokens
└── provenance
~~~

Text is only one representation.

Structured data can be rendered by the compiler.

---

## 10. ContextPolicy

Keep current policy semantics and add:

~~~text
max_input_tokens
allowed_layers
mandatory_layers
max_item_tokens
retrieval_budget
expansion_budget
sensitivity_ceiling
allowed_provider_trust
summary_policy
repository_disclosure_policy
~~~

Role-specific policies remain versioned with SpecialistSpec.

---

## 11. Context Broker

Responsibility:

> determine WHAT information is relevant and eligible.

Inputs:

- Task;
- Specialist;
- Project;
- Run;
- required parent Artifacts;
- repository state;
- Evidence;
- Memory/indexes.

Output:

- ranked eligible ContextItems.

Broker does not format the final model prompt.

---

## 12. Context Compiler

Responsibility:

> determine HOW eligible context fits one model invocation.

Admission order:

1. security/system constraints;
2. Task objective;
3. requirements/acceptance criteria;
4. Specialist methodology;
5. required parent Artifacts/interfaces;
6. relevant repository slices;
7. high-value Evidence;
8. accepted decisions/Memory;
9. optional history.

If mandatory authority cannot fit:

- request larger eligible model/context;
- or fail/escalate.

Never silently truncate mandatory authority.

---

## 13. ContextManifest

Every significant invocation records a bounded manifest.

~~~json
{
  "schema_version": 1,
  "context_id": "...",
  "agent_instance_id": "...",
  "job_id": "...",
  "compiler_version": 1,
  "source_refs": ["artifact:...", "file:..."],
  "omitted_refs": [],
  "estimated_input_tokens": 52100,
  "provider_input_tokens": 50780,
  "trust_class": "COMMUNITY_CLOUD_WORKER",
  "content_hash": "sha256:..."
}
~~~

The full prompt does not need indefinite persistence.

This supports reproducibility without storing hidden reasoning.

---

## 14. Repository Context

Use progressive disclosure.

Initial Developer package:

~~~text
repository map
target symbols/files
interface contracts
affected tests
Git diff/state
relevant decisions
~~~

Agent may issue ContextRequest for more slices.

Whole-repository prompt stuffing is not the default.

---

## 15. ContextRequest

Structured control message:

~~~json
{
  "type": "ContextRequest",
  "reason": "Need SessionStore implementation",
  "requested_sources": [
    {"kind": "symbol", "name": "SessionStore"}
  ],
  "max_additional_tokens": 12000
}
~~~

Expansion remains:

- authority checked;
- budget bounded;
- trust filtered.

---

## 16. Artifact Envelope

Canonical Artifact metadata lives in D1.

Cognitive Artifact schemas include:

~~~text
ResearchEvidencePack/v1
ArchitectureDecisionPack/v1
RepositoryLocalization/v1
ImplementationArtifact/v1
TestReport/v1
FailureAnalysis/v1
SecurityAssessment/v1
PerformanceReport/v1
VerificationReport/v1
~~~

Use stable typed contracts where available instead of arbitrary text handoffs.

---

## 17. Artifact Validation

Pipeline:

~~~text
Agent output
↓
parse / schema validation
↓
semantic validation
↓
store immutable Artifact
↓
optional promotion
~~~

Malformed output may trigger bounded repair.

It never silently mutates authoritative Project State.

---

## 18. Promotion

Examples:

- Architecture proposal → accepted Decision after review/policy;
- requirement extraction → Project Requirement;
- MemoryProposal → Memory record;
- implementation patch → integration candidate only after verification.

Promotion is explicit and evented.

---

## 19. Control Signals

Minimum v1 signals:

~~~text
CompletionSignal
DependencyRequest
ContextRequest
ClarificationRequest
ApprovalRequest
EscalationRequest
ConflictNotice
FailureSignal
~~~

Each contains:

- schema version;
- Agent/Task identity;
- reason code;
- bounded payload;
- Evidence/Artifact refs where relevant.

Signals propose orchestration action.

They do not mutate the DAG directly.

---

## 20. Bounded Agent Loop

~~~text
compile initial context
↓
invoke model
↓
parse proposed output/tool call
↓
if tool:
    Tool Broker policy check
    execute bounded tool
    persist observation
    compile incremental context
    repeat
else:
    validate result
    emit Artifact/control signal
    stop
~~~

Stop on:

- completion;
- blocked;
- budget exhaustion;
- cancellation;
- unrecoverable schema failure;
- approval wait.

---

## 21. Tool Call Contract

Agent-facing tool definition contains:

~~~text
tool name
input schema
output schema
risk class
required capability
side-effect class
recovery strategy
network policy
timeout
~~~

The Agent does not receive raw secret values.

Tool Broker handles enforcement.

---

## 22. Completion Contract

Specialist completion should be machine-checkable where possible.

Example Architect:

~~~json
{
  "required_artifact_type": "ArchitectureDecisionPack",
  "required_sections": [
    "requirements",
    "state_ownership",
    "alternatives",
    "failure_modes",
    "migration"
  ],
  "requires_validation": true
}
~~~

Model saying “done” is insufficient.

---

## 23. Independent Verifier

Verifier rules:

- independent_verifier=true;
- no implementation mutation tools;
- explicit acceptance criteria;
- subject Artifacts + deterministic evidence;
- no hidden implementer reasoning;
- output VerificationReport;
- reject/request repair through control signal.

Verifier may use a different model family if the Router selects it.

---

## 24. Team Model

AgentTeam is grouping/policy over Control Plane Tasks.

Persist:

- objective;
- strategy;
- parent Task;
- member Tasks/Agents;
- budget;
- concurrency envelope;
- completion/failure/disagreement policy;
- plan version.

Team never owns a second Task DAG.

---

## 25. Team Strategies

Supported identifiers:

~~~text
pipeline
parallel_decomposition
sharded
independent_replication
adversarial_review
~~~

These inform orchestration and telemetry.

They do not create separate schedulers.

---

## 26. Minimum-Sufficient-Team Formation

~~~text
one Specialist sufficient?
  yes → one Agent
  no
   ↓
useful independent decomposition?
  no → stronger/specialized Agent
  yes
   ↓
expected gain > coordination/cost?
  no → sequential
  yes → Team
~~~

Initial policy should be conservative and rule-based.

---

## 27. TeamPlan

Versioned TeamPlan Artifact:

~~~json
{
  "team_id": "...",
  "plan_version": 1,
  "members": [
    {"task_id": "...", "specialist": "developer.backend@2"}
  ],
  "dependencies": [],
  "completion_policy": "ALL_REQUIRED"
}
~~~

Replanning creates a new version and event.

---

## 28. Mutation Isolation

Parallel mutating Tasks must have compatible MutationScopes.

~~~json
{
  "workspace_id": "...",
  "branch": "reverend/run-...",
  "paths": ["src/server/**", "tests/server/**"]
}
~~~

Before concurrent admission:

- detect overlapping scopes;
- serialize conflict;
- or isolate in separate worktrees and require Integration Task.

---

## 29. Integration Task

Inputs:

- implementation Artifacts/workspaces;
- interface contracts;
- test reports.

Outputs:

- integrated workspace/ref;
- IntegrationReport;
- ConflictNotice if unresolved.

Developers never silently merge into each other's mutation scope.

---

## 30. Team Completion

Initial policies:

~~~text
ALL_REQUIRED
FIRST_VALID
SYNTHESIS_REQUIRED
SUFFICIENT_COVERAGE
~~~

Defaults:

- engineering Team → ALL_REQUIRED + explicit integration;
- research shard Team → SYNTHESIS_REQUIRED;
- speculative experiment → benchmark-defined;
- independent assurance → parent acceptance rule.

---

## 31. Disagreement

Resolution order:

1. deterministic observation;
2. source/evidence quality;
3. benchmark/simulation;
4. independent specialist adjudication;
5. human decision.

Majority vote is non-authoritative.

---

## 32. MemoryProposal

Agents cannot directly insert permanent Memory.

~~~text
MemoryProposal
├── type
├── statement
├── evidence_refs
├── proposed_scope
├── confidence
└── expiry?
~~~

Promotion validates:

- evidence;
- scope;
- duplication;
- contradiction/supersession.

---

## 33. Model Invocation Provenance

Record:

- Agent;
- Job;
- Specialist version;
- model profile;
- runtime;
- node;
- ContextManifest;
- input/output tokens;
- stop reason;
- tool-call count;
- latency;
- estimated cost.

Hidden chain-of-thought is not persisted.

---

## 34. Failure Taxonomy

Initial codes:

~~~text
MODEL_FAILURE
MODEL_INELIGIBLE
STRUCTURED_OUTPUT_FAILURE
CONTEXT_INSUFFICIENT
CONTEXT_POLICY_DENIED
TOOL_FAILURE
TOOL_DENIED
DEPENDENCY_REQUIRED
APPROVAL_REQUIRED
BUDGET_EXHAUSTED
VERIFICATION_FAILED
CANCELLED
RUNTIME_FAILURE
~~~

Executive orchestration maps these to retry/escalation/replan/terminal action.

---

## 35. Cause-Aware Retry

Examples:

~~~text
STRUCTURED_OUTPUT_FAILURE
→ bounded repair with same model

MODEL_FAILURE
→ bounded retry then alternate eligible profile

CONTEXT_INSUFFICIENT
→ approved ContextRequest

VERIFICATION_FAILED
→ Failure Investigator / repair Task

TOOL_DENIED
→ replan/escalate, not identical retry
~~~

Generic retry-everything is rejected.

---

## 36. Existing-Code Migration

### SpecialistSpec

Keep and evolve.

model_role maps to ModelRequirement during compatibility transition.

### WorkerRole

Compatibility only.

New Team/Agent runtime must not depend on a closed enum.

### WorkerOrchestrator

Preserve bounded execution ideas; outer topology authority moves to Control Plane.

### Workstation Context Compiler

Generalize its strong token-admission semantics into shared infrastructure.

### Engineering Memory

Retain records; route future writes through MemoryProposal/promotion.

---

## 37. Acceptance Tests

Must prove:

- Agent does not own workflow state;
- same Agent can retry on different model;
- mandatory context cannot silently disappear;
- ContextRequest respects budget/trust/authority;
- verifier lacks mutation tools;
- Team expansion requires orchestrator admission;
- invalid Artifact blocks promotion;
- conflicting mutation scopes serialize/isolate;
- HYPOTHESIS does not become FACT automatically;
- Agent budget exhaustion emits deterministic signal;
- model output cannot directly modify Project decisions.

---

## 38. Exit Condition

C4 is ready when a Task can be assigned to a versioned Specialist, run as AgentInstance, receive bounded context, invoke an eligible model through an abstract router, use mediated tools, produce typed Artifacts/control signals, and participate in a bounded Team without becoming a second workflow authority.


---

## 39. Recursive Audit Cycle 2 — Context Isolation, Human Blocking and Mutation Enforcement

### Clarification lifecycle

`ClarificationRequest` creates a D1 `human_input_requests` record and a Task blocker.

It is not represented as Approval.

If useful independent Tasks remain ready, the Run may continue while the requesting Task is BLOCKED. The Run enters `AWAITING_INPUT` only when clarification is the aggregate reason no useful work can proceed.

### Project-scoped memory is the default

Automatic Memory promotion defaults to `PROJECT` scope.

`USER` or `GLOBAL` promotion requires explicit policy and stronger validation because it can affect unrelated Projects.

Context Broker must never retrieve:

- another Project's Project-scoped Memory;
- another user's User-scoped Memory;
- Global Memory that current policy has not admitted.

Semantic similarity cannot override scope authorization.

### External content remains untrusted data

Research pages, repository comments/issues, dependency metadata and other externally supplied text retain trust labels through ContextItem and ContextManifest.

The Context Compiler places untrusted content below system/authority instructions and marks it as data. Instructions found inside such content do not gain tool or policy authority.

### ContextManifest durability

Every model invocation references an immutable `ContextManifest` Artifact.

The manifest records source refs/hashes and transformations, but not hidden chain-of-thought.

This closes the provenance chain:

~~~text
Task
→ AgentInstance
→ Job
→ ContextManifest Artifact
→ model invocation
→ output Artifact
~~~

### MutationScope is enforced, not advisory

A model/Agent may propose a MutationScope, but trusted orchestration normalizes it.

Every mutating filesystem/Git tool validates the actual target path/ref against the effective MutationScope before change.

After implementation, the produced diff is checked again against the scope.

Out-of-scope mutation:

- fails the tool/Task;
- creates a policy/security Event;
- cannot be accepted merely because tests pass.

### Parallel Team blocking

A single Team member entering Approval/Human-input wait does not automatically suspend unrelated members.

Team completion policy decides whether remaining members can proceed; the top-level Run only enters an aggregate zero-compute waiting state when no useful admitted work remains.


---

## 40. Recursive Audit Cycle 6 — Sensitivity Propagation

Context trust is computed from durable source sensitivity plus execution destination trust.

Rules:

1. Project repository slices inherit the Project disclosure policy.
2. Artifact-derived ContextItems inherit `Artifact.sensitivity_label`.
3. Summaries/compressions inherit the strongest sensitivity of their source set.
4. Combining PUBLIC and RESTRICTED material produces RESTRICTED output unless trusted declassification explicitly proves otherwise.
5. Memory promotion preserves sensitivity/provenance.
6. Semantic retrieval cannot downgrade a label.
7. If mandatory context is too sensitive for an otherwise eligible DeploymentProfile/worker, the Router/Compute Scheduler rejects that destination rather than silently omitting mandatory context.

External/untrusted content trust labels and confidentiality sensitivity are separate dimensions and both are preserved.


---

## 41. Capability Modernization Integration

D15 is the canonical Context Broker refinement for Cloud v1.

Agent runtime changes:

- Agent asks for ContextNeed/ContextRequest, not physical database/vector/browser operations;
- Research Fabric and Repository Intelligence are deterministic/capability services beneath the Agent;
- Team strategies may partition Research/Repository work, but member Tasks remain canonical Control Plane Tasks;
- Context acquisition does not create a new Agent merely because a provider/index query exists;
- browser/search/LSP/index operations are tools/capabilities and consume delegated budgets;
- model escalation is not used to compensate for missing evidence or missing repository facts.

New typed output families may include:

~~~text
ResearchEvidencePack
SourceSnapshotReference
RepositoryMap
RepositoryLocalization
SymbolContext
DiagnosticContext
ChangeImpactReport
BrowserTestReport
CapabilityExecutionReport
~~~

These remain normal D3 Artifacts with provenance/validation/promotion semantics.


---

## 42. Capability Result Validity & Late-Result Semantics

Cloud capabilities are asynchronous and may finish after the originating Task was cancelled, replanned, retried or superseded.

Every capability execution result therefore carries:

~~~text
run_id
task_id
job_id
attempt_number
agent_instance_id?
input snapshot/version refs
capability id/version
result digest
completed_at
~~~

Before any result can affect current Task/Run state, trusted orchestration revalidates:

- the Job attempt is still current/eligible;
- required RepositorySnapshot/SourceSnapshot/policy versions still match;
- Task has not been cancelled/superseded;
- result scope matches Run/Project;
- result Artifact passed schema/policy validation.

A late valid result may be retained as historical evidence/cache material, but **cannot silently complete or promote a newer Task attempt**.

This applies equally to:

- web research;
- browser tests;
- repository indexing/LSP queries;
- build/test workers;
- model inference;
- simulations/media workers.


---

## 43. Specification-Driven Engineering Mode

The preferred high-reliability workflow is:

~~~text
Human / external design intelligence
        ↓
SpecificationPackage
        ↓
Specification validation + normalization
        ↓
Requirements / Decisions / AcceptanceCriteria
        ↓
Run
        ↓
Task DAG
        ↓
Agent / Team implementation
        ↓
build / test / diagnose / repair
        ↓
independent verification
        ↓
integration / documented result
~~~

This formalizes the useful separation between **design intelligence** and **implementation throughput** without making Reverend dependent on any specific external model vendor.

### 43.1 SpecificationCompiler

A deterministic/trusted orchestration service compiles an ACCEPTED SpecificationPackage into implementation inputs.

It may use model assistance for extraction, but trusted code validates output.

Outputs include:

~~~text
Requirement set
AcceptanceCriteria set
Architecture/Interface Artifacts
Constraint set
initial Task DAG proposal
unresolved ambiguity list
Context seed references
~~~

The compiler does not execute implementation work.

### 43.2 Specification validation

Validation checks:

- manifest/schema;
- duplicate/conflicting requirements;
- missing required sections for the selected Project policy;
- acceptance criteria coverage;
- interface/data-contract references;
- security/failure-semantics presence when required;
- impossible/inconsistent constraints where deterministically detectable;
- unresolved ambiguity.

The system does not claim that structural validation proves the architecture itself is good.

### 43.3 Run behavior from specification

For a specification-driven Run:

- pinned specification version is mandatory context authority;
- Tasks derive acceptance and constraints from normalized Project objects;
- implementation Agents receive only relevant specification slices;
- whole package is not dumped into every prompt;
- Repository Intelligence and Research Fabric fill implementation facts, not rewrite accepted design authority.

### 43.4 EscalationArtifact

When Reverend is stuck after bounded attempts or discovers an architectural ambiguity, it emits a typed escalation:

~~~text
EscalationArtifact
├── Run / Task
├── pinned SpecificationPackage/version
├── relevant contract/requirement refs
├── attempts made
├── deterministic failures/evidence
├── candidate explanations
├── exact decision/question required
├── cost/budget consumed
└── recommended next action
~~~

The consumer may be:

- the human;
- an optional frontier/external design model;
- a designated Architect Specialist.

The response becomes an explicit amendment/Decision/clarification Artifact and is validated before use.

### 43.5 External frontier model is optional, not in-loop authority

A workflow such as:

~~~text
human + frontier model
→ design
→ accepted SpecificationPackage
→ Reverend implementation
~~~

is a first-class usage pattern.

However:

- Reverend does not require OpenAI/GPT/Codex to operate;
- external design models are replaceable adapters/tools;
- their output is not authority until accepted/promoted;
- routine implementation/debugging stays within Reverend unless escalation is warranted;
- external API use follows Project disclosure/cost policy.

### 43.6 Deterministic reality remains the final gate

Even a perfect specification does not make model output correct.

The implementation loop remains:

~~~text
inspect
→ implement
→ compile/build
→ test
→ observe
→ diagnose
→ repair
→ verify
→ integrate
~~~

Compilers, tests, benchmarks, simulations, linters and integration checks outrank Agent confidence.

### 43.7 Specification drift

If implementation discovers that satisfying one requirement would violate another or the accepted architecture cannot be implemented as written:

- do not silently reinterpret the specification;
- emit ConflictNotice/EscalationArtifact;
- block the affected Task;
- continue unrelated safe work if possible;
- require a durable Decision/specification amendment.

This prevents “helpful” autonomous drift from changing the Project design.
