# D13 — Client & Operator UX State Contract

> **Status:** DESIGN CLOSED / READY FOR C2+C8 IMPLEMENTATION  
> **Depends on:** D1, D2, D5, D6, D8  
> **Purpose:** Ensure browser, CLI and IDE clients present authoritative Reverend state faithfully and preserve safety-critical intermediate states.

---

## 1. UX Invariant

> The client presents Control Plane truth; it never invents workflow truth.

A UI may optimize presentation, but cannot imply that:

- pause completed while Actions are still settling;
- cancellation completed before CANCELLED;
- an approval caused an action to execute;
- recovery succeeded while RECOVERY_BLOCKED;
- provider stop means billing has stopped before confirmation;
- model confidence equals verification.

---

## 2. Client Responsibilities

Clients own presentation, authenticated command submission, human input, approval decisions, navigation and local UI preferences.

Clients do not own:

- Run/Workflow/Task/Job state;
- queue order;
- Approval validity;
- external credential identity;
- cost ledger;
- ResourceLease;
- recovery truth;
- policy authorization.

---

## 3. Primary Cloud Views

1. Sign in/session
2. Projects
3. Project overview
4. Run queue
5. Run detail
6. Workflow/Tasks
7. Agents/Teams
8. Approvals
9. Human input requests
10. Artifacts/Evidence
11. Costs/Budgets
12. Compute/Worker health
13. System status
14. Recovery issues
15. Emergency/Maintenance controls for authorized operators

CLI/IDE may expose subsets but preserve the same semantics.

---

## 4. Run Detail

Primary operational fields:

- immutable owner;
- objective;
- pinned repository/base commit;
- exact Run status;
- queue class/position where meaningful;
- Tasks/dependencies;
- Agents/Jobs;
- blockers;
- cost/budget;
- compute/lease summary;
- checkpoint/recovery state;
- verification/integration state;
- resulting branch/PR.

---

## 5. Run State Presentation Matrix

| State | Meaning | Compute expectation | Primary actions |
|---|---|---|---|
| QUEUED | waiting for top-level slot | zero | cancel; authorized run-now |
| STARTING | preparing durable execution/resources | may begin | request cancel |
| RUNNING | useful work is admitted | possible | pause; cancel |
| PAUSE_REQUESTED | request accepted; current safe action settling | possible temporarily | cancel |
| PAUSING | checkpoint/resource release in progress | possible temporarily | cancel |
| PAUSED | durable and intentionally stopped | zero active compute | resume; cancel |
| RESUME_QUEUED | waiting to resume | zero until admitted | cancel |
| RESUMING | restoring/revalidating | possible | request cancel |
| AWAITING_APPROVAL | aggregate progress requires approval | zero productive compute for blocked aggregate Run | approve/reject if authorized; cancel |
| AWAITING_INPUT | aggregate progress requires human clarification | zero productive compute for blocked aggregate Run | answer; cancel |
| RECOVERING | reconciling durable state after interruption | bounded recovery work | observe/cancel where safe |
| RECOVERY_BLOCKED | cannot prove a safe automatic continuation | zero productive compute | inspect and choose authorized recovery action |
| CANCEL_REQUESTED | cancellation requested; actions/resources may still settle | possible temporarily | observe |
| CANCELLING | releasing/reconciling remaining effects | possible temporarily | observe |
| COMPLETED | accepted verified completion | zero | review result |
| FAILED | terminal failure | zero | inspect/retry via allowed path |
| CANCELLED | cancellation fully settled | zero | inspect history |

Use exact state or an unambiguous equivalent label.

---

## 6. Progress Presentation

Do not invent a single percentage from model chatter.

Prefer:

~~~text
requirements: 8 / 10 satisfied
tasks:        5 complete / 2 running / 1 blocked
verification: pending
cost:         £x / £budget
~~~

Any future approximate percentage must be labeled estimated and must never drive state.

---

## 7. Pause UX

After Pause:

1. submit idempotent D2 command;
2. show server-reported PAUSE_REQUESTED;
3. explain current safe operation may finish;
4. show PAUSING during checkpoint/release;
5. show Paused only after PAUSED.

No optimistic PAUSED state.

---

## 8. Cancellation UX

Use:

~~~text
Cancel requested
→ settling active actions/resources
→ Cancelled
~~~

Never show Cancelled during CANCEL_REQUESTED/CANCELLING.

If cleanup leads to RECOVERING or FAILED, show that truth.

---

## 9. Approval UX

Approval card shows:

- action type;
- Run/Project;
- requesting Task/Agent;
- effective external identity;
- target repository/resource/ref;
- risk summary;
- cost/resource summary when relevant;
- expiration;
- why approval is required.

Approval flow:

~~~text
approve/reject
↓
decision persisted
↓
Run may become RESUME_QUEUED
↓
action revalidates policy/fingerprint before effect
~~~

Approved does not mean executed.

Owner-only approval must make owner identity explicit.

---

## 10. Human Input UX

Clarification is separate from Approval.

Show question, requester, reason, sensitivity ceiling, affected work and whether unrelated Tasks continue.

Answering a question never authorizes an unrelated privileged action.

---

## 11. RECOVERY_BLOCKED UX

Dedicated surface shows:

- ambiguous Action ID/type;
- last Action state;
- latest valid checkpoint;
- reconciliation evidence;
- external ref/resource;
- why automatic continuation is unsafe;
- allowed human recovery choices.

Do not expose a generic Retry when retry could duplicate a side effect.

Recovery choices are authenticated durable commands.

---

## 12. Failure UX

Distinguish:

~~~text
task/model/tool failure
policy denial
budget block
provider unavailable
verification rejection
recovery ambiguity
system failure
~~~

Show stable error code + safe explanation.

Do not expose secrets, raw headers, hidden chain-of-thought, unrestricted tool output or internal stack traces to ordinary users.

---

## 13. Cost and Budget UX

Show:

- estimated cost;
- reconciled actual when available;
- hard/soft budget;
- active reservations;
- variable Run cost;
- shared cost separately;
- billing uncertainty.

Hard-limit copy must explain that productive paid work stops at a safe boundary while narrowly necessary safety cleanup may still run.

Do not display zero GPU cost until provider-confirmed billing state satisfies D8.

---

## 14. Compute UX

Show logical fields:

- node/worker class;
- trust class;
- lifecycle;
- model profile;
- lease/Job;
- health;
- rate;
- startup/load state;
- idle grace/draining.

Community compute must be visibly lower-assurance.

Never expose worker credentials.

---

## 15. Workflow / Agent UX

Distinguish authoritative Tasks from AgentInstances/Teams executing them.

Show dependencies, blockers and produced Artifacts.

Agents are never presented as independent workflow authority.

One blocked Team member may coexist with continuing work elsewhere.

---

## 16. Verification UX

Separate implementation from acceptance:

~~~text
Implementation produced
Deterministic tests: PASS
Security review: PASS
Independent verification: PASS
Integration gate: PENDING
~~~

A model-emitted completion signal is not accepted completion.

---

## 17. Artifact / Evidence UX

Artifact viewer shows type/schema, producer, provenance, validation, promotion, sensitivity and lineage.

Evidence drawer shows source URL/title, authority, freshness, retrieval/publication dates, transport and citation refs.

Active HTML/SVG/media renders through D6 sandboxing, never in the authenticated app origin.

---

## 18. SSE / Reconnect

~~~text
authenticate
↓
fetch authoritative snapshot
↓
open events stream from durable cursor
↓
apply authorized presentation events
↓
disconnect?
  reconnect with Last-Event-ID
↓
if replay requires resync:
  refetch snapshot
~~~

UI state is a projection. Missed SSE does not imply no server change.

---

## 19. Optimistic UI

Allowed:

- spinner;
- request-submitted indicator.

Not allowed:

- optimistic lifecycle transition;
- optimistic Approval completion;
- optimistic cost settlement;
- optimistic provider stop;
- optimistic Git merge result.

---

## 20. Authorization Presentation

UI may hide unavailable actions for usability, but hidden is not security and visible is not authorization.

Server always rechecks capability/resource scope.

401/403/409/approval-required are first-class outcomes.

Distinguish Project member, Project owner, immutable Run owner and SYSTEM_ADMIN where relevant.

---

## 21. Emergency / Maintenance UX

Authorized operator controls:

- STOP_RUN;
- STOP_PROJECT;
- STOP_GLOBAL;
- maintenance mode.

Emergency messaging means:

~~~text
deny new productive work
+ allow required safety cleanup
+ wait for confirmed settlement
~~~

Do not show fully stopped until required cleanup is known.

Maintenance remains distinct from outage: reads/auth may remain available while new Run admission is blocked and current work drains.

---

## 22. Security Presentation

Browser requirements:

- D2 secure session/cookie handling;
- CSRF for mutations;
- strict CSP/security headers;
- no secret/token dump to local storage;
- no hidden chain-of-thought;
- no active Artifact in main origin;
- no direct untrusted remote image load;
- no credential in URL/query.

---

## 23. Accessibility

Minimum v1:

- keyboard-accessible actions;
- visible focus;
- semantic landmarks/headings;
- state not conveyed by color alone;
- appropriate live-status announcements;
- labeled tables;
- text labels for approval/emergency actions;
- reduced-motion compatibility;
- error messages associated with controls.

---

## 24. CLI / IDE Consistency

CLI/IDE preserve the same lifecycle semantics.

A client timeout does not imply command failure. Retry uses idempotency.

They may show a subset of browser views but cannot collapse Approval, Input, Recovery or cancellation states.

---

## 25. Existing UI Migration

Keep useful current UI elements such as source drawers, safe presentation helpers and diagram rendering.

Cloud mode must replace:

- loopback-only session token assumptions;
- local /api endpoints;
- Workstation SQLite as authority;
- local-only model/job state assumptions.

Local Workstation remains supported through C9.

---

## 26. UX Acceptance Tests

Must prove:

- no PAUSED before server PAUSED;
- no CANCELLED during cancellation;
- Approval decision distinct from action completion;
- AWAITING_INPUT distinct from Approval;
- RECOVERY_BLOCKED has no blind retry;
- SSE reconnect replays/resyncs safely;
- owner-only Approval cannot be decided by wrong user;
- revoked session loses stream/action access;
- budget warning/block semantics are clear;
- provider stop is not shown as zero-cost prematurely;
- active Artifact content cannot execute in app origin;
- chain-of-thought/secrets never render;
- keyboard paths cover approval/input/pause/cancel/recovery;
- local Workstation remains usable during migration.

---

## 27. Exit Condition

D13 is satisfied when client developers can implement Cloud UI without inventing state meanings, pause/cancel behavior, approval semantics, recovery presentation, cost/compute semantics, SSE reconnection, Artifact security or emergency behavior.


---

## 28. Specification & Capability UX Addendum

Cloud UI/CLI must surface the specification-driven operating model introduced by D1–D3.

### Project specification view

Display:

- SpecificationPackage versions;
- DRAFT / VALIDATING / ACCEPTED / SUPERSEDED / REJECTED;
- exact accepted hash/version;
- validation findings;
- acceptance actor/time;
- supersession lineage;
- linked Requirements / Decisions / AcceptanceCriteria.

Only authorized humans can accept/supersede a package.

### Run creation

Run creation explicitly chooses:

~~~text
Specification-driven Run
or
Objective-driven Run
~~~

For specification-driven mode, UI shows the exact pinned package version before submission.

### Run detail

Display the pinned SpecificationPackage/version alongside immutable Run owner.

A later Project specification update must not visually imply that the active Run changed specification.

### Escalation

EscalationArtifact gets a first-class operator view containing:

- Task/Run;
- relevant requirement/contract refs;
- attempts/failures;
- deterministic evidence;
- exact question/decision required;
- cost consumed;
- allowed response actions.

### Capability / disclosure state

Where relevant, UI exposes:

- Community Cloud disclosure policy;
- whether a Job is blocked because mandatory context cannot be sent to an available worker;
- research/browser/network wait/failure;
- CPU/browser/model-worker lifecycle;
- recovery/degraded state.

The client explains state; it never becomes the source of policy truth.
