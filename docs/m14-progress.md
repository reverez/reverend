# M14 Intelligence & Runtime Optimisation — COMPLETE

M6–M14 are COMPLETE under the frozen vNext architecture.

## Frozen objective

M14 optimises the accepted intelligence/runtime architecture rather than replacing it.

The ReverendBench contract already defines the dimensions M14 must improve or preserve:

- task success;
- factual/retrieval/routing correctness;
- escalation and abstention behaviour;
- development verification safety;
- latency;
- model calls;
- prompt tokens;
- generated tokens;
- RAM/VRAM;
- security invariants.

Optimisation is accepted only when measurable cost/latency/resource behavior improves
without reducing correctness, evidence quality, safety, privacy or deterministic
verification.

## Accepted seams M14 must preserve

- deterministic request understanding remains the first classification layer;
- the bounded local classifier is only a fallback for low-confidence Auto requests;
- capability roles remain independent from concrete model names;
- cheapest-sufficient routing and bounded escalation remain authoritative;
- model-call/retrieval budgets remain hard limits;
- all inference remains local;
- M9 evidence gating and network policy remain authoritative;
- M10 knowledge fabric and M12 code intelligence remain bounded;
- M11 workers remain typed and bounded;
- M13 privacy, encryption, trust and execution boundaries remain unchanged;
- no unrestricted parallel heavyweight inference;
- no cloud inference or paid API dependency.

## Baseline finding — repeated model inventory queries

Current request/runtime flow repeatedly calls `ModelRegistry.installed_models()`, which
performs a provider `list_models()` request every time.

Examples:

- bounded classifier generation resolves the ROUTER role;
- `available_roles()` queries installed models before planning;
- the final answer generation resolves its selected role;
- development/worker calls resolve roles independently.

On Ollama this maps to repeated `/api/tags` round trips even though the installed-model
inventory normally remains stable across an individual request and short interactive burst.

This adds control-plane latency and holds the heavyweight scheduler boundary longer than
necessary without improving inference quality.

## Slice 1 — bounded model-inventory cache

Add a short-lived, thread-safe inventory cache inside `ModelRegistry`.

Requirements:

- preserve the provider as the source of truth;
- deterministic explicit refresh/invalidation path;
- small bounded TTL;
- no stale-cache fallback after an explicit refresh failure;
- identical role/model/digest resolution while cache is valid;
- no change to local-only inference policy;
- benchmark/test exact provider inventory-call reduction.

Target request-level effect:

```text
before:
classifier resolve → list_models
available_roles    → list_models
answer resolve     → list_models

after, within cache lifetime:
classifier resolve → list_models
available_roles    → cached inventory
answer resolve     → cached inventory
```

## Slice 2 — runtime accounting and scheduler overhead

After Slice 1 is green:

- expose control-plane/cache metrics needed to measure model-resolution overhead;
- distinguish scheduler queue wait from provider generation time where useful;
- preserve existing model-call/token accounting;
- avoid expensive model residency churn where evidence shows it is unnecessary;
- add deterministic ReverendBench runtime cases.

## Slice 3 — intelligence cost optimisation

Use ReverendBench evidence to inspect:

- unnecessary classifier calls;
- avoidable embedding/retrieval calls;
- prompt/context over-allocation;
- escalation paths that spend model calls without improving success.

Only change behavior where benchmark cases demonstrate equal/better correctness with
lower bounded cost.

## Slice 4 — workstation live acceptance

Final M14 acceptance must compare a frozen baseline and optimised runtime over representative
local flows and report at least:

- task/routing success;
- provider inventory calls;
- model calls;
- prompt/generated tokens when available;
- wall-clock latency;
- loaded-model/resource behavior where observable;
- all M13 security/privacy invariants still green.

## Green optimisation checkpoint

Revision `46dfa7e304ce029fa9addeb874ab41b78646700a` passed:

- targeted M14/relevant regression suite: **254 passed**;
- complete Python suite: **484 passed / 0 failed**.

Implemented optimisation slices:

### Model inventory control plane

- short-lived thread-safe `ModelRegistry` inventory cache;
- explicit refresh and invalidation;
- stale cache is not reused after an explicit refresh failure;
- provider remains authoritative;
- exact provider-read/cache-hit telemetry;
- deterministic benchmark reduces the classifier/availability/answer resolution burst
  from three logical inventory reads to **one provider read**.

### Workstation scheduler lifecycle

- one lazy thread-safe underlying local scheduler per Workstation process;
- existing in-process inference gate remains authoritative;
- existing cross-process model lock remains authoritative;
- registry/cache state can therefore be reused across an interactive Workstation lifetime.

### Router-call optimisation

- clear low-risk public fact questions use deterministic understanding directly;
- clear fact benchmark requires **zero classifier calls**;
- ambiguous/advisory negative controls still invoke the local router;
- end-to-end clear fact chat can operate with a one-model-call budget.

### Runtime observability

- model execution distinguishes scheduler queue wait, setup/control-plane time, provider
  generation time and total elapsed time;
- per-request inventory provider reads/cache hits are reported alongside existing
  model-call and token accounting.

### Output budget enforcement

- the existing `ExecutionPlan.output_tokens` policy now reaches the actual streamed
  provider `num_predict` boundary;
- default behavior remains 1,536 tokens;
- legacy injected schedulers remain compatible through a narrow unexpected-`predict`
  adapter path;
- output ceilings are **not** being lowered speculatively. Live M14 measurements will
  determine whether route-specific reductions have safe headroom.

## Final pre-acceptance checkpoint

Revision `5122ff57a41c29c85a007ebbcf395e9955b0bc10` passed:

- targeted optimisation/security suite: **260 passed**;
- complete Python suite: **490 passed / 0 failed**.

The final `reverend.benchmarks.m14_validation` harness now combines:

1. the complete pytest suite;
2. all deterministic M14 runtime benchmark cases;
3. the accepted M13 portable privacy/security contract;
4. a live local Workstation clear-fact request;
5. a live ambiguous-request router guard.

The live clear-fact gate requires:

- deterministic understanding;
- FAST_GENERAL routing;
- exactly one model/generation call;
- zero embedding calls;
- at most one provider inventory read with at least one cache hit;
- nonzero prompt/generated token accounting;
- generated tokens within the enforced output ceiling;
- nonnegative queue/setup timing and positive provider time;
- a nonempty relevant Ada Lovelace answer.

The ambiguity gate requires the local ROUTER to be invoked or a fail-closed clarification
result after that router attempt.

No output ceiling has been reduced yet. M14 will accept the optimisation first from measured
runtime behavior; route-specific ceiling reductions are deferred unless the live evidence
shows a clear, quality-safe margin.

## Final M14 acceptance

Canonical validation completed on
`84ce730554a7a9a879ee74b91c8723cdee17227f`.

Final results:

- complete Python suite: **490 passed / 0 failed**;
- deterministic M14 runtime cases: **3 / 3 passed**;
- M13 portable privacy/security contract: **PASS**;
- live clear-fact optimisation gate: **PASS**;
- live ambiguity-router guard: **PASS**;
- `portable_ok: true`;
- `overall_ok: true`.

Canonical evidence:
`benchmarks/results/vnext/m14/live-validation/validation-20260914T194733Z.json`.

M14 is **COMPLETE**. M15 — vNext Release is next.
