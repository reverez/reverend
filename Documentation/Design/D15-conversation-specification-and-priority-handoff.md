# D15 — Conversation, Specification & Priority Handoff Contract

> **Status:** DESIGN ACCEPTED FOR DEVELOPMENT  
> **Depends on:** A12, D1, D2, D3, D5, D6, D13, ADR-001, ADR-002  
> **Purpose:** Define the ChatGPT-style interaction surface, durable conversation objects, BuildSpecification contract, manual frontier-design boundary and safe global Run priority handoff.

---

## 1. Product Interaction Goal

Reverend Cloud should feel conversational to both developers while preserving server-authoritative engineering state.

Canonical user flow:

~~~text
user
  ↓
Chat / attachments
  ↓
analysis or accepted BuildSpecification
  ↓
one globally active Run
  ↓
Task DAG / Agents / Tools
  ↓
Artifacts / tests / verification
  ↓
conversation-visible progress and results
~~~

The chat surface is the primary product interface.

Chat is not the workflow database.

---

## 2. Cloud-Only Client Rule

Production clients are thin presentation/input surfaces.

Allowed client responsibilities:

- render authenticated UI;
- send messages/commands;
- upload attachments;
- answer clarification requests;
- approve actions when authorized;
- inspect/download Artifacts;
- render server state and SSE updates.

Disallowed production client responsibilities:

- LLM or embedding inference;
- repository indexing;
- builds/tests;
- sandbox execution;
- media generation;
- provider lifecycle;
- authoritative project state;
- required disaster-recovery replication.

Closing every client does not affect an active Run.

---

## 3. Conversation Model

A Conversation is durable Project-scoped interaction history.

Recommended contract:

~~~text
Conversation
├── conversation_id
├── project_id
├── title
├── created_by_user_id
├── visibility
├── created_at
├── archived_at?
└── metadata

Message
├── message_id
├── conversation_id
├── author_kind
├── author_user_id?
├── body_ref / bounded inline_body
├── created_at
├── edited_from_message_id?
├── referenced_artifact_ids[]
├── referenced_run_ids[]
└── metadata
~~~

Initial visibility values:

~~~text
PROJECT
PRIVATE
~~~

A Project conversation is readable by Project members subject to policy.

A private conversation is readable only by the owning user unless explicitly shared later.

---

## 4. Interaction History Is Non-Authoritative

Conversation text may contain:

- ideas;
- hypotheses;
- proposed architecture;
- generated specifications;
- questions;
- explanations;
- progress summaries.

None of these changes authoritative Project state merely by appearing in chat.

Promotion path:

~~~text
conversation content
      ↓
explicit accept/promote action
      ↓
BuildSpecification / Decision / Requirement / Artifact
      ↓
authoritative Project input
~~~

The Context Broker may use interaction history as a low-authority context layer.

It never outranks:

- policy;
- accepted BuildSpecification;
- accepted Project requirements/decisions;
- deterministic evidence.

---

## 5. Attachments

Every accepted upload becomes durable server-side data before it can be relied upon.

Supported examples:

- Markdown/text;
- PDF;
- image;
- screenshot;
- dataset;
- archive;
- specification;
- structured JSON/YAML.

Flow:

~~~text
client upload
   ↓
validation / size / media policy
   ↓
BlobStore
   ↓
Artifact metadata + hash
   ↓
Attachment reference in Message
~~~

If the client disconnects after upload completion, the attachment remains available.

No Task may depend on a local client path.

---

## 6. BuildSpecification/v1

A substantial autonomous engineering Run should be grounded in a versioned specification.

Canonical Artifact type:

~~~text
BuildSpecification/v1
~~~

Required semantic fields:

~~~text
specification_id
project_id
version
objective
scope
non_goals
requirements[]
architecture
interfaces[]
invariants[]
constraints[]
implementation_guidance
references[]
acceptance_criteria[]
verification_requirements[]
escalation_policy
provenance
accepted_by_user_id
accepted_at
supersedes_specification_id?
~~~

Large sections may be separate linked Artifacts while the BuildSpecification stores their references and hashes.

---

## 7. Specification Acceptance

A specification may originate from:

- the users;
- a separate ChatGPT conversation;
- another external reasoning system;
- Reverend research/drafting;
- imported project documentation.

Origin does not create authority.

Cloud v1 acceptance is explicit:

~~~text
draft/import
   ↓
review
   ↓
Accept Specification
   ↓
immutable BuildSpecification version
~~~

An accepted version is immutable.

Changes create another version linked by `supersedes`.

---

## 8. Manual GPT Boundary

Cloud v1 deliberately contains **no automatic frontier-model API dependency**.

Recommended human workflow:

~~~text
users + GPT/other reasoning tool
        ↓
high-quality design/specification
        ↓
manual paste/upload/import
        ↓
human accepts BuildSpecification
        ↓
Reverend implements autonomously
~~~

Reverend must not require:

- OpenAI API credentials;
- ChatGPT session automation;
- automatic external frontier escalation;
- external model availability for routine recovery/resume.

A later architecture decision may add an external model adapter, but it is outside Cloud v1 and disabled by default.

---

## 9. Conversation Intent Classification

Normal chat does not automatically become a paid/mutating Run.

Initial intent classes:

~~~text
CHAT_EXPLAIN
CHAT_ANALYZE
RESEARCH_REQUEST
SPECIFICATION_DRAFT
RUN_REQUEST
RUN_CONTROL
APPROVAL_OR_INPUT
ASSET_REQUEST
~~~

Examples:

~~~text
"Explain this stack trace."
→ CHAT_ANALYZE

"Research alternatives to our scheduler."
→ RESEARCH_REQUEST

"Turn this design into an accepted build spec."
→ SPECIFICATION_DRAFT / explicit accept step

"Implement BuildSpecification v3."
→ RUN_REQUEST

"Pause after the next safe checkpoint."
→ RUN_CONTROL
~~~

A model may classify intent, but trusted application code validates whether the requested action is legal and charge-bearing.

---

## 10. Run Creation from Specification

Run creation records:

~~~text
run_id
project_id
owner_user_id
build_specification_artifact_id
build_specification_version/hash
requested_priority
budget
created_from_conversation_id?
created_from_message_id?
~~~

The Task DAG is derived from the accepted specification plus Project state.

A model-generated plan is validated before Task creation.

---

## 11. One Global Active Run

Cloud v1 retains exactly one active top-level Run across both users and all Projects.

This is intentionally simpler than concurrent top-level Runs.

Internal Agent/Job parallelism remains allowed within the active Run.

Queued Runs carry explicit priority metadata.

---

## 12. Priority Handoff

A user with sufficient Project/system authority may raise a queued Run's priority.

This does not immediately kill the active Run.

Canonical flow:

~~~text
queued Run B priority raised
        ↓
active Run A receives PREEMPT_REQUESTED
        ↓
A continues to next safe boundary
        ↓
settle/journal side effects
        ↓
flush valuable workspace state
        ↓
commit/checkpoint durable Project progress
        ↓
publish RunCheckpoint
        ↓
release paid/transient compute
        ↓
A → RESUME_QUEUED
        ↓
B → STARTING / RUNNING
~~~

"Commit/checkpoint" means valuable current repository state is durably represented according to Git/workspace policy. It does not permit unsafe auto-commit of unvalidated changes to protected branches.

---

## 13. Priority Rules

Initial priorities:

~~~text
NORMAL
HIGH
URGENT
RESUME_NEXT
~~~

Policy principles:

- one explicit active pre-emption request at a time;
- priority does not bypass owner authorization;
- priority does not bypass approvals;
- priority does not bypass Action Journal settlement;
- priority cannot interrupt an unsafe/non-reconcilable side effect;
- repeated priority thrashing may be rate-limited;
- RESUME_NEXT prevents a pre-empted Run from being starved indefinitely.

Exact queue ordering remains a trusted Control Plane function.

---

## 14. Handoff Workspace Durability

Before a Run yields control:

1. classify current workspace state;
2. complete/abort safe local operation;
3. persist required diff/commit/worktree metadata;
4. publish relevant Artifacts;
5. record repository base/head identity;
6. create checkpoint manifest;
7. release leases.

Unvalidated work may be stored on a Run-owned branch/worktree or as immutable patch Artifact.

It must never be silently promoted to main merely to allow pre-emption.

---

## 15. Chat Progress Projection

The assistant surface may render:

- current Run status;
- current phase;
- Task counts;
- active Agent(s);
- blockers;
- test/verification state;
- produced Artifacts;
- cost/budget summary;
- pre-emption state.

The assistant may summarize those facts conversationally.

The underlying values come from server projections, not model prose.

---

## 16. Human Input

Clarification remains distinct from Approval.

A user message answering a clarification is bound to a specific `human_input_request_id`.

Unrelated chat messages never implicitly resolve blockers.

---

## 17. Project Navigation

Recommended primary product navigation:

~~~text
CHAT | PROJECT | RUN | ARTIFACTS | STUDIO
~~~

### CHAT
Conversation-first interaction and attachments.

### PROJECT
Accepted specifications, requirements, decisions, repository, references and project settings.

### RUN
Queue, current Run, Tasks, Agents, checkpoints, blockers, verification and costs.

### ARTIFACTS
Reports, patches, outputs, evidence and lineage.

### STUDIO
Developer media/asset surface defined by D16.

Operator/security controls remain available to authorized users without dominating the primary UX.

---

## 18. API Additions

D2 should expose versioned endpoints equivalent to:

~~~text
GET/POST /api/v1/projects/{project_id}/conversations
GET       /api/v1/conversations/{conversation_id}
GET/POST /api/v1/conversations/{conversation_id}/messages

POST      /api/v1/uploads
POST      /api/v1/projects/{project_id}/specifications
POST      /api/v1/specifications/{artifact_id}/accept

POST      /api/v1/runs
POST      /api/v1/runs/{run_id}/priority
~~~

Actual path details may be refined during C0/C2 so long as semantics remain unchanged.

Mutations use D2 authentication, authorization, CSRF/idempotency and bounded request rules.

---

## 19. SSE Additions

Useful event types:

~~~text
ConversationCreated
MessageCreated
AttachmentCreated
BuildSpecificationAccepted
RunPriorityChanged
RunPreemptionRequested
RunCheckpointPublished
RunYielded
RunResumed
~~~

Large message/Artifact content is fetched separately; SSE contains bounded metadata.

---

## 20. Context Rules

Conversation history is selectively retrieved.

Do not dump complete conversations into every model call.

Priority order remains:

1. system/security authority;
2. active Task objective;
3. accepted BuildSpecification;
4. Project requirements/decisions;
5. required Artifacts/interfaces;
6. repository/evidence;
7. accepted Memory;
8. selected relevant conversation excerpts.

---

## 21. Cost Rules

Chat without heavy model/tool execution should remain inexpensive.

Charge-bearing actions require normal D8 budget admission.

Priority switching may create:

- checkpoint work;
- worker drain;
- later model reload/cold start.

Where material, UI should disclose this before repeated manual reprioritization.

---

## 22. Security Rules

- no model/provider secret in Message content;
- uploaded active content never executes in authenticated app origin;
- message bodies are subject to sensitivity labeling;
- private conversations are excluded from other users' context;
- Project conversations do not cross Project authorization;
- external pasted/generated specifications are treated as untrusted until acceptance.

---

## 23. Development Implications

C0:
- Conversation/Message/BuildSpecification contracts;
- priority/pre-emption contract additions.

C1:
- PostgreSQL persistence.

C2:
- chat/upload/specification APIs + SSE.

C3:
- priority handoff integration with one-global-Run queue.

C4:
- specification compiler/context integration.

C6:
- safe yield/checkpoint/resume.

C8:
- ChatGPT-like product UX and operational projections.

C9:
- full two-user handoff acceptance.

---

## 24. Acceptance Tests

Must prove:

- both users can use the GUI while one Run remains globally active;
- closing all clients does not affect the Run;
- a Message cannot mutate Project truth by itself;
- accepted BuildSpecification is immutable/versioned;
- Run records exact specification version/hash;
- queued high-priority Run waits for safe checkpoint;
- pre-empted Run releases paid resources;
- pre-empted Run later resumes from durable state;
- upload remains available after client disconnect;
- private conversation content does not enter another user's context;
- no automatic external frontier API is invoked.

---

## 25. Exit Condition

D15 is satisfied when a browser client can provide a natural ChatGPT-like experience while all engineering authority remains server-side, accepted specifications become durable implementation contracts, and two users can safely reprioritize the single global Run without losing project progress.


### Model storage is not a client responsibility

ADR-004/D17 clarify the Cloud-only boundary:

- production cold starts hydrate pinned models directly from approved upstream repositories;
- the GUI is not required to upload model weights;
- developers may keep personal archival copies independently, but those copies are not part of scheduler availability or normal startup;
- closing both clients does not affect hydration, inference or Run continuation.
