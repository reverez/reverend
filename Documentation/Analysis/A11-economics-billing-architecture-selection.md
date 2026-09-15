# A11 — Economics, Billing & Cloud v1 Architecture Selection

**Status:** topology and accounting contract frozen; exact GPU instance/rate requires A9/A10 evidence  
**Programme:** Reverend Cloud Analysis Phase  
**Baseline:** `main@a2d4194153976b1bc9f21212d72874e0b0e6e757`  
**Depends on:** A2 users/runs; A6 resource model; A7 lifecycle/recovery; A8 identity/secrets; A9 model research; A10 hardware/runtime/provider analysis  
**Currency:** GBP (£)

## Objective

Define how Reverend Cloud v1 is paid for, measured and shared between two developers, then select the deployment topology that best matches the actual operating model:

```text
two trusted users
one active Run at a time
active Run may use essentially the full VPS
GPU VPS billed by runtime
VPS should be off while idle
clients can wake the VPS
clients can hold off-VPS recovery replicas
```

The economic target is not minimum £/hour in isolation.

The primary engineering-economic metric is:

```text
£ per verified successful engineering task
```

A cheaper configuration that causes repeated failures, long repair loops or excessive human intervention may be more expensive overall.

## Baseline audit

The current repository already records useful timing and resource signals:

- runtime scheduler queue wait and provider timing;
- ResourceRequest/ResourceLease CPU/RAM/GPU/VRAM accounting;
- model profiles and measured residency;
- Control Plane Job timestamps;
- observability traces/spans with durations and model/tool identity.

What does not yet exist:

- user ownership on resource usage;
- provider PowerSession accounting;
- durable CostEvent ledger;
- per-user cost attribution;
- idle/boot/shutdown overhead policy;
- cloud budget enforcement;
- actual-vs-estimated provider reconciliation.

The local architecture therefore has measurement primitives but no cloud billing authority.

## Input dependency

A11 must not fabricate an instance price or GPU requirement.

The final numeric Cloud v1 instance selection requires A9/A10 to supply:

```text
candidate model set
minimum/target VRAM
system RAM requirement
CPU requirement
context requirement
runtime choice
measured throughput
provider instance candidates
actual provider billing granularity
actual GBP-equivalent prices
storage/network charges
startup/deallocation behaviour
```

Until those exist, A11 freezes the topology, accounting rules and selection method while leaving hardware values as parameters.

## Architecture options considered

### Option A — always-on full GPU VPS

```text
clients
  ↓
always-on Reverend + GPU
```

Advantages:

- simplest wake/access path;
- always-available API;
- no boot/recovery latency.

Disadvantages:

- pays expensive GPU rate while idle;
- poor fit for two users and one active Run;
- makes cost dominated by unused time.

**Decision:** rejected for Cloud v1.

### Option B — always-on cheap control node + elastic GPU worker

```text
clients
  ↓
persistent control node
  ↓
on-demand GPU node
```

Advantages:

- queue/API always available;
- control state survives GPU deallocation;
- clean future multi-node path.

Disadvantages:

- permanent fixed hosting cost;
- more infrastructure and authentication paths;
- two machines to operate before Reverend needs concurrent/distributed compute;
- duplicates some durability value already provided by client recovery peers.

**Decision:** retain as a future scale-up topology, not the default Cloud v1 topology.

### Option C — metered full-stack GPU VPS + client lifecycle/recovery

```text
Developer A client ─┐
                    ├── provider lifecycle control
Developer B client ─┘
                    │
                wake/deallocate
                    │
                    ▼
         metered Reverend GPU VPS
         ├── API/control plane
         ├── durable local state
         ├── worker
         ├── models
         └── active workspace
                    │
            encrypted recovery
              ┌─────┴─────┐
              ▼           ▼
          A client      B client
```

Advantages:

- no mandatory always-on server;
- one machine receives the whole workload;
- directly matches `MAX_ACTIVE_RUNS = 1`;
- full GPU/CPU/RAM can be used by the current Run;
- hourly compute cost stops when deallocated;
- least operational complexity;
- client recovery peers provide off-VPS durability.

Disadvantages:

- API unavailable while VPS is off;
- clients must wake it before submitting/resuming work;
- startup/model warm-up latency;
- provider lifecycle credentials or a tiny external wake relay are required;
- queue authority exists only while the server is running, so an offline submission first wakes the VPS.

**Decision:** selected Cloud v1 topology.

## Cloud v1 topology decision

Cloud v1 should use:

> **one metered full-stack GPU VPS, one active top-level Run, automatic idle deallocation, client-driven wake, and encrypted client-backed recovery replicas.**

A separate persistent control server is not required for v1.

This is intentionally reversible. A2/A7 contracts keep users, Runs, queue state, workers and ComputeNodes explicit so a future cheap control plane + elastic worker topology can be introduced without redefining Run ownership.

## Provider lifecycle requirement

The selected VPS/provider must expose reliable:

```text
start
stop/deallocate
status
```

operations through an API or equivalent automation interface.

A guest OS shutdown is not assumed to stop billing.

A10/A11 implementation must verify whether charges continue for:

- stopped/deallocated compute;
- attached volumes;
- public/reserved IPs;
- snapshots;
- object storage;
- network egress.

## Automatic idle shutdown

The server enters idle only when:

```text
active Run = none
resume queue = empty
normal queue = empty
critical background work = none
shutdown inhibitor = none
```

Runs blocked in `AWAITING_APPROVAL` do not count as runnable work and do not by themselves inhibit idle shutdown once their Approval record, checkpoint and required recovery generation are durable. They retain durable state but no exclusive compute lease.

Use a configurable grace period:

```text
IDLE_GRACE_SECONDS
```

Initial operational target: 5–10 minutes.

The exact value should be tuned against provider billing increment and startup/warm-up latency rather than hardcoded permanently.

Before deallocation, A7's graceful-drain requirements must pass, including an acknowledged off-VPS recovery generation.

## Wake path

When a client attempts to start/resume work while the VPS is off:

```text
client
↓
provider status check
↓
start VPS
↓
wait for Reverend /ready
↓
recovery completes
↓
submit/resume Run
```

If the only pending work is a human decision for an `AWAITING_APPROVAL` Run, the client follows the same wake path, submits the durable approval/rejection decision, and the Run returns to scheduling through `RESUME_QUEUED`. The approval request itself never executes the privileged action inline.

Two implementation options remain acceptable:

1. clients hold narrowly scoped provider lifecycle credentials;
2. a tiny external wake relay holds the provider credential.

If client-held credentials are used, scope them to instance start/stop/status only.

## Cost categories

Reverend should distinguish:

### Variable user-attributable costs

- active VPS compute while a Run holds the exclusive compute lease;
- paid model/API usage enabled for that Run;
- run/project-specific temporary storage if materially billable;
- project-specific egress if materially billable.

### Shared infrastructure costs

- attached persistent volume retained while compute is off;
- domain/DNS where paid;
- shared snapshots/backups;
- tiny wake relay if one exists;
- shared fixed IP charge if unavoidable.

### Shared transient overhead

- VPS boot/recovery;
- model warm-up before ownership can reasonably be assigned;
- idle grace after all Runs complete;
- graceful shutdown/backup finalization;
- system maintenance.

## Authoritative accounting objects

### PowerSession

Represents one provider-billed powered/deployed interval.

```text
PowerSession
├── power_session_id
├── provider
├── node_id
├── requested_start_at
├── provider_running_at
├── stop_requested_at
├── provider_stopped_at
├── billing_start_at
├── billing_end_at
├── rate_snapshot
├── estimated_cost_gbp
├── actual_cost_gbp
├── trigger_user_id
├── trigger_run_id
└── reconciliation_state
```

Provider timestamps/rules determine billable duration where available.

### ComputeLeaseUsage

Derived from the exclusive Run compute lease.

```text
ComputeLeaseUsage
├── lease_id
├── run_id
├── user_id
├── project_id
├── acquired_at
├── released_at
├── duration_seconds
├── node_id
├── gpu_model
├── model_usage_summary
├── rate_snapshot
└── estimated_cost_gbp
```

Paused time is excluded because the paused Run no longer holds the compute lease.

### CostEvent

Immutable accounting event:

```text
CostEvent
├── cost_event_id
├── occurred_at
├── category
├── user_id
├── project_id
├── run_id
├── node_id
├── quantity
├── unit
├── unit_price_gbp
├── estimated_cost_gbp
├── actual_cost_gbp
├── source
└── metadata
```

Do not maintain only a mutable `user.total_cost` counter. Totals must be derivable from immutable events.

## Per-user attribution policy

Initial two-user policy:

| Cost | Attribution |
| --- | --- |
| active Run compute | 100% Run owner |
| external paid API invoked by Run | 100% Run owner |
| project-specific paid storage/egress | Run/project owner policy |
| boot/recovery overhead | shared 50/50 |
| idle grace | shared 50/50 |
| graceful shutdown overhead | shared 50/50 |
| system maintenance | shared 50/50 |
| fixed persistent storage/backups | shared 50/50 |
| paused Run while not holding compute | £0 active compute |
| `AWAITING_APPROVAL` while not holding compute | £0 active compute |

This is deliberately simple and auditable.

If the users later want a different shared-overhead split, that is a billing policy change, not a scheduler change.

## Pre-emption accounting

Example:

```text
20:00–20:40  Alex Run A active
20:40–21:10  Friend Run B pre-empts A
21:10–21:50  Alex Run A resumes
```

Attributed active compute:

```text
Alex   = 80 min
Friend = 30 min
```

Alex is not charged active compute for the period Run A was paused.

This is why billing attaches to the exclusive compute lease, not merely `run.started_at → run.finished_at`.

The same rule applies to approval waits: once the Run reaches a safe `AWAITING_APPROVAL` checkpoint and releases its lease, the waiting interval is not attributed to the Run owner as active compute. Any provider boot/idle/shutdown overhead remains subject to the explicit shared-overhead policy.

## Billing formula

For a provider rate `R` GBP/hour and billable duration `T` seconds:

```text
raw_estimate = R × T / 3600
```

But provider billing granularity must be applied:

```text
billable_seconds =
    provider_rounding_rule(
        max(T, provider_minimum_duration)
    )
```

Then:

```text
estimated_compute_cost =
    R × billable_seconds / 3600
```

Never assume the marketing phrase "per hour" means whole-hour rounding or per-second billing. A10 must verify the provider's actual rule.

## Rate snapshot

Every cost-bearing event must store the rate used at the time.

```text
RateSnapshot
├── provider
├── product/instance type
├── currency_source
├── native_rate
├── native_currency
├── gbp_rate
├── billing_increment
├── minimum_duration
└── effective_at
```

Historical costs must not change because the provider later changes its price.

## Estimated vs actual cost

Reverend's live dashboard reports **estimated** cost.

Provider invoice/API data is the source of actual billed cost where available.

Reconciliation:

```text
sum estimated PowerSession cost
↓
provider actual charge
↓
difference
↓
shared overhead/reconciliation CostEvent
```

Do not pretend internally measured seconds are exact billing truth if the provider applies other charges.

## Budget hierarchy

The future A6 hierarchy can expose cloud financial limits:

```text
User monthly budget
   ↓
Run budget
   ↓
Team/task budget
   ↓
Model/tool budget
```

Cloud v1 minimum controls:

```text
max_run_cost_gbp
max_run_runtime
monthly_user_soft_limit_gbp
monthly_user_hard_limit_gbp
```

### Soft limit

Warn the owner and surface projected cost.

### Hard limit

Prevent acquisition of new paid compute/tool work unless an authorized human increases the budget.

A hard budget must not terminate an unsafe atomic external action halfway through. It prevents the next charge-bearing action at a safe boundary.

## Cost dashboard

Per Run:

```text
Runtime
Active compute time
Estimated VPS cost
Paid API cost
Total estimated Run cost
```

Per user/month:

```text
active compute
paid APIs
allocated shared overhead
estimated total
reconciled actual total
```

Shared account view:

```text
Alex
Friend
Shared overhead
Provider actual
Unreconciled difference
```

## Economic benchmark

Model/hardware evaluation must record, at minimum:

```text
task success
verification success
repair rounds
human intervention
wall-clock time
GPU active time
provider billed time
estimated/actual cost
```

Primary comparison:

```text
£ / verified successful task
```

Secondary metrics:

- median completion latency;
- P95 completion latency;
- £ per successful repair;
- human interventions per task;
- idle/warm-up overhead percentage.

## Cloud v1 instance selection rule

After A9/A10 provide candidates, select the **lowest-cost instance/model/runtime combination that satisfies all mandatory quality and workload constraints**, not the smallest GPU in isolation.

Mandatory checks:

1. primary development model fits target context without unsafe memory pressure;
2. verifier/critic path fits;
3. required model transitions are operationally acceptable;
4. repository-scale target benchmark passes;
5. expected Run does not exceed target human-intervention threshold;
6. startup/model-load overhead is measured;
7. provider deallocation genuinely stops compute billing;
8. the selected instance remains within agreed monthly/run budget.

If two configurations pass, compare `£ per verified successful task`.

## Deferred numeric table

A11 intentionally leaves the following table unfilled until A9/A10 evidence exists:

| Candidate | GPU/VRAM | RAM | Runtime | Provider £/h | Verified success | Median task time | £/verified task |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| A9/A10 candidate 1 | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| A9/A10 candidate 2 | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| A9/A10 candidate 3 | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

Filling this without measured model/hardware/provider inputs would be fake precision.

## Why not split the VPS between the two users?

Cloud v1 intentionally does not reserve:

```text
50% GPU to Alex
50% GPU to Friend
```

The active Run should have access to effectively the whole allocatable machine.

Cost fairness comes from time attribution, not static resource partitioning.

This maximizes model capability and simplifies scheduling/accounting.

## Migration from current architecture

| Current | Cloud v1 |
| --- | --- |
| local machine cost implicit | explicit provider PowerSession |
| ResourceLease by Job | Run-owner-linked compute usage |
| no user IDs in runtime cost | immutable per-user CostEvents |
| workstation always locally available | metered VPS wakes on demand |
| no idle billing policy | automatic deallocation after grace |
| runtime telemetry only | estimated + provider-reconciled costs |
| no financial budget | run/user cost limits |

## Acceptance gates

A11 contract is complete when:

1. active compute is attributable to exactly one Run owner;
2. paused time is excluded from active Run cost;
3. provider uptime is separately measured through PowerSession;
4. shared and variable costs are distinct;
5. cost records are immutable/derivable;
6. actual provider charges can be reconciled;
7. budgets can block future paid work at safe boundaries;
8. automatic deallocation is part of the selected topology;
9. client wake/recovery is part of the selected topology;
10. always-on GPU hosting is rejected for v1;
11. a persistent control node is optional future infrastructure, not mandatory v1 cost;
12. approval-blocked Runs release compute and may coexist with another active Run or an idle/deallocated VPS;
13. `AWAITING_APPROVAL` time without a compute lease is £0 active user compute;
14. exact hardware/rate selection waits for A9/A10 measured evidence.

## Selected Cloud v1 architecture

> **Metered full-stack GPU VPS, one active Run, whole-machine scheduling, automatic idle deallocation, client-driven wake, encrypted client recovery replicas, per-owner active compute accounting and 50/50 shared overhead.**

## Frozen A11 invariant

> Reverend must be able to explain every material cloud charge in terms of a provider power interval, a user-owned Run or an explicit shared-overhead policy. The system optimizes for verified engineering outcomes per pound, and expensive compute remains powered only while it provides enough expected value to justify its cost.
