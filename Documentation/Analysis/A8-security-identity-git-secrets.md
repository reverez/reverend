# A8 — Security, Identity, Git & Secrets

**Status:** analysis contract  
**Programme:** Reverend Cloud Analysis Phase  
**Baseline:** `main@a2d4194153976b1bc9f21212d72874e0b0e6e757`  
**Depends on:** A2 identity/run contracts; A7 durable execution/recovery; A6 resource/worker contracts  
**Scope:** authentication, authorization, run ownership, Git/GitHub identity, secrets, worker authentication, model trust, approvals and emergency control

## Objective

Define the authority boundaries required to turn Reverend from a trusted single-user local workstation into a private two-user remote system without giving models, workers or clients more authority than they need.

The governing principle is:

> **Identity creates authority; model output never does.**

The cloud system must preserve the existing fail-closed capability model and execution isolation while making human, worker and external-service identities explicit.

## Baseline audit

The current repository already contains meaningful security foundations.

### Local transport protection

`src/reverend/workstation/server.py`:

- binds only to loopback;
- validates Host/Origin/Sec-Fetch-Site;
- requires a random session token for API calls;
- does not expose a shell endpoint;
- suppresses request logging.

This is appropriate for localhost but is not multi-user remote authentication.

### Capability policy

`src/reverend/policy/models.py` and `policy/engine.py` provide:

- named capabilities;
- explicit risk class;
- scoped permissions;
- `ALLOW`, `DENY`, `APPROVAL_REQUIRED`;
- default deny;
- explicit deny precedence;
- expiry;
- rejection of authority originating from model/classifier/prompt output.

This is the correct core authorization direction and should be extended rather than replaced.

### Encrypted local state

`src/reverend/workstation/crypto.py` uses Fernet authenticated encryption with a local protected key file.

`WorkspaceStore` encrypts persisted conversation/job/task payloads and supports privacy modes.

The cloud system needs server-side secret separation and key lifecycle beyond one workstation key file, but the accepted invariant that durable sensitive state is encrypted remains.

### Execution isolation

`src/reverend/development/sandbox.py` already constructs fail-closed bubblewrap execution for untrusted repositories with:

- no shared network namespace;
- no host home;
- no inherited environment;
- bounded writable workspace;
- CPU/RAM/process/file limits;
- no unsafe fallback if required sandbox tools are missing.

### Git isolation

`src/reverend/development/worktrees.py` creates isolated per-task branches/worktrees and preserves the primary checkout.

### Deployment hardening

The current VPS service runs under a dedicated `reverend` user with `NoNewPrivileges`, `PrivateTmp`, `ProtectHome` and `ProtectSystem`. Repository hygiene excludes local secret/key files from Git.

The missing pieces are authenticated multi-user identity, durable authorization subjects, per-user GitHub authority, a server-side secret broker and explicit worker/device identities.

## Decision summary

A8 freezes the following Cloud v1 direction:

1. Reverend has two distinct authenticated human identities.
2. A client may not select another identity without authenticating as that user.
3. Run ownership is immutable and is the source of user-scoped external authority.
4. Authentication and authorization are separate.
5. The existing capability/permission engine remains the authorization foundation.
6. GitHub credentials are stored server-side per user and are never returned to clients/models.
7. Commit author identity and push authentication are both derived from the Run owner.
8. Routine isolated-branch Git operations may be automatic; dangerous integration operations require approval.
9. Models never receive raw GitHub/provider/cloud credentials.
10. Workers receive only short-lived task-scoped authority.
11. Secrets are referenced by ID and injected only at the enforcement point that needs them.
12. Recovery clients are authenticated devices and store only encrypted recovery material.
13. emergency controls have Run, Project and Global scopes.
14. all privileged actions are attributable through immutable audit events.

## Human identity

Canonical user:

```text
User
├── user_id
├── display_name
├── status
├── created_at
└── updated_at
```

The initial installation is private and intentionally supports only the configured two users.

This is not an excuse to make identity a cosmetic dropdown.

### Authentication rule

The server establishes:

```text
request.principal.user_id
```

from an authenticated session/device credential.

A request body field such as:

```json
{"user_id":"alex"}
```

must never be sufficient to act as Alex.

### Initial authentication implementation

The implementation may choose either:

- locally provisioned password/passkey-backed sessions;
- device-bound login tokens created during administrator pairing.

For v1, the important frozen contract is not the exact UX. It is:

- credentials are user-specific;
- sessions are revocable;
- sessions expire;
- the server resolves the principal;
- credentials are not stored in ordinary browser-visible project state.

OAuth/social login infrastructure is unnecessary for a private two-user deployment unless it simplifies implementation.

## Device identity

Each client installation that participates in login or recovery has a device identity:

```text
Device
├── device_id
├── user_id
├── public_key_or_credential_ref
├── created_at
├── last_seen_at
├── revoked_at
└── recovery_enabled
```

A lost device can be revoked without deleting the human user.

A device is not a Run owner. The owner remains the human `user_id`.

## Authorization model

Extend the existing `Capability` / `PermissionEvaluator`.

Authorization input becomes conceptually:

```text
subject
capability
resource scope
authenticated principal
Run ownership
Project membership
current policy
```

Useful scope dimensions include:

```text
user_id
project_id
run_id
repository_id
branch
worker_id
secret_id
provider
```

Models cannot create or widen permissions. This existing invariant remains frozen.

### Human subjects

Examples:

```text
user:<user_id>
project-role:<project_id>:member
system-admin
```

### Non-human subjects

Examples:

```text
run:<run_id>
agent:<agent_instance_id>
worker:<worker_id>
service:lifecycle
service:recovery
```

Non-human subjects must only receive capabilities delegated by trusted server policy.

## Run ownership authority

For every user-scoped external action:

```text
Run
 ↓
owner_user_id
 ↓
user credential / policy
 ↓
Tool Broker enforcement
```

Never:

```text
currently connected viewer
 ↓
external credential
```

If Alex starts a Run and the friend later opens its dashboard, the Run remains Alex-owned and continues to use Alex-scoped GitHub authority.

Ownership changes are not supported in Cloud v1. A different user creates a new Run if authority must change.

## Git and GitHub identity

Each Reverend user may register one or more GitHub identities.

Minimum binding:

```text
GitHubIdentity
├── identity_id
├── user_id
├── github_login
├── git_author_name
├── git_author_email
├── credential_ref
├── repository_scope
├── created_at
└── revoked_at
```

Do not store GitHub passwords.

The credential should be a narrowly scoped GitHub token/OAuth credential or future GitHub App-derived credential.

The implementation must support credential rotation without rewriting Run history.

### Commit identity

In the Run worktree:

```text
git user.name  = run owner configured Git author name
git user.email = run owner configured Git author email
```

### Push identity

Push/PR authentication uses the credential referenced by the Run owner's GitHub identity.

Commit authorship and network authentication should normally correspond to the same human owner.

## GitHub credential scope

Prefer the narrowest practical repository permissions.

Cloud v1 should not require broad account administration.

Expected needs may include:

- read repository contents;
- push branches;
- create/update pull requests;
- read branch/commit/PR state;
- optionally merge when policy approves.

Delete-repository, organization administration and secret-management scopes are not required.

## Git/GitHub operation policy

Initial default:

| Operation | Default |
| --- | --- |
| inspect Git state/history | allow within project |
| create isolated Run branch/worktree | allow |
| commit to isolated Run branch | allow |
| push isolated Run branch | allow |
| create/update PR from Run branch | allow |
| push directly to protected/default branch | approval required or denied by repo protection |
| merge PR | approval required |
| force-push | approval required, normally disabled |
| delete remote branch | approval required |
| alter repository permissions | deny |
| delete repository | deny |
| change organization settings | deny |

Repository-native branch protection remains authoritative where stronger.

## Approval contract

A durable Approval must identify:

```text
approval_id
run_id
project_id
action_type
action_fingerprint
requested_actor
effective_external_identity
resource summary
required_policy
created_at
expires_at
state
decision_user_id
decision_at
```

The UI must display the effective external identity for sensitive GitHub actions.

Example:

```text
Merge reverend/run-481 → main
GitHub identity: @alex
Run owner: Alex
```

The approval cannot silently switch the action to the approver's GitHub credentials. Approval authorizes the Run owner's action; it does not transfer ownership.

### Approval execution rule

An Approval authorizes one bounded action; it does not execute that action and it does not justify retaining compute while a human is deciding.

The `action_fingerprint` binds the decision to the security-relevant operation, target/resource scope and effective external identity that were presented for approval.

A7 owns the lifecycle mechanics:

```text
approval required
↓
durable Approval + checkpoint
↓
AWAITING_APPROVAL
↓
release compute
↓
human decision
↓
RESUME_QUEUED
↓
fresh compute lease
↓
revalidate approval
↓
execute bounded action
```

Before using an approved action, trusted host enforcement must verify:

- the Approval is still approved and unexpired;
- the Run and immutable owner still match;
- the effective external identity still matches;
- the action fingerprint and target/resource scope still match;
- no revocation or stronger current policy invalidates the decision.

If any security-relevant input changed, the previous Approval is stale and a new Approval is required.

The approval endpoint must never bypass the Tool Broker, scheduler or policy checks by executing the privileged action inline.

## Approval policies

Supported v1 policy values:

- `owner_only`;
- `project_member`;
- `project_owner`;
- `either_operator`;
- `system_admin`.

Suggested defaults:

```text
routine isolated branch operations → no human approval
merge/default-branch mutation       → owner or project-member approval by project policy
force push                          → explicit elevated approval
provider lifecycle destructive op   → either operator/system policy
secret export                       → deny by default
```

## Secrets architecture

Create a server-side Secrets Manager/Broker.

```text
Secret
├── secret_id
├── scope_type
├── scope_id
├── secret_type
├── encrypted_value
├── key_version
├── created_at
├── rotated_at
└── revoked_at
```

Supported scopes:

```text
SYSTEM
USER
PROJECT
RUN_EPHEMERAL
```

Examples:

- GitHub user token → USER;
- project deployment token → PROJECT;
- VPS provider lifecycle token → SYSTEM;
- temporary worker credential → RUN_EPHEMERAL.

### Secret-reference rule

Application state stores:

```text
credential_ref = secret:<id>
```

not plaintext credentials.

### Secret delivery rule

Secrets are resolved at the narrowest enforcement point:

```text
agent asks Tool Broker for git push
↓
Policy Engine authorizes
↓
GitHub tool resolves Run owner's credential_ref
↓
credential injected into subprocess/request environment only for that action
↓
credential removed
```

The model sees the operation result, not the raw secret.

## Secret encryption and master keys

At-rest secret encryption must use a dedicated server secret-encryption key, separate from ordinary conversation-state encryption.

The key itself must not be committed or stored in the same plaintext database it protects.

Cloud v1 may use:

- an OS-protected root-owned/dedicated key file;
- provider secret storage if available;
- an encrypted envelope key architecture.

Recovery copies must contain encrypted secret-store material only.

A8 requires a documented recovery-key procedure so replacing the VPS does not make all secrets permanently unreadable.

## Logging and redaction

Existing redaction must be extended to cloud credentials.

Never persist or stream:

- Authorization headers;
- GitHub tokens;
- provider API keys;
- session tokens;
- private keys;
- raw secret values;
- model-visible credential dumps.

Operational events should store:

```text
secret_id
secret_type
scope
operation
success/failure
```

without values.

## Worker identity

A worker is not trusted merely because it can reach the Control API.

Canonical worker:

```text
WorkerIdentity
├── worker_id
├── node_id
├── credential_ref
├── capabilities
├── registered_at
├── expires_at
└── revoked_at
```

### Cloud v1 same-VPS workers

If worker and control plane are on the same machine, authentication may use:

- Unix-domain-socket peer controls; or
- a short-lived service credential.

Do not expose a privileged unauthenticated worker API on a network port.

### Future remote workers

Remote workers should use mutually authenticated transport or equivalently strong short-lived signed credentials.

A worker token should be bound to:

```text
worker_id
run_id where applicable
allowed capabilities
expiry
```

A compromised worker must not automatically gain control-plane administration authority.

## Model trust boundary

Models are untrusted decision components with bounded capabilities.

A model may receive:

- task-specific context;
- source/repository excerpts;
- tool schemas;
- opaque resource/secret references where required.

A model must not receive:

- GitHub tokens;
- provider cloud keys;
- session credentials;
- recovery private keys;
- arbitrary host environment;
- unrestricted filesystem paths;
- Docker/host-control sockets.

Model output may propose an action. The host validates policy and executes it.

This preserves the current invariant that model output cannot create authority.

## Tool enforcement

All privileged operations pass through host enforcement.

```text
Model / Agent
    ↓ proposed action
Tool Broker
    ↓
Policy Engine
    ↓
scope / owner / approval check
    ↓
Secret Broker if needed
    ↓
validated host action
```

No specialist should be able to bypass policy by constructing its own network client with embedded credentials.

## Sandbox boundary

The existing fail-closed untrusted-repository sandbox is retained.

Cloud implementation must additionally ensure:

- worker containers/processes do not run as root where avoidable;
- no host home is mounted;
- no control-plane DB/socket is mounted into untrusted execution;
- no `/var/run/docker.sock` exposure;
- no server secret directory is mounted;
- network is disabled by default for untrusted code;
- project workspaces are scoped to the active Run/task.

## Recovery-peer security

A7 permits developer clients to store recovery replicas.

A8 requires:

1. every recovery device has a registered device identity;
2. the VPS authenticates the device before sending project state;
3. the device authenticates the Reverend server;
4. recovery payloads are encrypted before or during storage;
5. clients acknowledge only hash-verified durable writes;
6. secret-store backups remain encrypted;
7. lost devices can be revoked.

If recovery data is content-addressed, hashes are integrity identifiers, not confidentiality controls.

## Network edge

Initial private deployment should prefer:

```text
Tailscale/private network
+
HTTPS
+
Reverend authentication
```

Defence in depth is intentional. Private networking does not replace application authentication.

Only required ports should be reachable.

Database, model-runtime, internal worker and secret services should not be publicly exposed.

## Emergency controls

Replace a single undifferentiated kill switch with explicit scopes.

### Run stop

```text
STOP_RUN(run_id)
```

Stops/cancels one Run according to A7 safe-emergency semantics.

### Project stop

```text
STOP_PROJECT(project_id)
```

Stops active work and blocks new work for one project until cleared.

### Global stop

```text
STOP_GLOBAL
```

Stops all Reverend execution and prevents new tool/model work until an authorized human explicitly clears the condition.

Emergency control events must be durable and attributed to the authenticated human.

## Audit requirements

Privileged events should capture:

```text
event_id
occurred_at
user_id
run_id
project_id
actor
capability
resource scope
decision
approval_id if any
external identity ref if any
result
```

Do not log secret values.

The existing immutable Control Plane Event store is a suitable foundation.

## Migration from current implementation

| Current | Cloud target |
| --- | --- |
| loopback random token | persistent per-user authentication/session |
| implicit one human | two explicit users + devices |
| Capability/Permission model | retain and extend with user/project/run scopes |
| one local state key | separated state/secret/recovery key responsibilities |
| local Git config/ambient credentials | Run-owner Git identity + server credential ref |
| no GitHub credential broker | per-user encrypted GitHub identities |
| local worker trust | explicit worker/service identities |
| bubblewrap local sandbox | retain, plus no cloud-control/secret mounts |
| one emergency stop concept | run/project/global stops |
| local audit context | user/run/project-attributed immutable events |

## Non-goals for A8

A8 does not attempt to build:

- public customer signup;
- enterprise SSO;
- organization/RBAC complexity beyond the two-user need;
- a general-purpose password manager;
- arbitrary secret export;
- model-controlled credential handling;
- a full zero-trust multi-cloud mesh.

The design should stay proportionate to a private two-developer system while preserving clean authority boundaries.

## Acceptance gates

A8 analysis is complete when all of the following are unambiguous:

1. every human request has an authenticated principal;
2. clients cannot self-select another identity;
3. authorization remains default-deny and host-controlled;
4. model output cannot create permissions;
5. Run ownership is immutable;
6. Git author and push authority derive from Run owner;
7. GitHub credentials are server-side secret references, not client/model payloads;
8. routine Run-branch Git operations and approval-required operations are separated;
9. secret scopes and key responsibilities are defined;
10. workers have explicit authenticated identities;
11. privileged tools enforce policy before secret resolution;
12. untrusted execution cannot access host/control/secret surfaces;
13. recovery peers are authenticated and encrypted;
14. emergency control has run/project/global scope;
15. privileged events are attributable without recording secret values;
16. approvals bind to a stable action fingerprint and cannot be reused for a changed action;
17. approving records authority but does not directly execute the privileged action or bypass fresh scheduling/policy validation.

## Frozen A8 invariant

> No model, worker or client may obtain authority merely by claiming an identity or emitting an instruction. Human identity is authenticated by the server; Run ownership is immutable; permissions are explicit and fail closed; external credentials are resolved only by trusted enforcement code at the moment an authorized action is executed.
