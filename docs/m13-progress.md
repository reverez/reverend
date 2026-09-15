# M13 Privacy & Execution Security v2 — COMPLETE

M6–M13 are COMPLETE under the frozen vNext architecture.

## Frozen objective

M13 hardens Reverend's state, privacy, network and execution boundaries without changing
the accepted local-first architecture.

The architectural targets are:

- Normal / Private / Ephemeral privacy modes;
- persistent state protected at rest;
- private conversations excluded from long-term memory promotion;
- ephemeral conversation/session state removed after use;
- explicit OFF / ASK / AUTO network policy;
- trust labels preserved through retrieval, context and workers;
- bounded approved execution only;
- untrusted-repository execution only inside an approved disposable sandbox;
- no host-home or host-credential access for sandboxed execution;
- network disabled by default for sandboxed execution;
- bounded writable filesystem and resource/time limits;
- permanent ReverendBench security regressions.

## Existing accepted security baseline

Reverend already provides:

- local-only inference endpoint validation;
- loopback-only workstation HTTP transport with per-process session token;
- CSP, no-store, origin/Host and cross-site request checks;
- isolated Git development worktrees;
- structured edits with path/hash validation;
- shell-free argv execution;
- worktree cwd containment;
- time/output process limits and process-group termination;
- secret-like environment filtering;
- complete refusal of untrusted-repository execution;
- public research in bubblewrap with minimal mounts, cleared environment and seccomp;
- HTTPS-only public-source acquisition;
- SSRF protection through public-IP validation and DNS pinning;
- external-source trust label `UNTRUSTED_EXTERNAL`;
- bounded typed worker state with no direct model filesystem/shell authority.

## Gaps confirmed at M13 start

### Privacy state

`WorkspaceStore` currently persists conversations, messages and jobs in plain SQLite and
has no Normal / Private / Ephemeral mode. Privacy policy therefore does not yet control
persistence or long-term-memory promotion.

### Development execution

Trusted-repository commands are cwd-contained but are not OS-contained. A subprocess can
still attempt arbitrary host filesystem or network access. The environment uses a
secret-name denylist rather than a minimal capability-oriented allowlist.

### Untrusted repositories

Execution correctly fails closed today. The architecture permits future execution only
after an approved disposable sandbox satisfies the required isolation properties.

## Implementation plan

### Slice 1 — privacy policy primitives

Add first-class typed privacy modes and make conversation persistence semantics explicit.
Ephemeral state must not survive its session. Private state must not be promoted to
long-term memory. Preserve compatibility for existing Normal conversations.

No home-grown cryptography will be introduced. At-rest encryption must use an audited
system/library primitive or remain an explicit unmet acceptance item until such a
primitive is available without weakening the dependency/security contract.

### Slice 2 — execution capability policy

Introduce a deterministic execution-policy object in front of the host command runner.
Separate filesystem, environment and network capabilities from argv execution and make
unsafe combinations fail closed.

### Slice 3 — OS sandbox for untrusted execution

Reuse the accepted bubblewrap direction where appropriate, but build a development-specific
sandbox rather than reusing the public-research worker blindly. Required properties include
no host home/credentials, bounded writable worktree, disabled network by default and hard
resource/time limits.

### Slice 4 — security regression and live acceptance

Add ReverendBench security invariants covering privacy persistence, host-path escape,
network capability, environment leakage, untrusted execution and malformed/adversarial
model output. M13 is not complete until the portable suite and workstation-relevant live
security checks pass.

## Slice 1 checkpoint — privacy modes and state handling

Implemented and green:

- first-class `normal`, `private` and `ephemeral` conversation modes;
- backward-compatible workspace schema migration with existing conversations defaulting
  to Normal;
- Ephemeral conversations, messages and chat jobs remain process-local and never enter
  SQLite;
- Ephemeral state is cleared on Workstation shutdown;
- privacy mode is immutable after conversation creation;
- workstation API and UI expose the privacy choice for new conversations;
- runtime workspace state directory is owner-only (`0700`) and SQLite/WAL/SHM state files
  are owner-only (`0600`);
- command artifact directories are owner-only (`0700`) and stdout/stderr artifacts are
  owner-only (`0600`);
- a real `Workstation.chat()` Ephemeral regression proves user message, streamed assistant
  response and job lifecycle work while durable tables remain empty.

The full Python suite is green at this checkpoint.

Encrypted persistent payloads remain an explicit M13 acceptance item. The current declared
runtime does not include an audited encryption primitive, and M13 will not introduce
home-grown cryptography or silently expand the dependency contract.

## Slice 2 checkpoint — execution capability environment

Implemented and green:

- inherited credential/capability handles such as SSH agents, cloud profiles, kube/docker
  endpoints, askpass hooks, Python startup/path injection and preload hooks are removed
  from development subprocesses;
- explicit attempts to reintroduce those capabilities are rejected;
- ordinary bounded build/test environment variables remain usable.

## Slice 2 checkpoint — trust and execution capability policy

Implemented and green:

- re-registering an existing project can no longer change its trust mode;
- user-facing project registration defaults to `untrusted_repo`; trusted execution is an
  explicit opt-in;
- untrusted projects remain inspection-only at the Workstation development boundary;
- `run_command(..., sandbox=True)` is the only command-level path that can cross the
  untrusted trust gate;
- sandboxed commands receive no inherited host environment and cannot inject a custom
  environment;
- command artifacts record whether execution was sandboxed;
- security regressions are first-class targeted CI gates.

## Slice 3 checkpoint — development sandbox substrate

Implemented:

- fail-closed bubblewrap discovery with no unsafe fallback;
- `--unshare-all` namespace isolation and no shared network namespace;
- cleared process environment;
- no host-home mount;
- private sandbox home and `/tmp`;
- read-only system runtime mounts;
- exactly one writable task-workspace bind;
- bounded sandbox cwd;
- absolute host executables outside the workspace/system runtime are refused;
- symlink workspace roots are refused;
- `prlimit` caps address space, CPU time, process count, file descriptors and core dumps;
- a live M13 sandbox probe validates host-home invisibility, network isolation, read-only
  runtime, workspace writes, credential-handle absence and resource limits.

The Workstation still does **not** enable full untrusted development. Establishing an
isolated command boundary is insufficient by itself because Git worktree materialization
can invoke repository-controlled hooks/filters. Untrusted projects therefore remain
inspection-only until the entire checkout lifecycle meets the same isolation standard.

## Slice 4 checkpoint — encrypted persistent state

Implemented:

- audited `cryptography==50.0.1` dependency;
- versioned Fernet authenticated encryption for durable workstation payloads;
- production state key stored separately from the workstation data directory;
- key directory/file permissions restricted to owner-only;
- conversation titles, message bodies/metadata, job responses/details encrypted at rest;
- legacy plaintext rows migrated to authenticated ciphertext;
- SQLite `secure_delete`, WAL truncation and VACUUM used after plaintext migration;
- wrong-key and tampered-ciphertext startup failures are fail-closed;
- direct stores keep isolated local test keys so tests never touch the production key.

The one encryption CI failure was a test expectation bug: a conversation explicitly
created with title `Sensitive title` correctly preserves that title instead of replacing
it with the first message. The corrected regression is green.

## Live workstation evidence

The WSL sandbox probe passed on revision
`07c4955ba73d68ceab9144a1693f2b58b158bf40`.

Every required live assertion passed:

- host home hidden;
- network namespace contains loopback only;
- credential handles absent;
- system runtime read-only;
- task workspace writable;
- private sandbox home and `/tmp`;
- address-space, process, file-descriptor and core-dump limits applied.

Canonical evidence:
`benchmarks/results/vnext/m13/live-validation/sandbox-validation-20260914T191321Z.json`.

## Final M13 acceptance

Canonical combined validation completed on revision
`3050a002e8e37a99e75e8944b63ccbbb805d8937`.

Final results:

- full Python suite: **462 passed / 0 failed**;
- portable privacy/encryption/trust/capability contract: **PASS**;
- live WSL bubblewrap/prlimit sandbox: **PASS**;
- `portable_ok: true`;
- `overall_ok: true`;
- model calls: **0**.

Canonical evidence:
`benchmarks/results/vnext/m13/live-validation/validation-20260914T192128Z.json`.

M13 is **COMPLETE**. M14 — Intelligence & Runtime Optimisation is next.
