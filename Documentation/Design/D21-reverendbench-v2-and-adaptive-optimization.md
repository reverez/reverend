# D21 — ReverendBench v2 & Adaptive Optimization

> **Status:** DESIGN ACCEPTED FOR DEVELOPMENT  
> **Depends on:** A1, A9, A11, D7, __D20__–D20  
> **Purpose:** Expand ReverendBench from model/runtime validation into the evidence system used to choose models, retrieval methods, context policies, Team structures, worker/cache policies and capability implementations.

---

## 1. Primary Objective

> **Optimize verified engineering outcomes, not subsystem vanity metrics.**

Primary economic metric:

~~~text
GBP per verified successful engineering Task
~~~

Promotion still uses a multidimensional quality gate.

---

## 2. What ReverendBench Must Evaluate

~~~text
Models
DeploymentProfiles
reasoning effort
context size
Context Broker policies
repository retrieval
web/research acquisition
embedding/reranking
Agent methodologies
AgentTeam strategies
parallelism
browser workflows
CPU/GPU placement
cache/idle policy
recovery behavior
verification strategies
~~~

Subsystem benchmarks matter only when connected to Task/project outcomes.

---

## 3. Benchmark Families

Retain:

~~~text
B1 surgical
B2 feature
B3 subsystem
B4 full project
B5 evolving project
~~~

Add capability families:

~~~text
R1   research/evidence acquisition
RI1  repository intelligence/localization
C1   context compilation/retrieval
T1   Team/swarm organization
W1   browser/frontend workflows
X1   execution/worker placement
E1   ephemeral-worker/recovery economics
S1   security/adversarial capability use
M1   memory/knowledge reuse
~~~

Capability cases can be embedded inside B1–B5 Projects.

---

## 4. Controlled Experiment Rule

When comparing one factor, hold others stable where possible.

Example model bake-off:

~~~text
same Task
same SpecialistSpec
same Context policy
same tools
same acceptance
same budget
same verifier policy
different DeploymentProfile
~~~

Example context bake-off:

~~~text
same model
same Task
same RepositorySnapshot
different retrieval/context policy
~~~

Do not claim a model won if it also received materially better tools/context.

---

## 5. Benchmark Result

~~~text
BenchmarkResult
├── scenario/version
├── Reverend commit
├── fixture hash
├── Specialist versions
├── Team strategy
├── Model/Deployment profiles
├── Context policy/compiler
├── Repository Intelligence version
├── Research policy/providers
├── tools/capabilities
├── resource profile
├── acceptance/verification result
├── human intervention
├── repair rounds
├── wall time
├── tokens
├── resource seconds
├── provider cost
└── Artifact/evidence refs
~~~

---

## 6. Success Hierarchy

Promotion order:

1. correctness / deterministic acceptance;
2. security / integrity;
3. requirement satisfaction;
4. independent verification;
5. robustness;
6. human intervention;
7. maintainability;
8. latency;
9. GBP.

A cheap profile that fails acceptance is not economically superior.

---

## 7. Repository Intelligence Benchmarks

Measure:

- target-file localization;
- symbol Hit@K/MRR;
- reference precision/recall;
- affected-test recall;
- diagnostic usefulness;
- context tokens;
- final coding success.

Compare:

~~~text
legacy Python AST/lexical
Tree-sitter structural
LSP/type service
semantic embeddings
hybrid combinations
~~~

---

## 8. Research Benchmarks

Measure:

- evidence coverage;
- primary/official-source rate;
- citation/source correctness;
- contradiction detection;
- freshness;
- unsupported-claim rate;
- search/fetch/browser calls;
- bytes/time;
- model synthesis calls;
- downstream decision quality.

Compare:

~~~text
single Research Agent
vs partitioned Research Team

static fetch only
vs static + browser escalation

fresh acquisition
vs cached evidence reuse
~~~

---

## 9. Context Benchmarks

Compare:

~~~text
legacy broad context
authority-first Context Broker
32K
64K
128K
exact-only
hybrid retrieval
iterative ContextRequest
~~~

Measure:

- required-fact recall;
- irrelevant-token ratio;
- verification success;
- model latency;
- GPU memory;
- total cost.

---

## 10. Team / Swarm Benchmarks

Questions:

- when does Architect + Developer beat one Agent?
- when does parallel Developer decomposition reduce wall time?
- when does Research sharding improve evidence coverage?
- does independent replication reduce errors enough to justify cost?
- how much integration failure comes from overlapping MutationScopes?

Default Team policy is evidence-driven, not “more Agents is better”.

---

## 11. Model Benchmarks

Evaluate:

- workhorse candidates;
- coding specialists;
- reasoning tiers;
- quantization;
- context profile;
- verifier independence;
- prefix caching/concurrency;
- embedding/reranker alternatives.

Public benchmarks guide candidate discovery.

Production eligibility comes from ReverendBench.

---

## 12. Worker / Economics Benchmarks

Measure:

~~~text
cold start
image/container start
model download
model load
browser boot
CPU worker boot
cache hit/miss
idle grace
drain
provider billed time
useful lease time
~~~

Compare:

~~~text
ephemeral weights
vs warm persistent model cache

5 vs 7 vs 10 minute idle grace

reuse worker
vs terminate/reprovision
~~~

Choose by total verified-task economics and responsiveness.

---

## 13. Recovery Benchmarks

Fault injection includes:

- GPU worker killed;
- browser/CPU worker lost;
- Control Plane process restart;
- catastrophic host loss after off-host ActionIntent;
- checkpoint corruption;
- provider timeout;
- Git side-effect ambiguity.

Success means correct recovery, not merely fast restart.

---

## 14. Security Benchmarks

Adversarial fixtures test:

- prompt-injection web page;
- malicious repository instructions/config;
- SSRF attempts;
- worker requesting unrelated Artifact;
- cross-Project vector retrieval;
- sensitive context to Community worker;
- forged tool call/Approval;
- malicious active HTML Artifact.

Mandatory security failure is a release blocker, not a score tradeoff.

---

## 15. Repetition and Variance

Model/Agent Tasks are stochastic.

For promotion:

- repeat representative cases;
- retain per-run results;
- report success distribution/rate, not best run;
- use paired comparisons where possible;
- avoid interpreting tiny samples as certainty.

Exact statistical threshold depends on risk and experiment cost.

---

## 16. Held-Out / Contamination Policy

Maintain:

- development fixtures;
- promotion/held-out fixtures;
- rotating real Project retrospective cases.

Candidate models/Agents must not receive expected patch/reference answers through Context/Memory/cache.

Benchmark Project scopes are isolated.

---

## 17. Regression Registry

Every accepted capability/profile has:

~~~text
baseline result set
mandatory non-regression gates
known weaknesses
promotion date
Reverend version
~~~

A later change that improves one metric but violates a frozen gate does not silently replace it.

---

## 18. Adaptive Policy

After enough evidence, Reverend may choose among already-approved strategies.

Examples:

~~~text
Task type → context profile
research breadth → Team size
repository language → intelligence adapters
cold-start prediction → idle grace
Task complexity → reasoning effort
~~~

Adaptive selector should be deterministic/rule-based first.

A learned selector is future work and can choose only approved options.

---

## 19. Experiment Budget

Experiments consume explicit budget.

Normal user Runs must not unknowingly become unlimited benchmark harnesses.

Possible modes:

- dedicated benchmark Run;
- opt-in shadow comparison;
- offline replay where valid.

---

## 20. Reporting

Every report should answer:

~~~text
What changed?
What stayed fixed?
Did acceptance pass?
How much human help?
How much time?
How much CPU/GPU/browser use?
How much cost?
Was it independently verified?
What evidence supports promotion?
~~~

---

## 21. Promotion Authority

Benchmark service recommends.

Privileged registry/policy action promotes.

Applies to:

- DeploymentProfile;
- retrieval policy;
- ContextPolicy;
- Team strategy default;
- browser/research strategy;
- idle/cache policy.

No candidate self-promotes.

---

## 22. Initial Experiment Order

After core Cloud works:

1. validate baseline Qwen/A100/vLLM;
2. compare current codeintel vs Repository Intelligence upgrades;
3. compare authority-first Context Broker vs broad context;
4. measure Research Fabric cache/static/browser paths;
5. compare single vs sharded Research Team;
6. test coding-specialist candidate vs workhorse;
7. test 48GB cost-down model/profile;
8. optimize idle/model-cache economics;
9. test independent verifier diversity.

This discovers system-level value before model-zoo expansion.

---

## 23. Acceptance Tests

Must prove:

- result records enough configuration to reproduce;
- security/verification failure cannot win on cost;
- benchmark candidate cannot write production eligibility;
- held-out answer not available through Memory/Context;
- one-factor comparison identifies changed dimensions;
- Team experiment records coordination cost;
- cache economics uses provider-billed time;
- old accepted baseline remains after new candidate fails.

---

## 24. Exit Condition

ReverendBench v2 is ready when architecture optimization decisions can be made from reproducible Reverend-specific evidence across models, context, research, repository intelligence, Teams and compute rather than intuition or public benchmark rankings alone.
