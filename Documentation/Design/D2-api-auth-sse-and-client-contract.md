# D2 — API, Authentication, SSE & Client Contract

> **Status:** DESIGN ACCEPTED FOR DEVELOPMENT  
> **Depends on:** A2, A8, A12, D0, D1  
> **Purpose:** Define the Cloud v1 application protocol so backend, browser UI, CLI, and future IDE clients can be implemented independently against one stable contract.

---

## 1. Protocol Summary

Cloud v1 uses:

~~~text
REST / JSON
under /api/v1

+
Server-Sent Events
for live server → client updates
~~~

The client is non-authoritative.

Every mutating command is authenticated and server-authorized.

SSH is administrative only.

The current loopback Workstation protocol is not the remote cloud API.

---

## 2. API Server

Recommended implementation:

~~~text
FastAPI
Pydantic v2
Uvicorn
~~~

The cloud UI may be served by the same origin initially.

Production edge:

~~~text
Tailscale/private network
        +
HTTPS reverse proxy
        +
Reverend application authentication
~~~

Do not expose the current LocalServer by rebinding it to 0.0.0.0.

---

## 3. Request Context

Every authenticated request constructs:

~~~text
RequestContext
├── request_id
├── principal_user_id
├── session_id
├── device_id?
├── remote metadata
├── received_at
└── trace_id
~~~

The authenticated principal comes from session validation.

It is never taken from a body field.

---

## 4. Authentication Baseline

Cloud v1 chooses a simple private-system implementation.

### Human credential

Administrator provisions each of the two users with a password or one-time setup credential.

Password storage uses Argon2id through a reviewed library.

If implementation elects device-pairing-only login instead, it must preserve the same session contract and security gates.

### Browser session

After successful login:

- server generates at least 256 bits of random session material;
- database stores only SHA-256/HMAC token hash;
- browser receives an HttpOnly Secure SameSite=Strict cookie;
- session has explicit expiry and revocation.

### CLI session

CLI may use a separately issued opaque bearer session token.

The token is displayed only at creation or stored in the user's OS-protected client config/credential store.

The server stores only the token hash.

---

## 5. CSRF

Cookie-authenticated state-changing browser requests require CSRF protection.

Cloud v1 design:

- session has random CSRF value;
- same-origin bootstrap exposes the public CSRF token;
- mutation requests send X-Reverend-CSRF;
- server compares against the session-bound hash;
- bearer-auth CLI requests do not use cookie CSRF semantics.

SameSite is defence in depth, not the sole control.

---

## 6. Session Rules

Session fields:

~~~text
session_id
user_id
device_id?
created_at
expires_at
revoked_at
last_seen_at
~~~

Rules:

- expired/revoked session fails closed;
- logout revokes server-side session;
- disabling a user invalidates their sessions;
- password/credential rotation may revoke all active sessions;
- session tokens never enter SSE payloads or logs.

---

## 7. Standard Response and Error Shapes

Successful resource response:

~~~json
{
  "data": {},
  "request_id": "uuid"
}
~~~

Collection response:

~~~json
{
  "data": [],
  "next_cursor": null,
  "request_id": "uuid"
}
~~~

Error response:

~~~json
{
  "error": {
    "code": "invalid_state_transition",
    "message": "Run cannot transition from paused to running directly.",
    "details": {}
  },
  "request_id": "uuid"
}
~~~

Do not expose stack traces to clients.

---

## 8. HTTP Status Mapping

| Condition | Status |
|---|---:|
| success read | 200 |
| resource created | 201 |
| accepted async command | 202 |
| no content | 204 |
| validation error | 400 / 422 |
| unauthenticated | 401 |
| authenticated but forbidden | 403 |
| not found / inaccessible resource | 404 |
| state/idempotency conflict | 409 |
| expired resource where semantically relevant | 410 |
| hard budget/rate policy | 429 or 409 with domain code |
| server failure | 500 |
| provider unavailable | 503 |

Prefer domain error code over inferring semantics only from HTTP code.

---

## 9. Idempotency

Required for retriable mutation endpoints such as:

- Run creation;
- approval decisions;
- Run pause/resume/run-now/cancel;
- Project registration where remote side effects exist.

Client sends:

~~~text
Idempotency-Key: UUID
~~~

Server scope:

~~~text
principal_user_id
+
operation
+
idempotency key
~~~

Behavior:

1. first request stores request hash;
2. successful/accepted result is persisted;
3. retry with same hash returns original result;
4. retry with same key but different body returns 409 idempotency_conflict.

Never use an idempotency key to bypass authorization revalidation.

---

## 10. Authentication Endpoints

### POST /api/v1/auth/login

Request:

~~~json
{
  "username": "configured-login",
  "password": "..."
}
~~~

Response:

~~~json
{
  "data": {
    "user": {
      "user_id": "...",
      "display_name": "..."
    },
    "session_expires_at": "...",
    "csrf_token": "..."
  },
  "request_id": "..."
}
~~~

For browser login, raw session token is in secure cookie, not JSON.

### POST /api/v1/auth/logout

Revokes current session.

### GET /api/v1/me

Returns:

- user identity;
- safe device/session metadata;
- Project memberships;
- no credentials.

---

## 11. Project Endpoints

### GET /api/v1/projects

Returns Projects visible to authenticated user.

### POST /api/v1/projects

Creates/registers a Project.

Example:

~~~json
{
  "name": "AstraFlow",
  "repository": {
    "provider": "github",
    "owner": "reverez",
    "repository": "AstraFlow"
  },
  "default_branch": "main",
  "trust_mode": "normal"
}
~~~

Server resolves/canonicalizes repository identity.

### GET /api/v1/projects/{project_id}

Includes:

- Project metadata;
- membership;
- latest Run summary;
- no raw secret values.

### GET /api/v1/projects/{project_id}/runs

Cursor-paginated Run history.

---

## 12. Run Endpoints

### POST /api/v1/runs

Request:

~~~json
{
  "project_id": "...",
  "objective": "...",
  "resource_policy": {
    "max_run_cost_gbp": 10.0,
    "max_run_runtime_seconds": 14400
  }
}
~~~

Owner is the authenticated principal, not body input.

Response 201:

~~~json
{
  "data": {
    "run_id": "...",
    "owner_user_id": "...",
    "status": "QUEUED",
    "queue_class": "NORMAL"
  }
}
~~~

### GET /api/v1/runs

Filterable by:

- project;
- status;
- owner;
- cursor.

Authorization filters results.

### GET /api/v1/runs/{run_id}

Returns authoritative presentation state:

- immutable owner;
- objective;
- state;
- queue classification;
- workflow progress;
- active Agent/Team summaries;
- pending approval summary;
- compute summary;
- estimated/reconciled cost;
- recovery state.

### POST /api/v1/runs/{run_id}/pause

Means pause after current safe action.

Returns 202 with command/state summary.

### POST /api/v1/runs/{run_id}/resume

Valid from allowed blocked/paused states.

Transitions to RESUME_QUEUED, not directly RUNNING.

### POST /api/v1/runs/{run_id}/run-now

Requests pre-emption subject to MAX_PREEMPTION_DEPTH=1.

### POST /api/v1/runs/{run_id}/cancel

Cancellation remains server-mediated and safe-action-aware.

---

## 13. Queue Endpoint

### GET /api/v1/queue

~~~json
{
  "data": {
    "active": {
      "run_id": "...",
      "owner": {},
      "status": "RUNNING"
    },
    "resume_next": [],
    "normal": []
  }
}
~~~

The client never sends or owns a queue position.

---

## 14. Approval Endpoints

### GET /api/v1/approvals

Returns approvals visible/decidable by current principal.

### GET /api/v1/approvals/{approval_id}

Returns:

- action summary;
- effective external identity;
- target/resource;
- expiry;
- required policy;
- state.

Never returns secret values.

### POST /api/v1/approvals/{approval_id}/approve

Records a durable decision.

It does not execute the action.

The Run later proceeds through RESUME_QUEUED and fresh scheduling.

### POST /api/v1/approvals/{approval_id}/reject

Persists rejection with the same durability/idempotency rules.

---

## 15. Artifacts

### GET /api/v1/runs/{run_id}/artifacts

Returns Artifact metadata.

### GET /api/v1/artifacts/{artifact_id}

For text/small inline content:

~~~json
{
  "data": {
    "artifact_id": "...",
    "artifact_type": "VerificationReport",
    "validation_state": "validated",
    "promotion_state": "promoted",
    "provenance": {},
    "content": "..."
  }
}
~~~

Large bytes are served through a bounded server-controlled stream/path.

Never expose arbitrary filesystem paths.

---

## 16. Workflow / Agent Views

### GET /api/v1/runs/{run_id}/workflow

Projection includes:

- Workflow;
- Task DAG;
- Task states;
- current Jobs;
- Team grouping;
- Agent assignment.

Read-only.

Clients do not directly mutate Task status.

### GET /api/v1/runs/{run_id}/agents

Optional UI projection.

Agent status is derived from authoritative Task/Job state.

---

## 17. Cost Endpoints

### GET /api/v1/runs/{run_id}/costs

Returns:

- active resource usage;
- estimated variable cost;
- reconciled actual where available;
- budget status;
- allocated shared overhead when shown.

### GET /api/v1/costs/me

Monthly user view.

### GET /api/v1/system/rates

Display-safe captured rate snapshots.

---

## 18. System / Compute Endpoints

### GET /api/v1/system/status

Returns:

- Control Plane readiness;
- DB health;
- scheduler leader state;
- recovery state;
- current compute-node summary.

### GET /api/v1/system/compute

Presentation-safe ComputeNode state.

### POST /api/v1/system/emergency/stop-global

Privileged emergency command defined by D6.

---

## 19. SSE Stream

Canonical endpoint:

~~~text
GET /api/v1/events/stream
~~~

Client reconnect uses Last-Event-ID.

Event:

~~~text
id: 1842
event: RunStateChanged
data: {"schema_version":1,"event_id":"...","sequence":1842}
~~~

Envelope:

~~~json
{
  "schema_version": 1,
  "event_id": "uuid",
  "sequence": 1842,
  "event_type": "RunStateChanged",
  "occurred_at": "...",
  "user_id": "...",
  "project_id": "...",
  "run_id": "...",
  "workflow_id": null,
  "task_id": null,
  "job_id": null,
  "agent_instance_id": null,
  "payload": {}
}
~~~

---

## 20. SSE Replay

On connect:

1. authenticate/authorize principal;
2. parse Last-Event-ID;
3. replay durable visible events after cursor;
4. switch to live wake-up;
5. preserve sequence order.

PostgreSQL notification may wake the stream, but durable Event rows are authoritative.

---

## 21. Presentation-Safe Event Catalogue

Initial events:

~~~text
ProjectUpdated
RunQueued
RunStateChanged
RunProgressChanged
QueueChanged
WorkflowStateChanged
TaskStateChanged
JobStateChanged
AgentAssigned
AgentCompleted
TeamCreated
TeamChanged
ArtifactCreated
ArtifactValidated
ApprovalRequested
ApprovalDecided
ComputeNodeChanged
ResourceLeaseChanged
RecoveryStateChanged
BudgetWarning
BudgetBlocked
CostEstimateChanged
CostReconciled
EmergencyStopChanged
~~~

Do not stream:

- raw prompts;
- chain-of-thought;
- secrets;
- raw Authorization headers;
- unrestricted environment/tool payloads.

---

## 22. Authorization Pattern

Routes declare capability/resource needs.

Conceptual:

~~~text
require(
  capability = run.read,
  resource = Run(run_id)
)
~~~

Mutations additionally validate:

- Project membership;
- Run ownership where required;
- approval policy;
- emergency state;
- current resource/lifecycle state.

Avoid ad-hoc authorization inside route bodies.

---

## 23. Request Bounds

Initial design bounds:

~~~text
JSON request body       <= 1 MiB
ordinary objective      <= 100 KiB
approval note           <= 8 KiB
event payload           <= 32 KiB
inline Artifact content <= 64 KiB
~~~

Large uploads use dedicated Artifact/blob paths.

---

## 24. Client Reconnect Model

~~~text
authenticate
↓
GET /me
↓
fetch current Project/Run projections
↓
open SSE with last cursor
↓
apply updates
~~~

After disconnect:

~~~text
reopen with Last-Event-ID
↓
replay missed events
↓
continue
~~~

UI state is reconstructible from API resources + event cursor.

---

## 25. Browser Security Headers

Retain/extend:

~~~text
Cache-Control: no-store
X-Content-Type-Options: nosniff
Referrer-Policy: no-referrer
frame-ancestors 'none'
object-src 'none'
base-uri 'none'
strict CSP appropriate to bundled UI
~~~

---

## 26. OpenAPI

Expose generated OpenAPI in development.

Use it for frontend integration and schema tests.

Production docs may be restricted.

OpenAPI is derived documentation, not a replacement for domain tests.

---

## 27. Legacy Compatibility

Current local endpoints remain local-mode compatibility during migration.

New cloud UI targets /api/v1 only.

Do not teach the cloud frontend legacy local token semantics.

---

## 28. D2 Acceptance Tests

Development must prove:

- body user_id cannot impersonate another user;
- expired/revoked session rejected;
- CSRF blocks forged cookie mutation;
- Run creation retry is idempotent;
- changed body with reused key conflicts;
- Project visibility follows membership;
- Run owner remains immutable;
- pause/resume follows lifecycle;
- approval endpoint never executes action inline;
- SSE reconnect replays ordered durable events;
- secret fields never appear in public API/SSE;
- browser disconnect does not cancel execution;
- both authenticated users can independently observe permitted shared state.

---

## 29. Exit Condition

Frontend and backend can be developed independently once /api/v1 schemas, authentication/session behavior, lifecycle commands, idempotency, authorization, and SSE v1 are represented in executable contract tests.


---

## 29. Recursive Architecture Hardening — Authentication, Replay and Mutation Safety

These requirements close ambiguities identified during the pre-development recursive review.

### Credential-backed login identity

The `username` accepted by `POST /api/v1/auth/login` is backed by the D1 `auth_credentials` record. `users.display_name` is presentation only and is never a login identifier.

Rules:

- normalized login names are unique;
- Argon2id hashes are stored only in `auth_credentials.secret_hash`;
- disabled/revoked credentials fail closed;
- successful login always creates fresh session material;
- credential rotation invalidates sessions according to policy.

### Login abuse controls

Even on the private network, password login is rate limited.

Initial policy must provide:

- per-login-name exponential backoff;
- coarse source/device throttling;
- constant-shape authentication failure responses that do not reveal whether a login exists;
- durable security/audit events for repeated failures without logging submitted passwords.

The exact thresholds are configuration, not model-controlled values.

### SSE authorization and cursor semantics

`Last-Event-ID` is a global durable sequence cursor, not proof of authorization.

For every replay and live Event:

1. authenticate the session;
2. evaluate current visibility for the referenced Project/Run;
3. omit unauthorized payloads;
4. still advance the internal global cursor over invisible Events;
5. emit only authorized presentation-safe Events.

A client may not infer or retrieve another Project's Event payload by supplying an arbitrary sequence.

### Idempotency storage restrictions

Idempotency records may persist only bounded, non-secret response representations.

Never persist in `idempotency_records.response_body`:

- session or bearer tokens;
- CSRF secrets;
- credentials;
- raw secret values;
- recovery keys.

Authentication/token issuance endpoints use dedicated replay-safe semantics rather than generic response-body idempotency caching.

### Optimistic concurrency

Mutable Project/Run policy endpoints must support an expected version/ETag equivalent once exposed. A stale client update returns conflict rather than silently overwriting a newer human or scheduler decision.
