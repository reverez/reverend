# Reverend Cloud v1 — Design Specification Index

> **Phase:** Design  
> **Status:** DESIGN COMPLETE — READY FOR C0 DEVELOPMENT  
> **Accepted architecture input:** [A12 — Cloud Architecture Acceptance](../Analysis/A12-cloud-architecture-acceptance.md)  
> **Final closure authority:** [D22 — Pre-Development Architecture Closure](./D22-pre-development-architecture-closure.md)  
> **Purpose:** Define the complete implementation contract for Reverend Cloud v1 before C0 Development begins.

---

## 1. Design Objective

The Analysis phase established **what Reverend Cloud v1 must be**.

The Design phase defines:

> **the persisted objects, interfaces, state machines, security boundaries, research/context contracts, worker protocols, model/runtime profiles, migration strategy, recovery semantics, economics, UX states and acceptance gates that Development must implement.**

The Design set intentionally preserves Reverend 0.4.0's accepted semantics while replacing laptop-bound implementations with a durable server-authoritative Cloud architecture.

---

## 2. Canonical Product Model

Reverend is designed as a persistent autonomous engineering organization.

~~~text
Human authority
      ↓
Design intelligence
human / external frontier model / Reverend Architect
      ↓
accepted SpecificationPackage
      ↓
Persistent Control Plane
      ├── Project / Run / Workflow / Task / Job authority
      ├── Agent / Team Runtime
      ├── Context Broker
      ├── Research Fabric
      ├── Repository Intelligence
      ├── Memory / Evidence / Artifacts
      ├── Policy / Tool / Secret Brokers
      ├── Model Registry / Router
      ├── Workflow + Compute Schedulers
      ├── Capacity Controller
      ├── Recovery / Action Journal
      └── Cost / Observability
             │
             ▼
Replaceable Capability Workers
      ├── CPU build/test/index
      ├── Browser research/test
      ├── Model GPU
      ├── accelerated scientific GPU
      └── media/asset GPU
~~~

Core rule:

> **Persistent intelligence and durable state; disposable expensive execution.**

A healthy system may have zero GPU workers.

---

## 3. Design Documents

| Document | Scope | Primary Development Output |
|---|---|---|
| [D0](./D0-system-contracts-and-codebase-boundaries.md) | system boundaries, package plan, contract/version policy | module/contracts skeleton |
| [D1](./D1-authoritative-domain-and-postgresql-schema.md) | domain model, PostgreSQL authority, specification packages, capability metadata | migrations + repositories |
| [D2](./D2-api-auth-sse-and-client-contract.md) | auth, REST API, idempotency, SSE, specification API | Cloud API |
| [D3](./D3-agent-team-context-artifact-runtime.md) | Agent/Team runtime, Artifacts, specification-driven engineering | cognitive runtime |
| [D4](./D4-scheduling-compute-worker-and-provider-protocol.md) | schedulers, ComputeNode, worker/provider protocol | compute fabric |
| [D5](./D5-durable-execution-checkpoints-action-journal-recovery.md) | Run lifecycle, checkpoints, Action Journal, recovery | durable execution |
| [D6](./D6-security-secrets-git-approvals-and-emergency-controls.md) | security, secrets, Git/GitHub, approvals, emergency controls | enforcement plane |
| [D7](./D7-model-profiles-routing-serving-and-reverendbench.md) | model profiles, routing, serving, baseline benchmark gates | model registry/router |
| [D8](./D8-observability-cost-budgets-operations-deployment.md) | observability, budgets, billing, operations, deployment | operations plane |
| [D9](./D9-development-programme-migration-and-acceptance.md) | C0–C9 programme, migration/test/review gates | Development sequence |
| [D10](./D10-research-retrieval-evidence-acquisition.md) | foundational research, retrieval and evidence semantics | research/evidence contracts |
| [D11](./D11-legacy-to-cloud-migration-and-refactor-map.md) | 0.4.0 → Cloud refactor/cutover map | safe migration plan |
| [D12](./D12-tool-policy-side-effect-and-recovery-registry.md) | tool capability, side effects, approval/recovery registry | Tool Broker registry |
| [D13](./D13-client-operator-ux-state-contract.md) | browser/CLI/operator lifecycle UX | Cloud operational UX |
| [D14](./D14-development-readiness-baseline-and-postgresql-test-strategy.md) | fresh baseline, PostgreSQL tests, ADR/change-control discipline | C0 evidence/testing strategy |
| [D15](./D15-capability-modernization-audit.md) | laptop-era capability modernization | KEEP/GENERALIZE/REPLACE/NEW map |
| [D16](./D16-research-fabric-and-web-context-acquisition.md) | Cloud Research Fabric, browser acquisition, source snapshots | research execution fabric |
| [D17](./D17-repository-intelligence-and-code-context.md) | repository snapshots, Tree-sitter/LSP, code/test graphs | Repository Intelligence |
| [D18](./D18-model-fabric-serving-and-optimization.md) | dynamic model fleet, vLLM optimization, ephemeral model storage | Model Fabric v2 |
| [D19](./D19-worker-capability-fabric-and-ephemeral-bootstrap.md) | CPU/browser/GPU worker taxonomy, bootstrap/storage profiles | Worker Capability Fabric |
| [D20](./D20-context-broker-and-knowledge-retrieval-v2.md) | authority-first context routing and iterative retrieval | Context Broker v2 |
| [D21](./D21-reverendbench-v2-and-adaptive-optimization.md) | whole-organization benchmarking and promotion | ReverendBench v2 |
| [D22](./D22-pre-development-architecture-closure.md) | final architecture reconciliation and pre-C0 gate | Design closure |

Supporting controls:

- [Architecture Decision Records](./Decisions/README.md)
- [Development Baseline Records](./Baselines/README.md)
- [Architecture Diagrams](./Diagrams/README.md)
- [Tool Policy Registry YAML](./D12-tool-policy-recovery-registry.yaml)

---

## 4. Reading Order

Recommended order for a developer entering the project:

~~~text
A12
 ↓
D0 → D1 → D2
       ↓
      D3
   ↙   ↓   ↘
 D10  D11  D12–D14
       ↓
      D15
  ┌────┼────┬────┐
 D16  D17  D18  D19
  └────┴──┬─┴────┘
          D20
           ↓
          D21
           ↓
          D22
           ↓
           D9
           ↓
           C0
~~~

Focused developers may read the relevant subsystem document directly, but implementation questions must still respect the authority order below.

---

## 5. Canonical Authority Order

When documents overlap:

1. frozen A12 invariants;
2. D22 explicit final-closure decisions;
3. D15–D21 capability refinements for their domains;
4. D10–D14 closure/foundation specifications;
5. D0–D9 core contracts;
6. accepted A0–A11 analysis details;
7. accepted Reverend 0.4.0 code semantics where compatible;
8. implementation convenience.

A later Design refinement may narrow or strengthen an implementation rule but may not silently weaken an A12 authority/security/durability invariant.

Specific overlap rules:

~~~text
D10 foundational Research/Evidence semantics
→ D16 Cloud Research Fabric refinement
→ D20 Context Broker consumption

D7 Model Profile/Router foundation
→ D18 Model Fabric optimization
→ D21 benchmark-driven promotion

D4 Compute/Worker protocol foundation
→ D19 capability-worker/bootstrap refinement

D14 baseline/testing discipline
+ D22 final architecture closure
→ C0 Development entry
~~~

---

## 6. Frozen Cloud v1 Deployment Baseline

| Concern | Initial Baseline |
|---|---|
| Users | two authenticated developers |
| Top-level Run concurrency | one active |
| Control Plane | persistent CPU-oriented host |
| Control-host starting envelope | 4 vCPU / 8 GB RAM / 80 GB NVMe reference profile |
| Authoritative DB | PostgreSQL |
| Primary API | REST/JSON under /api/v1 |
| Live client events | SSE |
| GPU provider | RunPod Community Cloud |
| GPU baseline | A100 SXM 80 GB |
| Inference runtime | vLLM |
| Workhorse baseline | Qwen3.8-27B |
| Initial Reverend context profile | 64K |
| GPU idle behavior | drain + scale to zero |
| Provider-local model storage | reconstructible by default; persistent cache optional |
| Redis | not required |
| Kubernetes | not required |

These are benchmark/deployment defaults, not permanent semantic bindings.

The A100/Qwen/64K combination does not become production-eligible until C7 live fit/throughput validation succeeds.

---

## 7. Persistent vs Reconstructible State

### Durable / authoritative

~~~text
PostgreSQL
Git / recovery refs
durable BlobStore
SpecificationPackages
Requirements / Decisions / AcceptanceCriteria
Run / Workflow / Task / Job state
Artifacts / retained Evidence / Memory
Action Journal
RunCheckpoints / RecoveryGenerations
cost / audit / policy state
~~~

### Reconstructible

~~~text
GPU / CPU / browser workers
model weights
KV / prefix cache
Qdrant indexes
Tree-sitter indexes
LSP sessions
web/browser caches
build/package caches
temporary worktrees
provider instances
~~~

Loss of reconstructible state may increase latency but may not destroy Project truth.

---

## 8. Primary Run Entry Modes

### Specification-driven

~~~text
Human / design intelligence
→ DRAFT SpecificationPackage
→ validation
→ human ACCEPTED package
→ normalized Requirements / Decisions / AcceptanceCriteria
→ Run pinned to exact specification version/hash
→ Task DAG
→ Agent/Team implementation
→ deterministic verification
~~~

### Objective-driven

~~~text
Human objective
→ Reverend research / clarification / architecture
→ candidate specification / Project truth
→ implementation
~~~

No external model provider is required for either mode.

---

## 9. Development Compatibility

Reverend 0.4.0 remains the accepted local regression baseline while Cloud v1 is implemented.

Migration preference:

~~~text
new Cloud contract
→ adapter over accepted local semantics
→ targeted tests
→ replacement only after equivalent acceptance evidence
~~~

Do not delete proven local functionality merely because a future Cloud subsystem exists on paper.

---

## 10. Development Entry Gate

Design closure decision:

- D0–D22 form the final Cloud v1 Design set;
- README points to the accepted Analysis/Design set;
- system/subsystem diagrams reflect the final architecture;
- no known Design contradiction remains against A12;
- specification-driven and objective-driven Run authority models are explicit;
- Research/Repository/Context/Model/Worker refinements are reconciled with D0–D14;
- D22 records the final closure audit;
- Design PR #54 carries the merge to main;
- GitHub Actions runner availability is tracked in issue #56 and must be restored before any runtime-changing C0 code merges;
- a fresh C0-entry baseline is recorded before runtime-changing C0 code begins.

The fresh baseline is execution evidence, not more architecture design.

---

## 11. C0 Development Rule

Development begins with contracts, migrations and tests — not provider provisioning.

C0 must freeze executable v1 contracts for at least:

~~~text
SpecificationPackage / AcceptanceCriteria
Project / Run / Workflow / Task / Job
AgentSpec / AgentInstance / AgentTeam
Artifact / Evidence / Memory references
ContextNeed / ContextManifest
CapabilitySpec
WorkerProfile / StorageProfile / BootstrapSpec
ExecutionEnvironmentSpec
RepositorySnapshot
SourceRecord / SourceSnapshot / EvidenceClaim
ModelRequirement / ModelProfile / DeploymentProfile
ComputeNode / ResourceRequest / ResourceLease
ActionRecord
Approval
Secret metadata
CostEvent / RateSnapshot
BenchmarkScenario / BenchmarkRun
shared enums / IDs / schema versions
~~~

No paid provider work is enabled in C0.

---

## 12. Change Control During Development

If Development discovers a Design correction:

1. record the issue;
2. determine whether it changes an A12 invariant;
3. if no, update the relevant Design document and tests;
4. if yes, create an explicit ADR/architecture decision before implementation;
5. never encode a contradictory behavior only in code.

---

## 13. Design Exit Definition

The Design phase is successful when C0 can begin without inventing missing authority, security, durability, context, worker, model, research, recovery or cost semantics.

D22 records the final closure verdict.

Cloud v1 itself is not complete until D9/C9 passes the full end-to-end acceptance programme.
