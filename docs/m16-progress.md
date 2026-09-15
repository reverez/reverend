# M16 — Runtime Reliability, Agentic Context & Task-State Integrity

**Original milestone branch:** `architecture/m6-vnext-foundation`  
**Baseline:** Reverend 0.4.0 / M6–M15 accepted  
**M16 status:** LIVE ACCEPTED

## Scope

M16 extends the accepted vNext architecture to fix live reliability failures without
weakening local-only inference, privacy, evidence gating, deterministic verification,
network policy, worktree isolation, bounded execution, or security invariants.

The authoritative M16 brief requires:

- truthful generation-completion metadata;
- adaptive output budgets;
- persistent authoritative task state;
- Context Compiler V2 and layered conversation memory;
- hardware-aware context and model residency;
- requirement extraction and deterministic high-assurance verification;
- bounded agent loops;
- checkpointed continuation;
- richer Response Details;
- regression coverage for every reproduced live failure.

## Inspection findings

The initial inspection confirmed:

1. ordinary chat output defaults to 1536 tokens through `RequestBudget`;
2. `ModelScheduler.stream()` previously discarded Ollama `thinking` and
   `done_reason` metadata while only propagating final `response` text;
3. Workstation chat uses the latest 16 messages and then front-truncates the
   flattened transcript by character budget;
4. empty final output became the generic `Local model returned no answer`;
5. citation completion previously equated "not cancelled" with "complete",
   allowing length-limited output to be mislabelled;
6. deterministic verification is strong in the development engine but does not
   yet provide a general high-assurance layer for ordinary chat;
7. the existing development task schema is useful but too development-specific
   to serve as generic authoritative conversational task state.

## M16.1a — typed streaming completion metadata

This slice introduces the first completion-integrity foundation.

Implemented:

- provider-neutral safe completion states;
- propagation of provider `done_reason`;
- cumulative prompt/generated token metadata where available;
- requested output budget;
- response character count;
- answer-started state;
- hidden-reasoning-present boolean;
- hidden-reasoning activity count;
- cancellation state;
- explicit `output_limit_reached`;
- explicit `reasoning_budget_exhausted_before_answer`;
- explicit `empty_final_response`;
- raw Ollama `thinking` is discarded inside the scheduler and never emitted;
- Workstation additionally refuses to persist injected `thinking`,
  `raw_response` or `chain_of_thought` fields;
- partial length-limited answers are preserved and marked `incomplete` and
  `continuation_eligible`;
- citation completeness now requires a natural complete generation;
- typed generation failures persist an `error_code`;
- a fail-closed prompt rule forbids inventing missing authoritative tasks,
  milestones, exercises, requirements, source specifications or acceptance criteria.

Checkpoint storage and automatic continuation are intentionally deferred to the later
authoritative-task/checkpoint slices.

## Regression coverage added

Focused tests now cover:

- raw thinking never leaving the scheduler;
- safe hidden-reasoning aggregate metadata;
- natural stop vs output limit;
- reasoning budget exhausted before any final answer;
- BudgetedScheduler persistence of completion metadata;
- typed Workstation failure instead of generic no-answer failure;
- partial answer preservation;
- incomplete citation state;
- defence-in-depth removal of injected thinking fields.

## Next slice

M16.1b/M16.2 should validate this contract in CI, then introduce route/task-sensitive
output budgeting without globally increasing all generation limits.


## M16.1a validation

Accepted on branch revision `4a1480b6007e50e65058a180c7e48aceccce8347`.

GitHub Actions run 346:

- targeted tests: **273 passed**;
- complete Python suite: **503 passed**;
- clean package/startup release smoke: **PASS**.

The earlier run 345 exposed only a stale privacy assertion that treated the safe key
`response_chars` as if it were a raw `response` field. The assertion was corrected
to test exact keys, and raw provider `thinking` is now removed with `pop()` at the
scheduler boundary.

## M16.2 — adaptive output budgeting

In progress.

Policy introduced:

- low-cost FAST_GENERAL: 1536 tokens;
- medium FAST_GENERAL: 2048;
- high/research FAST_GENERAL: 3072;
- FAST_CODE: 2048 normally, 3072 for high complexity;
- DEEP_REASON: 4096;
- STRONG_CODE: 4096;
- ROUTER helper policy: 512.

`RequestBudget.output_tokens` is now the hard per-call ceiling (maximum 4096), while
`ExecutionPlan.output_tokens` records the actual routed budget.

The Workstation prompt compiler now reserves the actual planned generation budget rather
than always reserving 1536 tokens, so provider `num_predict`, execution metadata and
prompt allocation stay aligned.


## M16.2 validation

Accepted on branch revision `a5da05cab4fb292ce5400a9d57f859e83aee08a5`.

GitHub Actions run 348:

- targeted tests: **277 passed**;
- complete Python suite: **507 passed**;
- clean package/startup release smoke: **PASS**.

The first M16.2 run exposed two fixture issues: one stale 1536-token assertion and
one research test that deliberately disabled all retrieval, correctly causing an
evidence abstention before generation. The evidence gate was preserved; the fixtures
were corrected.

## M16.3 — authoritative task state

In progress.

The first M16.3 slice adds an encrypted, first-class authoritative task abstraction to
the Workstation state domain rather than overloading the development-task database.

Key invariants:

- exact user task text is the authoritative specification;
- specification SHA-256 and version are explicit;
- arbitrary progress updates cannot overwrite the authoritative specification or
  immutable requirements;
- Normal and Private task state is encrypted with the existing Workstation state key;
- Ephemeral task state remains process-local and never enters SQLite;
- explicit continuation fails closed with `authoritative_task_missing` when no
  authoritative task exists;
- task-worthy requests are detected deterministically and do not require another model
  call;
- active authoritative task state is injected ahead of untrusted evidence and recent
  conversation, so it survives ordinary history eviction;
- retrieved/untrusted content remains unable to redefine authoritative task state.

This slice does not yet implement hierarchical conversation summaries, semantic older-turn
retrieval, model-driven requirement extraction, or automatic continuation checkpoints.
Those remain subsequent M16 slices.


## M16.3 validation

Accepted on branch revision `15b7e7f63b8c1a4e18e7c7ff38241b6aefc4aa64`.

GitHub Actions run 350:

- targeted tests: **283 passed**;
- complete Python suite: **513 passed**;
- clean package/startup release smoke: **PASS**.

The first M16.3 run exposed an important continuation-routing edge case: the literal
message "Continue Exercise 8" was low-information and could invoke classification even
though authoritative state already existed. The repair now derives continuation
understanding/routing from the authoritative specification instead of asking a model to
infer the missing task from the word "continue".

## M16.4a — Context Compiler V2 core

In progress.

This slice replaces the Workstation's primary `last 16 messages + front truncation`
strategy with explicit context layers:

1. system/security instruction;
2. authoritative task state;
3. current user request;
4. bounded recent raw turns;
5. accepted evidence;
6. relevant project/repository context;
7. verified project memory;
8. deterministically retrieved relevant older turns;
9. optional non-authoritative summary.

The compiler exposes physical context, prompt budget, per-layer chars/tokens/counts,
source counts, and clipped/omitted layers. Older-turn retrieval is bounded and lexical
over decrypted local state; it does not make a model call and does not weaken privacy.


### M16.4a evidence-metadata integrity follow-up

The initial Context Compiler V2 implementation passed its targeted, full-suite and release
smoke stages, but review found a subtle accounting edge case: evidence excerpts were selected
against the evidence cap before the evidence section heading consumed its own bytes.

The compiler now reserves the heading before selecting source excerpts and asserts that the
evidence body delivered to the final prompt is exactly the evidence body represented by
`context_sources`. A regression verifies that every reported excerpt and citation label is
literally present in the final bounded prompt under aggressive context pressure.


## M16.5a — heavyweight residency integrity

In progress.

The validated `qwen3-coder:30b` 16K benchmark on the target RTX 5070 Laptop GPU
(~8 GiB VRAM, ~32 GiB RAM) leaves only roughly 1.1–1.4 GiB system RAM free while
resident. This slice therefore preserves the validated 16K strong-code production
context rather than inflating physical context blindly.

Residency policy:

- `STRONG_CODE` remains memory-exclusive;
- `DEEP_REASON` is now memory-exclusive;
- `CRITIC` inherits that policy because it reuses `deepseek-r1:8b`;
- `FAST_GENERAL` remains shared-residency;
- the scheduler records the residency policy and exact models unloaded before a
  heavyweight run;
- safe residency metadata is propagated into request-level model accounting and
  Workstation Response Details.

A later context-policy slice may raise a physical context window only after live
benchmark evidence confirms memory headroom and acceptable latency.


## M16.5a validation

Accepted on branch revision `e24ecb7c5e2f2b39e75d65a3ef1f5bb5fe7b3cac`.

GitHub Actions run 353:

- targeted tests: **290 passed**;
- complete Python suite: **520 passed**;
- clean package/startup release smoke: **PASS**.

## M16.6a — trusted requirement extraction

In progress.

Authoritative task creation now deterministically extracts only explicit user constraints
into first-class encrypted task state. The extractor recognizes explicit requirement,
constraint and acceptance sections plus strong modal constraints such as `MUST`,
`DO NOT`, `NEVER`, `ONLY`, `EXACTLY`, quantified limits and preservation
requirements.

Design constraints:

- the exact user specification remains the primary immutable authority;
- weak advisory prose is not promoted into an immutable requirement;
- extraction makes no additional model call;
- extracted requirements and acceptance criteria are encrypted under existing
  Workstation privacy semantics;
- Ephemeral conversations keep extracted state process-local;
- task metadata exposes requirement counts and a bounded high-assurance signal;
- the later generic verifier can consume this trusted checklist without asking a model
  to reconstruct requirements from conversation history.


### M16.6a runtime-capability follow-up

A second targeted run confirmed that authoritative task persistence succeeded but a
stream-only injected scheduler failed afterward: the serialization adapter itself exposes
`generate()`, so capability probing incorrectly enabled the optional local classifier.

Classifier capability detection now inspects the underlying scheduler implementation.
Explicit requirement/acceptance sections also remain active across normal Markdown blank
lines and terminate on non-list prose, preventing formatting from silently dropping
trusted constraints.


## M16.6a validation

Accepted on branch revision 1e1c39117a70d283b5456f2cb97a7f7540dd0e0d.

GitHub Actions run 356:

- targeted tests: 296 passed;
- complete Python suite: 526 passed;
- clean package/startup release smoke: PASS.

The earlier extraction runs exposed two real integration issues: assurance signals inside
explicit requirement sections could be skipped by early section handling, and the
serialization wrapper could falsely advertise classifier capability for stream-only test
schedulers. Both are now covered by regressions.

## M16.6b — deterministic high-assurance verification and repair

In progress.

The first generic verification layer now:

- verifies only machine-checkable constraints;
- reports every constraint as pass, fail or unchecked;
- never treats semantic-only constraints as passed;
- supports exact response literals, required/forbidden literals, valid JSON,
  exact/max word limits, exact list-item counts and exact fenced-code-block counts;
- runs before assistant output is persisted for high-assurance authoritative tasks;
- performs at most one bounded model repair when deterministic checks fail and the
  existing model-call budget permits escalation;
- re-runs deterministic verification after repair;
- publishes a typed verification_failed failure if repair still violates a
  machine-checkable constraint.

This is deliberately narrower than a model critic: deterministic checks provide hard
evidence first; a later critic slice may review semantic-only requirements without
overriding these machine checks.


### M16.6b verifier-contract hardening

Before accepting deterministic verification, two advertised machine-checkable contracts
were tightened:

- exact-response verification now recognizes `Return exactly ...` in addition to
  respond/reply/output phrasing;
- JSON object/array requirements now verify the requested container shape rather than
  only JSON parseability.

Both are covered by targeted regressions.


## M16.6b validation

Accepted through verifier-contract hardening revision ed43621dfc80554f96d4478151b446786cfdf77c.

GitHub Actions run 360:

- targeted tests: 303 passed;
- complete Python suite: 533 passed;
- clean package/startup release smoke: PASS.

## M16.7a — checkpointed continuation

In progress.

This slice uses the existing encrypted authoritative-task checkpoint field rather than
creating a parallel persistence mechanism.

Checkpoint policy:

- a bounded in-progress checkpoint exists before generation starts;
- partial output is refreshed every 1024 response characters;
- output-limit, reasoning-budget exhaustion and user cancellation preserve a resumable
  terminal checkpoint;
- durable checkpoints remain encrypted under existing Workstation privacy semantics;
- Ephemeral checkpoints remain process-local;
- explicit continuation injects checkpoint state below user authority as
  NON-AUTHORITATIVE execution state;
- duplicate partial assistant history is suppressed when the same checkpoint is resumed;
- a successful natural completion clears the checkpoint;
- checkpoint metadata exposes reason/count/size without exposing private reasoning.


### M16.7a restart and terminal-state hardening

The initial checkpoint implementation passed GitHub Actions run 361 at its primary gate:

- targeted tests: **307 passed**;
- complete Python suite: **537 passed**;
- clean package/startup release smoke: **PASS**.

Before accepting the slice, two additional lifecycle guarantees are now covered:

- a durable output-limit checkpoint is recovered after the Workstation is fully closed
  and reopened, injected as non-authoritative execution state, and cleared after the
  resumed response completes;
- deterministic verification failures persist an explicit
  `verification_failed` terminal checkpoint rather than leaving the task at generic
  `in_progress`.

Checkpoint summaries remain free of raw hidden reasoning; durable checkpoint payloads use
the existing encrypted Workstation state channel.


## M16.7a validation

Accepted through restart-hardening revision 89fa040cc90d0df0ddde15e876262dfa664a6f8b.

GitHub Actions run 362:

- targeted tests: PASS;
- complete Python suite: PASS;
- clean package/startup release smoke: PASS.

## M16.8a — bounded automatic continuation loop

In progress.

Authoritative tasks that hit an output limit after final-answer text has started can now
continue inside the same request under hard execution bounds.

Hard bounds and invariants:

- at most 2 automatic continuations per request;
- at most 8 total checkpoint continuations for a task lineage;
- every continuation consumes the existing RequestBudget model-call allowance;
- continuation uses the same routed role instead of escalating merely because output was long;
- cancellation stops immediately;
- reasoning-only empty output does not enter the loop;
- deterministic suffix/prefix overlap removal avoids duplicated text;
- no-progress output stops the loop and preserves a resumable checkpoint;
- authoritative task state is re-injected on every iteration;
- checkpoint text remains explicitly non-authoritative;
- evidence/project/memory context is recompiled under the same physical context budget;
- loop stop reason and per-iteration progress are exposed in Response Details.


## M16.8a validation

Accepted through compatibility revision `deed6f3c041c87c1ef02b16360855f3f840eed3a`.

GitHub Actions run 364:

- targeted tests: **PASS**;
- complete Python suite: **PASS**;
- clean package/startup release smoke: **PASS**.

## M16.9a — structured Response Details backend

In progress.

A normalized `response_details` contract now exposes safe aggregates for model/runtime,
completion, context, authoritative task state, verification, continuation/checkpoint state,
evidence, performance and typed errors. It explicitly excludes prompt bodies, source bodies,
raw model responses and hidden reasoning text.


### M16.9a UI follow-up

The chat now consumes the normalized `response_details` contract directly. Response
Details renders compact sections for runtime, completion, context, task state, verification,
continuation, evidence, performance and errors; raw metadata remains available only under
an Advanced metadata disclosure. CI now runs `node --check` on the workstation UI bundle.


## M16.9a validation

Accepted on branch revision `0f9a9788a89d5b4f353e3134d15d936158779408`.

GitHub Actions run 366:

- UI JavaScript syntax: **PASS**;
- targeted tests: **PASS**;
- complete Python suite: **PASS**;
- clean package/startup release smoke: **PASS**.

## M16.10a — ReverendBench reliability regressions

In progress.

A separate fixture-backed M16 reliability catalog now covers:

- reasoning-only output-budget exhaustion as an expected typed failure;
- partial output-limit completion with resumable checkpoint state;
- deterministic high-assurance requirement verification;
- verification failure that must fail closed.

ReverendBench can now evaluate an explicitly expected failed Workstation job when the
case declares the terminal `job_status`, while unexpected failures remain benchmark
errors. The evaluator also supports an explicit `response_empty` contract for protected
empty-final-answer cases. These M16 fixture cases are not added to the legacy default
live catalog, avoiding nondeterministic hardware/model behavior in ordinary benchmark runs.


## M16.10a validation

Accepted on branch revision `f26f79451308d64aa08ef2883419ad32a60c9a45`.

GitHub Actions run 367:

- UI JavaScript syntax: **PASS**;
- targeted tests: **PASS**;
- complete Python suite: **PASS**;
- clean package/startup release smoke: **PASS**.

## M16.11 — final acceptance harness

In progress.

`python -m reverend.benchmarks.m16_validation` now separates portable software
acceptance from hardware-dependent live acceptance.

Portable gates verify:

- the complete Python test suite unless explicitly skipped;
- clean package/startup release smoke;
- M16 output-budget, typed-completion, context-compiler, requirement, verifier,
  agent-loop, privacy-safe Response Details and model-profile invariants;
- the four dedicated M16 ReverendBench reliability cases are present.

Live gates verify on the actual Ollama workstation:

- one FAST_GENERAL Workstation request completes locally;
- one DEEP_REASON Workstation request completes without raw reasoning fields escaping;
- `qwen3-coder:30b` executes as STRONG_CODE at the validated 16K context under
  exclusive residency.

`--skip-live` can establish `portable_ok=true` but deliberately returns a distinct
portable-only outcome and can never set `overall_ok=true`. This prevents GitHub CI from
claiming hardware acceptance it did not execute.

The optional Ollama `/api/chat` transport is not required for M16 acceptance because the
existing local `/api/generate` streaming path now preserves the required provider
completion/thinking metadata while continuing to discard raw private reasoning. Physical
contexts remain conservative pending live hardware evidence.


## M16 software closure

Portable M16 implementation is complete on the development branch. The remaining gate is
intentionally hardware-dependent and must run against the real Windows-hosted Ollama
instance reachable from WSL2.

GitHub CI now executes the M16 validator in portable-only mode and asserts all of the
following simultaneously:

- `portable_ok == true`;
- `live_ok == false`;
- `overall_ok == false`;
- both live probes are explicitly marked skipped.

This ensures CI cannot accidentally certify hardware behavior.

### Required live acceptance command

From the Reverend repository in WSL2:

```bash
python -m reverend.benchmarks.m16_validation \
  --repository . \
  --report-root benchmarks/results/vnext/m16/live-validation
```

A fully accepted M16 run requires exit code 0 with `portable_ok`, `live_ok` and
`overall_ok` all true. The live section must include successful FAST_GENERAL and
DEEP_REASON Workstation probes plus the `qwen3-coder:30b` STRONG_CODE 16K exclusive
residency probe.

No merge, tag, release or publication is part of this milestone closure.


## M16 live acceptance closure

The final programme validation at revision
`418524b533f6c05587698dffe8b9a5e4f0434093` closed the hardware gate.
FAST_GENERAL and DEEP_REASON Workstation probes passed, and
`qwen3-coder:30b` passed STRONG_CODE execution at the validated 16K context under
exclusive residency. M16 is therefore **LIVE ACCEPTED**.
