# D14 — Development Readiness, Baseline & PostgreSQL Test Strategy

> **Status:** DESIGN CLOSURE / DEVELOPMENT ENTRY CONTRACT  
> **Depends on:** A12, D0–D13  
> **Purpose:** Close the remaining pre-development process gaps: baseline evidence, PostgreSQL validation strategy and architecture decision control.

---

## 1. Design Closure Verdict

Review covered:

- A0–A12;
- D0–D9;
- current 0.4.0 source structure;
- research/retrieval implementation;
- policy/development/runtime/workstation boundaries;
- current CI;
- current test inventory.

D10–D13 and the ADR framework close the remaining design-level gaps found by that review.

**No known Cloud-v1-blocking architecture question remains that should prevent C0 once a fresh current-main baseline is recorded.**

This is not a claim that implementation defects are impossible. D9's C9 recursive audit remains mandatory.

---

## 2. Closure Specifications

| Document | Closes |
|---|---|
| D10 | search/fetch/reference/evidence/retrieval/index authority |
| D11 | legacy 0.4.0 → Cloud refactor/cutover ambiguity |
| D12 | per-tool policy/secret/side-effect/recovery ambiguity |
| D13 | browser/CLI/operator lifecycle presentation ambiguity |
| D14 | baseline/testing/change-control Development entry |

Architecture decisions are managed under Documentation/Design/Decisions.

---

## 3. Historical Accepted Baseline

Retained 0.4.0 acceptance evidence:

~~~text
docs/current/release/final-acceptance.md
accepted revision: 418524b533f6c05587698dffe8b9a5e4f0434093
complete Python suite: 619 passed / 0 failed
M16 live: PASS
M17 live search/fetch: PASS
M18 live visual acquisition: PASS
portable_ok: true
live_ok: true
overall_ok: true
~~~

This is a historical regression baseline, not a claim about the current-main test count.

---

## 4. Static Test Inventory at Design Closure

Pre-closure review of main@c73b7a26451baed7fc8bdb856737906daf5c0bb7 found:

~~~text
123 test_*.py modules under tests/
approximately 758 KiB of Python test source
CI workflow: .github/workflows/python-unit.yml
full suite command: python -m pytest -q
~~~

CI also contains targeted tests, ResearchBench, full suite, release smoke, M16/M17/M18 portable contracts and final portable programme validation.

Static inventory is not runtime pass evidence.

---

## 5. Fresh C0 Baseline

Before the first C0 code branch changes runtime behavior, record a fresh baseline from current accepted main.

~~~bash
git rev-parse HEAD
python -m pip install -e '.[dev]'
python -m pytest -q

python -m reverend.benchmarks.final_validation \
  --repository . \
  --skip-live \
  --report-root benchmarks/results/vnext/final-validation
~~~

Where the supported live local environment is intentionally available:

~~~bash
python -m reverend.benchmarks.final_validation \
  --repository . \
  --report-root benchmarks/results/vnext/final-validation
~~~

Use the template under Documentation/Design/Baselines.

Never copy 619 passed into the new record unless a new run reports it.

---

## 6. Baseline Record Fields

Record:

- date/time;
- commit SHA;
- Python version;
- OS/WSL environment;
- dependency install result;
- pytest command/result/counts;
- portable validation report;
- live validation or explicit not-run reason;
- known environment limitations;
- operator;
- CI/run evidence where available.

A failing baseline becomes an explicit pre-C0 issue; it is not hidden.

---

## 7. PostgreSQL Test Strategy

SQLite-only tests cannot validate Cloud authority.

### 7.1 Migration tests

For every migration set:

1. start empty ephemeral PostgreSQL;
2. apply migrations;
3. validate schema/constraints/indexes/roles;
4. test supported forward migration;
5. prove failed migration does not become accepted partial schema;
6. run integrity assertions.

### 7.2 Repository contract tests

Exercise shared domain service semantics against PostgreSQL and local compatibility stores where both remain supported.

Compare behavior, not SQL syntax.

### 7.3 Database constraint tests

Database must reject invalid critical states, including:

- multiple active top-level Runs;
- invalid same-scope references;
- invalid immutable lineage;
- Artifact parent cycles/cross-Project linkage;
- mismatched Approval scope;
- invalid Secret scope;
- invalid active lease/resource uniqueness;
- forbidden mutation of immutable catalog/history.

### 7.4 Transaction tests

Prove lifecycle mutation + durable Event atomicity:

~~~text
both commit
OR
neither becomes visible
~~~

### 7.5 Concurrency tests

Use real concurrent PostgreSQL sessions/processes for:

- Run admission;
- idempotency key races;
- Event cursor ordering;
- Action cursor ordering;
- scheduler leadership;
- lease grant/revoke;
- budget reservations;
- queue selection;
- Project/policy bootstrap.

Mocks cannot substitute for these.

### 7.6 Database-role tests

Use separate credentials matching production roles.

At minimum:

- migration role can change schema;
- runtime/API role cannot ALTER/DROP;
- runtime role cannot hard-delete immutable audit lineage;
- controller roles receive only required privileges;
- Secret Broker master key is not exposed by DB privileges.

### 7.7 LISTEN/NOTIFY

Notification is acceleration only.

Prove:

- connected consumer receives notification;
- missed notification after disconnect is recovered by durable Event cursor;
- reconnect does not treat NOTIFY as authority.

### 7.8 Advisory leadership

Use dedicated connections.

Prove one leader per singleton controller, immediate stop on lock-connection loss and external-action reconciliation before replacement leader duplicates effects.

### 7.9 Backup/restore

By C6/C8:

- create representative state;
- back up PostgreSQL + BlobStore/recovery material;
- restore to blank environment;
- validate hashes/references;
- revoke restored sessions before readiness;
- reconcile post-backup Action intents.

---

## 8. PostgreSQL CI Topology

CI must provide real ephemeral PostgreSQL.

Requirements:

- pin a production-supported major version when C1 lands;
- health check before tests;
- isolated DB per test job;
- use the same migration entry point as operations;
- application tests do not run as DB superuser except controlled setup;
- concurrency tests never fall back to SQLite.

The exact major version is a C1 deployment dependency. Changing it later is an upgrade decision, not an incidental CI change.

---

## 9. Recommended Test Markers

~~~text
unit
postgres
concurrency
fault
security
browser
provider_live
model_live
billing_live
slow
~~~

Policy:

- deterministic unit/portable checks on normal code PRs;
- PostgreSQL tests on every Cloud code PR once C1 exists;
- fault/security tests as phases land;
- paid live tests only under explicit authorization;
- C9 executes the complete required matrix.

---

## 10. Test Data Policy

Fixtures must not use real GitHub/RunPod tokens, production recovery keys or personal Project data.

Use fake providers, ephemeral users/projects, local Git fixtures, deterministic model stubs and protected live secrets only for intentional live gates.

---

## 11. Fault-Injection Harness

C6 should support deterministic failpoints around:

~~~text
Action intent persisted
Action STARTED
external effect accepted
result before persistence
result persisted
checkpoint write/publish
Git push
provider provision/stop
Approval consumption
RecoveryGeneration replication
~~~

Every failpoint test asserts final durable state.

---

## 12. Fake Provider Requirements

Before paid RunPod tests, use the same provider contract to emulate:

- delayed provision;
- duplicate request;
- timeout after provider acceptance;
- instance disappearance;
- wrong GPU/trust tier;
- rate change;
- stop delay;
- billing still active;
- orphan instance;
- API/rate-limit failures.

---

## 13. Security Tests

Mandatory negative coverage includes:

- auth/session/CSRF;
- cross-user/Project isolation;
- default deny;
- stale Approval fingerprint;
- Secret Broker scope;
- credential destination pinning;
- SSRF/DNS rebinding/redirect;
- sandbox escape attempts;
- secret absence from argv/env/log;
- active Artifact browser isolation;
- Community worker isolation;
- supply-chain digest validation.

---

## 14. UX Contract Tests

D13 tests operate at API/client boundary:

- exact lifecycle states;
- SSE reconnect;
- pause/cancel intermediate state;
- Approval vs execution;
- human input;
- recovery blocked;
- cost uncertainty;
- session revocation;
- accessibility-critical paths.

Current Workstation UI tests remain regression coverage through C9.

---

## 15. C0 Contract-First Scope

C0 freezes/creates shared contracts for:

- IDs/enums;
- Run lifecycle;
- Event envelope;
- Artifact envelope;
- Approval;
- ActionRecord;
- ResourceRequest/Lease;
- AgentSpec/AgentInstance;
- ContextManifest;
- CostEvent/RateSnapshot;
- worker protocol;
- D10 ResearchRequest/EvidenceSource;
- D12 ToolDescriptor.

C0 does not expose unauthenticated Cloud mutation, provision paid GPU, delete Workstation, replace every SQLite implementation or enable unjournaled privileged tools.

---

## 16. Architecture Decision Control

Use Documentation/Design/Decisions.

An ADR is required when a change modifies:

- A12 invariant;
- authority ownership;
- durable contract meaning;
- lifecycle semantics;
- security/trust boundary;
- secret boundary;
- side-effect/recovery semantics;
- data authority;
- cost attribution;
- a deployment guarantee in a way that changes system guarantees.

Ordinary refactors preserving contracts do not need ADRs.

---

## 17. Design vs Implementation Boundary

These are not remaining Design blockers:

- concrete operational runbook commands before services exist;
- live RunPod/vLLM acceptance before C7;
- final ReverendBench fixtures before benchmark implementation;
- choosing a cheaper 48 GB profile without measurements;
- C9 blank-host disaster exercise;
- post-v1 multi-Run, Kubernetes, multi-region or SSO work.

They remain explicit Development/Operations deliverables under D7–D9.

---

## 18. C0 Entry Checklist

- [x] A12 accepted.
- [x] D0–D14 documented.
- [x] architecture diagrams indexed.
- [x] legacy migration map exists.
- [x] tool/recovery registry exists.
- [x] client/operator state contract exists.
- [x] ADR process/template exists.
- [x] PostgreSQL test strategy documented.
- [x] historical 0.4.0 baseline identified.
- [ ] fresh current-main Python suite recorded.
- [ ] fresh current-main portable validation recorded.
- [ ] any baseline failure triaged.
- [ ] C0 branch/issue opened from clean main.

Unchecked items require execution evidence. Documentation must not fabricate them.

---

## 19. Development Entry Decision

Once the fresh baseline is recorded, move to C0.

Do not repeat another broad pre-development redesign unless a concrete contradiction is found, C0 cannot implement a contract without inventing authority semantics, or new evidence invalidates a frozen assumption.

Otherwise use narrow ADRs during Development.

---

## 20. Exit Condition

D14 closes Design when no known Cloud-v1-blocking design gap remains and Development has precise migration, tool safety, research, UX, PostgreSQL testing and decision-control contracts.

The only remaining C0 prerequisite after this document is real baseline execution evidence.


---

## 21. Final-Closure Relationship to D15–D22

D14 closed the first Design-completion audit and remains authoritative for:

- fresh C0 baseline evidence;
- PostgreSQL integration/concurrency testing;
- database-role testing;
- ADR/change control;
- Development-entry evidence discipline.

Subsequent capability modernization and specification-driven refinement are captured in D15–D22.

Therefore the final Development-entry chain is:

~~~text
D14 baseline/testing discipline
+ D15–D21 capability specifications
+ D22 final architecture closure
→ C0 entry
~~~

The sentence in Section 1 that no known blocker remained after D10–D13 should be read as the status of that earlier closure pass, not as the final Design-phase verdict.

D22 is the final design-level closure authority.
