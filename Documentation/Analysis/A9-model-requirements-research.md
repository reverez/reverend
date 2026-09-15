# A9 — Model Requirements & Model Research

> **Programme:** Reverend Cloud Analysis  
> **Milestone:** A9  
> **Status:** ACCEPTED  
> **Owner:** Backend / systems track  
> **Research snapshot:** 2026-09-16  
> **Document purpose:** Derive Reverend's model capability requirements from A1–A6, research the current open/self-hostable frontier, define the model-admission process, and produce a benchmark shortlist without hard-coding permanent model identities into the architecture.  
> **Freshness warning:** Model releases, benchmark rankings, runtime support, quantizations, and licensing change quickly. The named models in this document are a dated research shortlist. The permanent architectural decision is the capability-based routing model, not the September 2026 names.

---

## 1. Executive Decision

Reverend must not encode:

```text
Researcher → Model X
Architect  → Model Y
Developer  → Model Z
Verifier   → Model Z
```

as permanent architecture.

The accepted model is:

```text
Specialist
   ↓
ModelRequirement
   ↓
eligible benchmarked ModelProfiles
   ↓
Model Router
   ↓
runtime / compute placement
   ↓
resolved model for this Job
```

A Specialist asks for **capability**.

A9 defines which current models deserve benchmarking against those capability requirements.

A10 determines which candidate deployment profiles are physically practical.

A11 determines which profiles are economically justified.

---

## 2. Why Model Selection Happens After A1–A6

The analysis deliberately postponed model selection.

Before A9, the system already knew:

```text
A1 — what Reverend must accomplish
A3 — what one Agent is
A4 — how Agents form Teams
A5 — how information/context behaves
A6 — how logical work maps onto finite compute
```

That means model research can now answer:

> **Which models actually satisfy Reverend's workloads?**

rather than:

> **Which model is currently popular?**

This order prevents the entire architecture from being designed around a temporary checkpoint.

---

## 3. Benchmark Landscape Relevant to Reverend

Generic conversational leaderboards are insufficient for Reverend.

The system needs evidence on:

- long-horizon repository engineering;
- terminal/tool use;
- repository understanding;
- coding;
- reasoning;
- structured output;
- multimodal engineering;
- scientific reasoning;
- cost and latency.

A particularly relevant current independent source is Artificial Analysis' **Coding Agent Index v1.5**.

As of the research snapshot, it equally combines:

```text
DeepSWE v1.1
113 long-horizon software-engineering tasks

Terminal-Bench 4.0
66 terminal / systems / engineering tasks

SWE-Atlas-QnA
124 repository-understanding questions
```

Each benchmark is evaluated with repeated attempts and task-specific verification.

This is significantly closer to Reverend's intended B2–B5 workload than isolated function-generation benchmarks.

---

## 4. Current Independent Open-Weight Frontier Snapshot

Artificial Analysis Intelligence Index v4.3 uses category weights of:

```text
Agents                30%
Coding                20%
General Intelligence  30%
Scientific Reasoning  20%
```

Its September 2026 landscape shows that the open-weight frontier has moved substantially beyond the models used in Reverend's original local deployment.

Representative current independent scores:

| Model / effort | AA Intelligence Index | Architectural interpretation |
|---|---:|---|
| GLM-5.3 (max) | 45 | frontier text reasoning / engineering control candidate |
| Kimi K3 (max) | 44 | frontier multimodal / long-context candidate |
| Qwen3.8 2.4T-A95B | 40 | enormous frontier Qwen reference |
| DeepSeek V4 Pro 0813 (max) | 36 | frontier/open engineering reasoning |
| DeepSeek V4 Flash 0731 (max) | 35 | strong but much smaller active footprint |
| Qwen3.8-27B (xhigh) | 34 | unusually strong practical-size dense workhorse |

These scores are useful **discovery evidence**, not automatic production selections.

The key lesson is:

> Reverend's existing `qwen3-coder:30b + deepseek-r1:8b` local fleet should be treated as a historical baseline, not a cloud target.

---

## 5. Public Benchmark Scores Are Not Final Authority

A model benchmark result is partly a property of:

```text
model
+
agent harness
+
prompting
+
tool interface
+
context strategy
+
time/token budget
+
runtime configuration
```

Reverend itself is an agent harness.

Therefore public benchmarks should be used to:

1. discover candidates;
2. eliminate obviously weak candidates;
3. understand model specialization;
4. establish quality controls.

Production role eligibility must come from **ReverendBench** using Reverend's own tools, context engine, specialist methodologies, and independent verification.

---

## 6. ModelRequirement

A9 replaces direct specialist-to-checkpoint thinking with capability requirements.

Conceptually:

```text
ModelRequirement
├── reasoning_quality
├── coding_quality
├── repository_reasoning
├── agentic_tool_use
├── instruction_following
├── structured_output
├── vision_requirement
├── context_requirement
├── latency_class
├── throughput_class
├── trust_requirement
├── runtime requirement
├── license / deployment constraints
└── cost ceiling
```

The exact scoring/enum system belongs to Design.

---

## 7. ModelProfile

Each deployable model configuration should eventually advertise:

```text
ModelProfile
├── model family / revision
├── capabilities
├── modalities
├── useful context range
├── structured-output support
├── tool-use support
├── runtime support
├── trust / deployment class
├── license metadata
├── benchmark provenance
├── quantization
├── hardware profile
├── latency / throughput
└── cost profile
```

This allows the Model Router to match:

```text
requirement
↔
eligible deployment profiles
```

---

## 8. Logical Model Capability Classes

A9 recommends maintaining capability-oriented routing classes such as:

```text
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
```

These are **routing profiles**, not Agent identities.

A single physical model may satisfy several profiles.

---

## 9. CONTROL Requirement

Typical workloads:

- routing;
- intent classification;
- schema filling;
- small structured decisions;
- simple orchestration assistance;
- cheap low-risk transformations.

Requirements:

```text
very low latency
low cost
small footprint
high structured-output reliability
good instruction following
basic tool awareness
modest context requirement
```

The CONTROL role should not consume frontier inference if a tiny model meets the task threshold.

---

## 10. CONTROL Candidate — MiniCPM5-2B

Current official release evidence:

```text
model:
openbmb/MiniCPM5-2B

size:
2B class

license:
Apache 2.0

positioning:
long-context / tool-calling / on-device / edge agent workloads
```

This makes MiniCPM5-2B a strong candidate for:

- classification;
- routing;
- structured small tasks;
- low-cost control-plane assistance.

### A9 classification

```text
CONTROL candidate
```

It should be benchmarked against Reverend's existing small Qwen baseline rather than assumed superior.

---

## 11. Lightweight Multimodal Control Candidate

Qwen's small multimodal family remains relevant for:

```text
routing
+
lightweight screenshot/image understanding
+
simple general inference
```

The specific model version should be revalidated at implementation time.

The architectural point is that Reverend may not need a separate heavyweight vision service for every small visual task.

---

## 12. FAST_GENERAL Requirement

Typical workloads:

- research scouting;
- summarization;
- artifact synthesis;
- memory proposals;
- simple review;
- low-risk interpretation;
- broad Team support.

Requirements:

```text
high throughput
reasonable reasoning
good structured output
useful context
low cost per call
tool friendliness
```

This profile may receive many calls in swarms, so efficiency matters significantly.

---

## 13. FAST_GENERAL Candidate — Nemotron 3.5 Lightning

Current official NVIDIA release:

```text
NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4

total parameters:
30B

active parameters:
3B

architecture:
hybrid MoE / Mamba-2 / attention

context:
up to 1M tokens

single-GPU deployment:
validated on supported NVIDIA hardware

runtime:
official vLLM recipe

license:
OpenMDW 1.1
```

The current NVFP4 repository is approximately:

```text
21.6 GB
```

This makes Nemotron particularly interesting as:

- high-throughput sub-agent model;
- FAST_GENERAL candidate;
- potentially efficient Agent Team workhorse;
- long-context experimental candidate.

### Important correction

Nemotron is **not Apache 2.0** in this current release.

Its OpenMDW-1.1 license must be reviewed as part of model admission.

---

## 14. FAST_ENGINEERING Requirement

Typical workloads:

- repository localization;
- small-to-medium patches;
- straightforward feature implementation;
- test generation;
- migration work;
- code explanation;
- routine repair.

Requirements:

```text
strong coding
repository understanding
good terminal/tool use
structured patches
useful context
lower cost than deep/frontier inference
```

---

## 15. FAST_ENGINEERING Candidate — North Mini Code

Cohere's North Mini Code was released specifically for agentic software engineering.

Current official positioning:

```text
30B total parameters
3B active parameters
Mixture-of-Experts
Apache 2.0
agentic software-engineering focus
terminal-oriented development workflows
```

Cohere's published material reports strong performance against similarly sized open models on coding-agent tasks.

This makes North Mini Code particularly relevant because its training target resembles Reverend's work more closely than generic chat models.

### A9 classification

```text
FAST_ENGINEERING candidate
```

---

## 16. Practical Workhorse Candidate — Qwen3.8-27B

Qwen3.8-27B is one of the most important A9 findings.

Current official characteristics include:

```text
27B dense model
Apache 2.0
image + text input
official vLLM support
official SGLang support
```

Current Artificial Analysis snapshot:

```text
Qwen3.8-27B (xhigh)
Intelligence Index: 34
context: 256K
```

That is exceptionally strong relative to its physical scale.

### Why it matters to Reverend

One practical model family may be able to cover:

```text
FAST_ENGINEERING
PRIMARY_ENGINEERING
VISION
moderate/deep reasoning
repository understanding
```

depending on ReverendBench.

### A9 classification

> **Highest-priority practical workhorse candidate.**

Not a permanent winner.

---

## 17. PRIMARY_ENGINEERING Requirement

This is Reverend's most strategically important language-model profile.

Workloads:

```text
large multi-file features
complex refactors
repository-scale implementation
C / C++
CUDA
Python
backend systems
frontend systems
integration
test repair
build-system work
```

Requirements:

- excellent code generation;
- repository-scale understanding;
- long-horizon tool use;
- strong debugging;
- reliable structured output;
- tool-call accuracy;
- context discipline;
- low hallucination about repository state;
- high success under iterative verification.

The strongest conversational model is not automatically the strongest PRIMARY_ENGINEERING model.

---

## 18. PRIMARY_ENGINEERING Shortlist

High-priority candidates:

```text
Qwen3.8-27B
North Mini Code
DeepSeek V4 Flash
```

with frontier controls such as:

```text
GLM-5.3
Kimi K3
DeepSeek V4 Pro
```

used to estimate the quality ceiling.

---

## 19. DEEP_REASONING Requirement

Used by roles such as:

- Systems Architect;
- Research Synthesizer;
- Failure Investigator;
- Product Strategist;
- Adjudicator;
- difficult scientific reasoning.

Requirements:

```text
strong multi-step reasoning
long-horizon coherence
alternative comparison
structured output
tool awareness
large effective context
evidence sensitivity
```

Coding quality remains useful, but this profile is broader than coding.

---

## 20. Deep/Stretch Candidate — DeepSeek V4 Flash 0731

Current official release evidence:

```text
DeepSeek-V4-Flash-0731
MIT license
FP8 release
vLLM support
```

Current independent Artificial Analysis snapshot:

```text
284B total
13B active
1M context
AA Intelligence Index: 35
~200 output tokens/s across evaluated providers
```

This creates an interesting position:

```text
much stronger than small models
much larger than 27–30B workhorses
much smaller active footprint than huge frontier MoEs
```

### A9 classification

```text
DEEP / STRETCH candidate
```

A10 determines whether self-hosting is physically reasonable.

---

## 21. Frontier Control — GLM-5.3

Current independent snapshot:

```text
GLM-5.3 (max)
AA Intelligence Index: 45
context: 1M
753B total
40B active
text input
open weights
custom GLM-5.3 license
```

This currently represents the top end of open-weight general intelligence on Artificial Analysis.

However, its physical footprint and license make it a **frontier control**, not an automatic Cloud v1 dependency.

### A9 classification

```text
MAX_QUALITY / FRONTIER CONTROL
```

---

## 22. Frontier Control — Kimi K3

Current independent snapshot:

```text
Kimi K3 (max)
AA Intelligence Index: 44
2.8T total
104B active
1M context
text + image input
open weights
```

Its Kimi Code deployment also performs strongly on long-horizon software-engineering benchmarks.

Kimi is highly relevant for determining the quality ceiling, but its parameter/storage scale makes permanent private self-hosting a major infrastructure decision.

### A9 classification

```text
FRONTIER MULTIMODAL / ENGINEERING CONTROL
```

---

## 23. DeepSeek V4 Pro

DeepSeek V4 Pro remains relevant as a frontier engineering/reasoning control.

Current independent data shows a stronger overall Intelligence Index than the Flash variant but at significantly larger physical scale.

It should be used to answer:

> How much verified engineering quality is Reverend leaving on the table by using a smaller practical workhorse?

not:

> Which model should always run?

---

## 24. Very Large Qwen Frontier Models

Qwen's enormous frontier variants remain useful quality references.

However, the existence of a high benchmark score does not imply that the model belongs in Reverend's default physical fleet.

A10 evaluates the storage/VRAM consequences.

### A9 classification

```text
FRONTIER CONTROL
```

unless deployment evidence shows an unusually favorable path.

---

## 25. Failure Investigation Requirement

Failure Investigation is a distinct cognitive workload.

It requires:

```text
code understanding
reasoning
terminal use
log/trace analysis
hypothesis generation
evidence-driven elimination
root-cause localization
```

A candidate may be excellent at implementation but mediocre at root-cause analysis.

Therefore this profile must be benchmarked independently.

Candidates include:

```text
Qwen3.8-27B
DeepSeek V4 Flash
frontier control model
```

---

## 26. Assurance / Verifier Requirement

Verifier capability needs:

- strong repository comprehension;
- acceptance-criteria discipline;
- subtle defect detection;
- structured verdicts;
- skepticism toward implementer claims;
- stable evidence use;
- low false-positive rate.

A verifier should not be selected merely because it is the same model already resident for development.

---

## 27. Cross-Family Verification Hypothesis

A4/A5 established independent assurance.

A9 carries the following hypothesis:

> **Developer and Verifier may benefit from different model families to reduce correlated failure.**

Example experimental pairing:

```text
Developer:
Qwen family

Verifier:
DeepSeek family
```

or the reverse.

This is not frozen policy.

ReverendBench must determine whether the independence benefit is worth:

- additional model storage;
- model loading;
- runtime complexity;
- cost.

---

## 28. VISION Requirement

Visual capability is important for:

```text
frontend screenshots
UI regression
design references
plots
scientific visualization
diagrams
document screenshots
```

Reverend should not automatically introduce a separate large vision model.

If the practical engineering workhorse already satisfies visual tasks, model consolidation may be economically superior.

Current practical direction:

```text
small multimodal model
→ lightweight visual work

Qwen3.8-27B
→ engineering-grade multimodal work

Kimi K3
→ frontier visual control
```

---

## 29. Embedding Requirement

Embedding is not a reasoning role.

Required uses include:

- repository retrieval;
- artifact retrieval;
- Project Memory retrieval;
- research retrieval.

Important properties:

```text
text/code semantics
batch throughput
context length
embedding dimension
multilingual support where useful
license
deployment cost
```

Current `bge-m3` remains an excellent baseline.

A9 requires benchmarking newer Qwen3 Embedding models.

---

## 30. Qwen3 Embedding Family

Current official family:

| Model | Context | Embedding dimension | Notes |
|---|---:|---:|---|
| Qwen3-Embedding-0.6B | 32K | 1024 | MRL + instruction aware |
| Qwen3-Embedding-4B | 32K | 2560 | MRL + instruction aware |
| Qwen3-Embedding-8B | 32K | 4096 | MRL + instruction aware |

License:

```text
Apache 2.0
```

The smallest model that reaches Reverend's retrieval-quality threshold should win.

Do not assume 8B is worth its recurring inference cost.

---

## 31. Reranking Requirement

A5's retrieval architecture benefits from a two-stage pattern:

```text
cheap candidate retrieval
        ↓
strong bounded reranking
```

Qwen3 Reranker currently provides:

```text
0.6B
4B
8B
32K context
100+ languages
instruction-aware ranking
Apache 2.0
```

Again, use the smallest model that satisfies quality requirements.

---

## 32. Media Generation Requirement

Media generation is a separate production capability.

A language model should not become an image generator merely to simplify the architecture.

### Initial image candidate — FLUX.2 Klein 4B FP8

Current official release:

```text
4B-class
FP8 checkpoint ~4.07 GB
Apache 2.0
text-to-image
image editing
```

This is a reasonable first production-asset candidate.

Video, audio, and 3D model selection remain deferred until those capabilities enter Design.

---

## 33. Minimum Sufficient Model Fleet

A4 established minimum sufficient Team.

A9 applies the same principle to models.

Reverend does **not** need:

```text
one permanent model per Specialist
```

A practical initial physical fleet may contain only:

```text
small control model
one primary engineering workhorse
one deep / independent escalation path
embedding model
reranker
optional asset model
```

Many Specialists can share the same workhorse through different methodologies, context policies, and authority profiles.

---

## 34. Candidate Tiers

### Tier S — Small Control

```text
MiniCPM5-2B
small Qwen multimodal candidate
```

### Tier W — Practical Workhorse

```text
Qwen3.8-27B
North Mini Code
Nemotron 3.5 Lightning
```

### Tier D — Deep / Stretch

```text
DeepSeek V4 Flash
```

### Tier F — Frontier Controls

```text
GLM-5.3
Kimi K3
DeepSeek V4 Pro
very large Qwen variants
```

The frontier tier establishes the quality ceiling.

It does not automatically belong in always-on infrastructure.

---

## 35. Preliminary Role-to-Candidate Matrix

This table is a **benchmark shortlist**, not a fixed routing configuration.

| Requirement | Priority candidates |
|---|---|
| CONTROL | MiniCPM5-2B; small Qwen |
| FAST_GENERAL | Nemotron 3.5 Lightning; small control model where sufficient |
| FAST_ENGINEERING | North Mini Code; Qwen3.8-27B |
| PRIMARY_ENGINEERING | Qwen3.8-27B; DeepSeek V4 Flash |
| ARCHITECT | Qwen3.8-27B; DeepSeek V4 Flash; GLM frontier control |
| RESEARCH SYNTHESIS | DeepSeek V4 Flash; GLM frontier control |
| FAILURE INVESTIGATOR | Qwen3.8-27B; DeepSeek V4 Flash |
| VERIFIER | Qwen3.8-27B / DeepSeek V4 Flash cross-family experiments |
| MAX QUALITY | GLM-5.3; Kimi K3 |
| VISION | practical Qwen multimodal; Qwen3.8-27B; Kimi control |
| EMBEDDING | Qwen3 Embedding family |
| RERANK | Qwen3 Reranker family |
| IMAGE ASSET | FLUX.2 Klein 4B |

---

## 36. Highest-Priority Reverend Bake-Off

If the model search space needs to be reduced to a manageable first evaluation set:

```text
MiniCPM5-2B
North Mini Code
Qwen3.8-27B
Nemotron 3.5 Lightning
DeepSeek V4 Flash
GLM-5.3
Kimi K3
```

This spans:

```text
tiny control
coding specialist
practical dense workhorse
efficient MoE workhorse
stretch reasoning
frontier text
frontier multimodal
```

without benchmarking dozens of near-duplicate models.

---

## 37. ReverendBench-Engineering

A9 requires a Reverend-owned benchmark suite.

Recommended initial size:

```text
~30–40 representative Tasks
```

Suggested distribution:

```text
6  B1 surgical bug fixes
6  B2 multi-file features
4  repository localization / architecture questions
4  Python/backend tasks
4  C++ / systems tasks
3  CUDA/scientific tasks
3  frontend/full-stack tasks
3  difficult failure-investigation tasks
3  research/architecture synthesis tasks
4+ B4/B5 project/evolving-project tasks
```

Actual Reverend/AstraFlow historical tasks should be included where licensing/privacy permits.

---

## 38. Controlled Benchmark Method

For each model comparison, hold constant:

```text
Task
requirements
toolset
Specialist methodology
Context Broker
Context Compiler
tool permissions
maximum budget
verification harness
```

Only the model/deployment profile should change.

For stochastic difficult Tasks, use repeated trials.

---

## 39. Core Benchmark Metrics

Measure at least:

```text
Task success
acceptance-criteria pass rate
deterministic test pass
independent verifier acceptance
repair rounds
tool-call validity
structured-output validity
human correction required
wall-clock time
input tokens
output tokens
GPU seconds
peak VRAM
RAM
context usage
monetary cost
```

Primary system-level economic metric:

> **£ per verified successful engineering Task**

A11 supplies the accounting mechanics.

---

## 40. Role-Specific Metrics

A single aggregate score should not choose every role.

### CONTROL

Measure:

```text
structured accuracy
latency
cost
```

### Developer

Measure:

```text
verified implementation success
repair count
regressions
```

### Verifier

Measure:

```text
true defect detection
false positives
missed defects
```

### Embedding

Measure:

```text
Hit@K
MRR
task retrieval success
latency
```

### Reranker

Measure:

```text
ranking quality
incremental retrieval gain
latency
cost
```

Different roles can therefore have different Pareto-optimal models.

---

## 41. Quantization Is Part of the Model Configuration

Production comparison must be:

```text
model
+
quantization
+
runtime
+
context
+
hardware
```

Example:

```text
Qwen3.8-27B FP8 on GPU A
```

and:

```text
Qwen3.8-27B 4-bit on GPU B
```

are different benchmark configurations.

A quantization is not production-eligible simply because it reduces VRAM.

---

## 42. Context Must Be Benchmarked

A5 established that context is a budget.

A9 therefore does not make:

```text
1M context
```

a procurement requirement merely because some models advertise it.

Useful initial benchmark envelopes:

| Model profile | Context to test |
|---|---:|
| CONTROL | 8–32K |
| FAST_GENERAL | 16–64K |
| FAST_ENGINEERING | 32–128K |
| PRIMARY_ENGINEERING | 64–256K |
| ARCHITECT | 64–256K |
| RESEARCH SYNTHESIS | 64–256K |
| VERIFIER | 64–256K |

If selective retrieval performs equally well at 64K vs 1M, the smaller context probably wins economically.

---

## 43. Model-Family Diversity vs Consolidation

There is a real trade-off.

### Diversity can provide

- independent blind spots;
- stronger verifier independence;
- alternative reasoning behavior.

### Consolidation can provide

- shared model residency;
- lower storage;
- fewer cold loads;
- better batching;
- simpler operations;
- easier benchmarking.

A9 therefore accepts:

> **Minimum sufficient model diversity.**

Cross-family routing must earn its complexity through benchmarked quality gain.

---

## 44. Preliminary Fleet Hypothesis

The following is a hypothesis for A10/A11 evaluation:

```text
CONTROL
MiniCPM5-2B

PRIMARY WORKHORSE / VISION
Qwen3.8-27B

FAST CODING CANDIDATE
North Mini Code

HIGH-THROUGHPUT CANDIDATE
Nemotron 3.5 Lightning

DEEP / INDEPENDENT ESCALATION
DeepSeek V4 Flash

EMBED
Qwen3 Embedding

RERANK
Qwen3 Reranker

IMAGE
FLUX.2 Klein 4B
```

Frontier models such as:

```text
GLM-5.3
Kimi K3
```

serve as quality controls and optional escalation candidates.

This is **not** an accepted deployment fleet.

---

## 45. Licensing Is a First-Class Admission Criterion

A technically excellent model may still be unsuitable.

Current shortlist examples:

### Apache 2.0

```text
MiniCPM5-2B
Qwen3.8-27B
North Mini Code
Qwen3 Embedding
Qwen3 Reranker
FLUX.2 Klein 4B
```

### MIT

```text
DeepSeek V4 Flash
DeepSeek V4 Pro
```

### Custom / review required

```text
NVIDIA Nemotron 3.5 Lightning — OpenMDW 1.1
GLM-5.3 — GLM-specific license
Kimi K3 — Kimi-specific license
```

License metadata belongs in the Model Registry.

---

## 46. Self-Hostability Is More Than “Open Weights”

Production admission also requires:

- supported runtime;
- stable model loading;
- required tool-call parser;
- context configuration;
- quantization path;
- hardware fit;
- measurable throughput;
- reproducible container/runtime version.

A weight file alone does not make a model operationally suitable.

---

## 47. Model Admission Pipeline

Canonical future process:

```text
MODEL DISCOVERED
      ↓
license acceptable?
      ↓
required modalities/capabilities?
      ↓
supported runtime?
      ↓
Reverend role benchmark passes?
      ↓
hardware feasible?
      ↓
cost acceptable?
      ↓
REGISTER AS ELIGIBLE
```

Popularity is not admission.

---

## 48. Benchmark Provenance

Every eligible deployment profile should record:

```text
benchmark date
benchmark suite version
model revision
runtime version
quantization
context
hardware
role eligibility
quality metrics
cost metrics
```

This enables periodic fleet refresh without changing Agent architecture.

---

## 49. Current Reverend Model Migration

| Current local model role | A9 direction |
|---|---|
| FAST_GENERAL / ROUTER — qwen3.5:4b | old baseline; replace through bake-off |
| FAST_CODE — qwen2.5-coder:7b | replace |
| STRONG_CODE — qwen3-coder:30b | replace through modern engineering bake-off |
| DEEP_REASON / CRITIC — deepseek-r1:8b | replace |
| EMBED — bge-m3 | keep as retrieval baseline |
| fixed Specialist→ModelRole | replace semantically with ModelRequirement |
| one-model-per-role | reject |
| strongest-model-everywhere | reject |

---

## 50. A9 Research Sources

The research snapshot used the following current sources.

### Independent benchmark sources

- Artificial Analysis — *Intelligence Index v4.3*  
  `https://artificialanalysis.ai/articles/artificial-analysis-intelligence-index-v4-3`

- Artificial Analysis — *Coding Agent Index v1.5 Methodology*  
  `https://artificialanalysis.ai/methodology/coding-agents-benchmarking`

- Artificial Analysis — Qwen3.8-27B  
  `https://artificialanalysis.ai/models/qwen3-8-27b`

- Artificial Analysis — Kimi K3  
  `https://artificialanalysis.ai/models/kimi-k3`

- Artificial Analysis — GLM-5.3  
  `https://artificialanalysis.ai/models/glm-5-3`

- Artificial Analysis — DeepSeek V4 Flash  
  `https://artificialanalysis.ai/models/deepseek-v4-flash`

### Official model sources

- Qwen3.8-27B  
  `https://huggingface.co/Qwen/Qwen3.8-27B`

- North Mini Code introduction  
  `https://huggingface.co/blog/CohereLabs/introducing-north-mini-code`

- NVIDIA Nemotron 3.5 Lightning NVFP4  
  `https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4`

- DeepSeek V4 Flash  
  `https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash-0731`

- MiniCPM5-2B  
  `https://huggingface.co/openbmb/MiniCPM5-2B`

- Qwen3 Embedding  
  `https://huggingface.co/Qwen/Qwen3-Embedding-0.6B`

- Qwen3 Reranker  
  `https://huggingface.co/Qwen/Qwen3-Reranker-0.6B`

- FLUX.2 Klein 4B FP8  
  `https://huggingface.co/black-forest-labs/FLUX.2-klein-4b-fp8`

All source-dependent numbers should be refreshed before production selection.

---

## 51. Frozen A9 Requirements

```text
A9-01
Specialists request capabilities rather than specific models.

A9-02
Model selection occurs through benchmarked ModelRequirements.

A9-03
Public leaderboards are discovery/filtering evidence, not production authority.

A9-04
Reverend-specific verified-task benchmarks determine final role eligibility.

A9-05
The fleet uses the minimum sufficient number of model families.

A9-06
Small high-frequency Tasks use small models when quality thresholds permit.

A9-07
The strongest model is reserved for Tasks where expected quality gain justifies cost.

A9-08
Primary engineering models are judged principally on repository-scale agentic engineering.

A9-09
Verifier models are benchmarked independently from Developer models.

A9-10
Cross-family Developer/Verifier diversity remains a benchmarked hypothesis.

A9-11
Advertised maximum context is not a procurement requirement.

A9-12
Model/runtime/precision/context/hardware form one benchmark configuration.

A9-13
Quantized deployments require independent quality validation.

A9-14
Licensing is a model-admission criterion.

A9-15
Self-hostability and supported runtimes are admission criteria.

A9-16
Model profiles record reasoning, coding, tool use, structure, modality, context, trust, and deployment capability.

A9-17
Vision may be supplied by the primary workhorse if economical.

A9-18
Embedding and reranking remain specialized model roles.

A9-19
Media generation remains separate production capability.

A9-20
Model selection remains replaceable over Reverend's lifetime.

A9-21
Every production deployment profile stores benchmark provenance.

A9-22
The primary optimization target is verified engineering work, not raw benchmark score or tokens/second.
```

---

## 52. Design-Phase Implications

The Design Phase must define concrete contracts for:

- `ModelRequirement`;
- `ModelProfile`;
- role eligibility;
- benchmark provenance;
- deployment-profile identity;
- runtime capability metadata;
- model/routing fallbacks;
- quality-degradation policy;
- cross-family verification experiments;
- ReverendBench runner and result storage;
- license metadata;
- model admission/removal.

No Specialist should contain a hard-coded production checkpoint.

---

## 53. A9 Decision Record

```text
MILESTONE:
A9 — Model Requirements & Model Research

STATUS:
ACCEPTED

PERMANENT MODEL ARCHITECTURE:
Capability requirements
→ eligible benchmarked ModelProfiles
→ runtime / compute placement.

HIGH-PRIORITY PRACTICAL CANDIDATES:
MiniCPM5-2B
North Mini Code
Qwen3.8-27B
Nemotron 3.5 Lightning

DEEP / STRETCH:
DeepSeek V4 Flash

FRONTIER CONTROLS:
GLM-5.3
Kimi K3
DeepSeek V4 Pro
very large Qwen variants

RETRIEVAL:
Qwen3 Embedding
Qwen3 Reranker
with bge-m3 retained as baseline.

IMAGE:
FLUX.2 Klein 4B.

SELECTION METHOD:
ReverendBench
+ verified engineering success
+ hardware feasibility
+ runtime stability
+ licensing
+ cost.

PRIMARY METRIC:
£ per verified successful engineering Task.

PERMANENT RULE:
No model name becomes part of Reverend's cognitive architecture.
```
