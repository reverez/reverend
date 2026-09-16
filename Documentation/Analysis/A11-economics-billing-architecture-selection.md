# A11 — Economics, Billing & Cloud v1 Architecture Selection

> **Programme:** Reverend Cloud Analysis  
> **Milestone:** A11  
> **Status:** ACCEPTED  
> **Owner:** akurkar07  
> **Research / price snapshot:** 2026-09-16  
> **Depends on:** A2, A6, A7, A8, A9, A10  
> **Currency:** GBP (£), with native provider rates retained in every immutable RateSnapshot  
> **Document purpose:** Reconcile the accepted A6/A9/A10 architecture with the two-user billing model, refresh provider pricing, select the initial Cloud v1 deployment profile, and freeze the economic/accounting rules required for implementation.

---

## 1. Executive Decision

A11 accepts the A10 topology and supersedes the earlier A11 framework assumption that the entire Reverend stack should live on one metered GPU VPS.

The accepted Cloud v1 topology is:

    Developer A client              Developer B client
            │                               │
            └──────── authenticated HTTPS/SSE ────────┐
                                                      ▼
                                      PERSISTENT CPU CONTROL PLANE
                                      Hetzner Cloud CX33 baseline
                                      ├── auth / API / SSE
                                      ├── Project / Run authority
                                      ├── Control Plane
                                      ├── Executive Orchestrator
                                      ├── Agent / Team runtime
                                      ├── Context / Memory coordination
                                      ├── Workflow Scheduler
                                      ├── Compute Scheduler
                                      ├── Capacity Controller
                                      ├── Policy / approvals / secrets
                                      ├── cost ledger
                                      └── authoritative durable state
                                                      │
                                                      │ provider API
                                                      ▼
                                      DISPOSABLE GPU COMPUTE
                                      RunPod Community Cloud Pod
                                      A100 SXM 80 GB baseline
                                      ├── vLLM
                                      ├── Qwen3.8-27B baseline profile
                                      ├── temporary workspace/cache
                                      └── bounded execution services

Core decisions:

1. the Control Plane stays online even when no GPU exists;
2. GPU workers scale to zero when no GPU work is runnable;
3. users never need provider credentials in ordinary clients;
4. the Capacity Controller provisions/stops GPU workers;
5. the initial production-quality baseline is **RunPod Community Cloud + A100 SXM 80 GB + vLLM + Qwen3.8-27B**;
6. the initial serving context target is **64K**, with 128K enabled only after workload evidence shows value;
7. 48 GB workers remain an explicit cost-down path, not the initial quality baseline;
8. user cost attribution follows durable Run/resource lineage;
9. fixed persistent infrastructure remains shared 50/50 for the initial two-user installation;
10. the economic comparison metric remains **£ per verified successful engineering task**.

This selection is deliberately provider- and model-replaceable at the architecture layer. It is the initial implementation profile, not a permanent hard-coded identity.

---

## 2. Inputs Reconciled

A11 consumes the following accepted decisions.

### A2

    two authenticated users
    immutable Run owner
    one active top-level Run in Cloud v1
    server-authoritative queue/state

### A6

    Workflow Scheduler != Compute Scheduler
    ResourceRequest / ResourceLease are canonical
    expensive resources are acquired only while needed
    resource use is attributable through User → Project → Run → ... → Job

### A7

    compute is replaceable
    Run state is durable
    pause / approval wait releases compute
    recovery reacquires fresh leases

### A8

    provider credentials are host/infrastructure authority
    models and untrusted workers never receive provider secrets
    Run owner determines user-scoped external authority

### A9

Highest-priority practical workhorse:

    Qwen3.8-27B

with smaller/economical candidates including North Mini Code and Nemotron 3.5 Lightning, and larger frontier models treated as escalation/benchmark controls rather than default infrastructure.

### A10

Accepted infrastructure direction:

    persistent inexpensive Control Plane
    +
    authenticated disposable GPU workers
    +
    RunPod initial ComputeProvider candidate
    +
    vLLM initial cloud inference runtime
    +
    48 GB and 80–96 GB main hardware tiers

A11 therefore does **not** preserve the previous framework's full-stack GPU-VPS topology.

---

## 3. Why the Previous Full-Stack GPU VPS Is Rejected

The earlier A11 framework selected API + DB + scheduler + models + GPU on one metered GPU VPS.

A10 subsequently completed the hardware/topology analysis and rejected that as the long-term Cloud v1 design.

A11 accepts the later evidence because it resolves three problems:

- **reachability:** login, queue, approvals and recovery remain available at zero GPUs;
- **failure domain:** a GPU-worker crash does not remove the authoritative database/API;
- **scaling:** changing model/GPU profiles does not redesign the control server.

---

## 4. Persistent Control Plane Selection

### Baseline host

Initial Cloud v1 control-plane baseline:

    Provider: Hetzner Cloud
    Region: EU, preferably Germany/Finland close to the chosen GPU region
    Plan: CX33
    Architecture: x86
    vCPU: 4
    RAM: 8 GB
    Local NVMe: 80 GB
    GPU: none

Why CX33:

- matches A10's 2–4 vCPU / 4–8 GB initial envelope at the safer end;
- x86 avoids introducing Arm compatibility work during the migration;
- 8 GB gives room for API, orchestration, PostgreSQL, event processing and bounded caches;
- 80 GB is materially safer than a 40 GB minimum for DB/WAL/logs/checkpoint metadata and repository metadata;
- it remains inexpensive enough to stay online continuously.

### Current price snapshot

Hetzner's 15 June 2026 EU price adjustment lists:

    CX33
    €0.0136 / hour
    €8.49 / month maximum
    excluding VAT and optional IPv4

At the Bank of England 14 Sep 2026 spot rate:

    £1 = €1.1680

the monthly price is approximately **£7.27/month** before VAT / optional address charges.

This GBP value is an analysis snapshot only. The billing ledger retains the native provider amount and the actual FX RateSnapshot used for settlement.

---

## 5. Authoritative Database Selection

A0 and A10 deliberately left SQLite vs PostgreSQL open.

A11/A12 final reconciliation selects:

> **PostgreSQL for Reverend Cloud authoritative state.**

SQLite remains valid for local compatibility/development mode.

Reasons:

- the cloud system has independent API, scheduler and worker-facing services;
- durable Run/Task/Job/event/action/cost records are written by more than one execution path;
- pause/recovery and provider lifecycle create transactional coordination requirements;
- PostgreSQL gives a cleaner basis for durable queues, leases, idempotency and backup/restore;
- choosing it now avoids treating a single-process SQLite write pattern as a hidden Cloud v1 invariant.

This does **not** require Redis. Redis remains optional until implementation evidence identifies a concrete ephemeral coordination/pub-sub/cache need.

---

## 6. GPU Compute Provider Selection

Initial production provider:

    RunPod Community Cloud Pods

The baseline deliberately accepts Community Cloud's lower infrastructure-assurance / higher variability profile in exchange for lower cost.

RunPod currently distinguishes Community Cloud from Secure Cloud as follows:

- Community Cloud uses shared-host / peer-supplied capacity with software/container isolation;
- Secure Cloud provides stronger dedicated/single-tenant infrastructure assurance and is the provider-recommended class for highly sensitive workloads.

A8 therefore treats the selected Community worker as a lower-assurance disposable execution class rather than trusted infrastructure authority.

This choice is acceptable for the normal two-user Reverend workload because:

- the persistent Control Plane remains separate and authoritative;
- Community workers receive only task-scoped repository/context material;
- GitHub/provider/control-plane/master-key credentials are never placed on the worker;
- worker credentials are short-lived and narrowly scoped;
- worker loss is already handled by A7/A10 recovery semantics;
- Jobs with stronger trust requirements are not eligible for Community placement.

Highly sensitive, regulated or otherwise policy-restricted Projects may require Secure Cloud or another stronger dedicated deployment class.

Provider lifecycle credentials belong only to the Capacity Controller / ComputeProvider adapter, never the browser client, Agent, model prompt or Community worker.

---

## 7. Baseline GPU Selection

Selected baseline:

    GPU: NVIDIA A100 SXM
    VRAM: 80 GB
    Provider: RunPod Community Cloud
    Current rate: $1.39 / hour

A100 SXM 80 GB is the canonical initial GPU target. The choice keeps the 80 GB quality/reference memory tier selected by A10 while reducing the hourly rate relative to the previously selected Secure A100 profile.

### Why A100 80 GB

A10 classifies 80–96 GB as the safer quality/reference tier for Qwen3.8-27B native/reference-style deployment.

This avoids making Cloud v1 depend immediately on:

- aggressive 4-bit quantisation;
- a 48 GB fit assumption;
- unmeasured model-quality loss.

At the Bank of England 14 Sep 2026 rate of £1 = $1.3476, $1.39/h is approximately **£1.03/GPU-hour**.

---

## 8. Primary Model / Runtime Selection

Initial Cloud v1 workhorse deployment profile:

    Model: Qwen/Qwen3.8-27B
    Runtime: vLLM
    GPU: A100 SXM 80 GB
    Serving context: 64K initial
    Modalities: text + image where required
    Trust: COMMUNITY_CLOUD_WORKER (lower-assurance shared-host execution class)
    Reasoning effort: selected per Job / ModelRequirement

Why Qwen3.8-27B:

- A9 marks it the highest-priority practical workhorse candidate;
- it is a practical 27B-class model rather than a frontier-scale MoE;
- its official repository supports vLLM and multimodal inference;
- it can plausibly cover FAST_ENGINEERING, PRIMARY_ENGINEERING, vision, repository understanding and moderate/deep reasoning through one physical workhorse;
- model consolidation reduces loading/cache complexity.

### Context policy

A5 already requires selective retrieval/context compilation.

Initial serving profile:

    64K default maximum
    128K only for measured workflows that benefit
    >128K requires explicit deployment-profile evidence

This keeps KV-cache cost visible and avoids using giant prompts as a substitute for context architecture.

---

## 9. Secondary / Cost-Down Profile

First explicit optimisation target:

    GPU: RTX A6000 48 GB Community Cloud
    Current rate: $0.33 / hour
    Approx analysis-time GBP: £0.24 / hour

Candidate model profiles:

- quantised Qwen3.8-27B;
- North Mini Code;
- Nemotron 3.5 Lightning.

This profile is **not** automatically promoted to production. It becomes eligible only if ReverendBench shows better £/verified successful engineering task without violating mandatory quality, verification or human-intervention thresholds.

---

## 10. Premium / Headroom Profile

Optional premium profile:

    GPU: RTX Pro 6000 96 GB Community Cloud
    Current rate: $1.69 / hour
    Approx analysis-time GBP: £1.25 / hour

Use only when measurements show value from larger context/KV headroom, Blackwell FP4/FP8 support, higher throughput, multimodal/asset flexibility or fewer model transitions.

It is not the default because the A100 baseline already gives sufficient memory for the initial workhorse at lower hourly cost.

---

## 11. Frontier Escalation Policy

Cloud v1 does not permanently host GLM-5.3, Kimi K3, DeepSeek V4 Pro, DeepSeek V4 Flash's published FP8 profile or very large Qwen variants as baseline infrastructure.

They remain:

- benchmark controls;
- temporary specialist experiments;
- future multi-GPU profiles;
- optional policy-permitted external escalation for non-sensitive context.

A8 trust policy must authorise any external-provider data release.

---

## 12. Minimum Initial Physical Model Fleet

A11 does not require one permanent model per Specialist.

Initial physical fleet:

    required:
    Qwen3.8-27B workhorse

    optional as benchmark evidence justifies:
    small CONTROL model
    Qwen3 embedding model
    Qwen3 reranker
    asset-generation model
    cross-family verifier/escalation model

Logical Agent role and physical model identity remain separate.

Before any optional model becomes production-resident, it must satisfy the A9 ReverendBench admission process.

---

## 13. GPU Worker Lifecycle

    Job becomes READY
    ↓
    scheduler derives ModelRequirement + ResourceRequest
    ↓
    no eligible worker
    ↓
    Capacity Controller checks policy + budget
    ↓
    RunPod provider adapter provisions/starts Pod
    ↓
    authenticated worker registers
    ↓
    vLLM/model becomes healthy
    ↓
    ResourceLease acquired
    ↓
    Job executes
    ↓
    lease released
    ↓
    idle grace
    ↓
    worker drains/stops when no runnable GPU work remains

Initial idle grace target remains **5–10 minutes**, as configurable policy rather than a fixed constant.

The persistent Control Plane remains online after GPU scale-to-zero.

---

## 14. Approval Wait and Pause Economics

A7 now freezes:

    AWAITING_APPROVAL = durable non-compute state
    PAUSED = no active compute lease

Therefore:

| Run state | Active GPU cost to Run owner |
|---|---:|
| RUNNING with GPU lease | yes |
| RESUMING before GPU lease | no |
| PAUSED | £0 |
| AWAITING_APPROVAL | £0 |
| RESUME_QUEUED | £0 |
| RECOVERY_BLOCKED | £0 unless explicit recovery compute is admitted |

A pending approval does not keep a GPU worker alive by itself.

---

## 15. Cost Categories

### User-attributable variable cost

100% to Run owner:

- GPU lease usage during the Run;
- paid external model/API calls for that Run;
- explicitly Run-specific paid storage/egress;
- separately provisioned CPU execution capacity used only by that Run.

### Shared fixed cost

Initially split 50/50:

- persistent Control Plane host;
- baseline authoritative-state storage;
- shared backups;
- domain/DNS where paid;
- shared monitoring;
- shared model-cache storage if retained across users.

### Shared transient GPU overhead

Initially split 50/50:

- provider boot time before a lease is attributable;
- model load/warm-up before first admitted Run GPU lease;
- idle grace after the last GPU lease;
- controlled drain/shutdown overhead;
- provider-side reconciliation gaps not attributable to one Run.

This preserves the previously agreed simple two-user policy.

---

## 16. Accounting Objects

### PowerSession

    PowerSession
    ├── power_session_id
    ├── provider
    ├── node_id
    ├── gpu_profile
    ├── requested_start_at
    ├── provider_running_at
    ├── stop_requested_at
    ├── provider_stopped_at
    ├── billing_start_at
    ├── billing_end_at
    ├── native_currency
    ├── native_rate
    ├── rate_snapshot_id
    ├── estimated_cost_gbp
    ├── actual_cost_gbp
    └── reconciliation_state

### ComputeLeaseUsage

    ComputeLeaseUsage
    ├── lease_id
    ├── run_id
    ├── user_id
    ├── project_id
    ├── job_id
    ├── node_id
    ├── resource profile
    ├── acquired_at
    ├── released_at
    ├── duration_seconds
    ├── rate_snapshot_id
    └── estimated_cost_gbp

### CostEvent

    CostEvent
    ├── cost_event_id
    ├── occurred_at
    ├── category
    ├── user_id?
    ├── project_id?
    ├── run_id?
    ├── job_id?
    ├── node_id?
    ├── quantity
    ├── unit
    ├── native_unit_price
    ├── native_currency
    ├── rate_snapshot_id
    ├── estimated_cost_gbp
    ├── actual_cost_gbp?
    ├── source
    └── metadata

Totals are derived from immutable events rather than mutable counters.

---

## 17. RateSnapshot

    RateSnapshot
    ├── provider
    ├── product / instance type
    ├── provider tier
    ├── native_rate
    ├── native_currency
    ├── billing increment
    ├── minimum duration
    ├── fx_source
    ├── fx_rate_to_gbp
    ├── effective_at
    └── captured_at

Historical bills must not change when provider prices or FX rates later move.

Live UI numbers are labelled **estimated** until provider reconciliation completes.

---

## 18. Provider Billing Granularity

Do not infer billing rules from marketing phrases such as "per hour".

Current RunPod material states granular/per-second Pod billing.

Hetzner Cloud uses hourly billing capped at the listed monthly maximum for the selected persistent host.

The accounting layer therefore supports different charging rules per resource.

---

## 19. Current Price Comparison

| Profile | Native provider rate | Approx GBP at 14 Sep FX | A11 role |
|---|---:|---:|---|
| Hetzner CX33 Control Plane | €8.49/month max | ~£7.27/month | selected persistent control plane |
| RunPod RTX A6000 48 GB Community | $0.33/h | ~£0.24/h | cost-down candidate |
| RunPod A100 SXM 80 GB Community | $1.39/h | ~£1.03/h | **selected baseline GPU** |
| RunPod RTX Pro 6000 96 GB Community | $1.69/h | ~£1.25/h | premium/headroom candidate |
| RunPod A100 SXM 80 GB Secure | $1.59/h | ~£1.18/h | stronger-infrastructure fallback |

FX snapshot:

    Bank of England, 14 Sep 2026
    £1 = $1.3476
    £1 = €1.1680

Prices exclude taxes and provider-specific optional charges.

---

## 20. Illustrative Monthly Cost

Using the selected A100 SXM Community baseline and the analysis FX snapshot:

| Monthly GPU worker billed time | Approx GPU cost | + control-plane baseline | Approx total before VAT/storage |
|---:|---:|---:|---:|
| 10 h | £10.31 | £7.27 | £17.58 |
| 20 h | £20.63 | £7.27 | £27.90 |
| 40 h | £41.26 | £7.27 | £48.53 |
| 80 h | £82.52 | £7.27 | £89.79 |

This excludes optional storage, IP/domain charges, external APIs and tax.

---

## 21. Per-User Attribution

Canonical rule:

> **A user pays the variable resources consumed by Runs they own; fixed shared infrastructure and unattributable shared overhead are split by explicit policy.**

Example:

    Alex Run A: 30 min GPU
    Friend Run B: 20 min GPU
    Alex Run A resumes: 15 min GPU

Variable attribution:

    Alex = 45 min
    Friend = 20 min

Paused/approval-wait time does not accrue active GPU cost.

---

## 22. CPU Execution Economics

A6/A10 treat CPU execution as first-class.

Cloud v1 may initially place small bounded CPU execution services on the persistent host only when isolation/resource limits prove they cannot jeopardise the Control Plane.

Heavy or untrusted CPU work should use a separate schedulable execution worker.

Economic rule:

- shared Control Plane CPU baseline is fixed overhead;
- separately provisioned CPU workers are charged to the Run owner;
- the scheduler must never keep a GPU alive merely because the Run is performing unrelated CPU-only work.

The exact external CPU-worker SKU belongs to Design measurement because A10 did not identify a mandatory one.

---

## 23. Storage Economics

Authoritative state remains independent of GPU workers.

Persistent / authoritative:

- PostgreSQL data;
- required durable Git/project state;
- checkpoint manifests/objects;
- Action Journal;
- required durable artifacts;
- encrypted secret-store material;
- cost ledger.

Reconstructible:

- model weights;
- vLLM cache;
- worker container layers;
- CUDA/runtime cache;
- temporary build output.

RunPod network storage may be used for reconstructible model cache where it measurably improves cold-start economics, but it is not the sole copy of Reverend authority.

---

## 24. Budget Hierarchy

    User monthly budget
       ↓
    Run budget
       ↓
    Team budget
       ↓
    Task budget
       ↓
    Agent budget
       ↓
    Job / model / tool budget

Cloud v1 minimum controls:

- max_run_cost_gbp;
- max_run_runtime;
- monthly_user_soft_limit_gbp;
- monthly_user_hard_limit_gbp.

A hard limit prevents the next charge-bearing action at a safe boundary. It does not interrupt a non-interruptible external side effect halfway through.

---

## 25. Cost Dashboard

Per Run:

- active GPU lease time;
- CPU-worker time;
- estimated provider cost;
- paid API cost;
- shared-overhead allocation;
- estimated total;
- reconciled actual.

Per user/month:

- variable Run compute;
- paid APIs;
- allocated shared fixed cost;
- allocated transient overhead;
- estimated total;
- actual reconciled total.

---

## 26. Economic Benchmark

Deployment profiles eventually record:

- task success;
- verification success;
- repair rounds;
- human intervention;
- wall-clock time;
- GPU lease time;
- provider billed time;
- cold-start time;
- idle/drain overhead;
- estimated/actual cost.

Primary metric:

> **£ per verified successful engineering task**

Secondary metrics include median/P95 latency, human interventions per Task, repair loops, GPU utilisation and cold-start overhead.

---

## 27. Model/GPU Promotion Rule

A cheaper profile may replace the baseline only when measured evidence shows:

1. mandatory ReverendBench quality gates pass;
2. verification success does not regress beyond the accepted threshold;
3. human intervention remains within A1 targets;
4. repository/context workloads fit reliably;
5. trust/licensing requirements pass;
6. £/verified successful task improves materially.

A more expensive profile may replace it only if improved success/latency lowers total verified-task cost or unlocks mandatory capability.

---

## 28. Why the 48 GB Worker Is Not the Initial Baseline

The raw rate difference is large:

    RTX A6000 Community: $0.33/h
    A100 SXM 80 GB Community: $1.39/h

However, A9/A10 do not contain ReverendBench evidence proving that the required Qwen3.8-27B quantised profile preserves long-horizon engineering quality.

A11 therefore starts from the safer native/reference-fit 80 GB tier and targets 48 GB as the first cost optimisation once measured evidence exists.

---

## 29. Why Community Cloud Is the Baseline

The two-user Reverend deployment deliberately prioritises lower GPU cost while preserving a strict separation between durable authority and disposable execution.

Community Cloud is accepted as the normal GPU tier because Reverend's architecture already limits what a worker can own or see:

- no long-lived GitHub credentials;
- no provider lifecycle credentials;
- no Control Plane database credentials;
- no secret-store master keys;
- no unrelated Project data;
- only task-scoped workspace/context and short-lived worker authority.

This does **not** make Community Cloud equivalent to dedicated infrastructure. Shared-host operation introduces greater infrastructure-assurance, noisy-neighbour and potential side-channel risk than Secure Cloud.

Therefore deployment policy must allow a stronger trust class for highly sensitive, regulated or explicitly restricted workloads. In those cases a Secure Cloud A100 SXM or another dedicated/single-tenant profile is the fallback rather than silently weakening the Job's trust requirement.

---

## 30. No Client-Driven Provider Credentials

The earlier full-stack design considered clients directly waking a stopped VPS.

That is no longer the accepted flow.

    client submits/resumes work
    ↓
    persistent Reverend Control Plane
    ↓
    scheduler determines GPU need
    ↓
    Capacity Controller
    ↓
    RunPod provider adapter
    ↓
    GPU worker

Clients remain thin and do not hold RunPod lifecycle credentials.

---

## 31. Recovery Economics

Routine GPU-worker loss is an execution failure, not a Control Plane outage.

    lease invalidated
    ↓
    A7 reconstructs/reconciles Job state
    ↓
    Capacity Controller replaces worker if budget permits

Client recovery replicas remain useful for disaster recovery of the persistent authority, but they are no longer required to make ordinary GPU scale-to-zero safe.

A12 records this interpretation explicitly so A7's earlier "VPS shutdown" wording is not confused with routine disposable-worker deallocation.

---

## 32. Accepted Cloud v1 Configuration

### Persistent authority

    Provider: Hetzner Cloud
    Baseline: CX33
    4 vCPU / 8 GB RAM / 80 GB NVMe
    EU region
    Database: PostgreSQL
    Role: always-on Control Plane + authoritative durable state

### GPU worker

    Provider: RunPod Community Cloud Pods
    Baseline GPU: A100 SXM 80 GB
    Runtime: vLLM
    Primary workhorse: Qwen/Qwen3.8-27B
    Initial serving context: 64K
    Lifecycle: provision on demand, drain/stop after idle grace
    Durable authority: none unique to worker

### First cost-down target

    RunPod Community RTX A6000 48 GB
    + validated lower-memory workhorse profile

### Premium target

    RunPod Community RTX Pro 6000 96 GB

only when workload evidence justifies the premium.

---

## 33. Source Register

Current sources used in the A11 finalisation:

- RunPod GPU pricing, updated 13 Sep 2026  
  https://www.runpod.io/pricing
- RunPod GPU model catalogue  
  https://www.runpod.io/gpu-models
- RunPod sensitive-data / Secure-vs-Community guidance  
  https://www.runpod.io/articles/guides/keep-data-secure-cloud-gpus
- Hetzner 15 Jun 2026 Cloud price adjustment  
  https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/
- Hetzner cost-optimised instance specifications  
  https://www.hetzner.com/cloud/cost-optimized/
- Bank of England spot exchange rates  
  https://www.bankofengland.co.uk/boeapps/database/Rates.asp?into=GBP
- Official Qwen3.8-27B repository/runtime guidance  
  https://huggingface.co/Qwen/Qwen3.8-27B

Provider prices, availability and FX are dated snapshots and must be refreshed during deployment/reconciliation.

---

## 34. Acceptance Gates

A11 is complete because the architecture now defines:

1. persistent vs disposable infrastructure;
2. exact initial Control Plane host/provider;
3. exact initial GPU provider/tier;
4. exact initial GPU profile;
5. exact initial workhorse model/runtime/context profile;
6. first cost-down and premium alternatives;
7. per-user variable-cost attribution;
8. shared fixed/transient-overhead policy;
9. pause/approval-wait cost semantics;
10. provider-native RateSnapshot and GBP settlement;
11. immutable cost accounting;
12. budget admission;
13. GPU scale-to-zero behaviour;
14. economic promotion/replacement criteria;
15. £/verified successful engineering task as the governing optimisation metric.

---

## 35. A11 Decision Record

    MILESTONE:
    A11 — Economics, Billing & Architecture Selection

    STATUS:
    ACCEPTED

    CONTROL PLANE:
    Hetzner CX33 baseline
    persistent / CPU-only
    PostgreSQL authoritative state

    GPU PROVIDER:
    RunPod Community Cloud Pods

    BASELINE GPU:
    A100 SXM 80 GB

    PRIMARY RUNTIME:
    vLLM

    PRIMARY WORKHORSE:
    Qwen3.8-27B

    INITIAL SERVING CONTEXT:
    64K

    TOP-LEVEL CONCURRENCY:
    one active Run in Cloud v1

    GPU LIFECYCLE:
    on demand
    scale to zero
    persistent Control Plane remains online

    VARIABLE COST:
    Run owner

    FIXED SHARED COST:
    50/50 initial policy

    PAUSED / AWAITING_APPROVAL:
    £0 active compute

    PRIMARY ECONOMIC METRIC:
    £ per verified successful engineering task

    FIRST COST-DOWN TARGET:
    Community RTX A6000 48 GB + validated lower-memory workhorse profile

    PREMIUM TARGET:
    Community RTX Pro 6000 96 GB only when measured economics justify it

    REJECTED:
    - full-stack expensive GPU VPS as the Cloud v1 authority
    - client-held provider lifecycle credentials
    - always-on GPU
    - permanent frontier GPU/model baseline
    - treating Community Cloud as equivalent to dedicated infrastructure
    - static 50/50 GPU partition
    - unverified quantisation as initial production assumption
    - Kubernetes as a v1 dependency

---

## Frozen A11 Invariant

> Reverend's durable authority stays on inexpensive persistent infrastructure; expensive compute is disposable, attributable and present only when admitted work justifies it. Every material charge is explainable through immutable provider/resource events and explicit shared-cost policy, and deployment profiles are promoted by verified engineering value per pound rather than by GPU prestige or headline benchmark score.


---

## Post-Analysis Refinement — Ephemeral Storage Economics

> **Refinement status:** Accepted by Design D18/D19/D21.

The A100 baseline remains the quality/reference starting profile.

The economic model is refined so provider-local persistent storage is never assumed to be free or required.

### Default lifecycle economics

~~~text
no GPU work
→ GPU worker ABSENT
→ GPU compute charge = 0

GPU work arrives
→ provision ephemeral worker
→ reconstruct runtime/model
→ execute

work ends
→ idle grace
→ durability gate
→ terminate by default
~~~

A stopped/warm worker or retained volume may still cost money; those charges are separately visible.

### Storage classes

~~~text
Control Plane durable storage
  shared fixed cost

BlobStore / backups
  durable cost

ephemeral worker disk
  PowerSession/provider lifecycle cost

optional warm volume/model cache
  storage optimization cost

model download/egress
  recorded when provider bills it
~~~

### Cache promotion criterion

Persistent cache is adopted only when measured:

~~~text
saved startup + download + billable runtime value
>
persistent storage + operational complexity
~~~

ReverendBench D21 evaluates this from real cold-start/cache-hit data.

### PowerSession refinement

PowerSession should span:

~~~text
provision request
→ provider billing start
→ boot
→ runtime/model load
→ attributable leases
→ idle grace
→ drain
→ provider billing end
~~~

This allows startup/load/idle overhead to be distinguished from useful lease time.

### Baseline storage target

The first RunPod A100 profile may start with approximately:

~~~text
200 GB temporary container disk
optional 10 GB warm cache volume
~~~

but these are configurable deployment values and do not affect correctness.
