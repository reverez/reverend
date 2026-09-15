# M15 vNext Release — COMPLETE

M6–M15 are COMPLETE under the frozen vNext architecture.

## Frozen objective

M15 does not redesign Reverend or add a new intelligence subsystem.

The goal is to turn the accepted M6–M14 branch into a coherent, reproducible release
candidate that can be installed, started, operated, validated and recovered from a clean
checkout.

M15 development must not merge, tag, publish or create a GitHub release. Those remain
explicit user actions after acceptance.

## Release identity

Existing lineage:

- package version: `0.3.0`;
- accepted baseline tag: `v3-m5-local-workstation`;
- earlier tag: `v3-pre-reverend-foundation`;
- GitHub releases: none.

vNext therefore advances the package to **0.4.0**.

No `v0.4.0` tag is created during M15.

## Release gate

### 1. Package and version integrity

- package metadata is `0.4.0`;
- one authoritative runtime version is exposed by the package;
- `reverend --version` and `python -m reverend.cli --version` agree;
- wheel contents include the Workstation UI and required package modules;
- package build/import is reproducible from a clean checkout.

### 2. Clean configuration

- example configuration contains no developer-specific host IPs or paths;
- WSL gateway auto-discovery remains the default when `OLLAMA_HOST` is unset;
- local-only inference remains authoritative;
- data-root/runtime-config overrides are documented;
- secrets are never committed to the example.

### 3. User/operator documentation

Rewrite stale pre-vNext documentation so the normal path explains:

- what Reverend vNext is;
- prerequisites;
- environment/venv installation;
- Ollama model expectations;
- GUI startup;
- privacy modes;
- network policies;
- project trust;
- local development workflow;
- knowledge/reference/public-source behavior;
- benchmark/validation commands;
- backup, migration and recovery boundaries;
- known limitations.

Old commands may remain documented only as legacy/advanced surfaces where still supported.

### 4. Release smoke path

A portable release smoke harness must verify without touching production state:

- build a wheel;
- inspect required wheel files;
- create an isolated temporary environment;
- install the wheel without mutating the source checkout;
- import `reverend`;
- verify package/CLI version;
- create temporary runtime state;
- instantiate the Workstation offline;
- instantiate the loopback-only HTTP server on an ephemeral port;
- serve/read the packaged UI root;
- verify state remains inside the temporary data root;
- close cleanly.

### 5. Retained vNext regressions

M15 final validation must retain the accepted contracts from M6–M14, including:

- ReverendBench;
- request routing and ambiguity behavior;
- evidence and citation gating;
- network policy;
- knowledge/code intelligence;
- bounded workers;
- isolated development;
- privacy/encryption/project trust;
- sandbox contract;
- M14 runtime optimisation metrics.

### 6. Configured workstation acceptance

Final release validation on the configured WSL workstation must include a bounded live local
inference smoke case in addition to portable package/startup/security checks.

## Initial release blockers found

1. `README.md` still describes the old Local AI Knowledge Fabric rather than Reverend vNext.
2. `README.md` still says autonomous coding is unreliable even though M5/M11/M12 have
   accepted isolated development and worker orchestration contracts.
3. `pyproject.toml` still reports version `0.3.0`.
4. `.env.example` contains a machine-specific WSL Ollama IP.
5. The CLI has no canonical `--version` surface.
6. No single M15 clean-package/startup validation exists yet.

## Implemented release slices

### Release identity and configuration

- authoritative package version: **0.4.0**;
- setuptools derives package metadata from `reverend.__version__`;
- `reverend --version` exposes the same value;
- portable environment template replaces the developer-specific WSL host address;
- release identity/config hygiene has permanent tests.

### Release documentation

- README rewritten for the accepted Reverend vNext Workstation;
- 0.4.0 install, models, GUI, privacy, network, project trust, development, knowledge,
  backup and validation behavior documented;
- `docs/release-0.4.0.md` records upgrade, encryption migration, rollback and recovery;
- roadmap updated from stale V2 future work to the 0.4.0 release state/post-release work.

### Clean package/startup smoke

The M15 release smoke:

1. records tracked working-tree changes but excludes them from the release artifact;
2. creates a clean `git archive HEAD` snapshot;
3. builds the 0.4.0 wheel from that committed snapshot;
4. verifies required Python/UI files and console entry points;
5. installs into an isolated temporary venv;
6. verifies package metadata and CLI version;
7. instantiates the packaged Workstation against temporary state/config/key roots;
8. starts the packaged loopback server on an ephemeral port;
9. fetches the packaged UI and JavaScript;
10. verifies encrypted state/key creation remains isolated.

### Final release validator

`reverend.benchmarks.m15_validation` combines:

- complete pytest suite;
- release identity/documentation contract;
- clean committed-wheel package/startup smoke;
- all three deterministic M14 runtime optimisation cases;
- accepted M13 portable privacy/security contract;
- real M13 live bubblewrap/prlimit sandbox probe;
- one bounded configured local Ollama Workstation inference.

Portable-only mode cannot mark M15 accepted.

## Green pre-acceptance checkpoint

Revision `db631c451d473f27b10fb2cd837b192f6cf96c7a` passed:

- targeted vNext/M15 suite: **266 passed**;
- complete Python suite: **496 passed / 0 failed**;
- clean package/startup release smoke: **PASS**;
- wheel: `reverend-0.4.0-py3-none-any.whl`;
- wheel files: **164**;
- installed CLI: `reverend 0.4.0`;
- packaged Workstation UI: **PASS**;
- isolated runtime state: **PASS**;
- isolated state-key creation: **PASS**.

## Final acceptance

Canonical validation completed on
`d10b8654f64f65aa1fbb8775199e5500162f7178`.

Final results:

- complete Python suite: **497 passed / 0 failed**;
- release/documentation contract: **PASS**;
- clean committed-HEAD wheel/install/startup smoke: **PASS**;
- deterministic M14 runtime cases: **3 / 3 passed**;
- retained M13 portable privacy/security contract: **PASS**;
- live WSL sandbox: **PASS**;
- live local Ollama Workstation inference: **PASS**;
- `portable_ok: true`;
- `overall_ok: true`.

Canonical evidence:
`benchmarks/results/vnext/m15/live-validation/validation-20260914T201903Z.json`.

Release artifact:
`reverend-0.4.0-py3-none-any.whl`.

Local edits to `scripts/ai-doctor` and `scripts/ai-status` were preserved and explicitly
excluded from the release artifact by the `git archive HEAD` release path.

M15 is **COMPLETE**. Reverend 0.4.0 vNext is **RELEASE-READY**.

Merge, tag, publish and GitHub-release creation remain separate explicit user actions.
