# D6 — Security, Secrets, Git, Approvals & Emergency Controls

> **Status:** DESIGN ACCEPTED FOR DEVELOPMENT  
> **Depends on:** A8, A12, D2, D4, D5  
> **Purpose:** Turn Reverend's fail-closed security architecture into concrete enforcement boundaries suitable for the private two-user Cloud v1 deployment.

---

## 1. Governing Invariant

> **Identity creates authority; model output never does.**

No model, Agent, worker, browser, CLI payload, or recovery replica may grant itself authority.

Authority originates from:

- authenticated human identity;
- explicit policy;
- immutable Run ownership;
- server-issued worker/service identity;
- durable Approval where required.

---

## 2. Security Domains

Cloud v1 separates:

~~~text
Human Identity
Project Membership
Run Ownership
Capability Authorization
Secrets
Tool Enforcement
Worker Identity
Model Trust
Git/GitHub External Identity
Approvals
Emergency Controls
Audit
~~~

Do not replace these with one broad “trusted user” flag.

---

## 3. Human Identity

Two configured users exist.

Authentication produces:

~~~text
principal_user_id
session_id
device_id?
~~~

Request body cannot select or alter principal.

A disabled user cannot create new sessions or authorize new work.

---

## 4. Authorization Engine

Extend existing Capability / PermissionEvaluator.

Authorization tuple:

~~~text
subject
capability
resource scope
authenticated principal
Run ownership
Project membership
current policy
emergency state
~~~

Useful resource dimensions:

~~~text
user_id
project_id
run_id
repository_id
branch
worker_id
secret_id
provider
~~~

Default is DENY.

Explicit deny takes precedence.

Model/classifier output is not an authority source.

---

## 5. Subject Types

Human:

~~~text
user:<uuid>
project-role:<project>:owner
project-role:<project>:member
system-admin
~~~

Non-human:

~~~text
run:<uuid>
agent:<uuid>
worker:<uuid>
service:scheduler
service:capacity
service:recovery
service:cost
~~~

Non-human authority is delegated and scoped.

---

## 6. Run Ownership

owner_user_id is immutable.

For user-scoped external action:

~~~text
Run
↓
owner_user_id
↓
configured external identity
↓
Tool Broker
↓
operation
~~~

Viewer identity never replaces owner identity.

---

## 7. GitHubIdentity

Persist metadata:

~~~text
identity_id
user_id
github_login
git_author_name
git_author_email
credential_ref
repository_scope
created_at
revoked_at
~~~

Credential itself lives in Secret Broker.

Rotation changes credential_ref while historical Run ownership remains unchanged.

---

## 8. Git Commit Identity

For Run worktree:

~~~text
git user.name  = Run owner's configured author name
git user.email = Run owner's configured author email
~~~

Do not inherit ambient control-host global Git identity.

---

## 9. Git Push Identity

Push/PR API uses Run owner's GitHub credential reference.

Credential must be narrowly scoped to required repositories/actions.

Do not require:

- repository deletion;
- organization administration;
- secret management;
- account administration.

Prefer fine-grained tokens/GitHub App-derived credentials where practical.

---

## 10. Git Policy v1

| Operation | Default |
|---|---|
| inspect state/history | allow within Project |
| create Run branch/worktree | allow |
| commit Run branch | allow |
| push Run branch | allow |
| create/update PR | allow |
| mutate protected/default branch directly | approval/branch protection |
| merge PR | approval |
| force push | elevated approval; normally disabled |
| delete remote branch | approval |
| alter repository permissions | deny |
| delete repository | deny |
| organization administration | deny |

Repository-native protections remain stronger authority where applicable.

---

## 11. Secret Model

Secret metadata:

~~~text
secret_id
scope_type
scope_id
secret_type
encrypted_value
key_version
created_at
rotated_at
revoked_at
~~~

Scopes:

~~~text
SYSTEM
USER
PROJECT
RUN_EPHEMERAL
~~~

Examples:

- RunPod API key → SYSTEM;
- GitHub token → USER;
- deployment credential → PROJECT;
- worker bootstrap/session → RUN_EPHEMERAL.

---

## 12. Secret-Reference Rule

Application/domain records store:

~~~text
credential_ref = secret:<uuid>
~~~

not plaintext.

No public API returns encrypted_value.

---

## 13. Secret Encryption

Use a dedicated secret-encryption master key separate from ordinary application/state encryption.

Cloud v1 acceptable implementation:

- root-owned key file outside repository/data DB;
- mode 0600;
- loaded only by Secret Broker process/module;
- encrypted values using cryptography library authenticated encryption;
- key_version stored per secret;
- documented rotation and recovery.

The master key is not stored plaintext in PostgreSQL.

---

## 14. Secret Recovery

Recovery backup contains:

- encrypted secret rows;
- protected key-recovery material per documented operator procedure.

A backup without required key material is not considered complete recovery.

Recovery devices receive encrypted secret-store material only.

---

## 15. Secret Broker API

Internal only.

Conceptual operations:

~~~text
resolve_for_action(secret_ref, action_context)
create(...)
rotate(...)
revoke(...)
metadata(...)
~~~

resolve_for_action validates:

- caller service identity;
- capability;
- Run/Project/user scope;
- action type;
- Approval where required.

Secret value is returned only to trusted adapter memory for bounded use.

---

## 16. Secret Delivery

Example Git push:

~~~text
Agent proposes GitPush
↓
Tool Broker validates schema
↓
Policy Engine checks Run owner + capability + approval policy
↓
Secret Broker resolves owner's Git credential
↓
trusted Git adapter executes
↓
credential removed from subprocess environment
↓
sanitized result returned
~~~

Model sees only result.

---

## 17. Tool Broker

All privileged operations pass through one host-enforcement surface.

Tool descriptor includes:

- capability;
- risk class;
- side-effect class;
- recovery strategy;
- required Approval policy;
- allowed execution environment;
- secret references needed.

No Specialist should open its own arbitrary privileged network connection with embedded credentials.

---

## 18. Approval v1

Required fields are in D1.

Security fingerprint must bind:

~~~text
action type
normalized arguments digest
target/resource
Run ID
Run owner
effective external identity
security-relevant policy version
~~~

Approval is invalid if any bound component changes.

---

## 19. Approval Policies

Supported:

~~~text
owner_only
project_member
project_owner
either_operator
system_admin
~~~

Initial defaults:

- isolated branch routine action → no approval;
- PR merge/default-branch mutation → Project policy, at least authorized human;
- force push → elevated explicit approval;
- provider destructive admin op → either_operator/system policy;
- secret export → deny by default.

---

## 20. Approval Use

Before executing approved action:

1. Approval state = APPROVED;
2. unexpired;
3. correct Run;
4. owner unchanged;
5. effective external identity unchanged;
6. action fingerprint unchanged;
7. current policy does not newly deny;
8. emergency state permits execution.

Then mark USED within the action/journal transaction as appropriate.

Never reuse an Approval for a changed action.

---

## 21. Worker Trust Classes

Minimum:

~~~text
CONTROL_PLANE
DEDICATED_WORKER
COMMUNITY_CLOUD_WORKER
LOCAL_UNTRUSTED_SANDBOX
EXTERNAL_API
~~~

Trust class is set by trusted launch/policy logic.

Worker cannot self-assert stronger trust.

---

## 22. Community Cloud Worker Rules

RunPod Community baseline receives only:

- Task-scoped workspace/snapshot;
- compiled context;
- required temporary Artifacts;
- short-lived worker credentials;
- opaque identifiers.

It must never receive:

- GitHub credential;
- RunPod lifecycle API key;
- PostgreSQL credentials;
- Secret Broker master key;
- recovery private keys;
- unrelated Project data;
- long-lived admin/service credential.

Privileged external actions remain on Control Plane.

---

## 23. Stronger-Trust Placement

Job declares trust_requirement.

If requirement exceeds COMMUNITY_CLOUD_WORKER:

- Compute Scheduler rejects Community node;
- waits/provisions eligible stronger class;
- never silently downgrades requirement.

Highly sensitive/regulatory workloads may require dedicated/Secure Cloud.

---

## 24. Worker Credential

D4 worker session is:

- short-lived;
- opaque;
- hashed at rest;
- node/epoch-scoped;
- limited to internal protocol.

Compromised worker does not gain:

- Project administration;
- provider lifecycle;
- Secret Broker;
- GitHub authority.

---

## 25. Model Trust Boundary

Model may receive:

- Task context;
- repository excerpts;
- Artifact/Evidence content allowed by policy;
- tool schemas;
- opaque resource references.

Model must not receive:

- raw secrets;
- session cookies/tokens;
- cloud provider keys;
- DB credentials;
- recovery keys;
- arbitrary host environment;
- Docker socket.

Model output is untrusted input to Tool Broker.

---

## 26. Sandbox Boundary

Retain fail-closed bubblewrap behavior for untrusted code.

Cloud requirements:

- non-root where possible;
- no host home;
- no inherited ambient environment;
- no Control Plane DB socket/credentials;
- no Secret Broker key directory;
- no Docker socket;
- writable Run/Task workspace only;
- network disabled by default;
- explicit CPU/RAM/process/file limits.

If required isolation mechanism is unavailable, fail closed.

---

## 27. Network Policy

Public endpoints:

- HTTPS Reverend API only.

Private/internal:

- PostgreSQL;
- vLLM/SGLang;
- worker protocol where private network is used;
- Secret Broker;
- internal metrics/admin endpoints.

Initial deployment prefers Tailscale/private networking plus HTTPS.

Private network does not remove application authentication.

---

## 28. Logging and Redaction

Extend current redaction to detect/strip:

- Authorization;
- cookies;
- GitHub tokens;
- RunPod keys;
- session tokens;
- private keys;
- DB URLs with passwords;
- raw secret values.

Logs store identifiers:

~~~text
secret_id
operation
scope
success/failure
~~~

never secret content.

---

## 29. Recovery Device Security

Recovery-enabled Device must:

- be registered to user;
- authenticate server;
- be authenticated by server;
- store encrypted payload;
- verify hashes before ACK;
- support revocation.

A revoked/lost device receives no new generations.

Stored recovery data must remain unreadable without intended recovery-key procedure.

---

## 30. Emergency Controls

### STOP_RUN(run_id)

- sets durable emergency/cancel state for one Run;
- prevents new action admission;
- uses D5 emergency-safe interruption.

### STOP_PROJECT(project_id)

- stops active Project work;
- blocks new Project Runs until cleared.

### STOP_GLOBAL

- stops all new model/tool work;
- scheduler admits no new execution;
- active unsafe side effects settle according to D5;
- requires authorized explicit clear.

Events are durable and human-attributed.

---

## 31. Security Event Audit

Privileged events capture:

~~~text
event_id
timestamp
principal user
Project / Run
actor
capability
resource scope
decision
Approval ID
external identity ref
result
~~~

No secret values.

---

## 32. Key Rotation

Design must support:

- session invalidation;
- GitHub credential rotation;
- provider key rotation;
- secret-encryption key version rotation.

Secret key rotation process:

1. install new key version;
2. new writes use new key;
3. background/restricted migration re-encrypts old records;
4. verify;
5. retain old key only until recovery generations no longer depend on it;
6. retire old key securely.

---

## 33. Threat Cases to Test

- client sends another user's user_id;
- viewer tries to push with own GitHub credential from another owner's Run;
- Agent fabricates approval object;
- worker requests unrelated Project artifact;
- Community worker requests Secret Broker endpoint;
- stale Approval reused after target changed;
- token appears in log exception;
- sandbox tries /var/run/docker.sock;
- worker reports stronger trust than launch profile;
- CSRF mutation from foreign origin;
- recovery device revoked mid-transfer;
- emergency stop while side effect active.

All must fail safely.

---

## 34. D6 Acceptance Tests

Must prove:

- default-deny capability behavior;
- model output cannot create permission;
- Run owner drives Git author/push;
- viewer cannot substitute identity;
- Secret Broker never returns value to model/API;
- approval fingerprint invalidates on action change;
- Community worker lacks protected credentials;
- trust mismatch blocks placement;
- sandbox has no host/control secret surfaces;
- STOP_GLOBAL prevents new Jobs;
- logs/SSE/API contain no seeded test secret;
- recovery device revocation is enforced.

---

## 35. Exit Condition

C5 is complete when privileged actions can be proposed by Agents yet executed only through authenticated, policy-checked, Approval-aware trusted adapters with server-side secret resolution, immutable Run-owner external identity, auditable events, and tested worker/sandbox isolation.


---

## 36. Recursive Architecture Hardening — Credential, Approval and Secret Isolation

### Password credentials are first-class security records

Human password/setup credentials are stored in the D1 `auth_credentials` table, separate from user presentation data and separate from generic retrievable Secrets.

Password hashes are never resolvable through Secret Broker as plaintext.

### Privilege-separated Secret Broker

The master key is available only to the D0 privilege-separated Secret Broker helper, not to the general Control Plane process.

The helper:

- runs under a separate OS credential boundary;
- exposes authenticated local IPC only;
- authorizes every secret resolution against an action context;
- returns plaintext only for a bounded trusted adapter invocation;
- never mounts its key/socket into a sandbox or worker;
- emits metadata-only audit records.

A Python module import is not treated as a security boundary.

### Owner-scoped credential approvals

An action that exercises a **USER-scoped external credential** under the immutable Run owner's identity defaults to `owner_only` whenever human approval is required.

`either_operator` may be used for system/provider administration, but it does not implicitly authorize the other developer to approve use of the Run owner's GitHub or other personal credential.

Explicit Project policy may delegate a narrower action class, but the delegation itself is durable, human-authored policy and is included in the Approval fingerprint.

### Single-use Approval binding

The Approval row records `used_action_id`. Approval consumption and creation of the corresponding PLANNED ActionRecord occur atomically as defined by D5.

Concurrent executors therefore cannot both consume one Approval.

### Secret references are typed

A `secret:<uuid>` reference resolves only when all of these match:

~~~text
expected secret_type
expected scope
expected owner/project/run
calling service identity
requested operation
current policy
~~~

A caller cannot substitute a different secret ID of another type merely because it has permission to invoke the same adapter.

### Community-worker disclosure statement

COMMUNITY_CLOUD_WORKER means the infrastructure provider can potentially observe any plaintext context intentionally sent to that worker. Therefore:

- never classify Community Cloud as confidential execution;
- Project/Task policy must tag material that may not leave the stronger trust domain;
- Context Broker filters such material before placement;
- a Job whose mandatory context exceeds the worker trust ceiling must be rejected or placed on stronger-trust infrastructure, never redacted into an incorrect Task silently.


---

## 37. Recursive Audit Cycle 2 — SSRF, Repository Canonicalization and Credential Execution

### Credential-bearing operations should avoid plaintext return to the general process

The preferred Secret Broker contract is execution-oriented:

~~~text
execute_with_secret(
  secret_ref,
  typed_adapter_operation,
  validated_action_context
)
~~~

The privilege-separated helper injects the credential only into the narrow trusted adapter/subprocess performing that operation and returns a sanitized result.

A raw `resolve_for_action` plaintext return is reserved for adapters that cannot reasonably execute inside the helper boundary and requires an explicit audited exception.

This reduces the value of compromising the general Control Plane process.

### SSRF and metadata-service protection

Any tool that fetches a URL supplied or influenced by a model, repository or external source must:

- allow only approved schemes;
- resolve DNS and reject loopback/private/link-local/multicast/metadata-service ranges unless an explicit local-provider adapter owns the endpoint;
- re-check the connected address after redirects;
- bound redirect count and response bytes;
- prevent DNS-rebinding bypass;
- strip ambient credentials;
- never inherit proxy credentials implicitly.

Cloud metadata endpoints such as link-local instance metadata are denied by default.

### Repository remote canonicalization

Projects do not accept arbitrary credential-bearing Git URLs as authority.

For GitHub Projects:

~~~text
owner + repository
→ server resolves via configured GitHub provider
→ canonical repository identity
→ server constructs clone/fetch transport
~~~

Reject:

- embedded username/password/token URLs;
- file:// remotes from remote clients;
- arbitrary SSH command/options;
- repository identity changes that bypass Project authorization.

### Worker identity credential

The D1 worker identity token is narrowly scoped to obtaining current-epoch worker sessions for its own node/provider instance.

It is:

- hashed at rest;
- never a Project/user credential;
- revoked at node termination/drain/compromise;
- not accepted by the public API;
- not sufficient to create ResourceLeases or widen trust.

### Artifact browser isolation

Security review includes active-content Artifacts.

HTML/SVG/media generated by models or repositories cannot execute in the authenticated Reverend origin. Preview uses the D2 sandboxed rendering boundary.
