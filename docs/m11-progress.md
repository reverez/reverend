# M11 Worker Orchestration — COMPLETE

M6–M11 are COMPLETE. M12–M15 remain outside this accepted milestone.

## Delivered

M11 introduced a single bounded orchestrator over typed specialist-worker state with
seven frozen logical roles:

- Research Scout
- Source Analyst
- Code Localizer
- Coder
- Reasoner
- Memory Curator
- Critic / Verifier

Workers cannot recursively delegate and cannot grant themselves capabilities. Input and
output state is bounded and JSON-compatible. Central budgets constrain workers, steps
and worker tool calls with deterministic exhaustion/failure stop reasons.

## Development integration

The mature M5 development engine now traverses the M11 worker seam:

- Code Localizer owns bounded coding-plan generation;
- typed localization state is passed to the Coder and checked fail-closed;
- Coder owns structured implementation proposals;
- host code retains edit application, path/hash validation and deterministic commands;
- typed candidate state is passed to a separately scheduled Critic / Verifier and
  checked against the edits actually applied;
- Critic / Verifier cannot edit or recursively request verification;
- Workstation development results expose worker stop reason and accounting.

The accepted default development worker budget is:

- workers: **3**
- worker steps: **3**
- worker tool calls: **0**

Zero worker tool calls is intentional: repository mutation and deterministic execution
remain execution-plane capabilities owned by host code.

## ReverendBench and validation

Canonical command:

```sh
"$PWD/.venv/bin/python" -m reverend.benchmarks.m11_validation
```

Final live run on revision `918c43b5e67d385a8e471c686fd217c2c579b15f`:

- complete Python suite: **408 passed / 0 failed**;
- M11 worker benchmark cases: **4 passed / 0 failed**;
- live development: **PASS**;
- stop reason: `complete`;
- workers / steps / worker tools: **3 / 3 / 0**;
- model calls: **3**;
- primary checkout unchanged: **true**;
- isolated worktree changed: **true**;
- independent verifier: `coder:verify`;
- `overall_ok: true`.

Evidence:

`benchmarks/results/vnext/m11/live-validation/validation-20260914T170931Z.json`

Acceptance:

`docs/m11-acceptance.md`

## Final state

M11 is COMPLETE. The worker architecture is accepted as a bounded typed orchestration
layer over Reverend's existing deterministic retrieval, execution and verification
planes. M12 may extend code intelligence without weakening these boundaries.