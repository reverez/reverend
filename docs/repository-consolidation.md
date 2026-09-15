# Reverend repository consolidation and stabilization

**Canonical integration branch:** `main`  
**Package identity:** Reverend 0.4.0  
**Retained live-accepted baseline:** `418524b533f6c05587698dffe8b9a5e4f0434093`  
**Stabilized integration baseline:** `a3be3c29893fe790147339015b0392f62eb708c8`  
**Policy:** one canonical `main`; short-lived scoped branches; review + CI before integration.

## Why this document exists

Reverend accumulated milestone, architecture, UI and research branches while the product
moved from the early Knowledge Fabric / Workstation prototypes to the accepted M6–M18
architecture. Those branches once represented genuine implementation choices, but they are
no longer competing production lines.

The repository has now been reconciled around one supported product path on `main`.

## Canonical product path

```text
Workstation UI
  -> request understanding / routing
  -> bounded local model scheduler
  -> Context Compiler + authoritative task state
  -> evidence gate
       -> local knowledge/reference
       -> optional fresh SearXNG/Brave discovery
       -> restricted page/image workers
       -> explicit first-party snippet fallback when remote fetch is blocked
  -> answer / source inspector / artifact preview

Development requests
  -> trusted project registration
  -> isolated worktree
  -> code intelligence
  -> structured plan / bounded workers
  -> host-controlled structured edits
  -> deterministic verification
  -> bounded repair
  -> independent verifier
```

There is no second production development engine and no alternate production research
pipeline hidden on historical branches.

## Retained acceptance

Canonical retained report:

`benchmarks/results/vnext/final-validation/final-validation-20260915T010131Z.json`

That report records:

- 619/619 Python tests;
- live FAST_GENERAL and DEEP_REASON Workstation inference;
- live `qwen3-coder:30b` STRONG_CODE at 16K under exclusive residency;
- live loopback SearXNG discovery and restricted page acquisition;
- live searched-image acquisition/cache validation;
- `portable_ok == live_ok == overall_ok == true`;
- no remaining M16–M18 gates.

The post-acceptance stabilization pass subsequently verified:

- correct selection of the existing authoritative `platform.db` registry;
- the 132,229-chunk local knowledge/Qdrant state;
- deterministic Workstation input admission;
- direct 30B recall at 15,455 prompt tokens;
- authority-first web research and source classification;
- explicit `search_snippet` fallback for blocked first-party pages;
- a live autonomous development task through PLAN -> IMPLEMENT -> VERIFY;
- the modern browser shell through Playwright smoke.

## Historical branch classification

The following branches are superseded and contain no forward work that belongs in the
canonical implementation:

- `architecture/m6-vnext-foundation`
- `architecture/m9-evidence-integrity`
- `architecture/v2-knowledge-fabric`
- `architecture/v3-local-development-engine`
- `implementation/m5-workstation`

The following stabilization branches were merged through reviewed PRs and are no longer
needed after merge:

- `stabilization/final-hardening`
- `stabilization/search-snippet-fallback`
- `stabilization/snippet-confidence-separation`

The following three 0.4.1 branches contain divergent historical experiments. They are not
production branches and should be retained only as archival history until they are tagged or
otherwise archived:

- `maintenance/0.4.1-fresh-research`
- `maintenance/0.4.1-ui-overhaul`
- `ux/0.4.1-workstation-overhaul`

Useful ideas from those experiments were already reconciled into the canonical Workstation
and research implementation; they must not be merged wholesale into current `main`.

## Current branch model

Parallel engineering now branches directly from stabilized `main`:

- `work/runtime-optimization`
- `work/context-engine`
- `work/research-quality`
- `work/dev-agent-optimization`
- `work/gui-polish`

See [development-workflow.md](development-workflow.md) for ownership and integration rules.

## Configuration policy

Runtime settings are environment/config first. Explicit `AI_DATA_ROOT` and
`REVEREND_RUNTIME_CONFIG` values always win. New installations use
`~/.local/share/reverend`; an existing authoritative legacy registry is preferred until an
actual `platform.db` migration exists at the canonical location.

Machine-specific external-tool profiles are not Reverend runtime authority and do not belong
in the canonical repository.

## Compatibility surfaces retained intentionally

The small `scripts/ai`, `scripts/ai-status` and `scripts/ai-doctor` wrappers remain as
compatibility shims. They delegate to the canonical Reverend entry points and do not contain
an alternate runtime.

Likewise, `reverend code` is only a compatibility alias for the canonical
`reverend dev implement` path.

## Deferred work

The autonomous image/video asset-generation subsystem remains deferred until the parallel
optimization programme improves runtime, context handling, research quality and development
autonomy.

## Repository hygiene rule

Historical acceptance reports and milestone documentation are retained because they are
evidence. Dead handoff instructions, machine-specific profiles and superseded implementation
branches are not part of the active product surface.
