# M11 Worker Orchestration — ACCEPTED

**Milestone:** M11 — Worker Orchestration  
**Status:** COMPLETE  
**Accepted revision:** `918c43b5e67d385a8e471c686fd217c2c579b15f`  
**Live validation:** 2026-09-14T17:09:31Z

## Accepted architecture

M11 implements one bounded `WorkerOrchestrator` over typed specialist-worker state.
It does not introduce a free-form agent swarm or transfer host execution authority to
model workers.

Accepted logical roles:

- Research Scout
- Source Analyst
- Code Localizer
- Coder
- Reasoner
- Memory Curator
- Critic / Verifier

Workers communicate through bounded JSON-compatible state. Recursive delegation is
forbidden. Architectural worker count, worker steps and worker tool calls are centrally
budgeted and terminate with deterministic stop reasons.

The live development path is:

```text
request
→ isolated worktree
→ Code Localizer
→ typed dependency state
→ Coder
→ host-controlled structured edit application
→ deterministic verification / bounded repair
→ typed candidate state
→ independent Critic / Verifier
→ development result and worker accounting
```

The Coder does not receive direct filesystem or shell authority. The accepted live
development budget uses three workers, three worker steps and zero worker tool calls.

## Portable validation

The M11 validation harness ran the complete portable Python suite and all M11
ReverendBench worker cases:

- Python tests: **408 passed / 0 failed**
- worker benchmark cases: **4 passed / 0 failed**
- bounded-success stop: **PASS**
- worker-budget exhaustion: **PASS**
- real isolated development-engine integration: **PASS**
- independent verifier rejection: **PASS**

The real development benchmark proves that Reverend can apply a hash-checked edit in
an isolated Git worktree, execute deterministic verification, preserve the primary
checkout and attribute fresh independent verification to `coder:verify`.

## Live local-model acceptance

The configured local Ollama-backed scheduler passed the same real development fixture:

| Check | Result |
| --- | --- |
| Live development | PASS |
| Overall acceptance | `overall_ok: true` |
| Stop reason | `complete` |
| Workers used | 3 |
| Worker steps | 3 |
| Worker tool calls | 0 |
| Model calls | 3 |
| Retrieval rounds | 0 |
| Primary checkout unchanged | true |
| Isolated worktree changed | true |
| Independent verifier | `coder:verify` |
| Roles | Code Localizer → Coder → Critic / Verifier |

The local-model response was:

> Implementation passed deterministic verification and fresh independent verification.

## Safety invariants retained

- one orchestrator owns all worker scheduling;
- no recursive delegation;
- typed bounded worker state;
- worker policies remain role-specific and fail closed;
- Coder proposes structured edits but cannot directly mutate the repository;
- path/hash validation remains authoritative;
- deterministic verification outranks model confidence;
- Critic / Verifier is separately scheduled and cannot mutate the candidate;
- development remains isolated from the primary checkout;
- M5 execution mechanisms remain the authority for edits and commands.

## Evidence

Canonical live summary:

`benchmarks/results/vnext/m11/live-validation/validation-20260914T170931Z.json`

Validation command:

```sh
"$PWD/.venv/bin/python" -m reverend.benchmarks.m11_validation
```

## Decision

M11 is **ACCEPTED and COMPLETE**. M12 — Code Intelligence v2 may begin.