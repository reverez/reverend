# M15 vNext Release — ACCEPTED

**Milestone:** M15 — vNext Release  
**Status:** COMPLETE  
**Release identity:** Reverend **0.4.0**  
**Accepted/validated revision:** `d10b8654f64f65aa1fbb8775199e5500162f7178`  
**Final validation:** 2026-09-14T20:19:03Z

## Decision

Reverend 0.4.0 vNext is **RELEASE-READY**.

This acceptance does **not** merge the branch, create a tag, publish a package, create a
GitHub release or modify the user's primary checkout. Those remain explicit post-acceptance
actions.

## Canonical final validation

Command:

```sh
"$PWD/.venv/bin/python" -m reverend.benchmarks.m15_validation
```

Result on `d10b8654f64f65aa1fbb8775199e5500162f7178`:

- complete Python suite: **497 passed / 0 failed**;
- release/documentation contract: **PASS**;
- clean committed-HEAD wheel/install/startup smoke: **PASS**;
- deterministic M14 runtime cases: **3 / 3 passed**;
- retained M13 portable privacy/security contract: **PASS**;
- real WSL bubblewrap/prlimit sandbox: **PASS**;
- live local Ollama Workstation inference: **PASS**;
- `portable_ok: true`;
- `overall_ok: true`.

Canonical evidence:

`benchmarks/results/vnext/m15/live-validation/validation-20260914T201903Z.json`

## Release artifact

The release smoke built from:

```text
git archive HEAD
```

Artifact:

```text
reverend-0.4.0-py3-none-any.whl
```

Validated wheel properties:

- version marker: `reverend-0.4.0.dist-info/`;
- console entry point present;
- **164 files**;
- packaged Workstation UI present;
- packaged JavaScript/CSS present;
- installed CLI reports `reverend 0.4.0`;
- Workstation starts from the installed wheel;
- packaged UI serves successfully on loopback;
- runtime state remains isolated;
- encrypted state key is created in the isolated config root.

## Local working-tree preservation

The user's checkout contained local tracked edits:

- `scripts/ai-doctor`;
- `scripts/ai-status`.

Those edits were **not reset, stashed, discarded or shipped**.

The release report records:

- `artifact_source: "git archive HEAD"`;
- `working_tree_changes_excluded: true`;
- the two modified script paths under `tracked_worktree_changes`.

A permanent regression verifies that committed HEAD bytes enter the release archive even
when a tracked file is locally modified, and untracked files are excluded.

## Live inference acceptance

Measured live local inference:

- Reverend version: **0.4.0**;
- model: `qwen3.5:4b`;
- role: `fast_general`;
- model calls: **1**;
- generation calls: **1**;
- embedding calls: **0**;
- model inventory provider reads: **1**;
- inventory cache hits: **1**;
- prompt tokens: **139**;
- generated tokens: **9**;
- provider time: **0.325 s**;
- wall time: **0.355834 s**;
- response: `Reverend local inference is running.`.

## Live sandbox acceptance

Every required live sandbox invariant passed:

- host home hidden;
- loopback-only network namespace;
- credential handles absent;
- private sandbox home;
- private temporary directory;
- system runtime read-only;
- workspace writable;
- address-space limit applied;
- process limit applied;
- file-descriptor limit applied;
- core dumps disabled.

## Release contract

All release contract assertions passed:

- version is exactly **0.4.0**;
- README identifies Reverend and the 0.4.0 release;
- 0.4.0 upgrade/recovery guide is present;
- roadmap tracks M15/0.4.0;
- environment example is portable;
- no API key is embedded in the example.

## Retained vNext invariants

M15 acceptance preserves the complete M6–M14 architecture:

- local-only model inference;
- deterministic-first request understanding;
- bounded local router fallback;
- explicit evidence classes and evidence gating;
- OFF / ASK / AUTO network policy;
- Knowledge Fabric v2;
- bounded code intelligence;
- typed bounded worker orchestration;
- isolated structured development;
- deterministic verification over model confidence;
- encrypted Normal / Private / Ephemeral privacy modes;
- explicit project trust;
- credential/environment filtering;
- fail-closed sandbox construction;
- bounded model-call, retrieval and output-token budgets;
- M14 model-inventory caching and runtime accounting;
- no automatic merge/tag/release/publish behavior.

## Release documentation

Release/operator documentation includes:

- `README.md`;
- `docs/release-0.4.0.md`;
- `docs/vnext-architecture.md`;
- `docs/safety.md`;
- milestone acceptance records under `docs/`.

## Final milestone state

M6 — COMPLETE  
M7 — COMPLETE  
M8 — COMPLETE  
M9 — COMPLETE  
M10 — COMPLETE  
M11 — COMPLETE  
M12 — COMPLETE  
M13 — COMPLETE  
M14 — COMPLETE  
M15 — COMPLETE

The frozen M6–M15 vNext development programme is complete.

## Post-acceptance boundary

The branch is **release-ready**, not automatically released.

The following require a separate explicit user decision:

- merge/integrate the branch;
- create a `v0.4.0` tag;
- create a GitHub release;
- publish/upload the wheel/package;
- discard or incorporate local script edits.
