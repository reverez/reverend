# Runtime Optimization Progress

**Branch:** `work/runtime-optimization`

**Starting baseline:** `072c418cd5371a25a29ad6282356e22b5ecc4d22`

**Code validation revision:** `5f01626aa24bd290209374e8b90845a71f5e092e`

**Status:** PORTABLE COMPLETE; LIVE RETENTION POLICY MEASURED AND PROMOTED ON INTEGRATION BRANCH

This workstream optimizes Reverend's canonical local model runtime without replacing
the strong model, creating a second scheduler/provider, weakening exclusive-memory
safety, or changing local-only inference.

## Milestone status

| Stage | Status | Evidence |
| --- | --- | --- |
| R1 — Audit + benchmark current runtime | COMPLETE | Exact baseline branch/SHA audited; retained model reports and baseline CI inspected |
| R2 — Identify residency/swap bottlenecks | COMPLETE | Cold load dominates; repeated same-model exclusive requests already reuse residency; model-inventory churn and missing lifecycle telemetry identified |
| R3 — Implement minimal policy improvements | COMPLETE | Inventory reuse window improved; live 330-second comparison justified promoting strong-code keep-alive from 5m to 10m on the integration branch |
| R4 — Add lifecycle/resource telemetry | COMPLETE (portable) | Provider load duration, residency state, loaded-model VRAM/context/expiry and unload reasons exposed |
| R5 — Stress contention/failure recovery | COMPLETE (portable) | Existing lock-timeout regression retained; generation and unload failure recovery regressions added |
| R6 — Benchmark before/after | COMPLETE (runtime policy) | Live cold/warm, strong-fast-strong, 5m delayed and 10m delayed measurements completed on RTX 5070 workstation |
| R7 — Regression validation + handoff | PORTABLE COMPLETE | Final runtime SHA `0ab4dc1759b25b2c5829710e2d50320e82541cef` validated by PR CI run `34949141274`: 438 targeted + 672 full tests, release smoke, M16/M17/M18/final portable gates all pass |

## Baseline measurements

The retained target-machine reports remain authoritative for the 30B model.

### qwen3-coder:30b, 8K

- cold instruction elapsed: 29.240 s;
- provider load: 23.647 s;
- warm coding load: 0.009 s;
- warm reasoning load: 0.003 s;
- warm generation: 36.72–36.92 tok/s;
- observed model VRAM after load: about 6.24 GB;
- observed free system RAM after load: about 1.27–1.33 GiB.

### qwen3-coder:30b, 16K

- cold instruction elapsed: 22.403 s;
- provider load: 21.064 s;
- warm coding load: 0.005 s;
- warm reasoning load: 0.004 s;
- warm generation: 32.04–36.80 tok/s;
- observed model VRAM after load: about 6.22 GB;
- observed free system RAM after load: about 1.10–1.40 GiB.

These measurements confirm that cold loading, not warm generation, is the dominant
strong-model latency.

## Audit findings

1. `STRONG_CODE` already preserves same-model residency. The scheduler unloads
   competing models before an exclusive run but does not unload the target after the run.
2. `DEEP_REASON` and `CRITIC` remain exclusive-memory; `FAST_GENERAL` and
   `FAST_CODE` remain shared-residency.
3. The production Ollama path already passes per-model `keep_alive` honestly.
4. The 30B production profile remains 16K context; live integration evidence now supports a ten-minute keep-alive.
5. The retained model bake-off used a ten-minute keep-alive successfully, but the target
   machine has very low free RAM while 30B is resident. A longer production default is
   therefore a policy choice that requires a delayed live workflow test, not a speculative
   code change.
6. Production runtime accounting previously discarded Ollama `load_duration` and detailed
   `/api/ps` residency fields, so Reverend could not distinguish cold vs reused exclusive
   runs in its own request accounting.
7. The model inventory cache default was five seconds. A representative 24-second
   multi-step workflow therefore re-read provider inventory three times even though model
   installation state had not changed.
8. No canonical CPU/RAM/GPU quota scheduler exists. Current safety is intentionally
   conservative: serialized execution plus memory-exclusive heavyweight roles. This
   workstream does not invent provider-independent VRAM allocation that Reverend cannot
   enforce.

## Implementation

### Residency and lifecycle telemetry

The canonical provider now exposes typed loaded-model facts when available:

- model name;
- total provider-reported size;
- provider-reported VRAM size;
- loaded context length;
- expiry timestamp.

Exclusive scheduler runs now record:

- `provider_load_seconds` from Ollama `load_duration`;
- `residency_state_before`: `resident`, `unloaded`, or `unknown`;
- whether the target was already loaded;
- models loaded before the run;
- models explicitly unloaded before the run;
- aggregate known loaded VRAM before the run;
- target VRAM and expiry before the run.

Shared-model requests deliberately do not add a new `/api/ps` probe, so observability
does not add routine network/provider latency to cheap requests.

Only states Reverend can actually infer are emitted. There is no fake asynchronous
`loading` or `evicting` precision.

### Inventory reuse

`ModelRegistry` default inventory TTL changed from 5 s to a bounded 30 s.

Explicit refresh/invalidation semantics are unchanged. This trades at most 30 seconds of
installation-inventory staleness for substantially fewer `/api/tags` reads during an
ordinary multi-step workflow.

The deterministic before/after benchmark runs the same logical sequence at t=0, 12 and
24 seconds:

- baseline five-second TTL: 3 provider reads;
- optimized 30-second TTL: 1 provider read;
- delta: -2 reads (-66.7%);
- model calls: unchanged at 0.

### Failure recovery

Regressions prove:

- a provider generation failure releases the scheduler file lock;
- an explicit competitor-unload failure prevents target generation;
- after the provider condition clears, the next strong-model request can acquire the
  same lock and complete;
- no scheduler-owned stale residency state is persisted across failures.

Provider unload operations themselves cannot be made transactional because Ollama owns the
actual process/memory state. Reverend therefore fails explicitly and re-observes provider
state on the next request instead of pretending to roll back an unload.

### Live residency benchmark

`python -m reverend.benchmarks.runtime_residency` exercises the canonical
`OllamaProvider -> ModelRegistry -> ModelScheduler` path and records safe runtime
measurements without writing model response text.

It supports:

- role sequences;
- bounded output tokens;
- explicit cold start of the first target;
- keep-alive override;
- inter-request delay;
- JSON report output.

## Architectural decisions

### Decision 1 — Keep qwen3-coder:30b and 16K production context

**DECISION**

Preserve the accepted 30B strong-code model and 16,384-token context.

**RATIONALE**

Retained live results show viable warm throughput and successful 16K execution. Cold load
is the bottleneck.

**ALTERNATIVES**

Replace the model with a smaller model; reduce context globally.

**MEASURED EVIDENCE**

16K cold load 21.064 s; warm loads 0.004–0.005 s; warm generation 32.04–36.80 tok/s.

**COMPATIBILITY IMPACT**

None.

**RISKS**

The model remains memory-heavy.

### Decision 2 — Promote strong-model keep-alive to ten minutes

**DECISION**

Leave the production 30B keep-alive at five minutes until delayed live validation is run.

**RATIONALE**

The retained bake-off proves Ollama accepts ten-minute retention, but the 30B model leaves
only about 1.1–1.4 GiB system RAM free. Extending idle residency is a hardware-policy
tradeoff.

**ALTERNATIVES**

Set ten minutes globally; pin indefinitely; shorten residency.

**MEASURED EVIDENCE**

Cold reload costs about 21–24 s while warm load is milliseconds; target-machine RAM
headroom is small.

**COMPATIBILITY IMPACT**

None in this branch.

**RISKS**

The 30B model retains about 6.22 GB of VRAM while idle, so a competing model or GPU-heavy
workload can still evict it. The live strong -> fast-general -> strong test confirms that this
workstation cannot keep the 30B and 4B inference models resident together.

### Decision 3 — Provider remains authoritative for residency

**DECISION**

Use Ollama `/api/ps`, `load_duration`, `keep_alive`, and explicit unload behavior as
the source of truth.

**RATIONALE**

Ollama owns model processes and memory. Reverend can schedule requests and ask for unloads
but cannot safely pretend to own low-level GPU allocation.

**ALTERNATIVES**

Maintain a hidden runtime residency database; infer VRAM state from model specifications.

**MEASURED EVIDENCE**

Existing live reports already contain provider-observed size, VRAM, context and expiry.

**COMPATIBILITY IMPACT**

Adds optional telemetry only.

**RISKS**

External Ollama activity can change residency between observations; the scheduler therefore
does not treat observations as durable truth.

### Decision 4 — Bounded 30-second inventory cache

**DECISION**

Increase only the model installation-inventory cache from 5 s to 30 s.

**RATIONALE**

Installed-model inventory changes much more slowly than request routing, and explicit
refresh remains available.

**ALTERNATIVES**

Keep 5 s; cache indefinitely; add a second registry.

**MEASURED EVIDENCE**

Portable before/after case: 3 provider reads -> 1 for the same 24-second workflow.

**COMPATIBILITY IMPACT**

Potential newly-installed-model visibility delay up to the bounded TTL when callers do not
refresh explicitly.

**RISKS**

Small bounded staleness; no inference-state staleness is cached.

### Decision 5 — No session-routing redesign without swap evidence

**DECISION**

Do not reroute shared requests to the 30B model or create a second workflow scheduler.

**RATIONALE**

Repeated strong-code requests already reuse the same target. The unresolved question is
whether a real interleaved shared-model call causes Ollama to evict 30B on the RTX 5070
machine.

**ALTERNATIVES**

Sticky 30B sessions, role substitution, proactive preloading.

**MEASURED EVIDENCE**

Same-model scheduler behavior is already correct; interleaved swap behavior has not yet
been measured through Reverend.

**COMPATIBILITY IMPACT**

Existing routing remains unchanged.

**RISKS**

A real `STRONG_CODE -> FAST_GENERAL -> STRONG_CODE` sequence may still incur a reload;
the live benchmark below resolves that question.

## Required real-machine validation

Run these from the Reverend repository in WSL2 with Windows Ollama reachable.

### 1. Cold then immediate warm 30B reuse

```bash
python -m reverend.benchmarks.runtime_residency \
  --cold-start \
  --roles strong_code strong_code \
  --predict 32 \
  --output benchmarks/results/runtime-optimization/strong-cold-warm.json
```

Expected evidence to inspect:

- run 1: `residency_state_before=unloaded`, load near the retained cold baseline;
- run 2: `residency_state_before=resident`, load in the millisecond range;
- no unnecessary target unload.

### 2. Interleaved shared-model swap test

```bash
python -m reverend.benchmarks.runtime_residency \
  --cold-start \
  --roles strong_code fast_general strong_code \
  --predict 32 \
  --output benchmarks/results/runtime-optimization/strong-fast-strong.json
```

This determines whether the shared request causes provider eviction/reload on the actual
memory-constrained machine.

### 3. Current five-minute expiry test

```bash
python -m reverend.benchmarks.runtime_residency \
  --cold-start \
  --roles strong_code strong_code \
  --predict 32 \
  --delay-seconds 330 \
  --output benchmarks/results/runtime-optimization/strong-default-5m-delay.json
```

### 4. Candidate ten-minute bounded retention

```bash
python -m reverend.benchmarks.runtime_residency \
  --cold-start \
  --roles strong_code strong_code \
  --predict 32 \
  --delay-seconds 330 \
  --keep-alive 10m \
  --output benchmarks/results/runtime-optimization/strong-10m-delay.json
```

Compare load time, residency state and the workstation's RAM/VRAM condition before changing
the production model profile.

### 5. Existing M16 and final live regressions

```bash
python -m reverend.benchmarks.m16_validation \
  --repository . \
  --report-root benchmarks/results/vnext/m16/runtime-optimization-live

python -m reverend.benchmarks.final_validation \
  --repository . \
  --report-root benchmarks/results/vnext/runtime-optimization-final-live
```

## Completion rule

Do not mark the overall runtime optimization programme live-complete until:

1. cold -> warm same-model reuse is observed through Reverend;
2. strong -> shared -> strong swap behavior is measured;
3. five-minute vs ten-minute delayed retention is compared on the actual workstation;
4. any production keep-alive change is justified by those results;
5. M16 and final live validators remain green.

Portable implementation is complete. Hardware-dependent residency policy remains
deliberately deferred rather than guessed.
