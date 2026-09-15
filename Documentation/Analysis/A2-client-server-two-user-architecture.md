# A2 — Client / Server & Two-User Architecture

**Status:** analysis contract  
**Programme:** Reverend Cloud Analysis Phase  
**Baseline:** `main@a2d4194153976b1bc9f21212d72874e0b0e6e757`  
**Scope:** frontend/backend boundary, authenticated identities, projects, run ownership, queueing, approvals, API contracts, live events and remote access

## Objective

Define the first cloud deployment boundary for Reverend without turning the project into a general multi-tenant SaaS platform.

The initial operating model is deliberately narrow:

```text
one private Reverend installation
two authenticated developers
one authoritative backend
one active top-level run initially
thin clients
shared project access where configured
```

The cloud system must preserve Reverend's existing local safety and verification invariants while making human identity, run ownership and remote execution explicit.

## Baseline audit

The current Workstation transport is intentionally local-only.

`src/reverend/workstation/server.py`:

- binds only to `127.0.0.1`;
- rejects non-loopback Host/Origin values;
- creates one random in-process session token;
- has no persistent user identity;
- exposes the GUI and JSON API from the same process;
- exposes current endpoints for conversations, jobs, projects, tasks, artifacts, status, control-plane inspection, chat, development, research and cancellation.

The current Workstation service is also the execution host. `src/reverend/workstation/service.py` owns the scheduler, background pool, local stores, cancellation state and application services in-process.

Current durable workstation state lives in local SQLite through `WorkspaceStore`. It contains conversations, messages, jobs and authoritative tasks, but those records do not have human-owner identities.

Current project registration in `src/reverend/development/projects.py` is based on canonical local repository paths. Project IDs are deterministic from the machine-local real path. That is unsuitable as the cloud-wide project identity because a client path must not define server authority.

The generic Control Plane already provides durable:

- Workflow;
- Task;
- Job;
- Event;
- Artifact

records in SQLite, including immutable events and bounded state transitions. These are strong migration seams, but the current contracts do not yet carry `user_id`, project membership or top-level cloud Run ownership.

The current design is therefore a good single-machine application boundary, not yet a remote two-user authority boundary.

## Decision summary

A2 freezes the following v1 direction:

1. Reverend becomes a client/server system.
2. The backend is authoritative for users, projects, runs, queue state, approvals and execution.
3. Each developer has a distinct authenticated Reverend identity.
4. Clients do not choose an arbitrary user identity through an unauthenticated dropdown.
5. Every top-level Run has one immutable initiating owner.
6. Run ownership, not the currently connected viewer, determines user-scoped authority.
7. Projects have explicit membership independent of filesystem paths.
8. The initial scheduler allows one active top-level Run.
9. REST/JSON is the command/query protocol.
10. Server-Sent Events are the v1 live-event protocol.
11. Remote access is over authenticated HTTPS, preferably inside a private Tailscale network for the initial deployment.
12. SSH remains an administrative interface, not the Reverend application protocol.

## Target deployment boundary

```text
Developer A client                 Developer B client
GUI / CLI                          GUI / CLI
      │                                  │
      └──────── HTTPS + auth ────────────┘
                       │
                       ▼
                network edge
          TLS / private network
                       │
                       ▼
                Control API
                       │
          ┌────────────┴─────────────┐
          ▼                          ▼
    authoritative state         live event stream
          │
          ▼
 orchestrator / queue / workers
          │
          ▼
  tools / models / workspaces
```

The client may cache presentation state, but it does not own execution truth.

Closing a browser, losing Wi-Fi or restarting a client must not cancel a running Run.

## Identity contract

### User

Minimum server-side identity:

```text
User
├── user_id
├── display_name
├── status
├── created_at
└── updated_at
```

The initial installation contains exactly two enabled users unless an administrator explicitly changes configuration.

Human identity is established by authentication. Request payloads must not be allowed to self-assert a different `user_id`.

### Device/session

A user may authenticate more than one client device.

```text
AuthSession
├── session_id
├── user_id
├── device_id
├── created_at
├── expires_at
└── revoked_at
```

The exact credential mechanism may be implemented later by A8, but A2 requires every API request to arrive with an authenticated principal.

### Viewer vs owner

The system distinguishes:

```text
viewer = authenticated user making this request
owner  = immutable user that initiated the Run
```

A viewer may inspect a Run owned by the other developer when project policy allows it. Viewing never changes ownership.

## Project contract

Cloud project identity must no longer be derived from a local filesystem path.

```text
Project
├── project_id
├── name
├── repository_identity
├── default_branch
├── trust_mode
├── created_by
├── created_at
└── updated_at
```

Membership is separate:

```text
ProjectMember
├── project_id
├── user_id
└── role
```

Initial roles may remain minimal:

- `owner`;
- `member`.

Both users may be members of the same project.

Server workspaces and repository paths are implementation details attached to `project_id`; they are not authority identifiers.

## Run contract

A cloud Run is the top-level schedulable unit above the existing Workflow/Task/Job hierarchy.

```text
Run
├── run_id
├── project_id
├── owner_user_id
├── objective
├── status
├── created_at
├── started_at
├── finished_at
├── active_checkpoint_id
├── queue_priority
├── interruption_depth
├── github_identity_ref
└── resource_policy
```

A Run owns or references one or more Control Plane Workflows.

`owner_user_id` is immutable after creation.

The following must be derived from Run ownership where relevant:

- Git/GitHub identity;
- user-scoped secrets;
- approval routing;
- cost attribution;
- audit attribution.

## Initial run queue

A2 adopts:

```text
MAX_ACTIVE_TOP_LEVEL_RUNS = 1
```

Queue classes:

```text
ACTIVE
RESUME_NEXT
NORMAL
```

Normal submissions are FIFO unless later policy introduces explicit priority.

A Run paused because it was deliberately pre-empted enters `RESUME_NEXT`, above ordinary queued work. A7 owns exact pause/recovery semantics.

The queue is backend state. Clients only submit queue commands and render the authoritative result.

## API contract

The production cloud API should be versioned from the start:

```text
/api/v1/...
```

### Identity and session

```text
GET  /api/v1/me
POST /api/v1/auth/login
POST /api/v1/auth/logout
```

The exact login implementation is owned by A8. `GET /me` is the canonical client identity check.

### Projects

```text
GET  /api/v1/projects
POST /api/v1/projects
GET  /api/v1/projects/{project_id}
GET  /api/v1/projects/{project_id}/runs
```

Project creation/registration must resolve a server-side repository identity rather than trusting an arbitrary client filesystem path.

### Runs

```text
POST /api/v1/runs
GET  /api/v1/runs
GET  /api/v1/runs/{run_id}
POST /api/v1/runs/{run_id}/cancel
POST /api/v1/runs/{run_id}/pause
POST /api/v1/runs/{run_id}/resume
POST /api/v1/runs/{run_id}/run-now
```

`run-now` means "request pre-emption according to A7 policy", not "bypass authority or resource safety".

### Queue

```text
GET /api/v1/queue
```

The returned representation should expose:

- active Run;
- resume-next Run if any;
- normal queued Runs;
- queue timestamps;
- owner display identity;
- state only, never credentials.

### Approvals

```text
GET  /api/v1/approvals
POST /api/v1/approvals/{approval_id}/approve
POST /api/v1/approvals/{approval_id}/reject
```

An Approval record must name:

```text
approval_id
run_id
project_id
requested_by_actor
required_approver_policy
action_type
bounded action summary
created_at
expires_at
state
```

The server checks whether the authenticated viewer is permitted to approve. The client never decides that itself.

### Artifacts and control state

Existing read-only concepts may be migrated under the versioned API:

```text
GET /api/v1/runs/{run_id}/events
GET /api/v1/runs/{run_id}/artifacts
GET /api/v1/runs/{run_id}/workflow
GET /api/v1/system/status
```

The existing local endpoints are compatibility inputs, not the final cloud contract.

## Command idempotency

Remote clients can retry after network failure. Creation and dangerous mutation endpoints therefore need idempotency.

For commands such as Run creation:

```text
Idempotency-Key: <client generated UUID>
```

The backend stores the key with the authenticated user and operation result for a bounded period.

A retried request with the same principal, key and payload returns the original result instead of creating a second Run.

This is required before clients can safely retry through unreliable networks.

## Live event transport

A2 selects **Server-Sent Events (SSE)** for v1.

Reason:

- Reverend's dominant live flow is server → client;
- normal commands already use HTTP;
- SSE reconnect semantics and event IDs are simple;
- browser support is mature;
- it avoids creating a second bidirectional command protocol before it is needed.

Canonical stream:

```text
GET /api/v1/events/stream
```

Each event exposes bounded presentation-safe metadata:

```json
{
  "event_id": "...",
  "sequence": 1234,
  "event_type": "RunStateChanged",
  "occurred_at": "...",
  "user_id": "...",
  "project_id": "...",
  "run_id": "...",
  "payload": {}
}
```

The stream must support `Last-Event-ID` or an equivalent sequence cursor so reconnecting clients can catch up from durable event state.

Raw prompts, secrets, chain-of-thought and unrestricted tool payloads are not live-event data.

WebSockets remain a future option if Reverend later needs genuinely bidirectional streaming that cannot be represented as REST commands plus SSE.

## Remote access

Initial preferred topology:

```text
clients
  ↓
Tailscale/private network
  ↓
HTTPS reverse proxy
  ↓
Reverend API bound to private/local interface
```

A public internet deployment is possible later but must still terminate TLS at an explicit network edge and authenticate all API traffic.

The current loopback Host/Origin/token mechanism must not simply be opened to `0.0.0.0`.

## Client behaviour

The client should show authenticated identity rather than asking the user to impersonate one:

```text
Signed in as Alex
```

Starting a Run may show:

```text
Project: InvariantLab
Running as: Alex
GitHub: @configured-account
Compute: Exclusive Reverend VPS
```

"Running as" is informational. To change identity, the user signs out and authenticates as the other account.

## Approval ownership

A2 defines the generic approval-policy values:

- `owner_only`;
- `project_member`;
- `project_owner`;
- `either_operator`.

A8 decides which sensitive actions map to which policy.

An approval request follows the Run even if its owner disconnects.

## Event attribution

All new cloud-level events should carry, directly or through trace context:

```text
user_id
project_id
run_id
workflow_id
task_id
job_id
actor
```

Fields may be null where the concept genuinely does not apply, but the schema must distinguish "not applicable" from "identity was never captured".

## Migration from current local architecture

The migration should extend rather than discard existing components.

| Current | Cloud target |
| --- | --- |
| loopback `LocalServer` | authenticated versioned Control API behind TLS/private network |
| per-process random token | persistent authenticated user/session |
| local viewer == implicit operator | explicit viewer identity and immutable Run owner |
| local path-derived project ID | server project ID + repository identity |
| Workstation in-process jobs | top-level durable Run + Control Plane Workflow/Task/Job |
| local polling/status requests | durable events + SSE |
| local cancellation map | server-owned Run/Job cancellation state |
| client/server same process | thin client + authoritative backend |
| no remote retry semantics | idempotent mutation commands |

## Non-goals for A2

A2 does not freeze:

- password hashing/OAuth implementation details;
- GitHub token storage format;
- checkpoint schema;
- provider lifecycle control;
- exact PostgreSQL schema;
- final cloud GPU hardware;
- multi-node scheduling;
- simultaneous top-level Runs.

Those belong to A7, A8, A10 and A11.

## Acceptance gates

A2 analysis is complete when implementation teams can independently build a client and backend against the same semantics.

Required gates:

1. human identities are explicit and authenticated;
2. no API payload may arbitrarily select another user;
3. project identity is independent of client filesystem paths;
4. every Run has immutable `owner_user_id`;
5. viewer and owner are distinct concepts;
6. Run ownership determines user-scoped external authority;
7. queue semantics define ACTIVE / RESUME_NEXT / NORMAL;
8. only one top-level Run is active in Cloud v1;
9. versioned REST resources and mutations are defined;
10. mutation retries have an idempotency strategy;
11. live events use a durable resumable SSE stream;
12. approvals are durable backend objects;
13. client disconnect does not terminate execution;
14. remote access does not expose the existing loopback server directly;
15. SSH remains administrative only.

## Frozen A2 invariant

> Every cloud request is attributable to an authenticated user, every top-level Run has one immutable owner, and all authoritative execution state lives on the server. Clients may observe and command the system through stable authenticated APIs, but they cannot redefine identity or execution truth.
