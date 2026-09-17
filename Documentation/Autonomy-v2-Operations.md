# Reverend Autonomy v2 — Production Operations Runbook

> Operational guidance only. This document is **not** Design authority and does not supersede `Documentation/Design/`.

## Purpose

Run Reverend Cloud v1 development through the Autonomy v2 deterministic controller while keeping the local 30B OpenCode/Ollama model subordinate to controller-owned state, Git, verification, review and acceptance.

## Safety invariants

The production runner must preserve all of the following:

- never develop directly on `main`;
- one production controller process per repository;
- one isolated worktree per issue attempt;
- issue N+1 begins from the accepted integration head of issue N;
- models do not commit, merge, push, mutate GitHub state, or decide acceptance;
- implementation changes must remain inside the planner's validated file set;
- `.git`, `.autonomy`, `.opencode`, `.github`, frozen `Documentation/Design`, Autonomy v2 controller code and autonomy harness scripts are protected from unattended model edits;
- `pyproject.toml` may only gain Design-approved dependencies; existing requirements and all non-dependency build/test/package configuration are immutable unattended;
- no live-provider, credential, browser, GPU or external-service evidence may be fabricated;
- every accepted issue passes objective verification and independent review;
- every completed C-stage passes the milestone gate before the next C-stage starts;
- controller crashes resume from durable state; deterministic blockers do not restart forever.

## 1. Inspect any existing legacy run first

Do not kill a useful legacy 30B run blindly. From the repository root:

```bash
tmux ls || true
tmux capture-pane -pt reverend-dev -S -120 2>/dev/null || true
tail -120 .autonomy/logs/project-live.log 2>/dev/null || true
git status --porcelain
git log --oneline --decorate -20
```

Preserve any useful accepted work before switching runners.

## 2. Check out the v2 production branch

```bash
cd "$HOME/Arnavs Folder/dev/projects/research/reverend"
git fetch origin
git switch autonomy/v2-production-runner
git pull --ff-only
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

The working tree must be clean before a production run starts.

## 3. Local deterministic validation

Run the Autonomy v2 tests first:

```bash
python -m pytest -q tests/test_autonomy_v2_*.py
```

Then run the full repository gates:

```bash
bash scripts/autonomy-gates.sh
```

Do not continue to live model execution if either command fails.

## 4. Prove the 30B model can actually use OpenCode tools

Capability metadata is not sufficient. Run the disposable canary preflight:

```bash
python -m reverend.autonomy_v2.cli preflight \
  --model ollama/reverend-coder30 \
  --ollama-model reverend-coder30
```

Expected result: JSON with `"passed": true`.

The preflight must demonstrate a real repository read and an exact canary edit inside a disposable worktree. A failure is a hard stop until model/OpenCode configuration is repaired.

## 5. One-issue production canary

Before a long unattended run, execute exactly one queued issue:

```bash
python -m reverend.autonomy_v2.cli run \
  --repository reverez/reverend \
  --model ollama/reverend-coder30 \
  --ollama-model reverend-coder30 \
  --max-issues 1
```

Confirm:

- result status is `COMPLETED`;
- exactly one issue is accepted;
- an Autonomy v2 integration branch exists;
- the accepted commit is the integration HEAD;
- the worktree is clean;
- Autonomy v2 logs show planner, implementer, verification and reviewer evidence.

A `COMPLETED` result with `--max-issues 1` means the bounded canary scope completed; it does **not** mean the whole C0 milestone is implemented.

## 6. Start the persistent C0-C9 supervisor

After the canary is sound:

```bash
bash scripts/autonomy-v2-supervisor.sh run \
  --repository reverez/reverend \
  --model ollama/reverend-coder30 \
  --ollama-model reverend-coder30
```

For an unattended laptop run, start the supervisor inside `tmux` and keep Windows/WSL awake. `tmux` does not survive machine sleep or WSL shutdown.

Example:

```bash
tmux kill-session -t reverend-v2 2>/dev/null || true
tmux new-session -d -s reverend-v2 \
  "bash -lc 'cd \"$HOME/Arnavs Folder/dev/projects/research/reverend\" && source .venv/bin/activate && bash scripts/autonomy-v2-supervisor.sh run --repository reverez/reverend --model ollama/reverend-coder30 --ollama-model reverend-coder30'"
tmux capture-pane -pt reverend-v2 -S -80
```

## 7. Status and logs

Latest durable session:

```bash
python -m reverend.autonomy_v2.cli status
```

Supervisor output:

```bash
tail -f .autonomy/v2-production/supervisor.log
```

Session manifests:

```bash
ls -lt .autonomy/v2-production/sessions/
```

Issue/model logs are stored under `.autonomy/logs/` and production milestone logs under `.autonomy/v2-production/logs/`.

## 8. Recovery

If the controller process crashes, the supervisor may restart a bounded number of times. To resume manually:

```bash
python -m reverend.autonomy_v2.cli resume
```

Do **not** use `--retry-failed` automatically. First inspect the blocker. Use it only when the cause was repaired and a new issue attempt is justified:

```bash
python -m reverend.autonomy_v2.cli resume --retry-failed
```

Recovery semantics:

- accepted but not yet integrated: fast-forward the accepted commit and continue;
- interrupted unaccepted attempt: preserve evidence, remove the isolated attempt, and restart from current accepted integration HEAD;
- deterministic issue blocker: stop;
- milestone gate failure: stop;
- concurrent controller detected: stop;
- explicit human interrupt: stop.

## 9. Expected blockers

A safe production run is allowed to stop. Likely legitimate blockers include:

- missing local PostgreSQL/service prerequisites for later milestones;
- live RunPod/provider credentials or paid-compute evidence;
- external network/provider acceptance gates;
- a requested dependency outside the frozen whitelist;
- a required edit to protected Design/controller/CI surfaces;
- repeated model protocol failure;
- test failures that exhaust the repair budget;
- reviewer defects that remain after the repair budget.

These are preferable to fabricated progress.

## 10. Before promoting anything toward main

Even after an unattended session reports completion:

```bash
git status --porcelain
git log --oneline --decorate --graph -40
bash scripts/autonomy-gates.sh
```

Review the integration diff and milestone evidence before any merge to `main`. Autonomy v2 intentionally does not push to `main`, close GitHub issues, or claim live-provider acceptance on its own.
