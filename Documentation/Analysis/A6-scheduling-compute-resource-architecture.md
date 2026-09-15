# A6 — Scheduling, Compute & Resource Architecture

> **Programme:** Reverend Cloud Analysis  
> **Milestone:** A6  
> **Status:** ACCEPTED  
> **Owner:** Backend / systems track  
> **Document purpose:** Define how Reverend maps logical work from A3–A5 onto finite CPU, RAM, GPU, VRAM, storage, time, and monetary resources while preserving one authoritative Control Plane.  
> **Important:** This report defines scheduling/resource semantics. Exact scheduling algorithms, database tables, provider adapters, heartbeat intervals, and cloud lifecycle code belong to the Design Phase.

---

## 1. Executive Decision

A6 separates four responsibilities that are often incorrectly merged under the word “scheduler”:

```text
1. WORKFLOW SCHEDULER
   What work is logically allowed to run?

2. COMPUTE SCHEDULER
   Where can admitted work physically run?

3. CAPACITY CONTROLLER
   Should more machines be acquired, woken, drained, or stopped?

4. EXECUTION RUNTIME
   How is the actual model/tool/workload executed on the selected machine?
```

These components cooperate through the authoritative Control Plane.

They do not become independent workflow authorities.

---

## 2. Canonical Execution Hierarchy

From A3–A5:

```text
Project
   ↓
Run / Workflow
   ↓
Team
   ↓
Task
   ↓
AgentInstance
   ↓
Job
   ↓
Execution operation(s)
```

Physical resources are ultimately allocated to **Job execution phases**.

Attribution flows upward.

---

## 3. Workflow Scheduler

The Workflow Scheduler operates on logical project state.

Inputs include:

- Task dependencies;
- Task status;
- required artifacts;
- Team plan;
- approvals;
- policy;
- failure/replan state.

Its output is the:

```text
READY SET
```

Example:

```text
             Architecture
                  │
        ┌─────────┼─────────┐
        ▼         ▼         ▼
     Backend   Frontend   Tests
        │         │         │
        └─────────┼─────────┘
                  ▼
             Integration
```

After Architecture succeeds:

```text
READY:
Backend
Frontend
Tests
```

Integration remains dependency-blocked.

---

## 4. Logical Readiness Is Not Physical Execution

Suppose:

```text
10 Tasks = READY
```

This means ten Tasks are logically eligible.

It does **not** imply:

```text
launch 10 simultaneous models
```

The Compute Scheduler may decide:

```text
3 RUNNING
7 WAITING_FOR_RESOURCES
```

This separation keeps A4's logical decomposition independent of current hardware.

---

## 5. Existing Job Lifecycle Fits the Model

Current Job states already include semantics similar to:

```text
QUEUED
ACQUIRING_RESOURCES
RUNNING
VERIFYING
SUCCEEDED
FAILED
CANCELLED
TIMED_OUT
```

This maps naturally onto the future distributed execution model.

A6 therefore keeps these semantics rather than inventing a second cloud-specific Job lifecycle.

---

## 6. ComputeNode as the Physical Abstraction

Cloud Reverend needs a provider-independent representation of execution capacity.

Conceptually:

```text
ComputeNode
├── node_id
├── provider
├── provider_instance_id
├── lifecycle state
├── trust classification
│
├── CPU capacity
├── RAM capacity
│
├── accelerators[]
│   ├── type
│   ├── model
│   ├── VRAM
│   ├── device IDs
│   └── capabilities
│
├── scratch storage
├── network capability
├── sandbox/runtime capability
│
├── installed runtimes
├── resident model profiles
│
├── active leases
├── health
├── telemetry
└── cost metadata
```

A10 later maps real cloud GPUs to this contract.

---

## 7. Capability-Based Placement

Agents should never say:

```text
run me on H100
```

They should request capabilities:

```text
GPU required
VRAM >= X
runtime capability Y
trust >= Z
```

Similarly, compilation may require:

```text
CPU >= 4 cores
RAM >= 8 GiB
Linux sandbox
C++ compiler
```

without knowing cloud provider or SKU.

---

## 8. Node Lifecycle Semantics

Exact enum values are Design work.

The architecture must support states equivalent to:

```text
PROVISIONING
REGISTERING
READY
BUSY
DRAINING
UNHEALTHY
UNREACHABLE
STOPPING
STOPPED
TERMINATED
```

Important distinction:

```text
READY / BUSY
```

are scheduling availability concepts.

```text
RUNNING / STOPPED / TERMINATED
```

are infrastructure lifecycle concepts.

---

## 9. ComputeNode Registry

The persistent Control Plane needs an authenticated view of available compute.

```text
ComputeNodeRegistry
├── node-1
├── node-2
└── node-3
```

Each node exposes:

### Declared capability

```text
96 GB GPU
192 GB RAM
32 CPU cores
CUDA/runtime support
```

### Runtime telemetry

```text
VRAM free
RAM available
utilization
resident models
active leases
health
```

The scheduler must distinguish capacity from current utilization.

---

## 10. ResourceRequest Semantics

The current resource request model is a strong foundation.

Useful existing concepts include:

- Job ownership;
- CPU;
- RAM;
- GPU requirement;
- estimated VRAM;
- GPU exclusivity;
- device constraints;
- expected runtime;
- priority;
- preemptibility;
- batchability;
- model identity;
- lease duration;
- queue timeout.

A future distributed form may also represent:

```text
accelerator capabilities
storage
runtime
sandbox
network
trust
data locality
deadline
cost ceiling
```

Not every field needs to ship in Cloud v1.

---

## 11. Atomic Allocation

Suppose a Job needs:

```text
4 CPU
16 GB RAM
1 GPU
40 GB VRAM
```

Reverend should either:

```text
grant the whole feasible bundle
```

or:

```text
grant nothing and keep the Job queued
```

It should not hold CPU/RAM while waiting indefinitely for GPU.

This preserves the existing all-or-nothing allocation philosophy and avoids hold-and-wait deadlocks.

---

## 12. ResourceLease Semantics

The current lease architecture is worth preserving.

Conceptual lease state:

```text
ACTIVE
RELEASED
EXPIRED
REVOKED
```

Useful properties:

- owner Job;
- acquisition timestamp;
- TTL;
- heartbeat;
- resource bundle;
- idempotent release;
- revocation;
- non-transferability.

---

## 13. Leases Are Job-Owned

Canonical ownership:

```text
ResourceLease
    ↓
Job
    ↓
Agent
    ↓
Task
    ↓
Team
    ↓
Run
    ↓
Project
    ↓
User
```

This lineage is essential for A11 billing and observability.

---

## 14. Phase-Level Leasing

An Agent should not hold an expensive GPU while doing unrelated CPU work.

Example:

```text
Inference #1
→ acquire GPU lease
→ infer
→ release

Run tests
→ acquire CPU/RAM lease
→ execute
→ release

Inference #2
→ acquire GPU lease
→ infer
→ release
```

One logical Job may own several execution-phase leases.

This greatly improves expensive GPU utilization.

---

## 15. Physical Resources vs Logical Capabilities

A6 separates:

### Physical resources

```text
CPU
RAM
GPU
VRAM
scratch storage
```

from:

### Logical execution authorities

```text
workspace mutation
Git branch ownership
deployment permission
secret access
network permission
```

These may both use lease-like concepts in implementation, but they are not one interchangeable resource model.

---

## 16. Compute Scheduler

Canonical placement flow:

```text
READY Job
   ↓
derive execution requirements
   ↓
candidate ComputeNodes
   ↓
filter infeasible nodes
   ↓
rank valid placements
   ↓
atomic ResourceLease
```

The Compute Scheduler is responsible for physical placement, not application correctness.

---

## 17. Model Routing and Placement Cooperate

A3 says Agents declare `ModelRequirement`.

A9 identifies eligible models.

A6 should not force this sequence:

```text
Model Router chooses exactly one model
   ↓
Compute Scheduler tries to find hardware
```

if several eligible models exist.

Preferred conceptual flow:

```text
ModelRequirement
   ↓
eligible model candidates
   ↓
eligible model × runtime × node placements
   ↓
best allowed execution choice
```

The Model Router and Compute Scheduler remain separate responsibilities.

---

## 18. Eligibility Before Optimization

Selection ordering:

```text
1. capability / trust eligibility
2. optimization among eligible choices
```

Possible optimization factors:

- queue delay;
- model residency;
- expected runtime;
- provisioning delay;
- cost;
- utilization;
- data locality.

A cheap or warm model cannot be chosen if it fails the Agent's minimum requirement.

---

## 19. ComputeProvider vs InferenceRuntime

A6 freezes this distinction:

```text
RunPod / cloud infrastructure
= ComputeProvider

vLLM / SGLang / Ollama
= InferenceRuntime

Qwen / DeepSeek / North / etc.
= Model
```

These concerns must not be one monolithic `Provider` abstraction.

---

## 20. Capacity Controller

The Compute Scheduler answers:

```text
Where can this run now?
```

The Capacity Controller answers:

```text
Should more infrastructure exist?
```

Example:

```text
No eligible capacity
   ↓
Capacity Controller
   ├── wait
   ├── wake stopped node
   ├── provision node
   ├── scale pool
   └── reject due to policy/budget
```

This component is deterministic infrastructure.

---

## 21. Budget Admission Before Paid Provisioning

Rejected flow:

```text
need GPU
→ provision expensive node
→ later discover budget exhausted
```

Accepted flow:

```text
capacity required
   ↓
estimated commitment
   ↓
budget admission
   ↓
provider action
```

A11 defines the ledger.

A6 freezes the admission seam.

---

## 22. Expensive Compute Is Disposable

A0 says compute is replaceable.

A6 adds:

> **Expensive compute must not contain unique durable Run state.**

A worker can eventually:

```text
drain
→ release leases
→ persist required artifacts/checkpoints
→ stop/terminate
```

without losing the project.

A7 defines durability and recovery.

A10 defines cloud lifecycle.

---

## 23. CPU and GPU Work Should Overlap

The current single-laptop architecture understandably serializes heavy work.

Cloud Reverend should not globally serialize unrelated operations.

Example:

```text
GPU:
Developer inference

CPU:
unit tests

CPU:
repository indexing

network:
research acquisition
```

These can proceed concurrently if dependency/resource policy allows.

A6 therefore freezes:

> **Serialize conflicting scarce resources, not unrelated work.**

---

## 24. GPU Concurrency Is Runtime-Specific

Rejected permanent rules:

```text
only one GPU call forever
```

and:

```text
if free VRAM appears, launch everything
```

Sharing depends on:

- runtime;
- model;
- batching;
- GPU architecture;
- VRAM;
- workload behavior.

A6 requires explicit validated sharing semantics.

---

## 25. Same-Model Batching

If a runtime explicitly supports controlled batching:

```text
Agent A request ─┐
Agent B request ─┼──► same resident model
Agent C request ─┘
```

This can make A4 swarms economical.

But Reverend should only rely on batching after runtime validation.

---

## 26. Model Residency Is Schedulable State

A node should advertise:

```text
resident model
model profile
VRAM usage
warm/cold state
```

All else equal:

```text
warm eligible model
```

may be preferable to:

```text
same model requiring 90s load
```

However, warmness is an optimization only.

It cannot override capability requirements.

---

## 27. Strategic Residency

Future policy might keep:

```text
frequently used workhorse
```

resident while unloading:

```text
rare escalation model
```

between tasks.

A9 estimates workload frequency.

A10 provides physical/runtime data.

A11 determines economics.

A6 provides the scheduling mechanism.

---

## 28. Priority Classes

Exact numeric weights are deferred.

Useful conceptual priority classes include:

```text
recovery / safety-critical
interactive foreground
critical path
normal autonomous work
background
optional batch
```

User-blocking and critical-path work should generally outrank speculative/background work.

---

## 29. Fairness and Aging

Priority must not allow permanent starvation.

The current resource system already includes priority aging.

A distributed scheduler should retain/generalize:

```text
priority
+
aging
+
fairness
```

---

## 30. Backfilling

Example:

```text
Job A:
needs 80 GB VRAM
cannot currently fit

Job B:
needs 8 GB VRAM
can fit
```

If B can run without materially delaying A:

```text
run B
```

rather than leaving capacity idle.

Current fit-aware scheduling is a useful foundation.

---

## 31. Critical-Path Awareness

Future scheduler optimization can consider:

```text
which Task unlocks more downstream work?
```

Example:

```text
Task A → D → F
Task B → optional experiment
```

A may deserve higher scheduling priority.

This is an accepted **direction**, not a frozen heuristic.

---

## 32. One Active Run Does Not Mean One-Threaded Execution

Kirk's A2 may retain:

```text
one active top-level Run
```

for Cloud v1.

That Run can still contain parallel:

- research;
- tests;
- build;
- indexing;
- inference.

Top-level exclusivity and internal concurrency are different concerns.

---

## 33. Run-Concurrency Policy Must Not Be Hard-Coded Into Resources

The scheduler should support attribution by:

```text
User
Project
Run
```

even if the first product policy allows only one active Run.

This prevents future resource-architecture redesign if the concurrency policy changes.

---

## 34. Hierarchical Budgets

Canonical hierarchy:

```text
Run Budget
   ↓
Team Budget
   ↓
Task Budget
   ↓
Agent Budget
   ↓
Job / model / tool operation budget
```

Possible dimensions:

```text
model calls
tokens
wall time
CPU time
GPU time
storage
network/tool calls
Agent count
retry count
monetary ceiling
```

Children cannot consume resources outside delegated parent budget.

---

## 35. Estimated vs Settled Cost

Before execution:

```text
estimated cost
```

supports admission.

After execution:

```text
actual measured usage
```

supports settlement.

A6 produces resource telemetry.

A11 defines pricing/allocation policy.

---

## 36. Avoid Hidden Runtime Queues

If Reverend submits 30 requests to a model server that queues them internally, Reverend loses visibility over:

- priority;
- cancellation;
- pause;
- fairness;
- attribution;
- cost.

Therefore:

> **The authoritative backlog should remain visible to Reverend.**

A runtime may batch/queue a bounded set of already-admitted requests internally.

---

## 37. Preemption

A6 may request preemption.

A7 determines whether it is safe.

Execution should conceptually classify:

```text
PREEMPTIBLE
SAFE_AT_BOUNDARY
NON_PREEMPTIBLE
```

Examples:

### Usually restartable

```text
repository indexing
embedding batch
pure inference
```

### Boundary-safe

```text
multi-step Agent
simulation
```

### Dangerous to interrupt blindly

```text
deployment
database migration
Git push
external side effect
```

---

## 38. Inference Preemption

For Cloud v1 it may be simpler to:

```text
cancel and restart inference
```

than preserve partial KV state across machines.

This is consistent with A0:

```text
KV cache is disposable
```

Exact runtime support belongs to A10/Design.

---

## 39. Lease Revocation

Possible reasons:

```text
node draining
user cancellation
budget ceiling
node unhealthy
administrative action
higher-priority recovery
```

Revocation must emit explicit Control Plane events.

The Job cannot silently continue as though it still owns the resource.

---

## 40. Lease Expiry / Heartbeats

Canonical behavior:

```text
worker alive
→ heartbeat
→ lease remains valid

worker lost
→ heartbeat stops
→ lease expires / invalidates
→ capacity reconciled
```

This prevents dead workers from permanently holding scheduler capacity.

---

## 41. Lease State vs Physical Reality

A Control Plane lease claiming:

```text
GPU assigned
```

does not prove the node still exists.

The scheduler must reconcile:

```text
lease state
```

against:

```text
node/provider health
```

Node disappearance triggers A7 recovery.

---

## 42. Authenticated Node Registration

A random process cannot announce:

```text
"I am a Reverend GPU worker."
```

Worker registration must be authenticated.

A8 defines credentials/trust.

A6 freezes the requirement that registry entries represent authenticated infrastructure.

---

## 43. Node Heartbeats

Workers should report:

```text
health
capacity
leases
runtime
resident models
telemetry
```

If heartbeats disappear:

```text
READY
→ UNREACHABLE
```

No new work is assigned.

Affected leases become invalid/recoverable.

---

## 44. Node Draining

Before planned shutdown:

```text
READY
  ↓
DRAINING
```

means:

- accept no new Jobs;
- finish or safely interrupt active work;
- checkpoint/sync;
- release leases;
- terminate when inhibitors clear.

This is essential for elastic compute.

---

## 45. Shutdown Inhibitors

Some operations make shutdown unsafe.

Examples:

```text
checkpoint write
artifact synchronization
Git push
DB backup
model download
critical external reconciliation
```

A7 defines durability semantics.

The Capacity Controller must respect the inhibitor state.

---

## 46. CPU Execution Is First-Class

Many operations do not need GPU:

```text
Git
tests
compilation
repository search
static analysis
file processing
research handling
```

CPU-only execution should be schedulable independently.

This can materially reduce cost.

---

## 47. Simulation and Asset Workloads Reuse the Same Fabric

Future:

```text
CFD
FEA
Blender
ComfyUI
image generation
video generation
CUDA simulation
```

should not each create a global scheduler.

They issue generic resource/capability requests.

Executors may differ:

```text
InferenceExecutor
SandboxExecutor
BuildExecutor
SimulationExecutor
AssetExecutor
```

Resource authority remains unified.

---

## 48. Network and Sandbox Capability

Some Tasks require:

```text
no network
restricted network
public HTTPS
provider access
```

Network policy is primarily A8, but the scheduler must ensure the selected worker can enforce the required isolation.

---

## 49. Trust as Placement Constraint

A8 will define trust classes.

A6 requires placement to honor them.

Example:

```text
sensitive project code
```

may be eligible for:

```text
private Reverend worker
```

but not an untrusted external runtime.

Physical fit alone is not enough.

---

## 50. Data Locality

Placement may consider:

- workspace location;
- artifact cache;
- model weights;
- datasets.

A node that already has the required data may be preferable.

However:

> **Worker-local cache never becomes authoritative state.**

---

## 51. Compute Failure Semantics

If a worker disappears:

```text
Node UNREACHABLE
   ↓
active leases invalidated
   ↓
affected Job interrupted / failed / recoverable
   ↓
Control Plane remains authoritative
   ↓
A7 decides recovery
```

The Task is never silently marked successful because the worker vanished.

---

## 52. Partial Artifacts

A failed Job may have produced durable partial artifacts.

These can remain for:

- diagnostics;
- future recovery;
- evidence.

But they do not automatically satisfy Task completion.

---

## 53. Event-Driven Scheduling

The scheduler should react to events such as:

```text
Task becomes READY
Job completes
lease releases
node registers
node disappears
approval arrives
budget changes
checkpoint completes
```

Implementation details are deferred, but event-driven control is preferred to coarse polling-only architecture.

---

## 54. Scheduler Explainability

Important decisions should expose structured reasons.

Examples:

```text
QUEUED:
No registered node satisfies >=80GB VRAM.

PLACED:
Node gpu-3 selected because:
- model eligible
- model already resident
- trust satisfied
- sufficient VRAM
- lower expected startup latency
```

No LLM is required to explain deterministic scheduling.

---

## 55. Required Telemetry

At minimum measure:

```text
queue wait
resource acquisition wait
node provisioning delay
model loading/setup time
inference time
tool execution time
CPU allocation/time
GPU allocation/time
VRAM
RAM
tokens
retries
lease duration
node utilization
estimated cost
settled cost
```

Especially distinguish:

```text
billable node time
allocated GPU time
actual inference time
```

This reveals idle waste.

---

## 56. Queue Efficiency

Measure:

```text
time Task READY but waiting
```

If many Agents exist but spend most time queued behind one GPU, extra logical parallelism may not improve wall-clock time.

This directly informs A10 hardware scaling.

---

## 57. Scaling Signals

More hardware is justified when:

```text
many independent runnable Tasks
+
high queue/resource saturation
+
budget permits
```

A single sequential critical path does not benefit from five GPUs.

More hardware should increase useful intelligence through parallelism, not Agent count for its own sake.

---

## 58. Scale-Up vs Scale-Out

### Scale up

```text
one larger/faster GPU
```

can improve:

- stronger model eligibility;
- context;
- single-Agent latency.

### Scale out

```text
several workers
```

can improve:

- parallel research;
- independent verification;
- concurrent engineering.

A9/A10 determine which dominates Reverend's actual workload.

---

## 59. No Speculative GPU Overcommit

Do not schedule:

```text
expected 120GB VRAM
```

onto:

```text
96GB GPU
```

because it might somehow fit.

Use conservative estimates until measured profiles justify tighter admission.

---

## 60. Resource Profiles Improve From Measurement

Initial estimates may be conservative.

Over time, Reverend can record:

```text
actual VRAM
actual RAM
runtime
context
batch
GPU type
```

and update deployment/resource profiles.

This supports better scheduling without compromising initial safety.

---

## 61. Unknown Requirements Are Conservative

If resource fit is unknown:

- use conservative estimate;
- benchmark/probe;
- run isolated;
- reject if required.

Do not silently risk shared expensive hardware.

---

## 62. Admission Before Placement

Before consuming compute:

```text
dependencies satisfied
  ↓
authority/policy valid
  ↓
budget available
  ↓
execution requirements valid
  ↓
eligible model/tool exists
  ↓
placement possible
  ↓
lease
```

This avoids spending GPU time discovering basic configuration failures.

---

## 63. Scheduler Does Not Own Application Semantics

Compute scheduling does **not** decide:

```text
code correctness
architecture safety
research sufficiency
```

Those belong to Agents and verification.

Scheduler domain:

```text
capacity
placement
priority
leases
health
cost constraints
```

---

## 64. Canonical A6 Flow

```text
CONTROL PLANE
Task dependencies satisfied
        │
        ▼
WORKFLOW SCHEDULER
Task enters READY set
        │
        ▼
Agent / Job prepared
        │
        ▼
Execution requirements derived
        │
        ├── model requirements
        ├── tool requirements
        ├── context requirement
        ├── trust
        └── budget
        │
        ▼
MODEL ROUTER
eligible models/runtimes
        │
        ▼
COMPUTE SCHEDULER
feasible node placements
        │
        ├── capacity exists? ── NO ──► CAPACITY CONTROLLER
        │                               ├── wait
        │                               ├── wake
        │                               ├── provision
        │                               └── reject
        │
        ▼
ATOMIC RESOURCE LEASE
        │
        ▼
EXECUTION RUNTIME
        │
        ▼
heartbeat + telemetry
        │
        ▼
artifact / result
        │
        ▼
release resources
        │
        ▼
CONTROL PLANE
```

---

## 65. Mapping From Current Local Architecture

Current components already map naturally:

```text
ResourceBroker
→ single-node precursor to distributed resource scheduling

ModelScheduler
→ local residency/inference protection

LeasedModelScheduler
→ bridge between resource admission and model execution

measure_hardware()
→ local ComputeNode snapshot
```

A6 therefore favors evolutionary migration.

The assumption that must disappear is:

```text
resource universe = this one Linux machine
```

---

## 66. A7 Boundary

A6 owns:

```text
request resource
grant lease
heartbeat
release
expire
revoke
node loss
drain
preemption request
```

A7 owns:

```text
safe interruption boundary
checkpoint content
resume semantics
side-effect reconciliation
RECOVERY_BLOCKED
```

These milestones should not duplicate each other.

---

## 67. A11 Boundary

A6 produces:

```text
resource identity
lease duration
usage
node
runtime
estimated cost inputs
actual metered usage
owner lineage
```

A11 defines:

- pricing;
- shared overhead;
- user billing;
- budget policies;
- settlement.

---

## 68. A9 Boundary

A9 provides:

```text
model capability requirements
candidate models
context needs
VRAM profiles
latency
batching support
expected usage
```

A6 uses those to schedule.

---

## 69. A10 Boundary

A10 instantiates:

```text
ComputeProvider
InferenceRuntime
ComputeNode types
cloud topology
storage topology
elastic lifecycle
```

using the A6 abstractions.

A10 should be a selection exercise, not a redesign of scheduling.

---

## 70. Required Benchmark Scenarios

### Scenario A — One GPU, multiple logical Agents

```text
3 GPU Agent Jobs READY
2 CPU Tasks READY
```

Expected:

- GPU requests follow validated serialization/batching;
- CPU work proceeds concurrently.

### Scenario B — New Worker Appears

Second GPU node registers.

Expected:

- waiting eligible Jobs may schedule to it safely.

### Scenario C — Worker Disappears

Expected:

- node unavailable;
- lease invalidated;
- Job not marked successful;
- A7 recovery triggered.

### Scenario D — Budget Exhausted

Expected:

- no paid node provisioned.

### Scenario E — High-Priority Job Cannot Fit

Expected:

- safe lower-priority backfill where allowed;
- no starvation.

### Scenario F — Same-Model Batching

Expected:

- compatible requests may share runtime only when batching is explicitly supported.

### Scenario G — Mutation Conflict

Expected:

- execution policy prevents unsafe concurrent repository mutation even if compute is available.

---

## 71. Benchmark Hypotheses

These remain hypotheses:

### H1
Persistent cheap Control Plane + elastic GPU workers gives best two-user cost/reliability.

### H2
Keeping one small common model resident may beat repeated cold loading.

### H3
Same-model batching makes multi-Agent execution materially cheaper.

### H4
One large GPU may beat several small GPUs on £/verified Task.

### H5
Several smaller GPUs may beat one large GPU for highly parallel B4/B5 workflows.

### H6
CPU/tool overlap materially reduces wall-clock time even if GPU inference remains serialized.

### H7
Critical-path-aware scheduling improves project completion time.

These require A9/A10/A11 evidence.

---

## 72. Frozen A6 Requirements

```text
A6-01
Workflow scheduling and physical compute scheduling are distinct.

A6-02
Control Plane remains authoritative for Workflow/Task/Job state.

A6-03
Workflow Scheduler produces logically runnable work.

A6-04
Logical readiness does not imply physical concurrency.

A6-05
ComputeNode is the canonical physical capacity abstraction.

A6-06
ComputeNodes are capability-described, not SKU-hard-coded.

A6-07
ComputeNode Registry tracks capacity, health, runtime, residency, and leases.

A6-08
ResourceRequest / ResourceLease remain canonical resource semantics.

A6-09
Resource bundles are atomically allocated.

A6-10
Leases are Job-owned and non-transferable.

A6-11
Leases are time-bounded, heartbeat-driven, revocable, and idempotently releasable.

A6-12
Agents do not hold scarce resources when not actively needed.

A6-13
One Job may acquire several leases across execution phases.

A6-14
Agents/models remain independent of physical node identity.

A6-15
Model routing produces eligible candidates.

A6-16
Compute placement considers model/runtime/node combinations.

A6-17
Capability/trust eligibility precedes cost/latency optimization.

A6-18
ComputeProvider and InferenceRuntime are separate abstractions.

A6-19
Capacity management is distinct from placement.

A6-20
Paid capacity requires budget admission before provisioning.

A6-21
Expensive compute stores no unique durable project/run state.

A6-22
Unrelated CPU/network/GPU workloads may execute concurrently.

A6-23
GPU sharing/batching occurs only where runtime semantics are validated.

A6-24
Model residency may influence but not override eligibility.

A6-25
Scheduling supports priority, aging/fairness, and safe backfilling.

A6-26
Top-level Run concurrency is policy, not hard-coded resource architecture.

A6-27
Budgets are hierarchically attributable.

A6-28
Resource use remains traceable to User/Project/Run/Team/Task/Agent/Job.

A6-29
Preemptibility is explicit.

A6-30
Revocation and node loss emit explicit Control Plane events.

A6-31
Heartbeats reclaim dead capacity.

A6-32
Nodes can drain before shutdown/replacement.

A6-33
Capacity lifecycle respects shutdown/recovery inhibitors.

A6-34
CPU-only execution is first-class.

A6-35
Inference/simulation/asset workloads reuse generic resource architecture.

A6-36
Trust/network/sandbox requirements participate in placement.

A6-37
Data locality may optimize placement, but caches remain non-authoritative.

A6-38
The authoritative backlog remains visible to Reverend.

A6-39
Scheduling decisions and resource use are observable/benchmarkable.

A6-40
Scaling is justified by runnable demand, utilization, latency, and cost—not Agent count.
```

---

## 73. Current-Code Migration Classification

| Current construct | Direction |
|---|---|
| RuntimeResourceRequest | CANONICAL SEMANTICS — EXTEND |
| RuntimeResourceLease | CANONICAL SEMANTICS — EXTEND |
| atomic allocation | KEEP |
| Job ownership | KEEP |
| heartbeat | KEEP |
| expiry | KEEP |
| revocation | KEEP |
| idempotent release | KEEP |
| priority aging | KEEP / GENERALIZE |
| fit-aware backfill | KEEP / GENERALIZE |
| explicit GPU exclusivity | KEEP |
| guarded same-model sharing | KEEP PRINCIPLE |
| ResourceBroker | EVOLVE INTO DISTRIBUTED/NODE SCHEDULER |
| HardwareSnapshot | GENERALIZE INTO ComputeNode TELEMETRY |
| local `nvidia-smi` | KEEP AS LOCAL NODE ADAPTER |
| local file-lock scheduler | KEEP ONLY AS LOCAL SAFETY |
| LeasedModelScheduler | KEEP SEMANTIC BRIDGE; GENERALIZE |
| single GPU assumption | REPLACE |
| local-only resource universe | REPLACE |
| ModelSpec resource estimates | KEEP + POPULATE FROM BENCHMARKS |
| ComputeNode Registry | NEW |
| Capacity Controller | NEW |
| ComputeProvider abstraction | NEW |
| cost admission seam | NEW; A11 SUPPLIES POLICY |

---

## 74. Design-Phase Implications

The Design Phase must define:

- `ComputeNode`;
- node registry and authentication seam;
- distributed `ResourceRequest` / `ResourceLease`;
- Workflow Scheduler interface;
- Compute Scheduler interface;
- Capacity Controller interface;
- placement decision records;
- node/lease heartbeat behavior;
- drain/revoke semantics;
- resource telemetry;
- budget-admission callback;
- model placement/residency information;
- executor interface;
- local compatibility adapters.

The Design Phase should extend current resource semantics rather than creating an unrelated cloud scheduler.

---

## 75. A6 Decision Record

```text
MILESTONE:
A6 — Scheduling, Compute & Resource Architecture

STATUS:
ACCEPTED

CONTROL FLOW:
Control Plane
→ Workflow Scheduler
→ READY Job
→ Model eligibility
→ Compute Scheduler
→ ResourceLease
→ Executor
→ Release
→ Control Plane

SCHEDULING LAYERS:
Workflow Scheduler  — what may run
Compute Scheduler   — where it may run
Capacity Controller — whether more machines should exist
Execution Runtime   — how the workload executes

PHYSICAL ABSTRACTION:
ComputeNode

RESOURCE CONTRACT:
Atomic Job-owned ResourceRequest / ResourceLease

PARALLELISM:
Maximize useful independent work, not raw Agent count.

GPU:
Sharing/batching only where explicitly validated.

MODEL:
Capability first; cost/latency/residency optimization second.

CLOUD:
Expensive workers disposable; durable Run state lives elsewhere.

ACCOUNTING:
Job → Agent → Task → Team → Run → Project → User

FAILURE:
Node/lease loss never implies success.
Recovery passes to A7.

REJECTED:
- one mega-scheduler owning cognition + cloud + resources
- Agent-owned GPUs
- permanent model-to-machine binding
- hidden unlimited runtime queues
- speculative GPU overcommit
- holding GPUs while Agents perform unrelated CPU/tool work
```
