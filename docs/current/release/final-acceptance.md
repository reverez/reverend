# Reverend final acceptance

**Original acceptance branch:** `architecture/m6-vnext-foundation`  
**Current canonical integration branch:** `main`  
**Release line:** Reverend 0.4.0  
**Status:** LIVE ACCEPTED — retained final validation passed

## Scope

This is the canonical closure gate for the reliability, fresh-web and workstation-experience
work added after the accepted M6-M15 vNext programme.

It composes:

- **M16** — runtime reliability, context/task integrity, verification and continuation;
- **M17** — fresh web evidence and frontier detection;
- **M18** — workstation GUI, safe artifacts, diagrams and searched-source images.

The final validator deliberately does not invent a new feature milestone. It exists only to
prove that these three accepted software slices remain compatible as one system.

## Canonical portable acceptance

Run:

```bash
python -m reverend.benchmarks.final_validation \
  --repository . \
  --skip-live \
  --report-root benchmarks/results/vnext/final-validation
```

A successful portable-only run exits **2** by design and requires:

- the complete Python test suite, unless `--skip-tests` was explicitly supplied;
- one clean package/startup release smoke;
- M16 `portable_ok == true`;
- M17 `portable_ok == true`;
- M18 `portable_ok == true`;
- `live_ok == false`;
- `overall_ok == false`.

Exit code 2 means **portable software is accepted but real-machine acceptance was
intentionally not executed**. It is not a failure.

## Canonical full acceptance

From the real WSL2 Reverend checkout, with Windows-hosted Ollama reachable and the bundled
self-hosted SearXNG backend running (or another explicitly configured supported provider),
run:

```bash
python -m reverend.benchmarks.final_validation \
  --repository . \
  --report-root benchmarks/results/vnext/final-validation
```

For the canonical free deployment, first run:

```bash
scripts/reverend-searxng up
eval "$(scripts/reverend-searxng env)"
```

This single command then runs the remaining live gates:

1. FAST_GENERAL local Workstation inference;
2. DEEP_REASON local Workstation inference with raw private reasoning containment;
3. `qwen3-coder:30b` STRONG_CODE at the validated 16K context with exclusive residency;
4. real configured web search followed by restricted page acquisition;
5. real searched-image candidate passing FRESH evidence gating;
6. restricted PNG/JPEG/WebP acquisition, integrity validation and local cache verification.

Full acceptance requires exit code **0** with:

```text
portable_ok = true
live_ok     = true
overall_ok  = true
```

The report contains a `remaining_gates` list when anything is still unaccepted.

## Security invariants retained

Final acceptance must not weaken:

- local-only model inference;
- no raw chain-of-thought persistence or display;
- explicit network policy;
- public content remaining untrusted until evidence gating;
- freshness provenance for current claims;
- fail-closed bubblewrap/seccomp network workers;
- no direct remote browser image loading;
- authenticated loopback-only workstation API;
- bounded model, context, retrieval, output and continuation budgets;
- no automatic merge, tag, release or package publication.

## Actions intentionally outside acceptance

The validator does **not**:

- merge this branch;
- create a tag;
- create a GitHub release;
- publish a package;
- modify unrelated local uncommitted files.

Those remain explicit user decisions after full acceptance.


## Accepted live result

Final acceptance completed on revision
`418524b533f6c05587698dffe8b9a5e4f0434093`.

Evidence:

- complete Python suite: **619 passed / 0 failed**;
- M16 live FAST_GENERAL, DEEP_REASON and qwen3-coder:30b STRONG_CODE residency: PASS;
- M17 configured local SearXNG discovery/fetch: PASS;
- M18 accepted searched-image acquisition and local cache/sandbox path: PASS;
- `portable_ok: true`;
- `live_ok: true`;
- `overall_ok: true`;
- `remaining_gates: []`.

Canonical report:
`benchmarks/results/vnext/final-validation/final-validation-20260915T010131Z.json`.

Later commits are stabilization work and do not erase this accepted baseline; they must
continue to pass portable CI and receive targeted live smoke where their behavior touches
the real Ollama/search/visual path.
