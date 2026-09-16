# Parallel development workflow

Reverend uses one canonical integration branch: `main`.

The stabilized baseline for the current optimization programme is:

`a3be3c29893fe790147339015b0392f62eb708c8`

## Rules

1. Do not develop directly on `main`.
2. Start each workstream from current `main`.
3. Give each GPT chat exactly one branch/worktree.
4. Keep branch scope narrow and avoid unrelated refactors.
5. Rebase or merge current `main` before opening the final PR.
6. Require green targeted tests, full unit CI and relevant live smoke before integration.
7. Merge only through review; do not force-push `main`.
8. After merge, delete the short-lived branch.

## Active workstreams

| Branch | Ownership |
| --- | --- |
| `work/runtime-optimization` | model residency, cold-load latency, scheduler and hardware use |
| `work/context-engine` | token-aware admission, context packing, long-request reliability |
| `work/research-quality` | authority, corroboration, claim support, contradiction/date resolution |
| `work/dev-agent-optimization` | repository context, coding quality, repairs, longer autonomous tasks |
| `work/gui-polish` | UX, observability and research/development presentation |

These branches were created from the same stabilized `main` baseline.

## Local worktrees

Recommended layout:

```bash
git fetch origin

git worktree add ../reverend-runtime origin/work/runtime-optimization
git worktree add ../reverend-context origin/work/context-engine
git worktree add ../reverend-research origin/work/research-quality
git worktree add ../reverend-dev-agent origin/work/dev-agent-optimization
git worktree add ../reverend-gui origin/work/gui-polish
```

If a GPT chat works in a normal checkout instead, it must still verify its branch before editing:

```bash
git status --short
git branch --show-current
git rev-parse --short HEAD
```

The checkout must be clean and on the assigned branch.

## Integration gate

Every workstream PR should state:

- objective and scope;
- files/subsystems changed;
- measured before/after behavior where relevant;
- targeted tests run;
- full CI status;
- live-machine smoke required and result;
- known risks or follow-up work.

Changes that alter runtime scheduling, research acquisition, development execution or the
browser shell require targeted real-machine smoke in addition to portable CI.

## Conflict ownership

When two branches need the same central file, coordinate ownership rather than racing edits.
The following files are high-conflict surfaces:

- `src/reverend/workstation/service.py`
- `src/reverend/runtime/scheduler.py`
- `src/reverend/intelligence/evidence.py`
- `src/reverend/cli.py`
- `src/reverend/ui/app.js`

Prefer extracting narrow helpers inside the owning subsystem instead of making broad
cross-cutting changes from several branches simultaneously.

## Historical branches

Milestone and stabilization branches are not valid bases for new work. New work starts from
`main` only. Divergent 0.4.1 branches are archival references and must not be merged
wholesale.
