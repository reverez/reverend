# D1 — Authoritative Domain Model & PostgreSQL Schema

> **Status:** DESIGN ACCEPTED FOR DEVELOPMENT  
> **Depends on:** A2, A5, A7, A11, A12, D0  
> **Purpose:** Define the concrete Cloud v1 authoritative object model, PostgreSQL table set, state transitions, indexes, transactional invariants, and migration rules.

---

## 1. Database Role

PostgreSQL is the Cloud v1 authoritative structured-state store.

It owns durable truth for:

- identity and membership;
- Project/Run lifecycle;
- Workflow/Task/Job;
- immutable events;
- Artifact metadata;
- Agent/Team assignment metadata;
- approvals;
- checkpoints;
- Action Journal;
- worker/node/lease metadata;
- idempotency records;
- cost ledger;
- recovery metadata.

It does not need to store large model weights or arbitrary artifact bytes.

---

## 2. SQL Conventions

Use:

~~~text
UUID             object identity
TIMESTAMPTZ      timestamps
BIGINT identity  event/monotonic sequence
JSONB            extensible bounded metadata
BYTEA only       small cryptographic/hash material where appropriate
TEXT             human-readable bounded fields
NUMERIC          monetary values where exact decimal arithmetic matters
~~~

All foreign keys are explicit.

Use CHECK constraints for enum values where stable.

Use unique constraints for semantic invariants that PostgreSQL can enforce.

Application state transitions remain validated in domain code as well.

---

## 3. Core Identity Tables

### users

~~~sql
users(
  user_id UUID PRIMARY KEY,
  display_name TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('enabled','disabled')),
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
)
~~~

Cloud v1 seeds exactly the configured two users.

No API accepts caller-selected authority merely from user_id.

### devices

~~~sql
devices(
  device_id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(user_id),
  label TEXT NOT NULL,
  public_key_or_credential_ref TEXT,
  recovery_enabled BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL,
  last_seen_at TIMESTAMPTZ,
  revoked_at TIMESTAMPTZ
)
~~~

### auth_sessions

~~~sql
auth_sessions(
  session_id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(user_id),
  device_id UUID REFERENCES devices(device_id),
  token_hash BYTEA NOT NULL UNIQUE,
  csrf_token_hash BYTEA,
  created_at TIMESTAMPTZ NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  revoked_at TIMESTAMPTZ,
  last_seen_at TIMESTAMPTZ
)
~~~

Only token hashes are persisted.

Raw session tokens exist only at issuance/client presentation.

---

## 4. Project Tables

### projects

~~~sql
projects(
  project_id UUID PRIMARY KEY,
  name TEXT NOT NULL,
  repository_identity JSONB NOT NULL,
  default_branch TEXT NOT NULL,
  trust_mode TEXT NOT NULL,
  created_by UUID NOT NULL REFERENCES users(user_id),
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
)
~~~

repository_identity should be server-resolved and may contain:

~~~json
{
  "provider": "github",
  "owner": "reverez",
  "repository": "example",
  "canonical_remote": "git@github.com:reverez/example.git"
}
~~~

A client filesystem path is never a Project authority identifier.

### project_members

~~~sql
project_members(
  project_id UUID NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('owner','member')),
  created_at TIMESTAMPTZ NOT NULL,
  PRIMARY KEY(project_id,user_id)
)
~~~

---

## 5. Run Table

### run_status values

Cloud v1:

~~~text
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
~~~

### runs

~~~sql
runs(
  run_id UUID PRIMARY KEY,
  project_id UUID NOT NULL REFERENCES projects(project_id),
  owner_user_id UUID NOT NULL REFERENCES users(user_id),
  objective TEXT NOT NULL,
  status TEXT NOT NULL,
  queue_class TEXT NOT NULL CHECK (queue_class IN ('ACTIVE','RESUME_NEXT','NORMAL','NONE')),
  queue_priority INTEGER NOT NULL DEFAULT 0,
  queued_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL,
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  active_checkpoint_id UUID,
  interruption_depth INTEGER NOT NULL DEFAULT 0,
  github_identity_ref UUID,
  resource_policy JSONB NOT NULL DEFAULT '{}'::jsonb,
  budget_policy JSONB NOT NULL DEFAULT '{}'::jsonb,
  schema_version INTEGER NOT NULL DEFAULT 1,
  row_version BIGINT NOT NULL DEFAULT 0
)
~~~

owner_user_id is immutable at the application layer and guarded by trigger if practical.

### one-active-run database invariant

Create a partial unique index:

~~~sql
CREATE UNIQUE INDEX runs_one_active_top_level_v1
ON runs ((1))
WHERE status IN (
  'STARTING',
  'RUNNING',
  'PAUSE_REQUESTED',
  'PAUSING',
  'RESUMING',
  'RECOVERING'
);
~~~

This gives the Cloud v1 one-active-Run policy a final database backstop.

PAUSED, RESUME_QUEUED, AWAITING_APPROVAL and RECOVERY_BLOCKED do not consume the active slot.

---

## 6. Run Transition Matrix

Allowed transitions include:

~~~text
QUEUED → STARTING | CANCELLED

STARTING → RUNNING | RECOVERING | FAILED | CANCELLED

RUNNING → PAUSE_REQUESTED
RUNNING → AWAITING_APPROVAL
RUNNING → RECOVERING
RUNNING → COMPLETED | FAILED | CANCELLED

PAUSE_REQUESTED → PAUSING | RUNNING | CANCELLED

PAUSING → PAUSED | RECOVERING | FAILED | CANCELLED

PAUSED → RESUME_QUEUED | CANCELLED

AWAITING_APPROVAL → RESUME_QUEUED | CANCELLED | FAILED

RESUME_QUEUED → RESUMING | CANCELLED

RESUMING → RUNNING | RECOVERING | FAILED | CANCELLED

RECOVERING → RESUME_QUEUED | RECOVERY_BLOCKED | FAILED | CANCELLED

RECOVERY_BLOCKED → RESUME_QUEUED | FAILED | CANCELLED

terminal states have no normal outgoing transition
~~~

Some rejected/expired approvals may cause workflow replanning before terminal state; they never jump directly to privileged action execution.

---

## 7. Workflow / Task / Job

Preserve the current generic Control Plane semantics while adding Run linkage.

### workflows

~~~sql
workflows(
  workflow_id UUID PRIMARY KEY,
  run_id UUID NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
  objective TEXT NOT NULL,
  status TEXT NOT NULL,
  trace_id UUID NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL,
  schema_version INTEGER NOT NULL DEFAULT 1
)
~~~

### tasks

~~~sql
tasks(
  task_id UUID PRIMARY KEY,
  workflow_id UUID NOT NULL REFERENCES workflows(workflow_id) ON DELETE CASCADE,
  team_id UUID,
  kind TEXT NOT NULL,
  objective TEXT NOT NULL,
  status TEXT NOT NULL,
  acceptance_criteria JSONB NOT NULL,
  priority INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL,
  schema_version INTEGER NOT NULL DEFAULT 1
)
~~~

### task_dependencies

~~~sql
task_dependencies(
  task_id UUID NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
  depends_on_task_id UUID NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
  PRIMARY KEY(task_id, depends_on_task_id),
  CHECK(task_id <> depends_on_task_id)
)
~~~

Cycle detection remains an application invariant with regression tests.

### jobs

~~~sql
jobs(
  job_id UUID PRIMARY KEY,
  task_id UUID NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
  agent_instance_id UUID,
  attempt_number INTEGER NOT NULL,
  status TEXT NOT NULL,
  executor_type TEXT,
  assigned_node_id UUID,
  runtime_epoch_id UUID,
  trace_context JSONB NOT NULL DEFAULT '{}'::jsonb,
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  error_code TEXT,
  result_ref TEXT,
  created_at TIMESTAMPTZ NOT NULL,
  UNIQUE(task_id, attempt_number)
)
~~~

Job state remains execution-attempt state.

Retries create a new attempt_number.

---

## 8. Event Store

### events

~~~sql
events(
  sequence BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  event_id UUID NOT NULL UNIQUE,
  event_type TEXT NOT NULL,
  occurred_at TIMESTAMPTZ NOT NULL,
  schema_version INTEGER NOT NULL,
  actor TEXT NOT NULL,
  user_id UUID,
  project_id UUID,
  run_id UUID,
  workflow_id UUID,
  task_id UUID,
  job_id UUID,
  agent_instance_id UUID,
  subject_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
  trace_context JSONB NOT NULL DEFAULT '{}'::jsonb,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb
)
~~~

Rules:

- no UPDATE;
- no DELETE through normal application role;
- bounded payload size enforced in application;
- secrets/raw chain-of-thought prohibited.

Create indexes on:

~~~text
run_id, sequence
project_id, sequence
event_type, sequence
job_id, sequence
~~~

SSE replays from sequence.

---

## 9. Artifact Tables

### artifacts

~~~sql
artifacts(
  artifact_id UUID PRIMARY KEY,
  project_id UUID NOT NULL REFERENCES projects(project_id),
  run_id UUID REFERENCES runs(run_id),
  artifact_type TEXT NOT NULL,
  schema_version INTEGER NOT NULL,
  content_ref TEXT,
  inline_content TEXT,
  content_hash TEXT NOT NULL,
  media_type TEXT,
  size_bytes BIGINT,
  producer_job_id UUID REFERENCES jobs(job_id),
  producer_agent_instance_id UUID,
  provenance JSONB NOT NULL,
  validation_state TEXT NOT NULL,
  promotion_state TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  CHECK(content_ref IS NOT NULL OR inline_content IS NOT NULL)
)
~~~

### artifact_parents

~~~sql
artifact_parents(
  artifact_id UUID NOT NULL REFERENCES artifacts(artifact_id) ON DELETE CASCADE,
  parent_artifact_id UUID NOT NULL REFERENCES artifacts(artifact_id),
  relation TEXT NOT NULL DEFAULT 'derived_from',
  PRIMARY KEY(artifact_id,parent_artifact_id,relation)
)
~~~

Artifact content is immutable.

A new revision creates a new Artifact.

---

## 10. Requirement / Decision State

Long-lived Project truth needs first-class durable identity.

### requirements

~~~sql
requirements(
  requirement_id UUID PRIMARY KEY,
  project_id UUID NOT NULL REFERENCES projects(project_id),
  statement TEXT NOT NULL,
  source_ref TEXT,
  status TEXT NOT NULL CHECK (status IN ('active','satisfied','superseded','rejected')),
  priority INTEGER NOT NULL DEFAULT 0,
  acceptance_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
  version INTEGER NOT NULL DEFAULT 1,
  supersedes_requirement_id UUID REFERENCES requirements(requirement_id),
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
)
~~~

### decisions

~~~sql
decisions(
  decision_id UUID PRIMARY KEY,
  project_id UUID NOT NULL REFERENCES projects(project_id),
  run_id UUID REFERENCES runs(run_id),
  decision_type TEXT NOT NULL,
  title TEXT NOT NULL,
  decision_text TEXT NOT NULL,
  rationale_ref TEXT,
  status TEXT NOT NULL CHECK (status IN ('accepted','superseded','rejected')),
  supersedes_decision_id UUID REFERENCES decisions(decision_id),
  created_at TIMESTAMPTZ NOT NULL
)
~~~

The accepted current decision is explicit; historical decisions remain auditable.

---

## 11. Memory Records

### memory_records

~~~sql
memory_records(
  memory_id UUID PRIMARY KEY,
  scope_type TEXT NOT NULL CHECK (scope_type IN ('USER','PROJECT','GLOBAL')),
  scope_id UUID,
  memory_type TEXT NOT NULL CHECK (
    memory_type IN ('FACT','DECISION','EXPERIMENT','FAILURE','RESULT','USER_CONSTRAINT','HYPOTHESIS')
  ),
  statement TEXT NOT NULL,
  evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
  source_ref TEXT,
  confidence NUMERIC,
  status TEXT NOT NULL CHECK (status IN ('ACTIVE','SUPERSEDED','ARCHIVED','EXPIRED')),
  supersedes_memory_id UUID REFERENCES memory_records(memory_id),
  created_at TIMESTAMPTZ NOT NULL,
  expires_at TIMESTAMPTZ
)
~~~

Memory is not execution state.

Memory writes occur through a promotion service, not direct arbitrary Agent writes.

---

## 12. Agent and Team Tables

### agent_specs

Persist versioned Specialist definitions used by Runs.

~~~sql
agent_specs(
  specialist_id TEXT NOT NULL,
  version INTEGER NOT NULL,
  name TEXT NOT NULL,
  role_family TEXT NOT NULL,
  methodology_ref TEXT NOT NULL,
  model_requirement JSONB NOT NULL,
  context_policy JSONB NOT NULL,
  tool_capability_ceiling JSONB NOT NULL,
  authority_ceiling JSONB NOT NULL,
  input_artifact_types JSONB NOT NULL,
  output_artifact_types JSONB NOT NULL,
  default_budget_policy JSONB NOT NULL,
  completion_contract JSONB NOT NULL,
  verification_policy JSONB NOT NULL,
  escalation_policy JSONB NOT NULL,
  metadata JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  PRIMARY KEY(specialist_id,version)
)
~~~

### agent_instances

~~~sql
agent_instances(
  agent_instance_id UUID PRIMARY KEY,
  run_id UUID NOT NULL REFERENCES runs(run_id),
  task_id UUID NOT NULL REFERENCES tasks(task_id),
  team_id UUID,
  specialist_id TEXT NOT NULL,
  specialist_version INTEGER NOT NULL,
  mission TEXT NOT NULL,
  effective_authority JSONB NOT NULL,
  budget_envelope JSONB NOT NULL,
  context_scope JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  closed_at TIMESTAMPTZ,
  FOREIGN KEY(specialist_id,specialist_version)
    REFERENCES agent_specs(specialist_id,version)
)
~~~

No separate authoritative Agent lifecycle enum is required.

Agent state is derived from Task/Job state.

### agent_teams

~~~sql
agent_teams(
  team_id UUID PRIMARY KEY,
  run_id UUID NOT NULL REFERENCES runs(run_id),
  parent_task_id UUID REFERENCES tasks(task_id),
  objective TEXT NOT NULL,
  strategy TEXT NOT NULL,
  leader_agent_instance_id UUID,
  budget_envelope JSONB NOT NULL,
  concurrency_envelope JSONB NOT NULL,
  completion_policy JSONB NOT NULL,
  failure_policy JSONB NOT NULL,
  disagreement_policy JSONB NOT NULL,
  plan_version INTEGER NOT NULL DEFAULT 1,
  created_at TIMESTAMPTZ NOT NULL,
  closed_at TIMESTAMPTZ
)
~~~

Tasks reference team_id for membership.

Team does not own a second task graph.

---

## 13. Approval Table

~~~sql
approvals(
  approval_id UUID PRIMARY KEY,
  run_id UUID NOT NULL REFERENCES runs(run_id),
  project_id UUID NOT NULL REFERENCES projects(project_id),
  action_type TEXT NOT NULL,
  action_fingerprint TEXT NOT NULL,
  requested_actor TEXT NOT NULL,
  effective_external_identity_ref UUID,
  resource_summary JSONB NOT NULL,
  required_policy TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('PENDING','APPROVED','REJECTED','EXPIRED','REVOKED','USED')),
  created_at TIMESTAMPTZ NOT NULL,
  expires_at TIMESTAMPTZ,
  decision_user_id UUID REFERENCES users(user_id),
  decision_at TIMESTAMPTZ,
  used_at TIMESTAMPTZ
)
~~~

An Approval is durable authority for one fingerprinted bounded action.

It never executes inline.

---

## 14. Checkpoint Table

~~~sql
run_checkpoints(
  checkpoint_id UUID PRIMARY KEY,
  run_id UUID NOT NULL REFERENCES runs(run_id),
  sequence BIGINT NOT NULL,
  schema_version INTEGER NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  run_status_at_checkpoint TEXT NOT NULL,
  manifest JSONB NOT NULL,
  journal_high_watermark BIGINT,
  manifest_hash TEXT NOT NULL,
  complete BOOLEAN NOT NULL DEFAULT FALSE,
  UNIQUE(run_id,sequence)
)
~~~

Only complete checkpoints are eligible for recovery.

Referenced blobs must already be durable before complete becomes true.

---

## 15. Action Journal

~~~sql
action_records(
  journal_sequence BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  action_id UUID NOT NULL UNIQUE,
  run_id UUID NOT NULL REFERENCES runs(run_id),
  job_id UUID REFERENCES jobs(job_id),
  actor TEXT NOT NULL,
  tool TEXT NOT NULL,
  operation TEXT NOT NULL,
  arguments_digest TEXT NOT NULL,
  idempotency_key TEXT,
  state TEXT NOT NULL CHECK (
    state IN ('PLANNED','STARTED','COMPLETED','FAILED','INTERRUPTED','UNKNOWN')
  ),
  resume_strategy TEXT NOT NULL CHECK (
    resume_strategy IN ('RESTART','VERIFY_THEN_RETRY','REBUILD','MANUAL_RECOVERY')
  ),
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  result_ref TEXT,
  reconciliation_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  schema_version INTEGER NOT NULL DEFAULT 1
)
~~~

Side-effecting tools must create/advance these records around the external effect.

---

## 16. Compute Tables

### compute_nodes

~~~sql
compute_nodes(
  node_id UUID PRIMARY KEY,
  provider TEXT NOT NULL,
  provider_instance_id TEXT,
  trust_class TEXT NOT NULL,
  lifecycle_state TEXT NOT NULL,
  capabilities JSONB NOT NULL,
  runtime_profiles JSONB NOT NULL,
  resident_models JSONB NOT NULL DEFAULT '[]'::jsonb,
  runtime_epoch_id UUID,
  last_heartbeat_at TIMESTAMPTZ,
  registered_at TIMESTAMPTZ NOT NULL,
  drained_at TIMESTAMPTZ,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb
)
~~~

### resource_requests

~~~sql
resource_requests(
  request_id UUID PRIMARY KEY,
  job_id UUID NOT NULL REFERENCES jobs(job_id),
  requirements JSONB NOT NULL,
  priority INTEGER NOT NULL,
  request_class TEXT NOT NULL,
  preemptibility TEXT NOT NULL,
  cost_ceiling_gbp NUMERIC,
  state TEXT NOT NULL,
  submitted_at TIMESTAMPTZ NOT NULL,
  queue_timeout_at TIMESTAMPTZ
)
~~~

### resource_leases

~~~sql
resource_leases(
  lease_id UUID PRIMARY KEY,
  request_id UUID NOT NULL REFERENCES resource_requests(request_id),
  job_id UUID NOT NULL REFERENCES jobs(job_id),
  node_id UUID NOT NULL REFERENCES compute_nodes(node_id),
  runtime_epoch_id UUID NOT NULL,
  granted_resources JSONB NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('ACTIVE','RELEASED','EXPIRED','REVOKED')),
  acquired_at TIMESTAMPTZ NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  last_heartbeat_at TIMESTAMPTZ NOT NULL,
  released_at TIMESTAMPTZ
)
~~~

Leases from a previous runtime epoch cannot be accepted as active after restart.

---

## 17. Idempotency Table

~~~sql
idempotency_records(
  principal_user_id UUID NOT NULL REFERENCES users(user_id),
  operation TEXT NOT NULL,
  idempotency_key TEXT NOT NULL,
  request_hash TEXT NOT NULL,
  response_status INTEGER,
  response_body JSONB,
  resource_ref TEXT,
  created_at TIMESTAMPTZ NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  PRIMARY KEY(principal_user_id,operation,idempotency_key)
)
~~~

Same key + same request returns the prior result.

Same key + different request hash returns idempotency_conflict.

---

## 18. Cost Tables

D8 defines semantics; D1 freezes persistence shapes.

### rate_snapshots

~~~sql
rate_snapshots(
  rate_snapshot_id UUID PRIMARY KEY,
  provider TEXT NOT NULL,
  product TEXT NOT NULL,
  provider_tier TEXT,
  native_rate NUMERIC NOT NULL,
  native_currency TEXT NOT NULL,
  billing_increment_seconds INTEGER,
  minimum_duration_seconds INTEGER,
  fx_source TEXT,
  fx_rate_to_gbp NUMERIC,
  effective_at TIMESTAMPTZ NOT NULL,
  captured_at TIMESTAMPTZ NOT NULL
)
~~~

### cost_events

~~~sql
cost_events(
  cost_event_id UUID PRIMARY KEY,
  occurred_at TIMESTAMPTZ NOT NULL,
  category TEXT NOT NULL,
  user_id UUID,
  project_id UUID,
  run_id UUID,
  job_id UUID,
  node_id UUID,
  quantity NUMERIC NOT NULL,
  unit TEXT NOT NULL,
  native_unit_price NUMERIC,
  native_currency TEXT,
  rate_snapshot_id UUID REFERENCES rate_snapshots(rate_snapshot_id),
  estimated_cost_gbp NUMERIC,
  actual_cost_gbp NUMERIC,
  source TEXT NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb
)
~~~

CostEvent rows are append-only.

---

## 19. Recovery Tables

### recovery_generations

~~~sql
recovery_generations(
  generation_number BIGINT PRIMARY KEY,
  created_at TIMESTAMPTZ NOT NULL,
  manifest JSONB NOT NULL,
  manifest_hash TEXT NOT NULL,
  complete BOOLEAN NOT NULL DEFAULT FALSE
)
~~~

### recovery_replica_acks

~~~sql
recovery_replica_acks(
  generation_number BIGINT NOT NULL REFERENCES recovery_generations(generation_number),
  device_id UUID NOT NULL REFERENCES devices(device_id),
  acknowledged_at TIMESTAMPTZ NOT NULL,
  manifest_hash TEXT NOT NULL,
  PRIMARY KEY(generation_number,device_id)
)
~~~

A client ACK means the encrypted generation has been durably written and hash-verified.

---

## 20. Queue Selection

Do not persist mutable integer queue positions.

Order is derived.

Priority order:

~~~text
1. active Run already executing
2. RESUME_NEXT by queued_at / explicit priority
3. NORMAL by queue_priority DESC, queued_at ASC
~~~

Cloud v1 normally has at most one RESUME_NEXT pre-emption chain because MAX_PREEMPTION_DEPTH = 1.

Queue selection transaction locks candidate Runs before transition.

---

## 21. Migration Versioning

Create ordered SQL migrations:

~~~text
0001_cloud_identity.sql
0002_projects_runs.sql
0003_controlplane.sql
0004_artifacts_agents.sql
0005_approvals_recovery.sql
0006_compute.sql
0007_costs.sql
0008_indexes_constraints.sql
~~~

Exact partitioning may change, but:

- migrations are monotonic;
- migration checksum is recorded;
- downgrade is not assumed for destructive schema changes;
- backups are required before destructive migrations;
- startup refuses to run against newer unsupported schema.

---

## 22. SQLite Compatibility

Do not attempt to make every PostgreSQL feature identical to SQLite.

Local mode keeps its current store.

Create repository interfaces where shared behavior is required.

Cloud-specific invariants such as the partial unique one-active-run index and advisory leadership may be implemented only in PostgreSQL.

Portable tests should still validate common domain behavior.

---

## 23. Initial Data Migration

Do not blindly copy all current Workstation rows into new authoritative tables.

Migration policy:

1. current Control Plane Workflow/Task/Job/Artifact data may be imported where structurally valid;
2. Workstation authoritative-task fields are decomposed into Project State, Run, checkpoint or conversation history;
3. development DB Task-like rows become historical/domain records unless explicitly mapped;
4. conversation history remains conversation history;
5. no duplicate authority is created.

For a private two-user v1, it is acceptable to start Cloud state clean while retaining old local data as an importable archive if direct migration creates unnecessary risk.

---

## 24. Integrity Tests

At minimum Development must prove:

- owner_user_id cannot change;
- task graph cycles are rejected;
- artifact content cannot mutate in place;
- event rows are immutable;
- one active top-level Run constraint holds under concurrent transactions;
- Job attempt_number is unique per Task;
- stale runtime-epoch leases cannot reactivate;
- approval fingerprint is stable and single-use where required;
- complete checkpoint cannot reference missing BlobStore objects;
- cost events remain append-only;
- idempotency collision behavior is deterministic.

---

## 25. D1 Acceptance Gate

D1 is implementable when C0/C1 can create PostgreSQL from empty state, run all migrations, seed two users, perform lifecycle transactions, and restore from backup without relying on current SQLite process state.
