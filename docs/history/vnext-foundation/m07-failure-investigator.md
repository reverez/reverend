# M-VNEXT-07 — Failure Investigator

**Status:** implementation candidate  
**Base:** `baseline/vnext-wave2-accepted@b8617b8fed546463ff8e6113cff58507ebf641aa`

## Objective

Add a bounded diagnostic specialist that explains observed Reverend failures without receiving repair, execution, merge, or promotion authority.

## Canonical flow

```text
failed / blocked authoritative workflow
        ↓
Control Plane + sanitized trace evidence
        ↓
bounded FailureCase
        ↓
Failure Investigator (DEEP_REASON)
        ↓
evidence-linked root-cause findings
        ↓
failure_investigation artifact
        ↓
proposed next actions + ReverendBench regression candidate
```

Diagnosis is recorded in a separate authoritative diagnostic workflow. The failed source workflow is immutable from the investigator's point of view.

## Authority

The specialist is `diagnosis_only`.

It may:

- read Control Plane state;
- read sanitized trace state;
- read artifact metadata;
- classify symptoms and likely causes;
- cite observed evidence;
- suggest bounded next actions;
- propose a regression case.

It may not:

- modify repository files;
- run shell commands;
- repair a task;
- retry a failed task;
- validate or promote an artifact;
- merge code;
- mutate the source workflow.

## Evidence contract

A `FailureCase` uses bounded operational evidence only:

- workflow status;
- failed/blocked/cancelled tasks;
- failed/cancelled/timed-out jobs and error codes;
- assurance-task/job metadata;
- verification/security/integration artifact state metadata;
- selected sanitized Control Plane events;
- error/cancelled trace spans when a trace store is supplied.

Implementation-patch payloads, prompts, model responses, credentials, and arbitrary event payload fields are not copied into the diagnostic evidence case.

Every root-cause finding returned by the model must cite one or more known `evidence_id` values. Unknown evidence references fail closed.

## Wave-2 observability additions

The Executive Orchestrator now emits two payload-minimized events:

- `AutonomyStageFailed` — stage + exception type only;
- `AutonomyPromotionBlocked` — verification/security/integration gate booleans and bounded reasons.

These events exist to make a blocked workflow diagnosable without exposing implementation payloads or private exception messages.

## Acceptance gates

Portable acceptance requires:

1. Failure Investigator specialist is discoverable in the Control Plane.
2. Specialist authority is diagnosis-only with no write/execute/promotion capability.
3. Failure cases exclude implementation payloads.
4. stage failures persist exception type but not private exception message.
5. blocked autonomy emits explicit gate evidence.
6. model findings referencing unknown evidence are rejected.
7. a successful investigation creates a separate diagnostic workflow and unpromoted diagnostic artifact.
8. source workflow state is unchanged by diagnosis.
9. the complete Python suite remains green.

Because the specialist uses the real `DEEP_REASON` role, final M-VNEXT-07 acceptance also requires one bounded live-model smoke after portable acceptance.


## Validation commands

Targeted portable gate:

```bash
python -m pytest -q tests/test_m_vnext_07_failure_investigator.py
```

Full portable gate:

```bash
python -m pytest -q
```

Live local-model gate:

```bash
python -m reverend.benchmarks.m_vnext_07_validation \
  --output benchmarks/results/vnext/full-system-alpha/m-vnext-07/live.json
```

A live PASS requires an evidence-linked security diagnosis, an unchanged failed source workflow, a completed diagnostic workflow, and an unpromoted diagnostic artifact.
