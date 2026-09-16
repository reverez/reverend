# M13 Privacy & Execution Security v2 — ACCEPTED

**Milestone:** M13 — Privacy & Execution Security v2  
**Status:** COMPLETE  
**Accepted revision:** `3050a002e8e37a99e75e8944b63ccbbb805d8937`  
**Final validation:** 2026-09-14T19:21:28Z

## Accepted privacy architecture

M13 adds first-class privacy policy without changing Reverend's local-first architecture.

Accepted modes:

- **Normal** — encrypted persistent conversation and workstation state.
- **Private** — encrypted persistent conversation state with no automatic long-term-memory
  promotion path.
- **Ephemeral** — conversation, messages and chat-job state remain process-local and are
  removed after use/restart.

Existing conversations migrate compatibly to Normal.

Durable workstation payloads are protected using the audited
`cryptography==50.0.1` dependency and versioned Fernet authenticated encryption.
Protected columns include conversation titles, message content/metadata and job
response/details. The production state key is stored separately from the data directory,
restricted to the current user, and wrong-key/tamper failures are fail-closed.

Legacy plaintext rows are migrated to authenticated ciphertext. SQLite secure-delete,
WAL truncation and VACUUM are used after migration so plaintext is not deliberately
retained in ordinary database free pages.

## Accepted execution-security architecture

Trusted development preserves the existing host-owned deterministic execution plane.

M13 additionally establishes:

- secret/credential/capability environment filtering;
- explicit project trust with user-facing default `untrusted_repo`;
- no implicit trust changes during project re-registration;
- owner-only command artifacts;
- an explicit fail-closed bubblewrap/prlimit sandbox boundary;
- no host-home mount;
- no inherited host credentials;
- no shared network namespace;
- private sandbox HOME and `/tmp`;
- read-only system runtime;
- exactly one bounded writable task workspace;
- bounded CPU, RAM, process count and file descriptors;
- symlink-root and absolute-host executable refusal;
- sandbox provenance in command artifacts.

The Workstation continues to keep untrusted projects **inspection-only**. M13 does not
claim full untrusted development because Git checkout/worktree materialization itself can
invoke repository-controlled hooks/filters. Command-level sandboxing is therefore not
misrepresented as end-to-end untrusted-repository safety.

## Canonical final validation

Command:

```sh
"$PWD/.venv/bin/python" -m reverend.benchmarks.m13_validation
```

Result on `3050a002e8e37a99e75e8944b63ccbbb805d8937`:

- full Python suite: **462 passed / 0 failed**;
- portable security contract: **PASS**;
- live workstation sandbox: **PASS**;
- portable acceptance: `portable_ok: true`;
- overall acceptance: `overall_ok: true`;
- model calls: **0**.

Portable security invariants all passed:

- credential capability filtering;
- durable encrypted round-trip;
- Ephemeral state never persisted;
- persistent payloads encrypted;
- protected plaintext absent from durable payload columns;
- explicit privacy modes;
- fail-closed sandbox contract;
- owner-only state files;
- trust escalation blocked.

Live WSL sandbox invariants all passed:

- host home hidden;
- loopback-only network namespace;
- credential handles absent;
- system runtime read-only;
- workspace writable;
- private sandbox home and temporary directory;
- address-space limit applied;
- process limit applied;
- file-descriptor limit applied;
- core dumps disabled.

## Evidence

Canonical combined report:

`benchmarks/results/vnext/m13/live-validation/validation-20260914T192128Z.json`

Standalone WSL sandbox report:

`benchmarks/results/vnext/m13/live-validation/sandbox-validation-20260914T191321Z.json`

## Safety invariants retained

- all inference remains local;
- explicit network policy remains authoritative;
- retrieved external content remains untrusted data;
- model workers still receive no arbitrary filesystem/shell authority;
- isolated task worktrees remain mandatory;
- structured path/hash validation remains authoritative;
- deterministic verification outranks model confidence;
- no automatic merge/release/tag behavior is introduced.

## Decision

M13 is **ACCEPTED and COMPLETE**. M14 — Intelligence & Runtime Optimisation may begin.
