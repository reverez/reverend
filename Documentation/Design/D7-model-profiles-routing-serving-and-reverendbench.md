# D7 — Model Profiles, Routing, Serving & ReverendBench

> **Status:** DESIGN ACCEPTED FOR DEVELOPMENT  
> **Depends on:** A9, A10, A11, A12, D3, D4  
> **Purpose:** Define how Reverend represents model capability, admits deployment profiles, routes each Job to eligible intelligence, controls context/reasoning effort, and promotes models only after Reverend-specific benchmark evidence.

---

## 1. Permanent Model Architecture

Reverend does not encode permanent Specialist-to-model bindings.

Canonical flow:

~~~text
Task / AgentInstance
        ↓
ModelRequirement
        ↓
Model Registry
        ↓
eligible ModelProfiles
        ↓
Model Router
        ↓
eligible DeploymentProfiles
        ↓
Compute Scheduler
        ↓
InferenceRuntime + ComputeNode
~~~

The model used by one Job is deployment configuration, not Agent identity.

---

## 2. ModelProfile

A ModelProfile describes an abstract model revision independent of where it runs.

Recommended contract:

~~~text
ModelProfile
├── model_profile_id
├── family
├── model_name
├── revision
├── license_id
├── modalities
├── capabilities
│   ├── reasoning
│   ├── coding
│   ├── repository_reasoning
│   ├── tool_use
│   ├── structured_output
│   └── vision
├── max_advertised_context_tokens
├── validated_context_profiles
├── runtime_compatibility
├── trust_eligibility
├── benchmark_snapshot_id
├── status
└── metadata
~~~

Status values:

~~~text
DISCOVERED
BENCHMARKING
ELIGIBLE
DISABLED
RETIRED
~~~

Only ELIGIBLE profiles may be selected for production Jobs.

---

## 3. DeploymentProfile

A DeploymentProfile binds one model to a specific serving configuration.

~~~text
DeploymentProfile
├── deployment_profile_id
├── model_profile_id
├── model_revision
├── runtime
├── runtime_version
├── quantization
├── container_digest
├── max_context_tokens
├── default_reasoning_effort
├── supported_reasoning_efforts
├── hardware_requirements
├── trust_class
├── concurrency_policy
├── batching_policy
├── benchmark_result_set
├── cost_profile
├── status
└── created_at
~~~

Example Cloud v1 baseline:

~~~text
deployment_profile_id:
qwen3.8-27b-a100sxm80-vllm-64k-v1

model:
Qwen/Qwen3.8-27B

runtime:
vLLM

GPU:
A100 SXM 80 GB

context:
64K

trust:
COMMUNITY_CLOUD_WORKER
~~~

Actual model revision, image digest and runtime version are pinned during C7 live validation.

---

## 4. ModelRequirement v1

Agent/Task requirements are capability thresholds.

Example:

~~~json
{
  "reasoning": "high",
  "coding": "high",
  "repository_reasoning": "high",
  "tool_use": "required",
  "structured_output": "required",
  "vision": "optional",
  "min_context_tokens": 65536,
  "trust_requirement": "COMMUNITY_CLOUD_WORKER",
  "latency_class": "normal",
  "cost_class": "normal"
}
~~~

A requirement never contains a provider GPU SKU unless the Task is explicitly a hardware experiment.

---

## 5. Capability Levels

Initial normalized ordinal values:

~~~text
NONE
BASIC
MODERATE
HIGH
VERY_HIGH
~~~

Capabilities are populated from ReverendBench evidence, not only vendor claims.

Vendor/public benchmark evidence may seed a DISCOVERED profile but cannot independently set production eligibility.

---

## 6. Routing Eligibility Pipeline

For every model-backed Job:

~~~text
1. load ModelRequirement
2. filter ELIGIBLE ModelProfiles
3. verify modality/context
4. verify trust/provider policy
5. verify license/project policy
6. verify DeploymentProfile active
7. verify ReverendBench role gate
8. verify budget/cost ceiling
9. send remaining candidates to Compute Scheduler
~~~

If zero candidates remain:

- produce MODEL_INELIGIBLE;
- do not silently degrade;
- Executive Orchestrator may request escalation, different context plan, or human decision.

---

## 7. Routing Ranking

Among eligible profiles, initial ranking should consider:

1. verified Task success for relevant role/benchmark class;
2. expected verified-task cost;
3. current model residency;
4. queue/startup latency;
5. expected wall-clock time;
6. model-family diversity requirement where explicitly requested.

No single global model score chooses all Jobs.

---

## 8. Routing Profiles

Logical convenience profiles may remain:

~~~text
CONTROL
FAST_GENERAL
FAST_ENGINEERING
PRIMARY_ENGINEERING
DEEP_REASONING
ASSURANCE
VISION
EMBEDDING
RERANKING
MEDIA_GENERATION
MAX_QUALITY_ESCALATION
~~~

These map to ModelRequirements, not checkpoint names.

The existing ModelRole enum may remain as compatibility input during migration.

---

## 9. Baseline Cloud v1 Workhorse

A12 accepts the initial baseline:

~~~text
Model:
Qwen/Qwen3.8-27B

Deployment:
A100 SXM 80 GB
vLLM
64K serving profile
RunPod Community Cloud
~~~

This profile is initially eligible for:

- FAST_ENGINEERING;
- PRIMARY_ENGINEERING;
- moderate/deep reasoning where ReverendBench passes;
- vision where required and validated.

It is not permanently tied to any Specialist.

---

## 10. Small CONTROL Model

A small CONTROL model remains optional for Cloud v1.

Do not provision a second persistent model merely because A9 identified candidates.

Promotion rule:

- measure frequency of CONTROL calls;
- measure cost/loading overhead;
- compare same-workhorse routing vs small-model routing;
- add separate profile only if total verified-project cost or latency improves materially.

Until then, the workhorse may handle control operations.

---

## 11. Embedding and Reranking

Current bge-m3 remains local baseline.

Potential Qwen3 embedding/reranking profiles are optional.

A profile becomes production-eligible only after retrieval benchmarks prove improvement on Reverend repository/memory queries.

Metrics:

~~~text
Hit@K
MRR
Task success after retrieval
latency
GPU/CPU cost
index size
~~~

Derived vector indexes remain reconstructible state.

---

## 12. Verifier Diversity

Cross-family verifier routing is a benchmarked option, not a mandatory architecture rule.

A ModelRequirement can contain:

~~~json
{
  "independence_from_model_family": "qwen"
}
~~~

only when the workflow explicitly requests independent family diversity and an eligible alternative exists.

If no eligible alternative exists:

- deterministic verification still runs;
- policy decides whether same-family LLM assurance is acceptable;
- do not fake independence.

---

## 13. Reasoning Effort

Reasoning effort is per Job.

DeploymentProfile advertises supported levels.

Model Router selects based on:

- Specialist requirement;
- Task complexity;
- prior failure/escalation;
- budget;
- benchmark evidence.

Example policy:

~~~text
CONTROL             → low
routine engineering → medium
difficult repair    → high
architecture        → high
escalation          → max where supported
~~~

Do not use maximum reasoning on every call.

---

## 14. Context Profiles

Cloud v1 baseline maximum:

~~~text
64K
~~~

128K may be admitted only for a DeploymentProfile with:

- measured VRAM fit;
- acceptable throughput;
- ReverendBench evidence that the extra context improves relevant Tasks.

Greater than 128K requires a separate profile and explicit benchmark evidence.

A5/D3 selective context remains primary.

---

## 15. Context Admission vs Model Maximum

A model advertising 256K or 1M does not make those windows production defaults.

The compiler requests:

~~~text
required effective context
~~~

not:

~~~text
maximum model context
~~~

If the Task can succeed with 32K/64K selected context, larger prefill/KV cost is avoided.

---

## 16. Quantization Admission

Every quantized variant is a separate DeploymentProfile.

Promotion requires:

- deterministic benchmark pass;
- role-specific ReverendBench success;
- verification-success comparison;
- human-intervention comparison;
- memory/context reliability;
- tool-call/structured-output reliability;
- cost improvement.

A quantized model is not equivalent to its native profile merely because the model name is identical.

---

## 17. 48 GB Cost-Down Experiment

A11 accepts this as first optimization target.

Candidate hardware/model combinations:

~~~text
RTX A6000 48 GB
+
validated quantized Qwen3.8-27B

or

North Mini Code

or

Nemotron 3.5 Lightning
~~~

The profile remains BENCHMARKING until promotion criteria pass.

No scheduler fallback may use it for PRIMARY_ENGINEERING before eligibility is granted.

---

## 18. Premium Profile

RTX Pro 6000 96 GB is optional.

Promotion/use cases require measured value from:

- larger context/KV headroom;
- higher concurrency;
- faster verified completion;
- multimodal workload;
- asset-generation flexibility.

A higher hourly rate is acceptable only when total verified-task cost or mandatory capability improves.

---

## 19. Frontier Escalation

Frontier-scale open models remain optional benchmark/escalation resources.

Potential external API models are represented as DeploymentProfiles with:

~~~text
trust_class = EXTERNAL_API
~~~

Context Broker filters sensitive material before routing.

External API escalation must never occur merely because local capacity is unavailable.

Trust policy and Project policy must explicitly allow it.

---

## 20. Runtime Request Contract

Worker-level InferenceRequest:

~~~json
{
  "invocation_id": "...",
  "job_id": "...",
  "agent_instance_id": "...",
  "deployment_profile_id": "...",
  "context_manifest_id": "...",
  "prompt_ref": "...",
  "output_budget_tokens": 4096,
  "temperature": 0.0,
  "reasoning_effort": "high",
  "structured_output_schema": null,
  "timeout_seconds": 900
}
~~~

The prompt may be transferred as encrypted/bounded payload or short-lived Artifact reference according to worker protocol.

No secret values are embedded.

---

## 21. Runtime Response Contract

~~~json
{
  "invocation_id": "...",
  "status": "complete",
  "model_revision": "...",
  "runtime_version": "...",
  "prompt_tokens": 50120,
  "generated_tokens": 3400,
  "finish_reason": "stop",
  "output_ref": "...",
  "metrics": {
    "queue_wait_seconds": 0.1,
    "provider_seconds": 34.2
  }
}
~~~

Raw private reasoning fields are discarded/sanitized before durable persistence.

---

## 22. Cancellation

InferenceRuntime must support bounded cancellation where runtime allows.

Cancellation semantics:

- marks invocation interrupted;
- does not claim model-level exact resume;
- recovery restarts from prior durable Agent/tool state.

Partial text may be retained only when a Specialist-specific continuation contract explicitly allows it.

---

## 23. Model Download and Integrity

Production profile pins:

- model repository;
- revision/commit;
- required files;
- expected checksums where available;
- license snapshot/reference.

Worker boot:

1. resolve pinned revision;
2. fetch/cache weights;
3. verify expected revision/checksums;
4. refuse unpinned latest drift;
5. expose loaded profile identity in health.

---

## 24. Runtime Image Integrity

DeploymentProfile pins container digest.

Do not use mutable latest tags in production.

A profile is invalid if:

- image digest differs;
- runtime version differs from validated profile;
- model revision differs;
- expected parser/tool support missing.

The worker registers exact runtime metadata.

---

## 25. ReverendBench Registry

Every benchmark scenario has:

~~~text
benchmark_id
version
class
domain
repository fixture/reference
objective
requirements
tool policy
acceptance checks
verification checks
budget
repeat count
sensitivity
~~~

Benchmark classes retain A1:

~~~text
B1 surgical
B2 feature
B3 subsystem
B4 full project
B5 evolving project
~~~

---

## 26. Model Bake-Off Controls

For model comparisons hold constant:

- SpecialistSpec version;
- Context Broker/Compiler version;
- Task;
- tool schemas/permissions;
- acceptance criteria;
- maximum budget;
- deterministic validation;
- verifier policy.

Record all changed deployment dimensions.

---

## 27. Benchmark Result Set

Persist:

~~~text
benchmark_result_set_id
deployment_profile_id
Reverend commit
SpecialistSpec versions
context compiler version
Task results
verification outcomes
human interventions
repair rounds
token usage
GPU lease time
provider billed time
estimated/actual cost
created_at
~~~

This is the evidence used by Model Registry eligibility.

---

## 28. Role Admission Gates

### PRIMARY_ENGINEERING

Must satisfy:

- deterministic acceptance threshold;
- independent verification threshold;
- bounded repair rate;
- structured/tool-call reliability;
- no material regression against baseline profile.

### ASSURANCE

Must satisfy:

- defect detection threshold;
- acceptable false positives;
- consistent acceptance-criteria adherence.

### CONTROL

Must satisfy:

- near-perfect schema validity;
- classification/routing correctness;
- meaningful latency/cost improvement.

Exact numeric thresholds are set when benchmark fixtures are finalized in C7/C9 and stored as versioned benchmark policy, not ad-hoc code constants.

---

## 29. Promotion Rule

A cheaper profile may replace baseline only if:

1. mandatory ReverendBench quality gates pass;
2. verification success stays within accepted tolerance;
3. human intervention stays within A1 target;
4. context/repository fit remains reliable;
5. license/trust pass;
6. measured cost per verified successful Task improves materially.

A more expensive profile may replace baseline only if it unlocks required capability or improves total verified-task economics.

---

## 30. Model Registry Update Process

Production model changes are controlled:

~~~text
discover
↓
record license/runtime evidence
↓
create BENCHMARKING ModelProfile/DeploymentProfile
↓
run ReverendBench
↓
review result
↓
promote ELIGIBLE
↓
scheduler may route
~~~

Disabling profile is immediate policy action.

Retiring does not delete historical benchmark/provenance records.

---

## 31. License Gate

Each ModelProfile records:

- license name;
- license source/ref;
- reviewed_at;
- allowed use classification;
- restrictions/notes.

Project policy can require:

- approved open license;
- commercial-use compatible;
- private-only;
- prohibited.

Do not infer legal eligibility solely from “open weights.”

---

## 32. Trust Gate

DeploymentProfile has trust class independent of model.

Same model could have:

~~~text
Qwen on Community RunPod
Qwen on dedicated Secure Cloud
Qwen on local worker
~~~

as separate DeploymentProfiles.

A sensitive Job can therefore choose a stronger infrastructure profile without changing Specialist semantics.

---

## 33. Observability

Per invocation expose:

- deployment profile;
- model revision;
- runtime version;
- reasoning effort;
- context tokens;
- output tokens;
- queue wait;
- setup/load time;
- provider/inference time;
- cost estimate;
- completion/failure reason.

Never expose hidden chain-of-thought.

---

## 34. D7 Acceptance Tests

Must prove:

- Specialist is not hard-bound to checkpoint;
- ineligible weaker model cannot silently satisfy stronger requirement;
- Community profile rejected for stronger trust requirement;
- quantized profile stays unavailable until promoted;
- model revision mismatch fails health/admission;
- runtime image mismatch fails profile validation;
- 128K profile cannot be used without explicit validation;
- disabled profile stops new routing;
- same Agent retry may route to alternative eligible model;
- benchmark result records enough provenance to reproduce comparison.

---

## 35. Exit Condition

D7/C7 is ready when one pinned Qwen/vLLM/A100 deployment profile can be registered, benchmarked, routed by capability, executed through D4, measured end-to-end, and later replaced by another profile without changing Agent or Task semantics.


---

## 36. Recursive Architecture Hardening — Registry Authority and Promotion Safety

### Durable registry authority

ModelProfile and DeploymentProfile production eligibility is persisted in the D1 PostgreSQL registry.

Configuration files may seed candidate profiles, but runtime routing reads the authoritative registry state.

A profile is routable only when both:

~~~text
ModelProfile.status = ELIGIBLE
AND
DeploymentProfile.status = ELIGIBLE
~~~

Historical Runs retain exact profile IDs, model revisions, runtime versions and image digests even after a profile is disabled or retired.

### Promotion is privileged and audited

A ReverendBench result can recommend promotion but can never autonomously promote itself.

Promotion, disable and retirement require a privileged human/system-administration command that:

1. references the BenchmarkResultSet;
2. checks license/trust policy;
3. records the actor;
4. records the exact before/after profile state;
5. emits a durable Event.

This prevents a compromised benchmark/model path from making itself production-eligible.

### Runtime identity attestation

Before a Job uses a DeploymentProfile, the worker-reported runtime identity must match the profile:

- model repository/name;
- pinned model revision;
- runtime implementation/version;
- container digest;
- quantization;
- served context limit.

Mismatch changes node/profile health to ineligible; it is not treated as a harmless metadata difference.

### Benchmark contamination guard

A candidate model must not receive hidden reference outputs, expected patches or verifier answers from ReverendBench fixtures through context, cache or Memory.

Benchmark execution uses isolated Project/Run scope and a clean context/index namespace where required.

### Routing reproducibility

Every routing decision persists:

~~~text
ModelRequirement
eligible profile set
rejection reasons
selected DeploymentProfile
router policy version
budget/trust inputs
~~~

This is bounded decision provenance, not hidden chain-of-thought.
