# M12 Code Intelligence v2 — ACCEPTED

**Milestone:** M12 — Code Intelligence v2  
**Status:** COMPLETE  
**Accepted revision:** `4afd617c7b3076f7b903aaffc88e637c74b82c61`  
**Live validation:** 2026-09-14T17:55:07Z

## Accepted architecture

M12 extends Reverend's deterministic code-intelligence subsystem without replacing the
M6–M11 architecture.

Accepted capabilities:

- bounded repository-internal Python dependency graph;
- deterministic forward dependencies and reverse dependents;
- conservative AST call-site capture;
- resolved symbol-call edges only when the target can be proven;
- symbol-focused graph-expanded context;
- reverse-dependent test discovery;
- bounded one-hop structural expansion;
- optional semantic code-vector overlay while current repository text remains authoritative;
- authoritative planner paths for modify/delete actions.

Workers still receive bounded context only. M12 does not grant workers filesystem or shell
authority, does not bypass M5 execution controls, and does not auto-merge generated edits.

## Structural localization behavior

The accepted retrieval path is:

```text
task/query
→ deterministic lexical/symbol scoring
→ high-confidence implementation seeds
→ bounded repository-internal dependency expansion
→ conservative symbol-call provenance
→ focused code/test spans
→ bounded task context
→ grounded Code Localizer plan
```

The final seed-stability fix prevents weak incidental substring matches from becoming
graph seeds and suppressing stronger structural provenance.

## Portable validation

The canonical M12 run executed the full Python suite and the deterministic
ReverendBench structural-localization case:

- Python tests: **421 passed / 0 failed**
- structural-localization cases: **1 passed / 0 failed**
- direct implementation top path: `src/example/tasks.py`
- dependency discovered structurally: **true**
- reverse-dependent test discovered structurally: **true**
- dependency symbol focus: **true**
- test symbol focus: **true**
- model calls for structural benchmark: **0**
- retrieval rounds: **1**

## Live local-model acceptance

The configured local Code Localizer also passed over a real isolated task worktree.

| Check | Result |
| --- | --- |
| Live localizer | PASS |
| Overall acceptance | `overall_ok: true` |
| Model | `qwen3-coder:30b` |
| Model calls | 1 |
| Needs more context | false |
| Dependency-focused context | true |
| Test-focused context | true |
| Grounded plan | true |
| Relevant plan path | true |
| Prompt estimate | 1,526 tokens |
| Context | 2,971 chars / 991 estimated tokens |

Context paths:

- `src/example/guard.py`
- `src/example/models.py`
- `src/example/tasks.py`
- `tests/test_tasks.py`

The planner selected only authoritative existing paths:

- modify `src/example/tasks.py`
- modify `tests/test_tasks.py`

## Safety invariants retained

- current repository text remains authoritative;
- semantic vectors remain optional and reconstructable;
- unresolved/dynamic calls are not guessed;
- structural traversal is bounded;
- external imports are ignored rather than inferred;
- planner modify/delete paths must come from authoritative context;
- development stays inside isolated task worktrees;
- model workers do not receive direct filesystem or shell authority;
- deterministic verification remains authoritative over model confidence.

## Evidence

Canonical live summary:

`benchmarks/results/vnext/m12/live-validation/validation-20260914T175507Z.json`

Validation command:

```sh
"$PWD/.venv/bin/python" -m reverend.benchmarks.m12_validation
```

## Decision

M12 is **ACCEPTED and COMPLETE**. M13 — Privacy & Execution Security v2 may begin.
