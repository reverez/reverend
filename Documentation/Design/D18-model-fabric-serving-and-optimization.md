# D18 — Model Fabric, Serving & Optimization

> **Status:** DESIGN ACCEPTED FOR DEVELOPMENT  
> **Research snapshot:** 2026-09-16  
> **Depends on:** A9, A10, D4, D7, D15  
> **Purpose:** Modernize Reverend from a laptop-era fixed local model set into a benchmarked elastic model fleet while keeping Agents independent of checkpoint/provider identity.

---

## 1. Governing Rule

~~~text
Specialist / Agent
      ↓
ModelRequirement
      ↓
eligible ModelProfiles
      ↓
eligible DeploymentProfiles
      ↓
Model Router
      ↓
Compute Scheduler
      ↓
InferenceRuntime
~~~

No Specialist permanently owns a checkpoint.

No GPU permanently owns a model.

---

## 2. Baseline vs Fleet

Cloud v1 starts deliberately simple.

### Baseline workhorse

~~~text
Qwen/Qwen3.8-27B
vLLM
A100 SXM 80 GB
64K Reverend serving profile
COMMUNITY_CLOUD_WORKER
~~~

This is a baseline to measure, not a permanent universal winner.

### Candidate classes

ReverendBench may evaluate:

- general agentic workhorse models;
- coding-specialized models such as Qwen3-Coder candidates;
- small CONTROL models;
- independent assurance models;
- embeddings;
- rerankers;
- vision/multimodal profiles;
- external API escalation profiles where Project trust permits.

Current model names are candidates, not semantic API contracts.

---

## 3. Current Evidence Snapshot

The 2026-09-16 research snapshot shows:

- Qwen3.8-27B's official repository advertises vLLM/SGLang compatibility and agentic/coding use;
- Qwen publishes coding-specialized Qwen3-Coder profiles including 30B-A3B and Coder-Next families.

These justify bake-off candidates only.

Model cards do not establish production eligibility.

---

## 4. InferenceRuntime

Canonical interface:

~~~text
health()
profiles()
ensure_loaded(profile_id)
generate(request)
stream(request)
embed(request)
cancel(invocation_id)
metrics()
~~~

Adapters:

~~~text
vLLM      primary cloud runtime
SGLang    alternate cloud runtime
Ollama    local compatibility
External  optional API adapter
~~~

Runtime implementation does not determine ModelRequirement semantics.

---

## 5. vLLM Optimization Opportunities

vLLM must not be treated as simply remote Ollama.

### Automatic Prefix Caching

Useful when Agent calls share:

- system constraints;
- Specialist methodology;
- Project policy;
- stable repository/context prefix.

The runtime may reuse prompt-prefix KV computation.

Security rule:

- cache reuse is a performance feature only;
- do not assume cross-Project cache sharing is safe;
- partition/flush cache domains on trust/sensitivity boundary where runtime isolation is insufficient;
- no correctness decision depends on cache presence.

### Structured tool calling / structured output

Where supported, use schema-constrained generation for tool parameters and typed outputs.

This reduces malformed structure.

It does not authorize the action.

Tool Broker still validates policy, scope and authority.

### Continuous batching / concurrency

Potentially improves multi-Agent throughput.

Do not maximize concurrency before measuring:

- latency;
- GPU utilization;
- KV pressure;
- cancellation;
- quality;
- cost.

### Context profiles

Serve explicit 32K/64K/128K profiles when useful rather than always the model's largest advertised context.

### Quantization

Every quantized serving configuration is a distinct benchmarked DeploymentProfile.

---

## 6. Prefix Stability and Context Design

Context Compiler should use a canonical ordering where possible:

~~~text
system/security policy
Specialist methodology
Project policy
Task/acceptance
stable dependency/interface context
dynamic observations
~~~

Correctness always outranks prefix-cache efficiency.

Do not keep stale or irrelevant text merely to preserve a cache hit.

---

## 7. ModelProfile vs DeploymentProfile

### ModelProfile

Abstract model/revision/capability/license identity.

### DeploymentProfile

Concrete serving contract:

~~~text
model revision
runtime + runtime version
container digest
quantization
context limit
reasoning settings
hardware requirements
trust class
concurrency policy
batching policy
storage/cache policy
benchmark result set
~~~

Changing a semantic deployment dimension creates a new profile identity.

---

## 8. Ephemeral Model Storage

Model weights are reconstructible.

Canonical authority is:

~~~text
ModelProfile
DeploymentProfile
pinned model repository/revision
artifact manifest/digests
runtime/container identity
benchmark provenance
~~~

Worker-local model directories are caches.

Startup:

~~~text
required DeploymentProfile
↓
cache hit?
├── yes → verify
└── no  → download pinned artifacts
            ↓
          verify
↓
load runtime
↓
functional smoke
↓
READY
~~~

Do not download the whole model fleet.

---

## 9. Optional Persistent Model Cache

Provider-local model persistence is an economics optimization only.

Decision inputs:

~~~text
expected cold starts
download/setup latency
storage price
bandwidth cost
cache hit probability
usage frequency
startup SLA
~~~

Default Cloud v1:

~~~text
model weight persistence_required = false
~~~

---

## 10. Reasoning Effort

Reasoning effort belongs to the Job.

Router may select/escalate:

~~~text
low
medium
high
max
~~~

only when supported by profile, Task complexity, evidence from prior attempts and remaining budget.

Maximum reasoning for every call is rejected.

---

## 11. Cause-Aware Model Escalation

~~~text
malformed structured output
→ bounded repair / parser-compatible retry

weak reasoning
→ stronger reasoning profile

coding failure
→ coding-specialist candidate

missing evidence
→ Research Fabric

missing repository fact
→ Repository Intelligence

trust mismatch
→ stronger infrastructure profile
~~~

Bigger model is not a substitute for missing system capability.

---

## 12. Embedding and Reranking Fleet

Embedding/reranking are ModelProfiles too.

Promotion uses:

- Hit@K/MRR;
- Project retrieval accuracy;
- downstream Task success;
- latency;
- resource cost;
- index migration cost.

Current BGE-M3 behavior remains a baseline.

---

## 13. Multimodal / Vision

Vision-capable profiles receive authorized image Artifacts only when required.

Vision is not added to every prompt by default.

Screenshots enter through Artifact provenance, not uncontrolled remote URLs.

---

## 14. External API Models

External APIs are optional DeploymentProfiles.

Requirements:

- EXTERNAL_API trust class;
- Project policy permits;
- Context Broker sensitivity filter;
- Secret Broker owns API credential;
- cost ledger records usage;
- no automatic fallback simply because self-hosted GPU is unavailable.

---

## 15. Supply Chain

Retain D7 hardening:

- immutable model revision;
- safe weight-format baseline;
- remote model repository code disabled by default;
- reviewed worker image;
- pinned container digest;
- cache checksum validation;
- license record;
- runtime/image vulnerability review.

---

## 16. Router Decision

Eligibility filters:

1. capability;
2. modality;
3. context;
4. trust/sensitivity;
5. license;
6. runtime/hardware support;
7. ReverendBench gate;
8. budget.

Ranking then considers:

- verified Task success;
- GBP per verified success;
- startup/load delay;
- current residency;
- latency;
- model-family diversity requirement.

---

## 17. One Workhorse First

Avoid an initial model zoo.

Recommended rollout:

~~~text
1 workhorse
+ embedding baseline
+ optional independent verifier candidate
↓
measure real workload
↓
add CONTROL/coding/vision/reranker profiles only when justified
~~~

This keeps ephemeral-worker startup and storage tractable.

---

## 18. Shared Model, Multiple Agents

AgentTeam size does not equal model count.

Several logical Agents can:

- share one vLLM runtime;
- interleave requests;
- benefit from batching/prefix reuse;
- run network/CPU tools concurrently.

Compute Scheduler decides physical concurrency.

---

## 19. Failure Modes

### Model unavailable

Remain queued or choose another eligible profile.

### Weight download fails

Worker remains unready; bounded retry; terminate expensive failed worker where policy dictates.

### OOM at validated profile

Mark profile/node unhealthy and capture evidence; do not loop identical retries.

### Runtime/image upgrade regresses quality

New DeploymentProfile fails promotion; historical profile remains distinct.

### Cache uncertainty

Disable/flush cache rather than risk correctness/security.

---

## 20. Observability

Per invocation:

- model/deployment profile;
- reasoning effort;
- context profile;
- token counts;
- prefix-cache metrics if available;
- queue/load/inference latency;
- structured-output/tool parse status;
- GPU utilization/VRAM;
- cost attribution;
- verification outcome.

Per cold start:

- download bytes/time;
- cache hit/miss;
- verification time;
- model load;
- smoke health.

---

## 21. ReverendBench Experiments

At minimum compare:

~~~text
workhorse candidates
coding specialist vs workhorse
same model 32K vs 64K vs 128K
native vs quantized
reasoning effort tiers
prefix caching on/off
concurrency policies
same-family vs cross-family verifier
embedding/reranker alternatives
~~~

Control Specialist, Context and tool policy when comparing models.

---

## 22. Acceptance Tests

Must prove:

- Agent retry may change DeploymentProfile without changing Agent identity;
- only required model downloads;
- destroyed model cache does not lose Run state;
- profile digest/revision mismatch prevents READY;
- schema-valid tool output still passes Tool Broker authorization;
- missing web evidence triggers Research Fabric rather than model escalation;
- missing symbol triggers Repository Intelligence rather than giant context;
- external API never receives restricted context;
- prefix cache is never durable authority;
- one workhorse can safely serve multiple logical Agents.

---

## 23. Exit Condition

Model Fabric is ready when Reverend can replace or specialize models based on measured capability without changing Agent semantics, reconstruct serving from pinned profiles on disposable workers and optimize runtime behavior without making caches or model claims authoritative.


---

## 24. Recursive Capability Audit — Model Artifact Acquisition & Cache Trust

### Community worker must not receive registry credentials by default

For the baseline public model:

~~~text
model artifacts are public
→ worker may fetch from approved public model host
→ pinned revision + digest verification
~~~

For private/licensed model artifacts requiring credentials:

- do not place long-lived Hugging Face/model-registry token on a Community worker;
- trusted Control Plane/build pipeline may pre-stage verified encrypted/model objects in an approved artifact store;
- worker receives short-lived object capability/signed download reference scoped to exact required artifacts; or
- use stronger-trust dedicated infrastructure with an explicit credential adapter.

### Model download network policy

Worker may contact only approved artifact origins needed by its DeploymentProfile.

Redirect/origin change is revalidated.

Model download path cannot become a general-purpose web client.

### Cache poisoning defense

Cache lookup key includes:

~~~text
DeploymentProfile ID
model revision
file identity
expected digest
quantization/runtime compatibility
~~~

A file with matching name but wrong digest/profile is quarantined/deleted.

### Baseline fit remains an empirical gate

A100 SXM 80 GB + Qwen3.8-27B + 64K is the accepted initial **target profile**, but C7 must measure real VRAM/runtime/context fit before production ELIGIBLE status.

If the exact serving profile does not fit safely or has unacceptable throughput, ReverendBench selects a revised DeploymentProfile rather than weakening worker safety margins.


---

## 25. Recursive Capability Audit — Inference Confidentiality & Placement

Model routing uses D1/D6 Project disclosure policy in addition to Worker trust class.

A technically eligible Community A100 is not context-eligible if mandatory ContextItems exceed the Project's Community disclosure policy.

The Router/Compute Scheduler then:

- selects a stronger eligible DeploymentProfile/worker; or
- blocks/escalates.

It never silently strips mandatory private context.

### Runtime logging

Production model runtime configuration disables prompt/request-body logging by default.

Worker logs may include:

~~~text
invocation ID
DeploymentProfile
token counts
queue/inference timing
GPU utilization
bounded failure code
~~~

but not raw source-code prompt/context or hidden reasoning.

Prefix/KV cache remains ephemeral worker memory and is destroyed/partitioned according to trust policy.
