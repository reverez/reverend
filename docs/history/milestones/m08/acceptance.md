# M8 acceptance — 2026-09-14

M8 integrates typed understanding, bounded routing and per-request inference accounting
with Workstation. Deterministic signals handle clear requests; a bounded local ROUTER
classifies ambiguous Auto requests. The local classifier cannot grant execution permission.
Auto development passes an explicit project/change request to the existing isolated engine.
Installed-model availability, explicit overrides, low-confidence clarification, call budgets
and output reserves are enforced. Failed requests retain usage diagnostics.

## Evidence

- [Deterministic routing](../../../../benchmarks/results/vnext/m8/routing/benchmarks/runs/20260914T093704440638Z-366ffa53.json): 6/6 pass, zero inference calls.
- [Live Auto classifier](../../../../benchmarks/results/vnext/m8/classifier/benchmarks/runs/20260914T093756096468Z-7bcb86df.json): pass, two local calls, no retrieval or network use.
- [Workstation regressions](../../../../benchmarks/results/vnext/m8/workstation/benchmarks/runs/20260914T093704459777Z-17d3c304.json): rocket passes; Xavier and nonexistent entity fail. No runtime errors/timeouts; each case uses one embedding and one generation call.

The rocket improvement is domain classification, not an implemented evidence gate. The
remaining failures are preserved for M9. Keyword relevance and response checks do not prove
factual correctness or safety. M6/M7 reports remain immutable.

The historical RAG cases now declare two **total inference** calls; earlier one-call budgets
were not enforced and omitted embeddings from accounting. No additional inference operation
was introduced into their existing RAG path. See `docs/current/architecture/intelligence.md` for the measurement
contract and scope boundaries.

## Validation

Full pytest: 314 passed. Chromium passed the Auto composer, rendering, source drawer,
citations, XSS, offline assets, persistence, streaming, Stop and responsive navigation.
`benchmark routing` passed through the CLI using isolated state. `git diff --check` passed.

The policy exposes bounded escalation decisions; M9/M11 own their evidence/worker execution.
M8 does not claim that entity resolution, factual evidence gating, reference corpus selection,
network-policy execution, encrypted privacy modes or vNext worker orchestration are complete.
Next milestone: M9 Research & Evidence Engine.
