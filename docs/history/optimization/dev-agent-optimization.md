# Development-agent optimization milestone

**Branch:** `work/dev-agent-optimization`
**Starting baseline:** `072c418cd5371a25a29ad6282356e22b5ecc4d22`
**Scope:** autonomous development-agent quality only

This milestone evolves Reverend's canonical development path. It does not create a second
engine, worktree implementation, project database, verifier, runtime scheduler, or Context
Engine.

## Stage status

| Stage | Status | Evidence |
| --- | --- | --- |
| D1 — Audit + benchmark baseline | complete | baseline branch CI passed; legacy CodingBench 7/10, recall 1.0, 4 unrelated selections; self-host localization 0/1 |
| D2 — Repository mapping/localization | in progress | typed development-local localizer added; optimized CI pending |
| D3 — Structured planning | pending | |
| D4 — Acceptance-criteria compilation | pending | |
| D5 — Implementation context/edit precision | pending | |
| D6 — Diagnosis/repair | pending | |
| D7 — Independent verification | pending | |
| D8 — Realistic CodingBench | in progress | ten deterministic fixtures plus read-only Reverend self-host localization case |
| D9 — Longer autonomous/self-host smoke | pending | |
| D10 — Regression validation + handoff | pending | |

## Baseline measurement

Command:

```bash
python -m reverend.benchmarks.codingbench --strategy legacy --self-host --repository .
```

Observed in branch CI run `34948548820`:

- fixture success: 7/10 (0.70);
- localization recall: 1.00;
- unrelated-file selections: 4;
- average selected files: 3.6;
- fixture wall time: 0.5933 s on GitHub-hosted CI;
- Reverend self-host localization: 0/1, recall 0.50;
- the missing self-host path was `tests/test_development_verifier.py`.

The three fixture failures were the wrong-file trap, architecture-bypass trap, and
unrelated-file penalty. All three retained full recall but admitted a path explicitly ruled
out by the request, which makes selectivity—not raw retrieval recall—the first localization
target.

## Audit findings

The stabilized baseline already provides the hard safety/execution foundation: explicit
project trust, isolated task worktrees, host-applied structured full-file edits with path/hash
validation, bounded command execution, deterministic verification, bounded repair, and a
fresh verifier worker.

The principal quality gap is before implementation. The current `CODE_LOCALIZER` worker
directly invokes the strong-model coding planner over generic task context. Repository
profiling, lexical/structural retrieval, Python symbols, dependency/call relationships, recent
Git history, and test detection already exist, but they are not exposed as a typed
development-local localization contract. Acceptance criteria are carried as free text rather
than compiled into explicit immutable requirements. Repair diagnostics are bounded but
largely textual, and the verifier does not yet have deterministic unrelated-diff or acceptance
coverage checks.

## Decisions

### D-01 — Evolve the canonical engine

**DECISION:** add development-local evidence helpers and feed them into the existing
planner/coder/repair/verifier.

**RATIONALE:** the execution plane is already safe and validated; duplicating it would create
conflicting state and safety paths.

**ALTERNATIVES:** replace the development engine; add an external agent framework.

**MEASURED EVIDENCE:** the baseline CI at the starting SHA passes the full repository suite
and portable M16–M18/final validation.

**COMPATIBILITY IMPACT:** new helpers must remain optional at public boundaries and preserve
existing task/worktree/edit contracts.

**RISKS:** over-constraining localization could hide a file the model needs. The design keeps
bounded graph expansion and the existing `needs_more_context` escape hatch.

### D-02 — Typed deterministic localization

**DECISION:** compose existing lexical/structural retrieval with a bounded one-hop Python
dependency expansion, explicit affected-test discovery, confidence labels, repository map,
recent history, and conservative negative-path constraints.

**RATIONALE:** the baseline already had perfect fixture recall; the measured failure was
selectivity and failure to surface the verifier's own test in the self-host case.

**ALTERNATIVES:** add another semantic index; dump more repository text into the 30B prompt.

**MEASURED EVIDENCE:** optimized CodingBench is required to preserve 1.0 recall while
reducing unrelated selections.

**COMPATIBILITY IMPACT:** this is read-only development-local evidence and does not modify
the global Context Engine.

**RISKS:** negative language is deliberately interpreted only for high-confidence path hints;
ambiguous prose is not used to hard-exclude arbitrary files.

### D-03 — Benchmark localization deterministically

**DECISION:** CodingBench uses ten small real Git fixture repositories and one read-only
Reverend self-host case.

**RATIONALE:** exact expected/forbidden paths provide deterministic scoring for the stage
that most directly controls repository understanding and unrelated edits.

**ALTERNATIVES:** judge patches only with another LLM; use only `safe_divide`.

**MEASURED EVIDENCE:** baseline/optimized results are emitted as JSON by
`python -m reverend.benchmarks.codingbench`.

**COMPATIBILITY IMPACT:** none; benchmark fixtures are ephemeral temporary repositories.

**RISKS:** synthetic fixtures do not prove live 30B end-to-end coding quality, so live
development smoke remains a separate gate.
