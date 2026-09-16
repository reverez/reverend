# M12 Code Intelligence v2 — COMPLETE

M6–M12 are COMPLETE under the frozen vNext architecture.

## Baseline retained

M12 extends, rather than replaces, Reverend's existing deterministic code-intelligence
stack:

- repository/Git profiling;
- Python AST symbols and imports;
- lexical/structural retrieval;
- bounded context compilation;
- optional reconstructable semantic code vectors;
- isolated development worktrees and M11 typed Code Localizer orchestration.

Current repository text and deterministic structure remain authoritative. Semantic vectors
remain an optional retrieval overlay.

## Slice 1 — bounded Python dependency graph

This slice adds a first-class repository-internal Python dependency graph derived only
from the existing AST import profile.

Properties:

- resolves absolute and relative imports only when they map to a known repository module;
- records deterministic source → target dependency edges;
- exposes both imported dependencies and reverse dependents;
- supports bounded breadth-first related-file expansion;
- defaults localization expansion to one hop;
- hard-bounds traversal depth and result count;
- ignores unresolved/external modules rather than guessing.

## Retrieval integration

Deterministic code retrieval now expands from at most the three strongest direct Python
matches into one-hop repository-internal dependencies/dependents.

Graph evidence is additive and explicitly labelled in hit reasons. It cannot replace
current lexical/symbol evidence, cannot escape the repository, and does not grant any
worker execution capability.

This immediately improves Code Localizer context because the existing context compiler
consumes `search_code()`: directly matched implementation files can now bring in
structurally related implementation modules and tests even when those neighbors do not
repeat the user's wording.

## Tests

New M12 regressions cover:

- relative and absolute internal import resolution;
- forward dependencies;
- reverse dependents/tests;
- bounded traversal;
- retrieval expansion into a structurally related file.

## ReverendBench localization gate

The first structural slice is green in CI:

- dependency-graph slice: **139 targeted / 412 full passed**;
- benchmark/provenance correction: **141 targeted / 414 full passed**.

The benchmark initially exposed that a lexically strong test could become a graph seed and
therefore lose its reverse-dependency provenance. Retrieval now seeds graph expansion from
implementation Python files only; tests remain eligible graph dependents and retain their
structural reason even when they also match lexically.

M12 now also owns a deterministic ReverendBench localization case backed by a real
temporary Git repository. It requires:

- the directly matched task implementation to rank first;
- an imported implementation dependency to be surfaced through graph evidence;
- the reverse-dependent test to be surfaced through graph evidence;
- zero model calls;
- one bounded retrieval round.

This creates a permanent regression gate for the structural-localization behavior rather
than relying only on unit-level graph assertions.

## Slice 2 — conservative symbol-call edges

The Python AST profile now records bounded call sites with their lexical caller. The
dependency graph resolves call edges only when Reverend can prove the target from:

- a same-module top-level symbol;
- an explicitly imported repository symbol;
- an explicitly imported repository module;
- a `self`/`cls` method within the same parsed class.

Ambiguous or dynamic calls remain unresolved rather than guessed.

Retrieval uses those resolved call edges to focus graph-expanded files on the relevant
target symbol or reverse-dependent caller/call line. This lets the existing context
compiler render a narrower code span instead of defaulting to the first block of a
related file.

## Slice 2 validation

The conservative symbol-call slice is green in CI:

- targeted suite: **143 passed**;
- full portable suite: **416 passed**.

## Slice 3 — task-worktree context integration

The real task-context compiler is now covered by an isolated-worktree regression that
places the relevant dependency symbol beyond the default first-file window. The compiled
Code Localizer context must still include that deep symbol because the call graph focuses
the related hit on the resolved callee.

The same regression requires the reverse-dependent test section to preserve both its
import-graph provenance and its resolved caller → callee reason.

The M12 ReverendBench structural-localization case is also strengthened to require
symbol-focused dependency and test evidence, while retaining a zero-model-call budget.

## Final acceptance

Canonical acceptance completed on revision
`4afd617c7b3076f7b903aaffc88e637c74b82c61`.

Final results:

- full Python suite: **421 passed / 0 failed**;
- ReverendBench structural-localization: **1/1 PASS**;
- live Code Localizer: **PASS**;
- dependency symbol focus: **true**;
- test symbol focus: **true**;
- grounded planner paths: **true**;
- local model calls: **1**;
- overall acceptance: `overall_ok: true`.

The final localization-seed correction excludes weak incidental direct matches from graph
seeding when they fall below the confidence floor relative to the strongest implementation
hit. This preserves stronger structural call provenance without removing low-score direct
hits from ordinary retrieval.

Canonical evidence:
`benchmarks/results/vnext/m12/live-validation/validation-20260914T175507Z.json`.

M12 is **COMPLETE**. M13 — Privacy & Execution Security v2 is next.
