# M14 Intelligence & Runtime Optimisation — ACCEPTED

**Milestone:** M14 — Intelligence & Runtime Optimisation  
**Status:** COMPLETE  
**Accepted revision:** `84ce730554a7a9a879ee74b91c8723cdee17227f`  
**Final validation:** 2026-09-14T19:47:33Z

## Accepted optimisation architecture

M14 optimises the accepted vNext intelligence/runtime path without weakening correctness,
evidence quality, privacy, security or deterministic verification.

Accepted changes include:

- a short-lived thread-safe `ModelRegistry` inventory cache;
- explicit inventory refresh and invalidation;
- no stale-cache fallback after an explicit refresh failure;
- provider-read/cache-hit telemetry;
- one lazy shared underlying local scheduler per Workstation process;
- retained in-process inference gate and cross-process scheduler lock;
- queue-wait, setup/control-plane, provider and total runtime timing;
- deterministic low-risk public-fact understanding that avoids an unnecessary ROUTER call;
- ambiguity/advisory negative controls that retain the ROUTER guard;
- enforced streamed output-token budgets at the Ollama `num_predict` boundary;
- narrow compatibility for legacy injected stream schedulers;
- permanent M14 ReverendBench runtime cases.

No cloud inference, paid API dependency, unrestricted parallel heavyweight inference or
safety downgrade was introduced.

## Canonical final validation

Command:

```sh
"$PWD/.venv/bin/python" -m reverend.benchmarks.m14_validation
```

Result on `84ce730554a7a9a879ee74b91c8723cdee17227f`:

- complete Python suite: **490 passed / 0 failed**;
- deterministic M14 runtime benchmark cases: **3 / 3 passed**;
- retained M13 portable privacy/security contract: **PASS**;
- live Workstation clear-fact gate: **PASS**;
- live ambiguous-router guard: **PASS**;
- `portable_ok: true`;
- `overall_ok: true`.

### Live clear-fact measurement

Prompt: `Who is Ada Lovelace?`

Measured:

- model role: `FAST_GENERAL`;
- understanding method: deterministic;
- model calls: **1**;
- generation calls: **1**;
- embedding calls: **0**;
- inventory provider reads: **1**;
- inventory cache hits: **1**;
- prompt tokens: **132**;
- generated tokens: **226**;
- provider time: **8.835 s**;
- wall time: **8.887425 s**;
- loaded model: `qwen3.5:4b`.

The request therefore bypassed the unnecessary classifier call while retaining the normal
local answer path and bounded output policy.

### Live ambiguity-guard measurement

Prompt: `Who is he?`

Measured:

- ROUTER invoked: **yes**;
- understanding method: `local_router`;
- classified intent: clarification;
- model calls: **2**;
- prompt tokens: **301**;
- generated tokens: **122**;
- inventory cache hits: **1**;
- router generation: **84 tokens**;
- answer/clarification generation: **38 tokens**;
- wall time: **10.740828 s**.

The optimisation therefore does not simply disable classification for ambiguous requests.

## Portable optimisation regressions

Permanent deterministic cases verify:

1. classifier / available-role / answer-role resolution uses one provider inventory read;
2. a clear public fact question requires zero classifier calls;
3. an ambiguous pronoun question still invokes the classifier.

## Retained M13 security/privacy invariants

All passed:

- credential capability filtering;
- durable encrypted round-trip;
- Ephemeral state never persisted;
- persistent payloads encrypted;
- protected plaintext absent;
- explicit privacy modes;
- fail-closed sandbox contract;
- owner-only state files;
- trust escalation blocked.

## Output-token decision

M14 makes `ExecutionPlan.output_tokens` enforceable at the provider boundary but does not
lower the default 1,536-token ceiling.

The final live fact answer used 226 generated tokens, demonstrating headroom for future
route-specific tuning, but release acceptance does not trade answer quality for an
unvalidated smaller ceiling.

## Evidence

Canonical combined report:

`benchmarks/results/vnext/m14/live-validation/validation-20260914T194733Z.json`

## Safety invariants retained

- all inference remains local;
- deterministic mechanisms remain preferred over model inference;
- cheapest-sufficient routing remains bounded;
- uncertainty still escalates or clarifies rather than guessing;
- explicit network policy remains authoritative;
- M9 evidence gating remains authoritative;
- M10 knowledge fabric remains bounded;
- M11 worker authority remains typed and bounded;
- M12 code intelligence remains bounded and current-text authoritative;
- M13 privacy, trust, encryption and sandbox boundaries remain unchanged;
- deterministic verification still outranks model confidence.

## Decision

M14 is **ACCEPTED and COMPLETE**. M15 — vNext Release may begin.
