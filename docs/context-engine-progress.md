# Context Engine optimization progress

Branch: `work/context-engine`  
Starting baseline: `072c418cd5371a25a29ad6282356e22b5ecc4d22`

This workstream evolves the existing M16 Context Compiler V2. It does not introduce a second chat context engine.

## Milestones

| Stage | Status | Notes |
| --- | --- | --- |
| C1 — Audit + baseline measurements | Complete | Confirmed branch/main baseline, 12,000-character gates, V2 compiler, role registry, continuation path, research/development context paths, CLI bypass and green baseline CI. |
| C2 — Define canonical budget model | Complete | `context_window - output_reserve - safety_margin = safe input budget`; mandatory material is budgeted before optional layers. |
| C3 — Implement role-aware admission | Complete | Removed 12K request gates; final admission is performed after model-role selection against the complete compiled prompt. |
| C4 — Improve optional context selection/clipping | Complete | Priority-ordered token caps, bounded message selection, evidence clipping with provenance preservation, no mandatory summarizer call. |
| C5 — Add context telemetry/errors | Complete | Structured `context_budget_exceeded`, estimator metadata, utilization, non-evictable layers, clipped/omitted layers and provider prompt-token comparison. |
| C6 — Review canonical CLI inference routing | Complete | `reverend ask` and `reverend reason` now use an ephemeral canonical Workstation call instead of Hermes/direct Ollama. |
| C7 — Long-context benchmark suite | Complete | Added portable legacy-vs-token admission benchmark and focused regressions. |
| C8 — Regression validation/handoff | Complete (portable) | PR CI passed targeted tests, full suite, release smoke, M16/M17/M18 and final portable validation. Real-machine Ollama validation remains explicitly deferred. |
| C9 — Governor repair + main synchronization | Complete (portable) | Replaced substring request deduplication with service-declared structured identity, added regressions for genuine first-turn duplication and substring continuations, merged current main `0eb4380...`, and revalidated the integrated head. |

## Audit findings

1. `Workstation.chat()` rejected `len(text) > 12000` before routing, so a 16K coding model could never receive a request substantially larger than the legacy textbox ceiling.
2. `intelligence.understanding.understand()` repeated the same 12K gate. Its optional model classifier was already independently bounded to the first 6,000 characters and a 4K router context.
3. Context Compiler V2 already protected authoritative task/current request and clipped optional layers, but packing used a fixed three-characters-per-token heuristic.
4. Role context windows were already authoritative in the model registry and consumed through Workstation's role-context lookup.
5. Output budgets were already task/role sensitive: Workstation passes the routing plan's output budget to both compilation and generation.
6. Provider prompt token counts were already available after Ollama calls through scheduler telemetry, but were not compared directly with the pre-call compiler estimate.
7. Continuation was already bounded by request/task limits and no-progress detection. This work does not relax those limits.
8. `reverend ask` still invoked `~/.local/bin/hermes`; `reverend reason` used a direct Ollama helper. Both bypassed canonical context admission.
9. Development repository context remains a purpose-specific repository compiler feeding the development engine. It is not replaced here because development-agent optimization is a parallel workstream.
10. Persistent authoritative-task validation repeated the 12,000-character ceiling and long relevance queries were disabled above that size. Authoritative storage now preserves the full specification; relevance search alone uses a bounded 6K-head + 6K-tail query projection.

## Decisions

### DECISION — conservative dependency-free token estimator

**RATIONALE**  
Exact model tokenization is not uniformly exposed before local provider submission, and adding a large tokenizer dependency solely for admission would increase installation and model-coupling cost. The compiler therefore takes the maximum of calibrated character, UTF-8-byte and lexical/punctuation-piece estimates. Actual provider prompt tokens remain the post-call truth and are recorded for calibration.

**ALTERNATIVES**  
A model-specific tokenizer dependency; the previous fixed 3 chars/token heuristic; provider-only failure handling.

**MEASUREMENTS**  
Existing Workstation measurements show roughly 2.1–2.8 characters per prompt token on representative stress prompts. The new character component uses 2.5 chars/token and is strengthened by byte/piece estimates.

**COMPATIBILITY**  
No provider API or model registry change.

**RISKS**  
The estimator can still differ from a model tokenizer. The safety margin and provider telemetry are retained specifically to bound and measure that error.

### DECISION — retain a 512-token safety margin

**RATIONALE**  
The previous V2 margin is already established and prevents prompt packing from reaching the physical context boundary.

**ALTERNATIVES**  
Zero margin; percentage-only margin; larger fixed margin.

**MEASUREMENTS**  
No live evidence justifies reducing the established margin.

**COMPATIBILITY**  
Preserves prior default behavior.

**RISKS**  
A fixed margin is conservative on larger windows; future calibration can make it model-specific if measurements justify it.

### DECISION — output reserve remains the routing plan output budget

**RATIONALE**  
The router already chooses bounded task-sensitive output budgets. Reserving exactly that amount aligns admission with the actual `predict` limit and avoids starving code/reasoning answers.

**ALTERNATIVES**  
One global 1,536-token reserve; consume the full context with input.

**COMPATIBILITY**  
No change to routing policy or scheduler limits.

### DECISION — optional context is selected before clipped, without mandatory summarization

**RATIONALE**  
Required authority is never evicted. Optional layers are considered in this order: checkpoint, accepted evidence, project context, verified memory, recent history, retrieved older history, older summary. Each layer has one centralized token cap and is omitted or clipped when necessary.

**ALTERNATIVES**  
Append-all history; model summarization on every request; a new RAG framework.

**RISKS**  
Fixed layer caps may not be optimal for every task. Telemetry makes clipping frequency measurable without logging prompt text.

### DECISION — CLI Ask/Reason use ephemeral Workstation conversations

**RATIONALE**  
This removes two user-facing inference paths while preserving command-line compatibility. Ephemeral privacy avoids turning stateless CLI calls into durable chat history.

**ALTERNATIVES**  
Keep Hermes/direct Ollama; duplicate compiler logic in CLI.

**COMPATIBILITY**  
CLI command names and stdout answer behavior are retained. Errors now expose canonical Workstation error codes.

## Context budget contract

```text
physical model context window
- routing-selected output reserve
- safety margin
= maximum compiled input budget
```

System/security instruction, authoritative task state and the current request are non-evictable. The only current-request deduplication is structural: when Workstation has just persisted the current turn itself as the authoritative specification, the compiler may omit a second verbatim current-request layer because the same trusted request is already present in authority. Substring coincidence is never treated as duplication. If required layers do not fit, compilation fails with `context_budget_exceeded` before model generation. Optional context is never allowed to force truncation of those layers.

## Telemetry contract

No prompt body is added to telemetry. The compiler records:

- model role and configured context window;
- input budget, output reserve and safety margin;
- estimator name and estimated prompt tokens;
- provider prompt tokens when available;
- estimate delta/error percentage;
- input/physical context utilization;
- non-evictable layer names;
- optional clipped/omitted layer names;
- evidence counts and bounded provenance metadata;
- continuation segment estimated/actual prompt tokens where available.

## Validation commands

Portable focused regression:

```sh
PYTHONPATH=src .venv/bin/python -m pytest -q \
  tests/test_context_engine_optimization.py \
  tests/test_workstation_context_v2.py \
  tests/test_workstation_continuation.py \
  tests/test_workstation_agent_loop.py \
  tests/test_intelligence_routing.py \
  tests/test_runtime_models.py \
  tests/test_runtime_scheduler.py \
  tests/test_cli_inference.py
```

Portable benchmark:

```sh
PYTHONPATH=src .venv/bin/python benchmarks/evaluate_workstation_context.py \
  --output benchmarks/results/context/context-engine-optimization.json
```

Full regression:

```sh
PYTHONPATH=src .venv/bin/python -m pytest -q
git diff --check
git status --short
```

Real-machine validation must additionally exercise the configured 8K and 16K roles through Workstation and compare `estimated_prompt_tokens` with `actual_provider_prompt_tokens`. Live results must not be claimed from the portable benchmark.


## Portable validation result

Validation PR: #24 (draft, coordinator-owned; this worker did not merge it).

Original pre-governor code/test head: `cfc27dd25a6ac45959b1b549aa6160401a87f458` — run `34949998599` passed the complete portable pipeline.

Governor repair commit: `dafcccb75c65e44c8a0f22059c102222f879c9ec`.

Integrated code/test head after synchronizing current main `0eb4380c7adaca688b50e575b779c947a885e84b`: `223e6aa10538bed38c875d90eddba97b78d3f766`.

GitHub Actions run `34952364493` on that exact integrated code/test head: PASS.

- Python compilation: PASS.
- Shell helper validation: PASS.
- UI JavaScript validation: PASS.
- Targeted repository suite: PASS, including the structured current-request deduplication regressions.
- Full unit suite: PASS.
- Portable long-context benchmark contract: PASS inside the full suite; short, medium, near-8K, near-16K, oversized, long-history and evidence/acceptance-criteria cases executed.
- Clean package/startup release smoke: PASS.
- M16 portable validation: PASS.
- M17 portable validation: PASS.
- M18 portable validation: PASS.
- Final portable programme validation: PASS.
- Branch is synchronized with main at `0eb4380...`; the merge preserves both Context exception `error_details` and Development Agent `failed_phase` / `phase_status` telemetry.
- Real Ollama/RTX long-context validation: NOT RUN and not claimed; this is the remaining integration gate.
