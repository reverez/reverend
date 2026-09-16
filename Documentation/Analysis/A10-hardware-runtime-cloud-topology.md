# A10 — Hardware, Runtime & Cloud Topology

> **Programme:** Reverend Cloud Analysis  
> **Milestone:** A10  
> **Status:** ACCEPTED  
> **Owner:** Backend / systems track  
> **Research snapshot:** 2026-09-16  
> **Document purpose:** Translate A6 scheduling semantics and A9 model requirements into a provider-independent cloud topology, identify practical runtime/hardware tiers, and define the v1 infrastructure direction without binding Reverend permanently to one provider or GPU.  
> **Freshness warning:** Cloud GPU inventory, pricing, runtime compatibility, quantization support, and provider products change quickly. A10 freezes topology and selection principles. A11 must refresh live costs before final architecture acceptance.

---

## 1. Executive Decision

The accepted Cloud v1 topology is:

> **Persistent inexpensive Control Plane + authenticated disposable execution compute.**

In particular:

- neither user's laptop is required for LLM inference;
- the authoritative Control Plane does not live on an expensive GPU worker;
- GPU workers are replaceable and may scale to zero;
- raw inference runtimes are private;
- durable Run state survives worker/container/model loss.

Target architecture:

```text
                         USER A          USER B
                           │               │
                           └──── HTTPS/WSS ┘
                                  │
                                  ▼
                    ┌────────────────────────────┐
                    │ PERSISTENT CONTROL PLANE   │
                    │                            │
                    │ authentication             │
                    │ projects / runs            │
                    │ authoritative state        │
                    │ Executive Orchestrator     │
                    │ Agent / Team runtime       │
                    │ Context / Memory           │
                    │ Workflow Scheduler         │
                    │ Compute Scheduler          │
                    │ Capacity Controller        │
                    │ Budget admission seam      │
                    │ Events / Observability     │
                    └──────────────┬─────────────┘
                                   │
                         authenticated fabric
                                   │
              ┌────────────────────┼─────────────────────┐
              ▼                    ▼                     ▼
        CPU EXECUTION        GPU INFERENCE        ACCELERATED
           WORKER               WORKER              WORKER
        tests/builds         vLLM/SGLang          CFD/assets/
        Git/sandbox          model serving        future GPU jobs
```

---

## 2. User Laptops Leave the Inference Architecture

The two laptops become thin clients.

They may contain:

```text
GUI
CLI
IDE integration
auth session
presentation cache
approval interaction
```

They should not be required to run:

```text
Ollama
Qwen
DeepSeek
embedding service
Reverend authoritative state
background orchestration
```

Closing a laptop must not terminate an active Reverend project.

This is now a frozen v1 direction.

---

## 3. Why One Giant GPU VPS Is Rejected

The simple migration would be:

```text
one GPU VPS
├── API
├── auth
├── DB
├── scheduler
├── Git
├── tools
└── vLLM
```

It is operationally simple but architecturally poor.

### Failure mode 1 — idle cost

If the server stays online:

```text
pay GPU rates
```

even when no GPU work is occurring.

### Failure mode 2 — reachability

If the server is stopped to save money:

```text
Reverend disappears
```

including:

- login;
- queue;
- history;
- recovery;
- approvals.

### Failure mode 3 — common failure domain

GPU worker failure also destroys:

- control API;
- orchestration;
- potentially authoritative state.

### Failure mode 4 — poor scaling

Changing GPU requirements changes the entire server architecture.

### A10 decision

> Combined Control Plane + expensive GPU worker is rejected as the long-term topology.

It may remain a temporary development scaffold only.

---

## 4. Persistent Control Plane

The persistent machine should be CPU-oriented and inexpensive.

Responsibilities include:

```text
authenticated API
WebSocket/SSE events
Project / Run lifecycle
authoritative Control Plane
Executive Orchestrator
Agent / Team runtime
Context / Memory coordination
Workflow Scheduler
Compute Scheduler
Capacity Controller
Provider Registry
budget admission integration
durable metadata
health / observability
```

It does **not** need a large GPU.

### Initial Design starting envelope

Not a hard A10 requirement:

```text
2–4 vCPU
4–8 GB RAM
SSD-backed Linux
always reachable
no GPU requirement
```

Real sizing must come from Design measurements.

---

## 5. Zero-GPU Is a Healthy Reverend State

The following should remain available with zero GPU workers:

- login;
- project browsing;
- Run history;
- queue;
- artifacts;
- approvals;
- memory;
- Run creation;
- cancellation;
- cost history;
- worker provisioning;
- recovery.

Valid system state:

```text
Control Plane:
ONLINE

GPU workers:
0
```

This is a major architectural benefit.

---

## 6. GPU Worker Lifecycle

When a GPU Task becomes runnable:

```text
READY GPU Job
   ↓
no eligible worker
   ↓
Capacity Controller
   ↓
ComputeProvider API
   ↓
provision / start worker
   ↓
worker boots
   ↓
authenticated registration
   ↓
runtime starts
   ↓
model loads
   ↓
health passes
   ↓
READY
   ↓
ResourceLease admitted
```

When expensive work finishes:

```text
0 active GPU leases
+
0 immediately runnable GPU Jobs
+
0 resume-next work
+
0 shutdown inhibitors
+
idle grace elapsed
   ↓
DRAINING
   ↓
durability / sync
   ↓
STOP / TERMINATE
```

---

## 7. Provider Credentials Are Infrastructure Authority

Only the Capacity Controller / provider-management component should hold cloud API credentials.

Rejected:

```text
LLM
→ RunPod token
→ create arbitrary resource
```

Accepted:

```text
Agent requests capability
   ↓
scheduler derives capacity need
   ↓
Capacity Controller validates budget/policy
   ↓
provider API
```

This requirement integrates directly with A8.

---

## 8. ComputeProvider, Runtime, and Model Stay Separate

Canonical distinction:

```text
RunPod
= ComputeProvider

vLLM / SGLang / Ollama
= InferenceRuntime

Qwen / North / Nemotron / DeepSeek
= Model
```

This separation allows:

```text
RunPod → another provider
```

without changing model semantics.

It also allows:

```text
vLLM → SGLang
```

without changing cloud provisioning semantics.

---

## 9. Initial ComputeProvider Direction — RunPod

RunPod is the initial candidate because it currently offers:

- programmable GPU Pods;
- a broad GPU catalog;
- REST lifecycle APIs;
- Serverless endpoints;
- persistent/network storage options;
- both Community and Secure Cloud tiers.

RunPod's API can start/resume a Pod from persistent infrastructure.

This supports A10's external lifecycle controller requirement.

### A10 status

```text
RunPod:
INITIAL ComputeProvider candidate

NOT:
permanent architecture dependency
```

A provider adapter is required.

---

## 10. Primary Inference Runtime — vLLM

vLLM's current documentation provides capabilities directly relevant to Reverend:

```text
PagedAttention
continuous batching
chunked prefill
automatic prefix caching
CUDA/HIP graphs
quantization:
  FP8
  MXFP8 / MXFP4
  NVFP4
  INT8
  INT4
  GPTQ / AWQ
  GGUF
  compressed-tensors
  ModelOpt
  TorchAO
tensor parallelism
pipeline parallelism
data parallelism
expert parallelism
context parallelism
disaggregated prefill/decode
```

It also has broad Hugging Face integration and OpenAI-compatible serving.

This makes vLLM the lowest-complexity first cloud runtime for the A9 practical fleet.

### A10 decision

```text
PRIMARY CLOUD V1 RUNTIME:
vLLM
```

---

## 11. Secondary Runtime — SGLang

SGLang remains a first-class alternate runtime.

Current documentation emphasizes:

```text
RadixAttention
prefix caching
high-throughput serving
multi-GPU parallelism
Qwen / DeepSeek support
multiple attention backends
expert parallelism
DeepEP
NIXL
Blackwell optimizations
```

Its advanced expert-parallelism support is particularly relevant for giant MoE models.

### A10 decision

```text
SECONDARY / BENCHMARK RUNTIME:
SGLang
```

Reverend must depend on an `InferenceRuntime` abstraction rather than importing one runtime directly into Agent logic.

---

## 12. Why vLLM First

The likely Cloud v1 fleet is dominated by practical single-GPU models:

```text
Qwen3.8-27B
North Mini Code
Nemotron 3.5 Lightning
```

rather than 8–32 GPU frontier MoEs.

Qwen3.8-27B publishes official vLLM and SGLang deployment paths.

Nemotron publishes explicit vLLM deployment recipes.

vLLM therefore has a strong compatibility/complexity position for the first worker.

This is a v1 default, not a permanent superiority claim.

---

## 13. Why SGLang Still Matters

SGLang may become preferable when:

- giant MoE models are introduced;
- expert parallelism becomes important;
- multi-GPU throughput matters;
- model-specific optimized attention/communication paths dominate.

The runtime architecture must preserve the option.

---

## 14. Ollama Survives as Compatibility Runtime

Ollama should not be deleted.

Useful future roles:

- local developer smoke tests;
- small-machine mode;
- local fallback;
- compatibility testing.

It simply stops defining the cloud production architecture.

Classification:

```text
Ollama:
KEEP as local / compatibility runtime

vLLM:
PRIMARY cloud runtime

SGLang:
SUPPORTED alternative runtime
```

---

## 15. ModelDeploymentProfile

The true deployable object is not only:

```text
Qwen3.8-27B
```

It is:

```text
ModelDeploymentProfile
├── model revision
├── quantization / precision
├── runtime + version
├── context limit
├── GPU architecture
├── parallelism configuration
├── tool/reasoning parser
└── benchmark provenance
```

This is necessary because the same model can behave very differently under:

- BF16;
- FP8;
- 4-bit;
- different runtime versions;
- different context windows;
- different GPU generations.

---

## 16. Quantization Is an Architectural Concern

Lower precision can reduce:

- weight memory;
- cost;
- loading time.

But may also change:

- quality;
- numerical behavior;
- supported kernels;
- throughput.

Therefore:

> **“It fits in VRAM” is necessary, not sufficient.**

Every realistic deployment profile requires ReverendBench validation.

---

## 17. Nemotron 3.5 Lightning Physical Profile

Current official NVFP4 release:

```text
30B total
3B active
~21.6 GB repository size
up to 1M context
official vLLM recipe
```

This makes the 32GB GPU class technically meaningful for efficient Agent workloads.

However:

- runtime overhead;
- KV cache;
- practical context;
- concurrency;

must still be measured.

### A10 implication

Nemotron can be benchmarked on:

```text
32GB
48GB
```

classes.

---

## 18. North Mini Code Physical Profile

North Mini Code:

```text
30B total
3B active
agentic coding specialization
```

Its practical FP8 deployment belongs naturally in the:

```text
48GB workhorse class
```

because a 32GB card leaves insufficient operational headroom once runtime/context/cache memory is included.

The exact profile must be validated in Design.

---

## 19. Qwen3.8-27B Physical Profile

Current official repository:

```text
27B dense
~mid-50GB published weight scale
multimodal
vLLM + SGLang supported
```

Practical consequences:

### Native/reference-style deployment

```text
80–96GB class
```

provides much safer room for:

- model weights;
- KV cache;
- vision state;
- runtime workspace;
- concurrency.

### Quantized deployment

```text
48GB class
```

becomes a serious candidate.

### 32GB

May be possible with aggressive quantization, but should not define Reverend's baseline because it leaves limited headroom for serious project contexts.

---

## 20. DeepSeek V4 Flash Changes the Scale

Current DeepSeek V4 Flash release is approximately:

```text
284B total
13B active
FP8
~167GB weight distribution
```

Raw consequences:

```text
96GB single GPU:
insufficient for published weights

141GB H200:
still smaller than published checkpoint

180GB B200:
only narrow raw margin before KV/runtime overhead

288GB B300:
much more realistic single-device experiment class
```

Alternatives include multi-GPU serving.

### A10 decision

> **DeepSeek V4 Flash must not determine Reverend Cloud v1's normal GPU size.**

It remains a stretch/escalation candidate.

---

## 21. Frontier Models Are Not Baseline Private Infrastructure

GLM-5.3 and Kimi K3 offer excellent open-weight quality controls, but their parameter/weight scale creates a very different infrastructure problem.

Current independent/model-source evidence puts them in enormous MoE territory.

They are appropriate for:

- frontier benchmark controls;
- temporary experiments;
- optional external escalation;
- future multi-GPU research.

They are not appropriate as:

```text
always-on default model for two students
```

### A10 decision

```text
GLM-5.3
Kimi K3
DeepSeek V4 Pro
very large Qwen variants

→ frontier/escalation class
→ NOT baseline self-hosted fleet
```

---

## 22. Hardware Capability Classes

Do not expose provider SKU names to Specialists.

A useful provider-independent classification is:

```text
GPU_EFFICIENT
~24–32GB

GPU_WORKHORSE
~48GB

GPU_LARGE
~80–96GB

GPU_XL
~141–288GB

MULTI_GPU
model-specific distributed profile
```

A ComputeProvider maps these to current hardware inventory.

---

## 23. Primary Cloud v1 Hardware Tiers

A10 selects two main classes for serious initial benchmarking:

```text
48GB
```

and:

```text
80–96GB
```

Why:

- practical 27–30B models fit these classes under realistic native/quantized profiles;
- they allow single-GPU operation;
- they are dramatically simpler than large MoE multi-GPU serving;
- they cover both economical and quality-reference configurations.

---

## 24. Current RunPod Community Price Snapshot

The RunPod GPU Models page used during the research snapshot listed approximately:

| GPU | VRAM | Community price shown |
|---|---:|---:|
| RTX 5090 | 32GB | $0.69/h |
| RTX A6000 | 48GB | $0.33/h |
| A40 | 48GB | $0.35/h |
| L40 | 48GB | $0.69/h |
| RTX 6000 Ada | 48GB | $0.74/h |
| L40S | 48GB | $0.79/h |
| A100 PCIe | 80GB | $1.19/h |
| A100 SXM | 80GB | $1.39/h |
| RTX Pro 6000 | 96GB | $1.69/h |
| H100 PCIe | 80GB | $1.99/h |
| H100 NVL | 94GB | $2.59/h |
| H200 | 141GB | $3.59/h |
| B200 | 180GB | $5.98/h |
| B300 | 288GB | $6.94/h |

### Critical pricing warning

RunPod's dedicated Pricing page can display **different rates** depending on:

- Community vs Secure Cloud;
- SKU/tier;
- availability;
- page/update date.

For example, a separate Pricing page updated on 2026-09-13 showed higher rates for several >80GB Secure-style entries.

Therefore:

> **A11 must retrieve the exact live provider tier/SKU price used for the final economic model.**

Static prices in A10 are only topology research evidence.

---

## 25. Why the 48GB Tier Is Important

The current market makes 48GB particularly attractive.

It may be able to host:

```text
North Mini Code
Nemotron NVFP4
quantized Qwen3.8-27B
retrieval models
FLUX-class image model
```

not necessarily simultaneously.

This creates the key question:

> **Can a 48GB Reverend workhorse achieve enough verified B4/B5 quality to avoid 80–96GB rates for most work?**

That should be experimentally answered.

---

## 26. Not All 48GB GPUs Are Equal

Examples:

```text
RTX A6000 / A40
→ extremely cheap
→ older architecture

RTX 6000 Ada / L40S
→ higher hourly price
→ newer precision/inference features
```

A cheaper hourly GPU may be slower enough that:

```text
£ / verified Task
```

is worse.

Therefore GPU selection must benchmark end-to-end engineering economics, not only hourly price.

---

## 27. Recommended 48GB Bake-Off

Test:

```text
RTX A6000 / A40
vs
RTX 6000 Ada / L40S
```

with:

```text
North Mini Code
Nemotron NVFP4
quantized Qwen3.8-27B
```

Measure:

```text
verified Task success
time to first token
prefill/decode throughput
model load time
context stability
concurrent throughput
GPU seconds per verified Task
```

---

## 28. A100 80GB as Quality Reference

A100 80GB is important because:

- it provides much more headroom than 48GB;
- it can support native/reference Qwen-sized deployment more comfortably;
- its current Community rate is materially below H100-class cards.

This makes it a useful:

```text
quality/reference configuration
```

against which cheaper quantized 48GB setups should be judged.

---

## 28A. A11 Final Selection Note — Community A100 SXM

A10 originally handed the 48 GB and 80–96 GB tiers to A11 for economic selection.

A11's accepted Cloud v1 baseline is now:

```text
provider:
RunPod

provider tier:
Community Cloud

GPU:
A100 SXM 80 GB

runtime:
vLLM

workhorse:
Qwen3.8-27B

initial serving context:
64K
```

Current RunPod research snapshot used by A11:

```text
A100 SXM 80 GB Community Cloud:
$1.39 / hour
```

This does not change A10's topology or abstraction decisions. RunPod remains replaceable behind `ComputeProvider`; A100 SXM is a deployment profile rather than a semantic dependency.

The Community tier is also a trust-placement input, not only a price choice. A8 classifies the selected worker as lower-assurance shared-host infrastructure. Jobs whose `trust_requirement` demands stronger infrastructure are not eligible for this profile.

---

## 29. RTX Pro 6000 96GB

The 96GB Blackwell-class RTX Pro 6000 is particularly interesting.

Potential benefits:

```text
larger KV cache
larger contexts
more quantized-model flexibility
multimodal headroom
multiple auxiliary models
asset-generation flexibility
modern FP4/FP8 support
```

Current Community price snapshot:

```text
~$1.69/h
```

### A10 hypothesis

The RTX Pro 6000 may be a strong **all-round premium Reverend node**.

A11 must determine whether its versatility justifies the price compared with:

- A100 80GB;
- cheap 48GB cards.

---

## 30. H100 Is Primarily a Speed Purchase

H100-class cards provide newer compute/precision acceleration, but their memory capacity is not automatically larger than an A100 80GB.

Therefore the economic question is:

```text
Does faster completion / throughput
offset the higher hourly price?
```

not:

```text
Is H100 newer?
```

Reverend should only pay the premium if measured project economics justify it.

---

## 31. H200 Does Not Automatically Solve Large-Model Hosting

H200 offers:

```text
141GB VRAM
```

which is substantial.

But the published DeepSeek V4 Flash checkpoint is larger than that.

Therefore:

```text
H200 ≠ automatic one-GPU V4 Flash solution
```

For the expected v1 27–30B workhorse, H200 is likely unnecessary unless:

- long contexts;
- batching;
- specialized workloads;

create measurable economic benefit.

---

## 32. B200 / B300 Are Escalation Infrastructure

Current Community snapshot:

```text
B200 180GB
B300 288GB
```

with much higher hourly costs.

These should be reserved for:

- frontier model experiments;
- very large temporary workloads;
- extreme simulation;
- specialized high-value Tasks.

They should not define v1.

---

## 33. Initial Model/Hardware Matrix

This is a **benchmark feasibility matrix**, not a production guarantee.

| Deployment candidate | 32GB | 48GB | 80GB | 96GB | 141GB | 180–288GB |
|---|---:|---:|---:|---:|---:|---:|
| small control models | ✓ | ✓ | unnecessary | unnecessary | unnecessary | unnecessary |
| Nemotron NVFP4 ~21.6GB | candidate | preferred | ✓ | ✓ | unnecessary | unnecessary |
| North Mini Code | tight | preferred | ✓ | ✓ | unnecessary | unnecessary |
| Qwen3.8-27B native-style | no | quantized candidate | preferred | preferred | unnecessary | unnecessary |
| DeepSeek V4 Flash published FP8 | no | no | no | no | no single-GPU | candidate |
| GLM/Kimi frontier | no | no | no | no | generally no | multi-GPU / specialized |

Actual context/concurrency may change fit.

---

## 34. Context Is the Hidden VRAM Variable

GPU memory is not only model weights.

It also includes:

```text
KV cache
activations
runtime workspace
CUDA graphs
vision state
batching overhead
speculative decoding state
```

Therefore every benchmark must specify:

```text
model
quantization
runtime
GPU
context
batch
concurrency
```

A weight file size alone cannot determine feasibility.

---

## 35. Do Not Serve Maximum Advertised Context by Default

Some A9 models advertise 1M-token windows.

That is capability, not a normal serving requirement.

Initial serving profiles should emphasize practical envelopes such as:

```text
32K
64K
128K
```

with:

```text
256K
```

tested where ReverendBench shows value.

A5's retrieval architecture is intended to avoid paying for giant prompts.

---

## 36. Prefix Caching Is Highly Relevant

Many Agent prompts share stable prefixes:

```text
system policy
Specialist methodology
Project requirements
architecture contracts
```

vLLM supports automatic prefix caching.

SGLang supports prefix-cache/RadixAttention-style reuse.

This means A5's structured context architecture can improve not only quality but physical inference efficiency.

Prefix reuse should be benchmarked.

---

## 37. Logical Agents Do Not Require Separate Model Copies

Example:

```text
Research Agent A
Research Agent B
Research Agent C
```

can physically become:

```text
one resident workhorse model
   ├── request A
   ├── request B
   └── request C
```

where the runtime provides compatible scheduling/batching.

This is much more economical than launching one model server per Agent.

---

## 38. Multi-Model Residency Must Earn Its Complexity

A 96GB worker might technically hold:

```text
workhorse
small router
embedder
reranker
```

but this consumes memory that could otherwise hold:

- KV cache;
- larger context;
- more concurrency.

Benchmark:

```text
single-model residency
vs
multi-model residency
```

Do not keep a model zoo resident by default.

---

## 39. CPU Tool Execution Is Separate From GPU Inference

A Developer may follow:

```text
LLM inference
  ↓
pytest
  ↓
LLM inference
```

There is no reason to hold expensive GPU resources during the CPU test if the execution architecture can release/reacquire them.

Preferred:

```text
GPU lease
→ infer
→ release

CPU sandbox lease
→ test/build
→ release

GPU lease
→ infer
```

This realizes A6's phase-level leasing.

---

## 40. Untrusted Code Must Not Run in the Authoritative Process

The persistent Control Plane should not casually execute:

```text
pip install ...
npm install ...
pytest ...
unknown shell scripts
```

inside its own authority/security boundary.

Cloud v1 requires a logical `SandboxExecutor` / worker boundary.

Whether the CPU sandbox initially shares a physical host under strong isolation or uses a separate CPU node is a joint A8/A11 Design decision.

The logical boundary is mandatory.

---

## 41. Raw vLLM / SGLang Must Not Be Public

Target network path:

```text
Internet / clients
   ↓
authenticated Reverend API
   ↓
private authenticated worker channel
   ↓
vLLM / SGLang
```

Rejected:

```text
Internet
→ raw vLLM port
```

A8 defines the exact worker-auth mechanism.

---

## 42. Worker Registration

A worker should advertise at least:

```text
node identity
provider instance ID
GPU type
VRAM
CPU / RAM
worker version
runtime version
loaded model profile
health
active leases
```

Only authenticated/compatible workers become schedulable.

---

## 43. Separate Provider / Node / Runtime / Model Health

A provider may say the VM exists while the model is still unavailable.

Required conceptual health layers:

```text
PROVIDER HEALTH
Does the cloud instance exist?

NODE HEALTH
Is the Reverend worker alive?

RUNTIME HEALTH
Does vLLM/SGLang respond?

MODEL HEALTH
Is the expected model loaded?

FUNCTIONAL HEALTH
Does a bounded smoke inference succeed?
```

This prevents false readiness.

---

## 44. RunPod Pods vs Serverless

RunPod currently offers both.

### Pods

Useful for:

- session-shaped autonomous engineering;
- explicit worker lifecycle;
- stable model residency during a Run;
- Reverend-controlled idle grace.

### Serverless

Current endpoint features include:

```text
active workers default: 0
max workers default: 3
idle timeout default: 5s
execution timeout default: 600s
FlashBoot enabled
model caching support
priority GPU fallback lists
```

Serverless is genuinely elastic.

However, workers are billed through:

- initialization/model load;
- execution;
- idle timeout.

For large development models, repeated cold/warm cycles may dominate.

---

## 45. Why Pods Are Preferred First

Reverend development is session-shaped:

```text
infer
→ tool
→ infer
→ tests
→ infer
→ verification
→ infer
```

A dedicated Pod that stays warm for a controlled idle grace may avoid repeated model-load overhead.

It also gives Reverend direct lifecycle control.

### A10 decision

```text
RunPod Pods:
PRIMARY Cloud v1 GPU path

RunPod Serverless:
SUPPORTED EXPERIMENT / later burst path
```

Serverless is not rejected.

It is simply not the default first implementation.

---

## 46. Serverless Use Cases

Serverless may become attractive for:

- sparse one-shot inference;
- embedding jobs;
- occasional asset generation;
- highly bursty external API workloads;
- future higher-concurrency public service.

The decision should be based on measured cold-start and cost behavior.

---

## 47. Pod Lifecycle

Cloud v1 should support semantic states approximately equivalent to:

```text
ABSENT
  ↓
PROVISIONING
  ↓
BOOTING
  ↓
REGISTERING
  ↓
RUNTIME_STARTING
  ↓
MODEL_LOADING
  ↓
READY
  ↓
BUSY
  ↓
IDLE_GRACE
  ↓
DRAINING
  ↓
STOPPED / TERMINATED
```

Abnormal paths include:

```text
UNHEALTHY
UNREACHABLE
RECOVERY
```

Exact enum definitions belong to Design.

---

## 48. External Lifecycle Controller Is Mandatory

A powered-off GPU cannot tell itself to wake up.

RunPod exposes an authenticated API for starting/resuming Pods.

Therefore:

> **GPU lifecycle control must live on persistent infrastructure.**

The worker can report:

```text
idle
```

but cannot be the sole authority for its own existence.

---

## 49. Stop vs Terminate

Provider semantics matter.

A stopped resource may:

- release GPU;
- retain some storage;
- continue charging for retained storage;
- fail to reacquire identical GPU capacity later.

Therefore Reverend must assume:

```text
stopped worker identity is not guaranteed
```

Recovery must tolerate a completely different replacement worker.

---

## 50. Authoritative vs Reconstructible Storage

### Authoritative / recovery critical

```text
Control Plane DB
Git state / remotes
artifact store
checkpoint store
backup / recovery replicas
```

### Reconstructible / cache

```text
model weights
worker container cache
workspace cache
KV cache
CUDA state
runtime cache
```

If every RunPod resource disappears, Reverend should still know:

- what the project is;
- what the Run was doing;
- what artifacts exist;
- how to rebuild execution.

---

## 51. Model Weights Are Reconstructible

Model checkpoints are large but not unique project state.

Cache aggressively for performance.

Do not treat a provider-local model copy as authoritative.

---

## 52. Workspace State Is Different

A worktree may contain unique uncommitted project progress.

Before a worker can disappear, A7 must ensure that progress has a durable representation, for example:

```text
Git checkpoint/ref
patch artifact
workspace snapshot
equivalent durable state
```

Worker filesystem alone is not enough.

---

## 53. Cloud Storage and Volumes

RunPod Serverless documentation currently lists:

```text
container disk:
~$0.10/GB/month equivalent

network volume:
~$0.07/GB/month below 1TB
```

and notes that network volumes:

- persist across worker restarts;
- add network latency;
- may constrain data-center placement.

These are useful for:

- model caches;
- datasets;
- reconstructible large files.

They should not be the sole copy of Reverend's authoritative state.

---

## 54. Container / Runtime Reproducibility

Production workers should use versioned images.

Record:

```text
container digest
CUDA version
driver requirements
vLLM/SGLang version
model revision
quantization revision
Reverend worker version
```

Avoid unpinned:

```text
latest
```

in accepted production profiles.

This is necessary for:

- benchmark reproducibility;
- debugging;
- recovery;
- rollback.

---

## 55. Cache by Measured Economics, Not Model Status

A9 contains many model candidates.

Provider-local cache policy is **not** determined simply by whether a model is “production”.

Default:

```text
required model
→ fetch/load on demand
→ worker-local ephemeral cache
```

Optional persistent/warm cache is enabled only when measured cold-start/download savings justify provider storage cost and complexity.

Do not permanently store:

```text
every model ever benchmarked
```

on paid provider storage.

Benchmark candidates/frontier comparisons are fetched only when required unless a measured cache policy explicitly promotes their storage behavior.

This section is superseded/refined by D18/D19.

---

## 56. Single-GPU First

A10 accepts multi-GPU capability in the architecture.

But Cloud v1 should prefer the strongest model configuration that fits economically on one GPU.

Multi-GPU introduces:

- placement constraints;
- interconnect dependence;
- distributed runtime complexity;
- larger failure surface;
- higher startup cost;
- more expensive idle periods.

Do not incur this complexity unless model-quality evidence justifies it.

---

## 57. Optional External Frontier Escalation

A future policy may permit:

```text
PRIVATE_SELF_HOSTED
normal project work

EXTERNAL_API
explicit policy-permitted frontier escalation
```

for eligible non-sensitive context.

A8 decides trust and data policy.

A10 only freezes that the architecture should not prevent this option.

Cloud v1 does not require it.

---

## 58. Scientific and Asset Workloads Reuse the Compute Fabric

Future:

```text
AstraFlow CUDA
CFD / FEA
Blender
FLUX
ComfyUI
other accelerators
```

should use the same A6 ResourceRequest/Lease system.

They may use separate executors/runtime images.

They do not need a new global infrastructure architecture.

---

## 59. GPU Workers Do Not Host the Authoritative Database

A GPU Pod may include plenty of CPU/RAM.

That does not justify putting:

```text
authoritative DB
```

on it.

Doing so would recouple permanent state to disposable expensive compute.

Use the GPU worker CPU/RAM for:

- inference runtime;
- temporary tools;
- worker cache;
- model loading.

Keep authoritative DB on persistent infrastructure.

---

## 60. SQLite vs PostgreSQL Remains Open

A10 does **not** force PostgreSQL.

Final choice depends on the write topology produced by:

- A2;
- A7;
- Design.

If one authoritative writer remains sufficient, SQLite may still be viable.

If independent distributed writers / concurrency requirements justify it, PostgreSQL becomes more appropriate.

The frozen A10 rule is only:

> **The authoritative database lives independently of GPU workers.**

---

## 61. Redis Is Not Automatically Required

Do not add Redis because cloud diagrams commonly include it.

Introduce it only if Design identifies a concrete need such as:

- distributed ephemeral queueing;
- pub/sub;
- coordination cache;
- lease acceleration.

One authority per concern remains more important than trendy infrastructure.

---

## 62. Containers Are Appropriate Worker Packaging

Inference and sandbox workers should be reproducibly containerized.

However:

> **Agents must never receive unrestricted Docker-daemon authority.**

Container lifecycle belongs to infrastructure/execution management.

---

## 63. Kubernetes Is Rejected for Cloud v1

Initial scale:

```text
2 users
1 active top-level Run policy
few workers
usually 0–1 GPU
```

Kubernetes would add substantial operational complexity before Reverend has demonstrated a need for it.

### A10 decision

```text
NO Kubernetes dependency for Cloud v1
```

Use:

- Linux services;
- containers;
- Reverend scheduler;
- provider APIs.

Revisit if real scale eventually justifies it.

---

## 64. Control Plane vs Data Plane

Conceptually separate:

### Control traffic

```text
auth
commands
Task/Run state
scheduling
approvals
events
```

### Data / execution traffic

```text
repository snapshots
large artifacts
datasets
model requests
tool results
```

This keeps control/UI responsiveness independent from large execution transfers.

---

## 65. Frontend Remains Available During Compute Failure

Because events come from the persistent Control Plane:

```text
GPU worker lost
```

should not make the UI disappear.

The user can still see:

```text
GPU worker unavailable
Job interrupted
replacement queued
recovery in progress
```

This is a major usability/reliability improvement over one-VPS topology.

---

## 66. Cold-Start Telemetry

Do not measure only:

```text
user starts Run
→ first token
```

Measure stages independently:

```text
provider allocation
VM boot
container start
worker registration
model download/cache
model load
runtime warmup
first token
```

Different optimizations target different phases.

A11 needs these measurements for cost analysis.

---

## 67. Idle Shutdown Policy

Initial eligibility direction:

```text
0 active GPU leases
AND
0 immediately runnable GPU Jobs
AND
0 resume-next work
AND
0 shutdown inhibitors
AND
idle grace elapsed
```

An initial grace around:

```text
5–10 minutes
```

is a reasonable Design starting point, not a frozen constant.

The Capacity Controller decides shutdown.

---

## 68. Failure / Replacement Example

```text
Developer Agent
   ↓
GPU worker 7
   ↓
node dies
   ↓
heartbeat lost
   ↓
node → UNREACHABLE
   ↓
ResourceLease invalidated
   ↓
Job interrupted
   ↓
Control Plane remains online
   ↓
A7 reconciles durable state
   ↓
Capacity Controller provisions worker 9
   ↓
Context reconstructed
   ↓
new Job attempt
```

This is the practical payoff from separating compute from authority.

---

## 69. Recommended Cloud v1 Topology

```text
┌────────────────────────────────────────────┐
│ PERSISTENT CONTROL PLANE                   │
│                                            │
│ Auth                                       │
│ Project / Run API                          │
│ Control Plane                              │
│ Executive Orchestrator                     │
│ Agent / Team Runtime                       │
│ Context / Memory                           │
│ Workflow Scheduler                         │
│ Compute Scheduler                          │
│ Capacity Controller                        │
│ Provider Registry                          │
│ budget-admission seam                      │
│ events / observability                     │
└───────────────┬────────────────────────────┘
                │
        ┌───────┴────────┐
        ▼                ▼
  DURABLE STATE      COMPUTE PROVIDERS
  DB                 RunPod first
  Git                    │
  Artifacts              ▼
  Checkpoints      ELASTIC WORKERS
  Backups         ┌───────────────┐
                  │ GPU inference │
                  │ vLLM primary  │
                  │ SGLang alt    │
                  └───────────────┘
                  ┌───────────────┐
                  │ CPU sandbox   │
                  │ build / tests │
                  └───────────────┘
```

---

## 70. Recommended Implementation Progression

A10 recommends implementing the cloud transition in controlled stages.

### C1 — Prove Distributed Inference

```text
persistent Control Plane
+
one statically configured GPU worker
+
vLLM
+
one A9 workhorse candidate
```

Goal:

- prove networking;
- prove authenticated worker call path;
- preserve current development behavior.

---

### C2 — Introduce Node Registry and Leases

Add:

```text
worker registration
health
ComputeNode
distributed ResourceLease
scheduler integration
```

Goal:

- move from hard-coded remote endpoint to schedulable worker.

---

### C3 — Provider Lifecycle Automation

Add:

```text
RunPodComputeProvider
create/start/stop
```

Goal:

- Control Plane can acquire expensive capacity itself.

---

### C4 — Drain and Recovery

Add:

```text
idle grace
DRAINING
shutdown inhibitors
A7 checkpoint integration
worker replacement
```

Goal:

- expensive workers become truly disposable.

---

### C5 — Model Placement

Add:

```text
multiple deployment profiles
residency
hardware classes
routing / placement cooperation
```

Goal:

- cost/quality-aware model execution.

---

### C6 — Only If Evidence Justifies

Possible additions:

```text
RunPod Serverless
multiple simultaneous GPU workers
SGLang specialized MoE serving
multi-GPU frontier escalation
```

Do not build C6 before C1–C5 prove the core architecture.

---

## 71. What Not to Build Initially

A10 explicitly rejects requiring:

```text
Kubernetes
8×H200 cluster
permanent H200/B300
one GPU per Agent
several always-on model servers
custom LLM inference engine
global multi-region orchestration
automatic 20-Agent GPU swarm
```

These would distract from validating Reverend's actual engineering value.

---

## 72. Primary Hardware Bake-Off

### Configuration E — Economical

```text
48GB modern/cheap GPU
vLLM
North / Nemotron / quantized Qwen
64–128K practical context
```

### Configuration Q — Quality Reference

```text
80–96GB GPU
vLLM
native/reference Qwen3.8-27B
larger context/KV headroom
```

Then compare:

```text
verified engineering quality
latency
throughput
load time
GPU utilization
billable time
£ / verified Task
```

This is more useful than comparing every available GPU.

---

## 73. First Hardware Candidates

Highest-priority practical benchmark set:

### 48GB

```text
RTX A6000
A40
RTX 6000 Ada
L40S
```

### 80GB

```text
A100 PCIe
```

### 96GB

```text
RTX Pro 6000
```

Only if justified:

```text
H100
H200
B200
B300
```

---

## 74. Required Configuration Measurements

Every hardware/runtime/model profile should record:

```text
model revision
quantization
runtime version
container digest
GPU
context
batch / concurrency

provider allocation time
boot time
model load time
TTFT
prefill throughput
decode throughput

VRAM
RAM

single-Agent success
multi-Agent throughput
verified Task success

GPU seconds
billable worker seconds
idle seconds
```

A11 turns these measurements into the real economic comparison.

---

## 75. Hypotheses Handed to A11

### H1 — 48GB Workhorse

A modern/cheap 48GB GPU plus a strong quantized 27–30B model may provide the best economics for normal Reverend work.

### H2 — 96GB Consolidation

RTX Pro 6000 96GB may offer the best single-worker versatility across:

- engineering;
- larger context;
- vision;
- auxiliary models;
- assets.

### H3 — A100 Reference

A100 80GB may be the most economical high-quality native-Qwen reference.

### H4 — H100 Speed Premium

H100 may justify its higher hourly price only if faster completion materially lowers total project cost.

### H5 — Pod Session Model

A Reverend-controlled Pod with a 5–10 minute idle grace may outperform Serverless for interactive autonomous development sessions.

### H6 — Serverless Burst

Serverless may be more economical for sparse one-shot or auxiliary inference.

### H7 — vLLM First

vLLM is likely the lowest-complexity runtime for the current practical fleet.

All are hypotheses pending measured A11 evidence.

---

## 76. A10 Research Sources

### RunPod

- GPU Models / Community pricing snapshot  
  `https://www.runpod.io/gpu-models`

- Pricing page  
  `https://www.runpod.io/pricing`

- Pod start/resume API  
  `https://docs.runpod.io/api-reference/pods/POST/pods/podId/start`

- Serverless endpoint configuration  
  `https://docs.runpod.io/serverless/endpoints/endpoint-configurations`

- Serverless pricing  
  `https://docs.runpod.io/serverless/pricing`

### vLLM

- vLLM documentation  
  `https://docs.vllm.ai/en/stable/`

- Automatic Prefix Caching  
  `https://docs.vllm.ai/en/latest/features/automatic_prefix_caching/`

### SGLang

- SGLang documentation  
  `https://docs.sglang.io/`

- Expert Parallelism  
  `https://docs.sglang.io/docs/advanced_features/expert_parallelism`

- Attention backends  
  `https://docs.sglang.io/docs/advanced_features/attention_backend`

### Model deployment evidence

See A9's official Hugging Face model-source register.

All provider prices and support claims should be revalidated during A11 / Design.

---

## 77. Frozen A10 Requirements

```text
A10-01
User laptops are thin clients and do not provide required LLM inference.

A10-02
Authoritative Control Plane runs on persistent CPU-oriented infrastructure.

A10-03
GPU compute is independent, replaceable, and disposable.

A10-04
Stopping all GPU workers does not make Reverend unavailable.

A10-05
GPU lifecycle is controlled externally by persistent infrastructure.

A10-06
ComputeProvider, InferenceRuntime, and Model are separate abstractions.

A10-07
RunPod is the initial ComputeProvider candidate, not a permanent dependency.

A10-08
vLLM is the preferred initial cloud inference runtime.

A10-09
SGLang remains a supported alternate runtime and benchmark target.

A10-10
Ollama remains a compatibility/local runtime.

A10-11
Model deployment profiles include model revision, precision, runtime, context, and hardware.

A10-12
Quantized deployment profiles require Reverend-specific quality validation.

A10-13
The default production fleet should aim to fit on one practical GPU.

A10-14
48GB and 80–96GB are primary v1 hardware tiers to evaluate.

A10-15
141GB+ hardware is specialized/escalation infrastructure unless evidence justifies otherwise.

A10-16
DeepSeek V4 Flash and frontier models do not determine normal v1 hardware.

A10-17
Frontier models may be temporary/external escalation subject to A8 trust policy.

A10-18
Context windows are configured to measured need, not advertised maximum.

A10-19
Prefix caching and batching should be benchmarked for multi-Agent efficiency.

A10-20
Logical Agent count does not imply model-server count.

A10-21
Model residency is optimized empirically rather than loading the whole fleet.

A10-22
CPU/tool execution is logically separated from GPU inference.

A10-23
Untrusted project execution must not occur inside the authoritative Control Plane process.

A10-24
Raw inference runtimes are not publicly exposed.

A10-25
Compute workers authenticate before registration.

A10-26
Provider, node, runtime, model, and functional health are distinct.

A10-27
RunPod Pods are the preferred first elastic GPU path.

A10-28
RunPod Serverless remains an optional later/burst inference path.

A10-29
Cloud model storage/cache is reconstructible.

A10-30
Provider storage is not Reverend's sole authoritative state store.

A10-31
Worker filesystems are never the only copy of valuable project progress.

A10-32
Production containers/runtime/model revisions are version-pinned.

A10-33
No Kubernetes dependency is required for Cloud v1.

A10-34
Multi-GPU capability remains representable but is not normal v1 workhorse execution.

A10-35
Capacity Controller performs shutdown only after A7 durability conditions are satisfied.

A10-36
Cloud hardware selection is driven by verified-task economics, not GPU prestige or raw VRAM.

A10-37
The first distributed deployment begins with one GPU worker before automatic scale-out.

A10-38
Provider/runtime/model replacement must not change Agent semantics.
```

---

## 78. Design-Phase Implications

The Design Phase must define:

- `ComputeProvider` interface;
- RunPod provider adapter;
- `InferenceRuntime` interface;
- vLLM runtime adapter;
- SGLang runtime adapter;
- Ollama compatibility adapter;
- `ComputeNode` registration/health protocol;
- deployment-profile identity;
- worker container/image specification;
- worker authentication;
- private worker networking;
- cold-start telemetry;
- model residency state;
- drain/shutdown protocol;
- provider lifecycle reconciliation;
- CPU SandboxExecutor;
- authoritative/cache storage boundaries;
- multi-GPU representation without requiring it;
- model-cache policy.

The Design should implement C1–C5 incrementally and preserve the ability to test each layer.

---

## 79. A10 Decision Record

```text
MILESTONE:
A10 — Hardware, Runtime & Cloud Topology

STATUS:
ACCEPTED

TOPOLOGY:
thin clients
→ persistent CPU Control Plane
→ authenticated elastic compute fabric

INITIAL COMPUTE PROVIDER:
RunPod candidate

INITIAL GPU MODE:
Pod-based elastic worker

A11 SELECTED BASELINE PROFILE:
RunPod Community Cloud
A100 SXM 80 GB
vLLM
Qwen3.8-27B
64K initial serving context

PRIMARY INFERENCE RUNTIME:
vLLM

SECONDARY RUNTIME:
SGLang

LOCAL COMPATIBILITY:
Ollama

PRIMARY HARDWARE BAKE-OFF:
48GB
80GB
96GB

NORMAL MODEL SCALE:
single-GPU practical 27–30B-class workhorse

FRONTIER:
temporary / external / specialized escalation,
not baseline infrastructure

STATE:
authoritative state independent of GPU workers

SHUTDOWN:
drain + A7 durability + idle policy

RECOVERY:
fresh workers reconstruct from durable state

REJECTED:
- one giant GPU VPS
- required laptop inference
- one GPU per Agent
- public raw vLLM/SGLang
- permanent XL GPU as baseline
- frontier hardware as normal requirement
- Kubernetes for v1
- worker-local state as project authority
```


---

## Post-Analysis Refinement — Ephemeral-First GPU Storage & Bootstrap

> **Refinement status:** Accepted by Design D19; does not change A10's persistent-Control-Plane + disposable-compute topology.

A10's disposable GPU direction is now made explicit.

### Default GPU worker class

~~~text
EPHEMERAL_GPU_WORKER

authoritative state:
  none

runtime:
  reconstructible

model weights:
  reconstructible / on-demand

workspace:
  temporary execution copy
  durable externalization required

provider-local persistent storage:
  optional cache only
~~~

### Initial RunPod storage target

~~~text
temporary container disk:
  approximately 200 GB target

optional warm volume:
  approximately 10 GB target

correctness dependency on either:
  none
~~~

These are deployment targets, not permanent architecture constants.

### Model-cache policy refinement

Any earlier wording that implies production models must live in persistent provider storage is superseded by:

> **Model weights are reconstructible cache objects. Persistent provider-local model cache is optional and must be justified by measured economics.**

Decision inputs include:

- model bytes;
- download/setup time;
- provider storage cost;
- bandwidth cost where relevant;
- expected cold-start frequency;
- cache hit probability;
- responsiveness target.

### Bootstrap

A worker should start from a pinned Reverend worker image and BootstrapSpec rather than mutable ad-hoc installation.

The bootstrap reconstructs:

~~~text
worker runtime
required capability adapters
only the selected DeploymentProfile/model
health probes
temporary workspace
~~~

It does not reconstruct PostgreSQL authority because PostgreSQL remains on the persistent Control Plane.

### Destruction invariant

~~~text
worker has unique unrecoverable state
→ stop/terminate forbidden
~~~

D19/D5 WorkerDurabilityGate defines the proof required before destructive provider lifecycle.

### Zero-provider-loss requirement

Deleting every RunPod resource including:

~~~text
Pod
container
optional volume
model cache
runtime cache
temporary worktree
~~~

must still leave the Project/Run recoverable from persistent Control Plane + Git + BlobStore/checkpoint material.
