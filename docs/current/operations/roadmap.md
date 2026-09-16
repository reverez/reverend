# Reverend roadmap

## Stabilized baseline

Reverend 0.4.0 M6–M18 is live-accepted and stabilized on `main`.

The original **M15** release-readiness milestone remains the accepted 0.4.0 packaging/release baseline; later M16–M18 work extends that same product line.

The retained M16–M18 acceptance report is:

`benchmarks/results/vnext/final-validation/final-validation-20260915T010131Z.json`

That retained report records 619/619 tests plus live local inference, 30B residency,
SearXNG research, searched-image acquisition and sandbox validation. The stabilization pass
that followed also verified:

- canonical data-root selection against the existing 132,229-chunk knowledge registry;
- deterministic Workstation input boundaries and usable 30B context up to 15,455 prompt tokens;
- authority-first fresh research with explicit primary/community/secondary source classification;
- safe primary-source snippet fallback when remote sites block restricted fetching;
- autonomous PLAN -> IMPLEMENT -> VERIFY development with independent verification;
- the modern browser shell, inspector, artifacts, streaming, Markdown, math, XSS protections,
  persistence, stop/cancel and mobile navigation.

`main` is the only canonical integration branch.

## Active optimization programme

Optimization proceeds in parallel from the stabilized `main` baseline:

| Workstream | Branch | Primary objective |
| --- | --- | --- |
| Runtime | `work/runtime-optimization` | reduce cold-load/residency latency and improve hardware scheduling |
| Context | `work/context-engine` | replace crude character admission with token-aware context budgeting |
| Research | `work/research-quality` | improve corroboration, claim support, contradiction/date resolution and fetch quality |
| Development | `work/dev-agent-optimization` | improve repository understanding, long-task autonomy, repair quality and coding benchmarks |
| Workstation | `work/gui-polish` | refine UX, observability and research/development presentation |

Each workstream must remain rebased or merged against current `main`, keep its scope narrow,
and return through review + green CI. See [development-workflow.md](development-workflow.md).

## Deferred subsystem

The autonomous image/video asset-generation subsystem remains intentionally deferred until
the optimization workstreams establish stronger runtime, context and orchestration behavior.

## Preserved invariants

Optimization must not weaken:

- local-only inference;
- explicit network policy and untrusted public-content handling;
- deterministic evidence gating and provenance;
- bounded model/retrieval/output budgets;
- explicit project trust;
- isolated development worktrees;
- host-controlled structured edits;
- deterministic verification and independent verification;
- fail-closed sandbox boundaries;
- encrypted privacy modes.

## Validation discipline

Portable CI must remain green after every integration. Real-machine changes to runtime,
research, development or Workstation behavior require targeted live smoke before integration.

Canonical validator:

```bash
python -m reverend.benchmarks.final_validation \
  --repository . \
  --report-root benchmarks/results/vnext/final-validation
```

Use `--skip-live` only for portable validation; it does not certify the real
Ollama/search/image paths.
