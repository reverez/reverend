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
  "repository": "example"
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
AWAITING_INPUT
RECOVERING
RECOVERY_BLOCKED
CANCEL_REQUESTED
CANCELLING
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
  'RECOVERING',
  'CANCEL_REQUESTED',
  'CANCELLING'
);
~~~

This gives the Cloud v1 one-active-Run policy a final database backstop.

PAUSED, RESUME_QUEUED, AWAITING_APPROVAL, AWAITING_INPUT and RECOVERY_BLOCKED do not consume the active slot.

---

## 6. Run Transition Matrix

Allowed transitions include:

~~~text
QUEUED → STARTING | CANCELLED

STARTING → RUNNING | RECOVERING | CANCEL_REQUESTED | FAILED

RUNNING → PAUSE_REQUESTED
RUNNING → AWAITING_APPROVAL
RUNNING → AWAITING_INPUT
RUNNING → RECOVERING
RUNNING → CANCEL_REQUESTED
RUNNING → COMPLETED | FAILED

PAUSE_REQUESTED → PAUSING | RUNNING | CANCEL_REQUESTED

PAUSING → PAUSED | RECOVERING | CANCEL_REQUESTED | FAILED

PAUSED → RESUME_QUEUED | CANCELLED

AWAITING_APPROVAL → RESUME_QUEUED | CANCELLED | FAILED

AWAITING_INPUT → RESUME_QUEUED | CANCELLED | FAILED

RESUME_QUEUED → RESUMING | CANCELLED

RESUMING → RUNNING | RECOVERING | CANCEL_REQUESTED | FAILED

RECOVERING → RESUME_QUEUED | RECOVERY_BLOCKED | CANCEL_REQUESTED | FAILED

RECOVERY_BLOCKED → RESUME_QUEUED | CANCELLED | FAILED

CANCEL_REQUESTED → CANCELLING

CANCELLING → CANCELLED | RECOVERING | FAILED

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


---

## 24. Recursive Architecture Hardening — Missing Tables, Keys and Cross-Object Invariants

The recursive pre-development review found that several objects referenced by D2/D4/D5/D6/D7/D8 were not yet frozen in the authoritative schema. This section closes those gaps and is mandatory for Cloud v1.

### 24.1 Human authentication credentials

```sql
auth_credentials(
  credential_id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(user_id),
  login_name TEXT NOT NULL UNIQUE,
  credential_type TEXT NOT NULL CHECK (credential_type IN ('PASSWORD')),
  secret_hash TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  rotated_at TIMESTAMPTZ,
  revoked_at TIMESTAMPTZ,
  failed_attempt_count INTEGER NOT NULL DEFAULT 0,
  locked_until TIMESTAMPTZ
)
```

Rules:

- `login_name` is normalized before uniqueness checks;
- `secret_hash` stores Argon2id encoded output, not plaintext;
- password credentials are never stored in the generic Secret Broker table;
- user disable/revocation invalidates authentication regardless of credential row state.

### 24.2 GitHub external identity

```sql
github_identities(
  identity_id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(user_id),
  github_login TEXT NOT NULL,
  git_author_name TEXT NOT NULL,
  git_author_email TEXT NOT NULL,
  credential_secret_id UUID NOT NULL,
  repository_scope JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  revoked_at TIMESTAMPTZ,
  UNIQUE(identity_id,user_id)
)
```

After `secrets` exists, `credential_secret_id` references `secrets(secret_id)`.

The Run binding is ownership-safe:

```sql
ALTER TABLE runs
  ADD CONSTRAINT runs_owner_membership_fk
  FOREIGN KEY(project_id,owner_user_id)
  REFERENCES project_members(project_id,user_id);

ALTER TABLE runs
  ADD CONSTRAINT runs_github_identity_owner_fk
  FOREIGN KEY(github_identity_ref,owner_user_id)
  REFERENCES github_identities(identity_id,user_id);
```

`github_identity_ref` may be NULL until an external Git action is required.

### 24.3 Secret metadata and ciphertext

```sql
secrets(
  secret_id UUID PRIMARY KEY,
  scope_type TEXT NOT NULL CHECK (scope_type IN ('SYSTEM','USER','PROJECT','RUN_EPHEMERAL')),
  scope_id UUID,
  secret_type TEXT NOT NULL,
  encrypted_value BYTEA NOT NULL,
  key_version INTEGER NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  rotated_at TIMESTAMPTZ,
  revoked_at TIMESTAMPTZ,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb
)
```

Scope ownership is validated by Secret Broker policy and explicit constraint triggers where the scope maps directly to an authoritative UUID.

### 24.4 Worker bootstrap and worker sessions

```sql
worker_bootstrap_credentials(
  bootstrap_id UUID PRIMARY KEY,
  token_hash BYTEA NOT NULL UNIQUE,
  provider TEXT NOT NULL,
  expected_provider_instance_id TEXT NOT NULL,
  intended_profile_id TEXT NOT NULL,
  intended_trust_class TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  consumed_at TIMESTAMPTZ
);

worker_sessions(
  worker_session_id UUID PRIMARY KEY,
  node_id UUID NOT NULL REFERENCES compute_nodes(node_id),
  runtime_epoch_id UUID NOT NULL,
  token_hash BYTEA NOT NULL UNIQUE,
  allowed_endpoints JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  revoked_at TIMESTAMPTZ
)
```

Bootstrap token plaintext is never persisted.

### 24.5 Runtime epochs and clean shutdown

```sql
runtime_epochs(
  runtime_epoch_id UUID PRIMARY KEY,
  started_at TIMESTAMPTZ NOT NULL,
  ended_at TIMESTAMPTZ,
  clean_shutdown BOOLEAN NOT NULL DEFAULT FALSE,
  final_recovery_generation BIGINT,
  shutdown_reason TEXT
)
```

A new authoritative backend boot inserts a new epoch before scheduler/worker authority is granted.

### 24.6 Durable pre-emption lineage

Add to `runs`:

```sql
preempts_run_id UUID REFERENCES runs(run_id)
```

Rules:

- a Run never pre-empts itself;
- a Run with non-NULL `preempts_run_id` cannot itself be pre-empted in Cloud v1;
- the pre-empted Run is placed in `RESUME_NEXT`;
- the relation is retained after terminal completion for audit;
- creating this relationship, pausing the old active Run and admitting the new Run is one serialized RunService operation.

This is the durable backstop for `MAX_PREEMPTION_DEPTH = 1`.

### 24.7 Power-session accounting

```sql
power_sessions(
  power_session_id UUID PRIMARY KEY,
  provider TEXT NOT NULL,
  provider_instance_id TEXT NOT NULL,
  node_id UUID REFERENCES compute_nodes(node_id),
  deployment_profile_id UUID,
  requested_start_at TIMESTAMPTZ NOT NULL,
  provider_running_at TIMESTAMPTZ,
  stop_requested_at TIMESTAMPTZ,
  provider_stopped_at TIMESTAMPTZ,
  billing_start_at TIMESTAMPTZ,
  billing_end_at TIMESTAMPTZ,
  rate_snapshot_id UUID REFERENCES rate_snapshots(rate_snapshot_id),
  estimated_cost_gbp NUMERIC,
  actual_cost_gbp NUMERIC,
  reconciliation_state TEXT NOT NULL,
  UNIQUE(provider,provider_instance_id,requested_start_at)
);

compute_lease_usage(
  lease_id UUID PRIMARY KEY REFERENCES resource_leases(lease_id),
  user_id UUID NOT NULL REFERENCES users(user_id),
  project_id UUID NOT NULL REFERENCES projects(project_id),
  run_id UUID NOT NULL REFERENCES runs(run_id),
  job_id UUID NOT NULL REFERENCES jobs(job_id),
  node_id UUID NOT NULL REFERENCES compute_nodes(node_id),
  deployment_profile_id UUID,
  acquired_at TIMESTAMPTZ NOT NULL,
  released_at TIMESTAMPTZ,
  duration_seconds NUMERIC,
  rate_snapshot_id UUID REFERENCES rate_snapshots(rate_snapshot_id),
  estimated_cost_gbp NUMERIC
)
```

### 24.8 Budget reservations

```sql
budget_reservations(
  reservation_id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(user_id),
  run_id UUID REFERENCES runs(run_id),
  team_id UUID,
  task_id UUID,
  agent_instance_id UUID,
  job_id UUID,
  operation_key TEXT NOT NULL,
  reserved_gbp NUMERIC NOT NULL CHECK (reserved_gbp >= 0),
  state TEXT NOT NULL CHECK (state IN ('ACTIVE','SETTLED','RELEASED','EXPIRED')),
  created_at TIMESTAMPTZ NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  settled_cost_event_id UUID REFERENCES cost_events(cost_event_id)
)
```

Reservation admission and parent-budget remaining balance are checked under transaction-level locking.

### 24.9 Model and deployment registry

Production model eligibility is durable and auditable.

```sql
model_profiles(
  model_profile_id UUID PRIMARY KEY,
  family TEXT NOT NULL,
  model_name TEXT NOT NULL,
  revision TEXT NOT NULL,
  license_id TEXT NOT NULL,
  capabilities JSONB NOT NULL,
  max_advertised_context_tokens INTEGER,
  validated_context_profiles JSONB NOT NULL DEFAULT '[]'::jsonb,
  runtime_compatibility JSONB NOT NULL,
  trust_eligibility JSONB NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('DISCOVERED','BENCHMARKING','ELIGIBLE','DISABLED','RETIRED')),
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL,
  UNIQUE(model_name,revision)
);

deployment_profiles(
  deployment_profile_id UUID PRIMARY KEY,
  model_profile_id UUID NOT NULL REFERENCES model_profiles(model_profile_id),
  profile_name TEXT NOT NULL UNIQUE,
  runtime TEXT NOT NULL,
  runtime_version TEXT NOT NULL,
  quantization TEXT,
  container_digest TEXT NOT NULL,
  max_context_tokens INTEGER NOT NULL,
  reasoning_policy JSONB NOT NULL,
  hardware_requirements JSONB NOT NULL,
  trust_class TEXT NOT NULL,
  concurrency_policy JSONB NOT NULL,
  batching_policy JSONB NOT NULL,
  cost_profile JSONB NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('BENCHMARKING','ELIGIBLE','DISABLED','RETIRED')),
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

benchmark_result_sets(
  benchmark_result_set_id UUID PRIMARY KEY,
  deployment_profile_id UUID NOT NULL REFERENCES deployment_profiles(deployment_profile_id),
  reverend_revision TEXT NOT NULL,
  specialist_versions JSONB NOT NULL,
  context_compiler_version TEXT NOT NULL,
  result_manifest_ref TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
)
```

Promotion/disable/retire is an audited privileged operation. Benchmark completion alone does not automatically promote a profile.

### 24.10 Cost-event deduplication

Add:

```sql
external_event_key TEXT
```

to `cost_events`, with a partial unique constraint over `(source, external_event_key)` where the key is non-NULL.

Provider reconciliation must supply a stable external key or a deterministic locally derived reconciliation key so repeated polling cannot double-charge the ledger.

### 24.11 Approval-to-Action binding

Add to `approvals`:

```sql
used_action_id UUID UNIQUE
```

After `action_records` is created:

```sql
ALTER TABLE approvals
  ADD CONSTRAINT approvals_used_action_fk
  FOREIGN KEY(used_action_id)
  REFERENCES action_records(action_id);
```

Approval `APPROVED → USED` and creation of the corresponding `PLANNED` ActionRecord occur in one transaction.

### 24.12 Action idempotency uniqueness

For non-NULL action idempotency keys:

```sql
CREATE UNIQUE INDEX action_idempotency_scope_v1
ON action_records(run_id,tool,operation,idempotency_key)
WHERE idempotency_key IS NOT NULL;
```

A retry reuses/reconciles the same intent rather than creating a competing one.

### 24.13 Resource uniqueness and provider identity

```sql
CREATE UNIQUE INDEX resource_leases_one_active_per_job_v1
ON resource_leases(job_id)
WHERE state='ACTIVE';

CREATE UNIQUE INDEX resource_leases_one_active_per_request_v1
ON resource_leases(request_id)
WHERE state='ACTIVE';

CREATE UNIQUE INDEX compute_nodes_provider_instance_v1
ON compute_nodes(provider,provider_instance_id)
WHERE provider_instance_id IS NOT NULL;
```

Granting capacity still requires scheduler transaction locking because these indexes do not by themselves prevent aggregate CPU/RAM/VRAM overcommit.

### 24.14 Artifact content exclusivity

Replace the loose Artifact content check with:

```sql
CHECK (
  (content_ref IS NOT NULL AND inline_content IS NULL)
  OR
  (content_ref IS NULL AND inline_content IS NOT NULL)
)
```

An Artifact has exactly one canonical content representation.

### 24.15 Same-scope relational integrity

The following are mandatory DB-backed invariants:

- TaskDependency endpoints belong to the same Workflow;
- AgentInstance Task belongs to the same Run as AgentInstance;
- AgentInstance Team, when present, belongs to the same Run;
- Team parent Task and leader Agent, when present, belong to the same Run;
- Artifact parent relation never crosses Project unless a future explicit import relation is introduced;
- Job assigned_node_id, when non-NULL, references `compute_nodes(node_id)`;
- `runs.active_checkpoint_id`, when non-NULL, references a complete checkpoint belonging to that same Run.

Because several relationships are circular or tables are created later, implement these with post-create `ALTER TABLE` foreign keys and DEFERRABLE constraint triggers where necessary.

### 24.16 Immutable lineage and deletion policy

Normal application roles may not hard-delete:

~~~text
runs
workflows
tasks
jobs
events
artifacts
approvals
action_records
cost_events
recovery_generations
```

Project/user lifecycle uses disable/archive state. Explicit retention maintenance may purge only after proving no active recovery, audit, provenance or BlobStore reachability depends on the records.

### 24.17 Revised migration set

The migration programme must now include the hardening objects:

~~~text
0001_cloud_identity.sql
0002_projects_runs.sql
0003_controlplane.sql
0004_artifacts_agents.sql
0005_security_approvals_recovery.sql
0006_compute_worker_identity.sql
0007_models_and_benchmarks.sql
0008_costs_and_budget_reservations.sql
0009_integrity_constraints.sql
0010_indexes_and_delete_policies.sql
```

Exact file boundaries may vary, but none of the entities or invariants in this section are optional.


---

## 25. Recursive Audit Cycle 2 — Lifecycle, Human Input, Worker Reconnect and Execution Provenance

### 25.1 Safe cancellation states

Direct `RUNNING → CANCELLED` is not sufficient for a system with non-interruptible or externally visible actions.

Add Run states:

~~~text
CANCEL_REQUESTED
CANCELLING
~~~

They consume the one-active-Run slot.

Revised active-run index includes:

~~~text
STARTING
RUNNING
PAUSE_REQUESTED
PAUSING
RESUMING
RECOVERING
CANCEL_REQUESTED
CANCELLING
~~~

Revised transitions:

~~~text
RUNNING → CANCEL_REQUESTED
PAUSE_REQUESTED → CANCEL_REQUESTED
STARTING → CANCEL_REQUESTED when execution resources/actions may already exist

CANCEL_REQUESTED → CANCELLING
CANCELLING → CANCELLED | RECOVERING | FAILED
~~~

A Run that is safely QUEUED, PAUSED, RESUME_QUEUED, AWAITING_APPROVAL, AWAITING_INPUT or RECOVERY_BLOCKED with no live Action/lease may transition directly to CANCELLED after invariant checks.

### 25.2 Human clarification is not Approval

Add Run state:

~~~text
AWAITING_INPUT
~~~

It does not consume the active slot.

Add:

```sql
human_input_requests(
  input_request_id UUID PRIMARY KEY,
  run_id UUID NOT NULL REFERENCES runs(run_id),
  task_id UUID REFERENCES tasks(task_id),
  prompt_summary TEXT NOT NULL,
  input_schema JSONB NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('PENDING','ANSWERED','CANCELLED','EXPIRED')),
  created_at TIMESTAMPTZ NOT NULL,
  expires_at TIMESTAMPTZ,
  answered_by UUID REFERENCES users(user_id),
  answered_at TIMESTAMPTZ,
  answer_artifact_id UUID REFERENCES artifacts(artifact_id)
)
```

Rules:

- model-generated clarification text is a request, not authority;
- human answer is stored as a typed Artifact or bounded authoritative input record;
- if other Tasks remain runnable, only the requesting Task blocks;
- Run enters AWAITING_INPUT only when no useful runnable work remains and progress requires human input;
- ANSWERED → Run RESUME_QUEUED when the Run was in aggregate AWAITING_INPUT.

### 25.3 Task blockers

Add:

```sql
task_blockers(
  task_id UUID NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
  blocker_type TEXT NOT NULL CHECK (
    blocker_type IN ('DEPENDENCY','APPROVAL','HUMAN_INPUT','BUDGET','RECOVERY','POLICY')
  ),
  blocker_ref TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  cleared_at TIMESTAMPTZ,
  PRIMARY KEY(task_id,blocker_type,blocker_ref)
)
```

Task `BLOCKED` therefore has a durable machine-readable reason.

### 25.4 Freeze Workflow/Task/Job state enums

Cloud v1 uses the existing semantics with one explicit recoverability extension.

~~~text
WorkflowStatus:
PENDING
ACTIVE
COMPLETE
FAILED
CANCELLED

TaskStatus:
PENDING
READY
RUNNING
BLOCKED
COMPLETE
FAILED
CANCELLED

JobStatus:
QUEUED
ACQUIRING_RESOURCES
RUNNING
VERIFYING
SUCCEEDED
FAILED
INTERRUPTED
CANCELLED
TIMED_OUT
~~~

`INTERRUPTED` means the execution attempt ended without a trustworthy terminal result and a new attempt/recovery decision may follow. It is not equivalent to FAILED.

### 25.5 Stable worker identity across Control Plane restart

A consumed bootstrap token cannot be the only credential for a still-running worker.

Add:

```sql
worker_identities(
  worker_identity_id UUID PRIMARY KEY,
  node_id UUID NOT NULL UNIQUE REFERENCES compute_nodes(node_id),
  provider TEXT NOT NULL,
  provider_instance_id TEXT NOT NULL,
  identity_token_hash BYTEA NOT NULL UNIQUE,
  created_at TIMESTAMPTZ NOT NULL,
  rotated_at TIMESTAMPTZ,
  revoked_at TIMESTAMPTZ,
  UNIQUE(provider,provider_instance_id)
)
```

Initial bootstrap exchanges the one-time bootstrap token for:

- a long-lived-for-node, narrowly scoped worker identity token;
- a short-lived runtime-epoch worker session.

The worker identity token:

- is stored only on that worker and hashed in PostgreSQL;
- can obtain a fresh session after Control Plane runtime-epoch restart;
- cannot claim another node/provider instance;
- cannot access Projects/Secrets/provider lifecycle;
- is revoked on drain, compromise or provider-instance termination.

If the worker identity token is lost, the node is safely reprovisioned rather than bypassing authentication.

### 25.6 Model invocation provenance

Add:

```sql
model_invocations(
  invocation_id UUID PRIMARY KEY,
  run_id UUID NOT NULL REFERENCES runs(run_id),
  task_id UUID REFERENCES tasks(task_id),
  job_id UUID NOT NULL REFERENCES jobs(job_id),
  agent_instance_id UUID REFERENCES agent_instances(agent_instance_id),
  deployment_profile_id UUID REFERENCES deployment_profiles(deployment_profile_id),
  node_id UUID REFERENCES compute_nodes(node_id),
  context_manifest_artifact_id UUID REFERENCES artifacts(artifact_id),
  started_at TIMESTAMPTZ NOT NULL,
  finished_at TIMESTAMPTZ,
  input_tokens BIGINT,
  output_tokens BIGINT,
  stop_reason TEXT,
  tool_call_count INTEGER NOT NULL DEFAULT 0,
  estimated_cost_gbp NUMERIC,
  status TEXT NOT NULL
)
```

ContextManifest is persisted as an immutable typed Artifact and referenced from the invocation.

### 25.7 Provider lifecycle intent

Provider provision/start/stop/terminate are external side effects and must be journalled.

Each paid provider lifecycle operation has:

- an ActionRecord before the API call;
- a stable provider idempotency/reconciliation key where available;
- a PowerSession or provider-instance correlation record;
- provider tags containing Reverend instance/action identity where supported.

A crash after provider creation but before local result persistence must reconcile provider inventory before another paid instance is created.

### 25.8 Blob garbage-collection safety

Blob GC is mark-and-sweep with a grace period.

Roots include:

- all live Artifact content refs;
- all complete retained checkpoints;
- all retained RecoveryGenerations;
- active backup manifests;
- in-progress upload publication records.

GC cannot delete an object merely because one transaction has not yet published its reference. Temporary/unpublished objects use a separate namespace or minimum-age grace window.


---

## 26. Recursive Audit Cycle 3 — Revocation, Repository Pinning and Immutable Catalogs

### 26.1 Membership is revocable, not deletable

Historical Run ownership must not make Project membership impossible to revoke.

Revise `project_members` to retain identity history:

```sql
ALTER TABLE project_members
  ADD COLUMN status TEXT NOT NULL DEFAULT 'ACTIVE'
    CHECK (status IN ('ACTIVE','REVOKED')),
  ADD COLUMN revoked_at TIMESTAMPTZ,
  ADD COLUMN revoked_by UUID REFERENCES users(user_id);
```

The Run ownership foreign key references the retained membership row, while authorization requires `status='ACTIVE'` at Run creation and for new user-authorized actions.

Project creation transaction must insert the creator as an ACTIVE `owner` member atomically with the Project.

Revoking membership never rewrites historical Run ownership.

### 26.2 User/membership revocation during an active Run

If a Run owner's user or Project membership becomes disabled/revoked:

- no new owner-scoped privileged action is admitted;
- no new user-scoped Secret is resolved;
- pending Approvals from that user become unusable;
- the active Run receives a POLICY blocker and is driven to a safe pause at the next safe boundary;
- system/project administrators may cancel or explicitly resolve policy according to D6;
- another viewer never silently becomes the Run owner.

Historical read visibility follows retention/admin policy, not accidental FK deletion.

### 26.3 Repository identity is pinned per Run

A mutable Project repository configuration cannot retarget an already-running autonomous Run.

Add:

```sql
run_repository_bindings(
  run_id UUID PRIMARY KEY REFERENCES runs(run_id),
  provider TEXT NOT NULL,
  repository_identity JSONB NOT NULL,
  default_branch_at_creation TEXT NOT NULL,
  base_ref TEXT,
  base_commit TEXT,
  run_branch TEXT,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
)
```

Rules:

- `repository_identity` is copied from the server-canonical Project identity at Run creation;
- before mutation begins, the base commit is resolved and pinned;
- worktrees/PRs/Git Actions use this Run binding, not a later mutable Project repository value;
- retargeting a Run to another repository is prohibited; create a new Run instead;
- changing target branch after execution begins requires an explicit fingerprinted privileged action and preserved history.

The human objective is also immutable after Run creation. Clarifications and scope changes become typed input/Requirement/Decision records rather than rewriting the original objective.

### 26.4 Credential revocation never falls back to another user

If `github_identity_ref` or its Secret is revoked while a Run is active, external Git actions fail with a typed POLICY/CREDENTIAL blocker.

The system may request the Run owner to repair/rotate their credential, but may not substitute:

- another Project member's GitHub identity;
- a system GitHub credential;
- ambient host Git credentials.

### 26.5 Immutable production catalogs

Once a ModelProfile or DeploymentProfile has been used by a Job, its semantic identity fields are immutable.

Allowed in-place changes are limited to lifecycle/status metadata that does not alter what was executed.

Changes to any of these create a new profile identity:

~~~text
model revision
runtime/runtime version
quantization
container digest
context limit
hardware requirement
trust class
reasoning semantics
~~~

BenchmarkResultSet and RateSnapshot rows are append-only.

This preserves historical reproducibility.

### 26.6 Canonical FK delete behavior

The original schema examples used several `ON DELETE CASCADE` clauses for convenience. For Cloud authoritative lineage, implementation must prefer `RESTRICT`/no-delete semantics for Run → Workflow → Task → Job and Artifact history.

CASCADE remains appropriate only for non-authoritative join/cache rows whose parent deletion has already passed explicit retention maintenance.

The normal application role cannot use hard deletes on authoritative lineage.


---

## 27. Recursive Audit Cycle 5 — Database Roles, Queue Fairness and Safety Accounting

### Database-role separation

Cloud v1 uses distinct PostgreSQL roles:

~~~text
reverend_migrator
  DDL / migration authority
  not used by normal application runtime

reverend_app
  bounded DML on application tables
  no schema alteration
  no general hard-delete on audit lineage

reverend_secret_reader
  optional minimal read-only authority required by privilege-separated Secret Broker
  no workflow mutation

reverend_backup
  backup/read permissions only as required by backup tooling
~~~

The application runtime must not connect with owner/superuser/migration credentials.

Event, CostEvent, ActionRecord and immutable catalog protections use both application services and database grants/triggers where practical.

### Queue priority authority

`queue_priority` is server/policy assigned.

Ordinary clients cannot submit arbitrary numeric priority.

Any privileged priority override is audited.

### Queue starvation prevention

Queue selection additionally enforces:

- an existing `RESUME_NEXT` chain is serviced before a new ordinary `run-now` request may create another pre-emption;
- a Run that itself pre-empts another Run cannot be pre-empted under Cloud v1;
- repeated run-now requests are rate-limited/idempotent;
- NORMAL Runs with equal policy priority retain FIFO ordering;
- per-user queued-Run quotas prevent unbounded queue flooding.

Emergency/system-administrator stop actions are not queue priority operations.

### Safety recovery overrun

Add CostEvent metadata/category support for:

~~~text
SAFETY_RECOVERY_OVERRUN
~~~

A hard user budget may stop new productive work, but mandatory cleanup/reconciliation needed to prevent duplicated external effects, leaked paid resources or corrupted durable state may consume a bounded configured safety reserve.

Such spend is:

- strictly limited;
- separately classified;
- auditable;
- surfaced to operators;
- reconciled to actual provider cost.

It is never used to continue ordinary engineering work after a hard limit.


---

## 28. Recursive Audit Cycle 6 — Sensitivity and Repository Identity Normalization

### Project disclosure policy

Add to `projects`:

```sql
disclosure_policy JSONB NOT NULL DEFAULT '{}'::jsonb
```

This defines the default trust ceiling for repository/project material.

### Artifact sensitivity

Add to `artifacts`:

```sql
sensitivity_label TEXT NOT NULL DEFAULT 'PROJECT_PRIVATE'
  CHECK (sensitivity_label IN (
    'PUBLIC',
    'PROJECT_PRIVATE',
    'USER_PRIVATE',
    'SECRET_ADJACENT',
    'RESTRICTED'
  ))
```

Sensitivity propagates conservatively through derived Artifacts:

- derived output inherits the strongest mandatory input sensitivity unless a trusted declassification rule applies;
- models/Agents may request a stronger label;
- models/Agents cannot autonomously weaken a label;
- Context Broker uses the durable label plus Project disclosure policy for trust admission.

Secret values themselves still belong in Secret Broker, not Artifacts.

### Repository identity contains no credential transport

Canonical `projects.repository_identity` and `run_repository_bindings.repository_identity` contain provider identity such as:

~~~json
{
  "provider": "github",
  "owner": "reverez",
  "repository": "example"
}
~~~

They do not store token-bearing URLs or a user-specific SSH/HTTPS credential transport.

Trusted Git adapter constructs the transport per action from canonical identity plus the immutable Run owner's GitHubIdentity.

### Human-input sensitivity

`human_input_requests` may declare an expected sensitivity ceiling.

Accepted answers become sensitivity-labelled Artifacts. A human input containing sensitive material therefore participates in the same Context Broker trust filtering rather than bypassing it.


---

## 29. Recursive Audit Cycle 7 — Policy, Administrative Authority and Durable Control State

### 29.1 System administrator roles

Cloud v1 persists administrative authority explicitly:

```sql
system_roles(
  user_id UUID NOT NULL REFERENCES users(user_id),
  role TEXT NOT NULL CHECK (role IN ('SYSTEM_ADMIN')),
  created_at TIMESTAMPTZ NOT NULL,
  created_by UUID REFERENCES users(user_id),
  revoked_at TIMESTAMPTZ,
  PRIMARY KEY(user_id,role)
)
```

At least one enabled SYSTEM_ADMIN must remain configured. Project ownership does not automatically imply SYSTEM_ADMIN.

Administrative role changes are audited privileged actions.

### 29.2 Versioned Project policy

Add:

```sql
project_policies(
  project_id UUID NOT NULL REFERENCES projects(project_id),
  version BIGINT NOT NULL,
  policy JSONB NOT NULL,
  created_by UUID NOT NULL REFERENCES users(user_id),
  created_at TIMESTAMPTZ NOT NULL,
  superseded_at TIMESTAMPTZ,
  PRIMARY KEY(project_id,version)
)
```

Add to `projects`:

```sql
active_policy_version BIGINT NOT NULL
```

with a composite FK to `project_policies(project_id,version)` after bootstrap creation.

Policy updates create a new immutable version and atomically move `active_policy_version`.

Approval fingerprints reference the exact security-relevant policy version.

### 29.3 Durable emergency and maintenance controls

Add:

```sql
execution_controls(
  control_id UUID PRIMARY KEY,
  scope_type TEXT NOT NULL CHECK (scope_type IN ('SYSTEM','PROJECT','RUN')),
  scope_id UUID,
  control_type TEXT NOT NULL CHECK (control_type IN ('STOP','MAINTENANCE')),
  state TEXT NOT NULL CHECK (state IN ('ACTIVE','CLEARED')),
  reason TEXT NOT NULL,
  created_by UUID NOT NULL REFERENCES users(user_id),
  created_at TIMESTAMPTZ NOT NULL,
  cleared_by UUID REFERENCES users(user_id),
  cleared_at TIMESTAMPTZ,
  schema_version INTEGER NOT NULL DEFAULT 1
)
```

Active controls survive process restart and are evaluated by Workflow Scheduler, Tool Broker, Secret Broker and Capacity Controller.

### 29.4 Shutdown/drain inhibitors

Add:

```sql
shutdown_inhibitors(
  inhibitor_id UUID PRIMARY KEY,
  scope_type TEXT NOT NULL CHECK (scope_type IN ('CONTROL_HOST','COMPUTE_NODE')),
  node_id UUID REFERENCES compute_nodes(node_id),
  reason_code TEXT NOT NULL,
  owner_action_id UUID REFERENCES action_records(action_id),
  owner_job_id UUID REFERENCES jobs(job_id),
  created_at TIMESTAMPTZ NOT NULL,
  expires_at TIMESTAMPTZ,
  cleared_at TIMESTAMPTZ,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb
)
```

Examples:

~~~text
CHECKPOINT_PUBLISH
RECOVERY_REPLICATION
GIT_PUSH_RECONCILIATION
DATABASE_BACKUP
ARTIFACT_SYNC
MODEL_DOWNLOAD
MIGRATION
PROVIDER_RECONCILIATION
~~~

Inhibitors are bounded and must have either an owning durable Action/Job or an expiry/watchdog path so a crash cannot permanently prevent draining.

### 29.5 Run policy provenance

At Run creation record:

```sql
policy_version_at_creation BIGINT NOT NULL
```

on `runs`.

Runtime privileged actions still re-evaluate the current Project policy; the creation version is historical provenance, not a frozen bypass.

### 29.6 RUN_EPHEMERAL secret lifecycle

Secrets scoped to `RUN_EPHEMERAL` are revoked automatically when the Run reaches a terminal state, after required recovery/action reconciliation no longer depends on them.

They are excluded from long-lived backups once retention no longer requires them.


---

## 30. Recursive Audit Cycle 8 — Commit-Safe Event and Action Sequences

### 30.1 Event replay cursor

Replace reliance on `GENERATED ALWAYS AS IDENTITY` as the replay-order authority.

Add singleton:

```sql
event_sequence_state(
  singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
  last_sequence BIGINT NOT NULL
)
```

Event append transaction:

~~~text
lock event_sequence_state FOR UPDATE
→ last_sequence += 1
→ insert Event(sequence = last_sequence)
→ apply lifecycle mutation/Event atomically
→ commit
~~~

Because the counter row lock is held to transaction end, another Event transaction cannot obtain a higher replay cursor until the lower cursor transaction commits or rolls back.

If the transaction rolls back, its proposed sequence is not durably advanced.

This provides the ordering guarantee required by `Last-Event-ID`.

The original `events.sequence BIGINT GENERATED ...` example is superseded by:

```sql
sequence BIGINT PRIMARY KEY
```

with explicit transactionally allocated value.

### 30.2 Per-Run Action Journal cursor

A PostgreSQL identity sequence is also unsafe as a checkpoint high-water mark when Actions can be journalled concurrently.

Add:

```sql
run_action_sequence_state(
  run_id UUID PRIMARY KEY REFERENCES runs(run_id),
  last_sequence BIGINT NOT NULL
)
```

Action creation:

~~~text
lock run_action_sequence_state(run_id) FOR UPDATE
→ increment
→ insert ActionRecord(journal_sequence = value)
→ commit
~~~

Change `action_records.journal_sequence` from generated identity to:

```sql
journal_sequence BIGINT NOT NULL,
UNIQUE(run_id,journal_sequence)
```

`RunCheckpoint.journal_high_watermark` is explicitly the highest **committed per-Run journal sequence** included/reconciled by that checkpoint.

### 30.3 Cursor gap behavior

Consumers tolerate gaps caused by explicit retention only when retention metadata proves the cursor range was deliberately compacted/archived.

They do not interpret a missing sequence as permission to advance past an uncommitted record.

### 30.4 Event serialization scope

The singleton Event counter serializes only the small authoritative append transaction, not model/tool execution.

For the private two-user v1 this correctness tradeoff is preferred over a more complex distributed-log design.

A later scale-out architecture may replace it with a log that has equivalent commit-order semantics.


---

## 31. Recursive Audit Cycle 9 — Cross-Scope Lineage, Idempotency Concurrency and Cost Attribution

### 31.1 Idempotency record state

Extend `idempotency_records`:

```sql
state TEXT NOT NULL CHECK (state IN ('IN_PROGRESS','COMPLETED','FAILED')),
owner_request_id UUID,
updated_at TIMESTAMPTZ NOT NULL
```

Admission transaction:

~~~text
INSERT key/hash/state=IN_PROGRESS
ON CONFLICT → lock existing row
→ compare request_hash
→ if COMPLETED return stored result
→ if IN_PROGRESS return/await canonical operation status
→ if different hash return idempotency_conflict
~~~

For Run/Project command creation, the authoritative resource/transition and idempotency completion record are committed atomically whenever possible.

A crashed IN_PROGRESS record is reconciled from its `resource_ref`/command state; it is not blindly executed again.

### 31.2 Artifact lineage integrity

Add:

```sql
CHECK(artifact_id <> parent_artifact_id)
```

to `artifact_parents`.

Application/constraint validation rejects transitive Artifact-parent cycles.

Mandatory same-scope checks include:

- `artifacts.run_id` belongs to `artifacts.project_id`;
- producer Job/Agent belongs to the Artifact Run/Project;
- parent Artifact belongs to the same Project unless a future explicit cross-Project import Artifact type is introduced.

### 31.3 Approval scope integrity

Constraint trigger verifies:

~~~text
Approval.run_id → Run.project_id == Approval.project_id
Approval.effective_external_identity_ref
  belongs to Run.owner_user_id when USER-scoped
```

Approval scope is never trusted from duplicated caller fields.

### 31.4 Billing lineage is derived, not caller supplied

For Run-specific CostEvents and BudgetReservations:

~~~text
project_id = Run.project_id
user_id    = Run.owner_user_id
```

are server-derived under transaction and cross-checked against Job/Lease lineage.

A worker/provider/client cannot choose the billed user by submitting `user_id`.

`compute_lease_usage` values are created from authoritative ResourceLease → Job → Task → Workflow → Run lineage.

### 31.5 Cost allocation without double counting

Add to `cost_events`:

```sql
ledger_role TEXT NOT NULL CHECK (ledger_role IN ('SOURCE_COST','ALLOCATION','ADJUSTMENT')),
parent_cost_event_id UUID REFERENCES cost_events(cost_event_id)
```

Rules:

- SOURCE_COST represents provider/system economic truth;
- ALLOCATION assigns all or part of a source cost to users/Projects;
- ADJUSTMENT corrects prior ledger effects;
- user dashboards sum allocations/Run-variable charges according to ledger policy, not both the source and its allocation;
- system total and allocation total are reconciled separately;
- allocation children for a settled shared source must sum to the intended allocatable amount within decimal tolerance.

This prevents the accepted 50/50 shared split from accidentally counting the same provider charge three times.

### 31.6 GPU/model cost source

Self-hosted model invocations running inside a GPU ResourceLease do not create a second token-priced charge unless the provider actually bills that way.

Their model invocation record carries metrics/estimated attribution, while economic source cost comes from PowerSession/ComputeLeaseUsage.

EXTERNAL_API deployments may generate usage-priced SOURCE_COST events.

### 31.7 Monetary validation

Use fixed precision suitable for provider billing, for example `NUMERIC(20,10)`, and validate:

- FX rates > 0;
- native unit price >= 0 except explicit adjustment representation;
- reservation amount >= 0;
- billing durations/quantities non-negative.

Credits/refunds are represented as explicit ADJUSTMENT semantics, not malformed negative source usage.


---

## 32. Recursive Audit Cycle 10 — Generalized Action Journal Scope

The earlier `action_records(run_id NOT NULL, journal_sequence ...)` shape is superseded.

Cloud v1 ActionRecord supports system, Project and Run effects.

### Global action counter

```sql
action_global_sequence_state(
  singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
  last_sequence BIGINT NOT NULL
)
```

### Revised ActionRecord identity

Conceptual revised columns:

```sql
action_records(
  action_id UUID PRIMARY KEY,
  global_sequence BIGINT NOT NULL UNIQUE,

  scope_type TEXT NOT NULL CHECK (scope_type IN ('SYSTEM','PROJECT','RUN')),
  project_id UUID REFERENCES projects(project_id),
  run_id UUID REFERENCES runs(run_id),
  run_sequence BIGINT,

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
```

Constraint rules:

~~~text
SYSTEM  → project_id NULL, run_id NULL, run_sequence NULL
PROJECT → project_id NOT NULL, run_id NULL unless operation is deliberately Run scoped instead
RUN     → run_id NOT NULL, run_sequence NOT NULL, project_id derived/matching Run.project_id
```

### Sequence allocation

Every Action intent allocates `global_sequence` using the global counter row held to commit.

A RUN-scoped Action also allocates `run_sequence` from `run_action_sequence_state(run_id)`.

Lock order follows D0:

~~~text
Run/Project aggregate
→ run action counter when applicable
→ global action counter
→ Event counter if an Event is emitted
→ commit
~~~

### Watermarks

`RunCheckpoint.journal_high_watermark` refers to `run_sequence`.

`RecoveryGeneration` records `global_action_high_watermark`.

System recovery scans all committed ActionRecords with global_sequence above the recovered generation watermark.

### Idempotency scope

Define canonical `scope_key` in trusted code:

~~~text
SYSTEM
PROJECT:<project_id>
RUN:<run_id>
```

Unique action idempotency becomes:

~~~text
(scope_key, tool, operation, idempotency_key)
```

for non-NULL idempotency keys.

This works correctly for system-level provider/backup operations where `run_id` is NULL.

### Shutdown inhibitors

`shutdown_inhibitors.owner_action_id` can therefore reference both Run and system-level Actions without inventing a fake Run.


---

## 33. Recursive Audit Cycle 11 — Bootstrap Transactions and Generic-Scope Constraints

### Project + initial policy bootstrap

`projects.active_policy_version` and `project_policies` form an intentional bootstrap cycle. It must be implemented transactionally without a window where a remotely visible Project has no policy.

Recommended schema pattern:

~~~sql
projects(
  ...
  active_policy_version BIGINT
)

project_policies(
  project_id UUID NOT NULL REFERENCES projects(project_id),
  version BIGINT NOT NULL,
  ...
  PRIMARY KEY(project_id,version)
)

ALTER TABLE projects
  ADD CONSTRAINT projects_active_policy_fk
  FOREIGN KEY(project_id,active_policy_version)
  REFERENCES project_policies(project_id,version)
  DEFERRABLE INITIALLY DEFERRED;
~~~

Creation transaction:

~~~text
INSERT Project(active_policy_version = 1)
→ INSERT ProjectMember(creator, owner, ACTIVE)
→ INSERT ProjectPolicy(project_id, version=1, baseline policy)
→ commit
~~~

The deferred FK is validated at commit, so no committed Project can lack the referenced active policy.

If implementation cannot support this exact cyclic FK cleanly, use an equivalent transaction-scoped bootstrap procedure with a deferred constraint trigger. Do not publish a Project before membership and baseline policy exist.

### Generic execution-control scope constraints

`execution_controls` scope integrity is enforced by constraints/triggers:

~~~text
SYSTEM  → scope_id IS NULL
PROJECT → scope_id references existing Project
RUN     → scope_id references existing Run
~~~

For PROJECT/RUN controls, creation additionally verifies the actor's current authorization for that scope.

A malformed generic UUID cannot silently create an orphan control.

### Shutdown-inhibitor scope constraints

~~~text
CONTROL_HOST → node_id IS NULL
COMPUTE_NODE → node_id IS NOT NULL and references ComputeNode
~~~

At least one of `owner_action_id` / `owner_job_id` / bounded explicit system-maintenance owner metadata must explain a non-expired inhibitor.

### Scoped Secret referential checks

For Secret scope:

~~~text
SYSTEM        → scope_id IS NULL
USER          → scope_id references users(user_id)
PROJECT       → scope_id references projects(project_id)
RUN_EPHEMERAL → scope_id references runs(run_id)
~~~

These checks are database-backed with constraint triggers where a single declarative FK cannot express the polymorphic scope.

### Recovery-recipient integrity

Recovery recipient/device references are explicit. A recovery-enabled Device must be non-revoked at generation creation time to receive a new key envelope/replica target.


---

## 34. Recursive Audit Cycle 12 — Recovery Action-Intent Replication

### 34.1 Recovery replica targets

Add:

```sql
recovery_replica_targets(
  target_id UUID PRIMARY KEY,
  target_type TEXT NOT NULL CHECK (target_type IN ('DEVICE','OBJECT_STORE')),
  device_id UUID REFERENCES devices(device_id),
  config_ref TEXT,
  status TEXT NOT NULL CHECK (status IN ('ACTIVE','REVOKED','UNHEALTHY')),
  durability_class TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  revoked_at TIMESTAMPTZ
)
```

`config_ref` contains no plaintext credential; object-store credentials remain Secret references/enforcement-boundary configuration.

### 34.2 Action intent recovery envelope

For an Action requiring off-host write-ahead safety, construct an authenticated compact envelope:

~~~text
RecoveryActionIntent/v1
├── action_id
├── global_sequence
├── scope_type / project_id? / run_id?
├── tool / operation
├── arguments_digest
├── idempotency_key?
├── side_effect_class
├── resume_strategy
├── reconciliation metadata required to identify external result
├── expected remote precondition/result identity where applicable
├── created_at
├── payload_hash
├── integrity_key_id
└── authenticator
~~~

The envelope contains no raw secret values.

### 34.3 Durable intent ACK

Add:

```sql
recovery_action_intent_acks(
  action_id UUID NOT NULL REFERENCES action_records(action_id),
  target_id UUID NOT NULL REFERENCES recovery_replica_targets(target_id),
  payload_hash TEXT NOT NULL,
  acknowledged_at TIMESTAMPTZ NOT NULL,
  PRIMARY KEY(action_id,target_id)
)
```

An ACK means the target has durably written and hash/authenticator-verified the envelope.

### 34.4 Action durability class

Add to `action_records`:

```sql
durability_barrier TEXT NOT NULL DEFAULT 'LOCAL'
  CHECK (durability_barrier IN ('LOCAL','OFF_HOST_INTENT_ACK'))
```

Default policy:

~~~text
PURE_READ                 → LOCAL
REPEATABLE_COMPUTE        → LOCAL
LOCAL_MUTATION            → LOCAL if recoverable from durable workspace/checkpoint rules
REMOTE_IDEMPOTENT         → OFF_HOST_INTENT_ACK unless provider idempotency + deterministic restored identity is explicitly proven by the Tool Recovery Registry
REMOTE_RECONCILABLE       → OFF_HOST_INTENT_ACK
IRREVERSIBLE_OR_HIGH_RISK → OFF_HOST_INTENT_ACK
~~~

No Action with `OFF_HOST_INTENT_ACK` may move from PLANNED into external-effect execution until the required ACK policy is satisfied.

### 34.5 Post-generation recovery deltas

A RecoveryGeneration manifest records:

~~~text
global_action_high_watermark
included_action_intent_delta_watermark / target state
~~~

After restoring generation G, Recovery Controller queries/imports every newer authenticated RecoveryActionIntent available from recovery targets before resuming productive work.

An imported intent whose full local ActionRecord was lost causes reconstruction of a recovery-only Action record/state sufficient to reconcile the external effect.

It never causes blind re-execution.

### 34.6 Target policy

Cloud v1 requires at least one ACTIVE durable target for `OFF_HOST_INTENT_ACK` operations.

A connected recovery-enabled client may satisfy this.

For unattended autonomous operation, an always-available encrypted object-store recovery target is strongly recommended so external actions do not depend on a laptop remaining online.

The target abstraction is provider-neutral.


---

## 35. Capability Modernization Schema Addendum

D10–D16 introduce additional durable metadata. These tables remain subordinate to the same PostgreSQL authority and BlobStore rules.

### 35.1 Capability specifications

~~~sql
capability_specs(
  capability_id TEXT NOT NULL,
  version INTEGER NOT NULL,
  capability_family TEXT NOT NULL,
  input_contract JSONB NOT NULL,
  output_contract JSONB NOT NULL,
  resource_requirement_template JSONB NOT NULL,
  trust_requirement TEXT NOT NULL,
  side_effect_class TEXT NOT NULL,
  network_policy JSONB NOT NULL,
  recovery_policy JSONB NOT NULL,
  benchmark_profile TEXT,
  status TEXT NOT NULL CHECK (status IN ('ACTIVE','DISABLED','RETIRED')),
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  PRIMARY KEY(capability_id,version)
)
~~~

This is a versioned catalog. Agent/model output cannot insert or promote production capability definitions directly.

### 35.2 Worker and storage profiles

~~~sql
storage_profiles(
  storage_profile_id TEXT PRIMARY KEY,
  schema_version INTEGER NOT NULL,
  profile JSONB NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('ACTIVE','DISABLED','RETIRED')),
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

worker_profiles(
  worker_profile_id TEXT PRIMARY KEY,
  schema_version INTEGER NOT NULL,
  trust_class TEXT NOT NULL,
  capability_refs JSONB NOT NULL,
  resource_envelope JSONB NOT NULL,
  provider_profile JSONB NOT NULL,
  container_digest TEXT NOT NULL,
  bootstrap_policy JSONB NOT NULL,
  storage_profile_id TEXT NOT NULL REFERENCES storage_profiles(storage_profile_id),
  network_profile JSONB NOT NULL,
  sandbox_profile JSONB NOT NULL,
  health_contract JSONB NOT NULL,
  idle_policy JSONB NOT NULL,
  cost_profile JSONB NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('ACTIVE','DISABLED','RETIRED')),
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
)
~~~

A semantic change to a profile that would alter historical execution creates a new profile identity/version rather than silently rewriting prior provenance.

### 35.3 Research source registry

~~~sql
source_records(
  source_id UUID PRIMARY KEY,
  canonical_locator TEXT NOT NULL,
  source_type TEXT NOT NULL,
  access_partition TEXT NOT NULL DEFAULT 'PUBLIC',
  publisher TEXT,
  authority_class TEXT NOT NULL,
  default_freshness_policy TEXT NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL,
  UNIQUE(source_type,access_partition,canonical_locator)
);

source_snapshots(
  snapshot_id UUID PRIMARY KEY,
  source_id UUID NOT NULL REFERENCES source_records(source_id),
  fetched_at TIMESTAMPTZ NOT NULL,
  published_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ,
  content_hash TEXT NOT NULL,
  content_ref TEXT NOT NULL,
  media_type TEXT NOT NULL,
  byte_count BIGINT NOT NULL CHECK (byte_count >= 0),
  trust_class TEXT NOT NULL,
  sensitivity_label TEXT NOT NULL,
  extraction_version TEXT NOT NULL,
  provider_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE(source_id,content_hash,extraction_version)
)
~~~

SourceSnapshot content referenced by retained Evidence is subject to durable BlobStore retention and backup roots.

### 35.4 Evidence claims

~~~sql
evidence_claims(
  claim_id UUID PRIMARY KEY,
  project_id UUID NOT NULL REFERENCES projects(project_id),
  snapshot_id UUID NOT NULL REFERENCES source_snapshots(snapshot_id),
  claim_text TEXT NOT NULL,
  source_locator JSONB NOT NULL,
  evidence_type TEXT NOT NULL,
  authority_class TEXT NOT NULL,
  confidence NUMERIC,
  freshness_state TEXT NOT NULL,
  extracted_by TEXT NOT NULL,
  validation_state TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
)
~~~

ResearchEvidencePack remains an Artifact whose manifest references EvidenceClaim and SourceSnapshot IDs.

### 35.5 Repository snapshots

~~~sql
repository_snapshots(
  repository_snapshot_id UUID PRIMARY KEY,
  project_id UUID NOT NULL REFERENCES projects(project_id),
  run_id UUID REFERENCES runs(run_id),
  workspace_id TEXT,
  repository_identity JSONB NOT NULL,
  base_commit TEXT NOT NULL,
  head_ref TEXT,
  head_commit TEXT,
  index_digest TEXT,
  diff_digest TEXT,
  untracked_manifest_digest TEXT,
  snapshot_hash TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  UNIQUE(project_id,snapshot_hash)
);

repository_index_builds(
  index_build_id UUID PRIMARY KEY,
  repository_snapshot_id UUID NOT NULL REFERENCES repository_snapshots(repository_snapshot_id),
  adapter_id TEXT NOT NULL,
  adapter_version TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('PENDING','BUILDING','READY','FAILED','STALE')),
  result_manifest_ref TEXT,
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  error_code TEXT
)
~~~

Repository index content is derived/rebuildable. Metadata exists so Context Broker can reject stale/mismatched results.

### 35.6 Context manifests

ContextManifest is persisted as an Artifact as already required by D3/D15.

The schema must include explicit references to:

- Task/Agent/Job;
- source Requirements/Decisions/Artifacts;
- RepositorySnapshot;
- SourceSnapshot/Evidence;
- Memory;
- compiler/policy/model tokenizer versions;
- sensitivity/trust domain;
- included/omitted source refs;
- content hash.

### 35.7 Benchmark registry

~~~sql
benchmark_scenarios(
  benchmark_id TEXT NOT NULL,
  version INTEGER NOT NULL,
  benchmark_family TEXT NOT NULL,
  scenario_manifest_ref TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('DEVELOPMENT','PROMOTION','RETIRED')),
  created_at TIMESTAMPTZ NOT NULL,
  PRIMARY KEY(benchmark_id,version)
);

benchmark_runs(
  benchmark_run_id UUID PRIMARY KEY,
  benchmark_id TEXT NOT NULL,
  benchmark_version INTEGER NOT NULL,
  reverend_revision TEXT NOT NULL,
  experiment_manifest_ref TEXT NOT NULL,
  result_manifest_ref TEXT,
  status TEXT NOT NULL,
  started_at TIMESTAMPTZ NOT NULL,
  finished_at TIMESTAMPTZ,
  FOREIGN KEY(benchmark_id,benchmark_version)
    REFERENCES benchmark_scenarios(benchmark_id,version)
)
~~~

D7 benchmark_result_sets for DeploymentProfiles may reference/aggregate these generalized benchmark runs.

### 35.8 Research and repository Project isolation

Database/service constraints enforce:

- EvidenceClaim.project_id controls retrieval scope;
- SourceSnapshot may be globally deduplicated only when disclosure policy allows reuse; Project Evidence references remain explicit;
- RepositorySnapshot never changes canonical Run repository binding;
- semantic/vector index keys always include Project/snapshot scope;
- cross-Project promotion/import is an explicit audited operation, not similarity-based leakage.

### 35.9 New migration groups

Development should extend the migration set with logically equivalent migrations for:

~~~text
capability + worker/storage profiles
research source/evidence registry
repository snapshots/index metadata
generalized benchmark registry
capability-specific indexes/constraints
~~~

Exact migration filenames are a C0/C1 implementation detail; these entities are not optional once their corresponding capability is enabled.


### 35.10 Source access partition refinement

The research cache is not globally reusable solely by URL.

Interpret access_partition as:

~~~text
PUBLIC
PROJECT:<project_id>:<credential-scope-version>
or another explicit policy-owned partition
~~~

Rules:

- anonymous public sources may deduplicate under PUBLIC;
- authenticated/private provider results are isolated by Project/credential scope;
- SourceSnapshot retrieval always checks the Evidence/Project authorization path;
- a cache hit never grants new access authority.

### 35.11 Capability index isolation

Derived repository/vector/search index records must include Project/snapshot scope in their key/filter model.

Authorization/scope filtering occurs before semantic ranking.

A future shared public-dependency index is a distinct explicitly public corpus, not implicit cross-Project reuse.


### 35.12 Execution environment profiles

~~~sql
execution_environment_profiles(
  environment_profile_id TEXT PRIMARY KEY,
  schema_version INTEGER NOT NULL,
  base_image_digest TEXT NOT NULL,
  toolchain_manifest JSONB NOT NULL,
  dependency_policy JSONB NOT NULL,
  network_policy JSONB NOT NULL,
  sandbox_policy JSONB NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('ACTIVE','DISABLED','RETIRED')),
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
)
~~~

Project lockfiles/manifests are referenced per Job/Artifact rather than mutating the profile catalog.

### 35.13 Ephemeral TestEndpoint authorization

~~~sql
test_endpoints(
  test_endpoint_id UUID PRIMARY KEY,
  run_id UUID NOT NULL REFERENCES runs(run_id),
  job_id UUID NOT NULL REFERENCES jobs(job_id),
  producer_lease_id UUID NOT NULL REFERENCES resource_leases(lease_id),
  consumer_lease_id UUID REFERENCES resource_leases(lease_id),
  route_ref TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('PENDING','ACTIVE','REVOKED','EXPIRED')),
  created_at TIMESTAMPTZ NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  revoked_at TIMESTAMPTZ
)
~~~

route_ref is an opaque private-network routing reference, not a publicly routable URL containing credentials.

Authorization requires current Run/Job/lease scope. Endpoint revocation is part of Job/lease cleanup.


### 35.14 Capability execution provenance

Every remote/derived capability output is associated with the canonical Job attempt and input version identities.

Where a capability produces a durable Artifact, Artifact provenance includes at least:

~~~text
run_id
task_id
job_id
attempt_number
capability_id/version
RepositorySnapshot / SourceSnapshot refs where applicable
policy/context version refs
producer node/worker profile when remote
~~~

Late results are storable but cannot transition a newer Job/Task attempt.

### 35.15 TestEndpoint authentication refinement

Extend test_endpoints with implementation-equivalent fields for:

~~~text
consumer_job_id
consumer_lease_id
connection_credential_hash / channel identity
allowed_protocol
allowed_port/path policy
~~~

The plaintext connection capability is short-lived and delivered only to the bound Browser Worker through the worker protocol.

route_ref by itself never authorizes access.


### 35.16 Project execution-disclosure policy

Project disclosure_policy must resolve an explicit placement rule by sensitivity/trust domain rather than relying on names alone.

Conceptual policy:

~~~json
{
  "community_cloud": {
    "PUBLIC": true,
    "PROJECT_PRIVATE": false,
    "USER_PRIVATE": false,
    "SECRET_ADJACENT": false,
    "RESTRICTED": false
  },
  "external_api": {
    "PUBLIC": true,
    "PROJECT_PRIVATE": false,
    "USER_PRIVATE": false,
    "SECRET_ADJACENT": false,
    "RESTRICTED": false
  }
}
~~~

The above is the **safe default shape**, not a prohibition on the selected Community baseline.

A Project owner may explicitly opt normal Project-private engineering material into COMMUNITY_CLOUD_WORKER execution through a versioned ProjectPolicy. Such opt-in:

- never includes Secret values;
- does not automatically authorize EXTERNAL_API;
- is visible in Project/Run UI;
- is included in context/placement provenance;
- can be tightened later, causing subsequent Jobs to require stronger placement.

Sensitivity labels describe data; disclosure policy determines where that data may go.
