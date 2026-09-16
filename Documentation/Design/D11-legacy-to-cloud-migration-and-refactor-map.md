# D11 — Legacy-to-Cloud Migration & Refactor Map

> **Status:** DESIGN CLOSED / C0–C9 MIGRATION MAP  
> **Depends on:** A12, D0–D10  
> **Purpose:** Define what happens to Reverend 0.4.0 as Cloud v1 lands, preventing duplicate authorities, unnecessary rewrites and permanent compatibility forks.

---

## 1. Migration Vocabulary

~~~text
KEEP       preserve implementation/semantics where compatible
EXTEND     retain and add Cloud contracts
ADAPT      keep core logic behind a new interface/authority boundary
REPLACE    migrate semantics to a new implementation, then retire old authority path
COMPAT     keep temporarily for local mode only
RETIRE     remove after an explicit replacement gate
ARCHIVE    preserve data/history; stop new writes
~~~

The governing rule:

> Never run two competing authoritative implementations for the same concern.

Feature flags may switch authority at a tested cutover boundary. They must not create indefinite dual truth.

---

## 2. Authority Cutover Procedure

For each migrated concern:

1. identify old authority;
2. identify new authority;
3. provide import/adapter path;
4. test semantic equivalence/invariants;
5. switch one explicit authority flag/configuration;
6. stop old writes;
7. retain old data read-only where required;
8. remove obsolete path only after acceptance.

Equal dual-writing PostgreSQL and SQLite workflow truth is prohibited.

---

## 3. Repository-Level Migration Map

| Existing area | Disposition | Cloud target | Phase | Cutover/retirement condition |
|---|---|---|---|---|
| controlplane/ | ADAPT + REPLACE STORE | PostgreSQL Control Plane repositories/services | C0–C3 | SQLite ControlPlaneStore local-only after PG transition tests |
| autonomy.py | ADAPT | Executive Orchestrator / validated TaskGraph proposals | C3–C4 | fixed Wave-2 topology no longer owns Cloud orchestration |
| specialists/ | KEEP + EXTEND | AgentSpec/AgentInstance/Team runtime | C0/C4 | evolves; no wholesale retirement |
| workers.py | COMPAT / PARTIAL RETIRE | bounded AgentTeam primitives | C4 | Cloud no longer depends on closed WorkerRole topology |
| intelligence/ | KEEP + ADAPT | cognitive specialists, ModelRequirement, routing/evidence | C4/C7 | Cloud path loses direct local-provider assumptions |
| research/ | KEEP + REWORK STORAGE | D10 Research Broker/tools/evidence | C4/C5 | public_sources SQLite no longer Cloud truth |
| reference.py | KEEP ADAPTER | ReferenceProvider | C4 | remains optional bounded provider |
| retrieve.py | ADAPT | Cloud Retrieval service | C4 | SQLite registry assumptions removed in Cloud mode |
| knowledge.py | KEEP + ADAPT | bounded reranking/embedding cache | C4/C7 | remains reconstructible |
| engineering_memory.py | MIGRATE | D1 MemoryRecord + promotion | C1/C4 | old DB archived; no Cloud writes after cutover |
| qdrant_migrate.py | KEEP UTILITY / ADAPT | derived-index migration tooling | C4 | never authority |
| codeintel/ | KEEP + EXTEND | Repository Intelligence | C4 | pinned Run repository and disclosure policy enforced |
| development/ | KEEP + HARDEN | Tool Broker-mediated implementation plane | C4–C6 | direct Cloud mutation paths removed |
| runtime/ | ADAPT / SPLIT | local adapter + Compute Scheduler + Capacity Controller + InferenceRuntime | C4/C7 | local scheduler remains local-mode only |
| policy/ | KEEP + EXTEND | durable policy/Approval enforcement | C0/C5 | in-memory permission set no longer sole Cloud authority |
| observability/ | KEEP + EXTEND | logs/metrics/tracing/redaction | C2/C8 | Events/Costs stay PG authority |
| workstation/ | COMPAT | local 0.4.0 mode; later thin-client boundary | C2–C9 | retained through C9; future default requires ADR |
| ui/ | ADAPT | D13 Cloud web client + local compatibility UI | C2/C8 | loopback-only auth/state assumptions removed in Cloud mode |
| benchmarks/ | KEEP + EXTEND | ReverendBench + regression gates | C0/C7–C9 | legacy milestones retained as regression evidence |
| cli.py | SPLIT / ADAPT | Cloud API client + local compatibility commands | C2/C9 | Cloud commands no longer touch authority stores/providers directly |
| config.py | ADAPT | layered local/Cloud config + secret refs | C0/C5 | provider secrets removed from general Cloud config |
| registry.py | COMPAT / MIGRATE | Project/Evidence semantics in PG/Artifacts | C1/C4 | local registry archive/local-only |
| notes.py | KEEP OPTIONAL ADAPTER | personal/reference ingestion | C4 | cannot become workflow authority |
| metadata.py | KEEP OPTIONAL ADAPTER | ingestion metadata normalization | C4 | same |
| sync.py | COMPAT / ADAPT | explicit ingestion/source adapters | C4 | no autonomous Cloud authority |
| health.py | ADAPT | D8 liveness/readiness/functional health | C2/C8 | local health remains compatibility |
| maintenance.py | ADAPT | D8 maintenance/GC operational jobs | C8 | Cloud uses durable controls/inhibitors |
| bulk.py | COMPAT | optional local bulk ingestion | post-C4 | never Cloud authority |
| assets/ | KEEP | Artifact/static asset support | as needed | governed by tool/Artifact policy |
| ui/vendor/ | REVIEW/PIN | client dependency supply chain | C2/C8 | digest/version policy required |

---

## 4. Control Plane Migration

Current src/reverend/controlplane/store.py already models Workflow, Task, Job, Event, Artifact, transitions, dependencies and promotion.

Preserve those semantic boundaries while replacing Cloud storage authority with D1 PostgreSQL services.

~~~text
existing contract/tests
        ↓
PostgreSQL repositories
        ↓
shared transition service
        ↓
Cloud authority cutover
        ↓
SQLite retained for local compatibility only
~~~

A PostgreSQL wrapper around the old SQLite store is not an acceptable Cloud authority implementation.

---

## 5. Workstation Persistence Migration

workstation/store.py currently owns local encrypted conversations/messages/jobs/task state/privacy modes.

Cloud disposition:

- conversation/history can remain local/client history or become optional interaction history;
- Project/Run/Workflow/Task/Job truth comes only from D1;
- privacy-mode semantics may inform history policy;
- old Workstation DB remains readable local history.

No Cloud scheduler reads Workstation SQLite to decide Run state.

---

## 6. Autonomy Migration

autonomy.py contains useful dependency and verification/integration structure but currently hard-codes a software workflow.

Cloud target:

~~~text
human objective
↓
Executive Orchestrator proposal
↓
trusted TaskGraph validation
↓
Control Plane Task records
↓
Specialist/Team selection
~~~

Keep explicit dependencies and typed outputs. Replace the fixed topology as universal production orchestration.

---

## 7. Specialist / Worker Migration

SpecialistSpec survives and evolves.

WorkerRole is compatibility only.

Migration:

1. adapt WorkerRole to SpecialistSpec where needed;
2. move budgets/authority to AgentInstance;
3. move topology to TaskGraph/TeamPlan;
4. preserve bounded execution;
5. remove Cloud production dependency on a closed WorkerRole enum.

---

## 8. Context Migration

Current Workstation Context Compiler V2 already provides useful token budgeting, priorities, clipping and provider token accounting.

Cloud target:

- extract/generalize strong compiler behavior;
- use D3 ContextItem/ContextPolicy/ContextManifest;
- keep client chat history distinct from authoritative Task context;
- never let history outrank security/requirements.

The Workstation compiler remains local compatibility until shared infrastructure is accepted.

---

## 9. Research / Knowledge Migration

Follow D10.

Key cutovers:

- public_sources SQLite → EvidenceSource Artifacts/BlobStore;
- Engineering Memory → D1 MemoryRecord;
- local lexical registry → reconstructible Cloud lexical index;
- Qdrant remains derived;
- isolated search/fetch workers remain useful;
- deterministic research quality remains useful.

Import legacy evidence/memory only when provenance maps safely.

---

## 10. Development Plane Migration

Current development/ already provides worktrees, command execution, sandboxing, verification and coder/repair logic.

Cloud changes authority:

~~~text
Agent proposal
↓
D12 ToolDescriptor
↓
Policy Engine
↓
Approval / Secret checks
↓
Action Journal
↓
existing hardened development primitive
~~~

Cloud cognitive code may not directly call mutating subprocess/worktree primitives.

---

## 11. Git Migration

Separate:

- local worktree/branch mutation;
- commit author identity;
- remote authentication;
- protected remote actions.

D1/D6 Run-pinned repository identity and immutable owner identity are mandatory.

GitHub credentials never migrate into remote URLs or repository config.

---

## 12. Runtime / Model Migration

Keep:

- ModelProvider abstraction concept;
- Ollama local adapter;
- model profile semantics;
- ResourceRequest/Lease ideas;
- residency metrics.

Cloud split:

~~~text
Model Router
↓
Compute Scheduler
↓
ResourceLease / ComputeNode
↓
InferenceRuntime
↓
vLLM worker
~~~

The local fcntl scheduler is not distributed Cloud authority.

---

## 13. Resource Scheduling Migration

runtime/resources.py already models Job-owned time-bounded leases.

Cloud migration:

- persist requests/leases in PostgreSQL;
- add ComputeNode/runtime_epoch/trust;
- replace process-local locking with D4 leadership;
- preserve Job ownership and TTL semantics;
- provider lifecycle only through Capacity Controller.

---

## 14. Policy Migration

The current fail-closed capability registry is a good semantic base.

Cloud adds:

- durable versioned Project policy;
- Run policy provenance;
- authenticated users/services/workers;
- Approval binding;
- D12 operation-specific capabilities;
- durable emergency control.

Compatibility Permission objects may seed tests but do not remain sole production authorization.

---

## 15. Observability Migration

Keep structured metadata, redaction and bounded diagnostics.

Cloud adds:

- trace lineage;
- durable typed Events;
- CostEvents;
- SSE presentation projection;
- controller/worker/provider metrics.

Logs remain non-authoritative.

---

## 16. CLI Migration

Current CLI directly knows Ollama, Qdrant and local data paths.

Split conceptually:

~~~text
reverend local ...
    → local compatibility adapters

reverend cloud ...
    → authenticated /api/v1 client
~~~

Cloud CLI must not open PostgreSQL directly, read Secret Broker keys, call RunPod directly, impersonate another user or mutate Run state outside D2.

---

## 17. UI Migration

Keep useful current presentation components such as source drawers, safe display helpers and diagrams.

Cloud changes:

- loopback token → D2 authentication/session/CSRF;
- local /api endpoints → /api/v1;
- Workstation state → authoritative Control Plane projection;
- polling/local job assumptions → snapshot + SSE;
- Artifact active content → sandboxed preview boundary.

Local UI remains supported through C9.

---

## 18. Configuration Migration

Cloud layering:

~~~text
compiled safe defaults
→ deployment configuration
→ environment overrides
→ authoritative Project policy
→ Run snapshot of effective policy
~~~

Secrets are references, not normal configuration values.

Existing env/config stays local compatibility where appropriate.

---

## 19. Data Migration

Cloud starts with clean PostgreSQL unless a record has clear semantic mapping.

Import candidates:

- Projects;
- validated Project facts/decisions;
- selected Artifacts;
- evidence with provenance;
- engineering Memory with evidence;
- users/identities through secure setup.

Archive by default:

- overlapping old Task/Job history;
- ephemeral chat state;
- caches/indexes;
- model residency;
- derived embeddings.

---

## 20. Feature Flag Rules

Migration flags are temporary and require:

- explicit owner;
- documented default;
- no simultaneous canonical dual write;
- rollback path;
- removal milestone.

Examples:

~~~text
postgres_controlplane_enabled
cloud_api_enabled
agent_runtime_v1_enabled
remote_gpu_enabled
cost_enforcement_enabled
~~~

A feature flag is not permission for two permanent architectures.

---

## 21. C0–C9 Cutover Map

### C0
Freeze shared contracts/adapters. No production authority switch.

### C1
Implement PostgreSQL repositories/migrations. Cloud test-mode authority can switch after migration/constraint tests.

### C2
Authenticated API/SSE. Cloud clients stop touching authority stores directly.

### C3
Canonical Run/queue/workflow convergence. Fixed local autonomy no longer owns Cloud topology.

### C4
Agent/Team/Context/D10 research migration. Old WorkerRole/Workstation context remain adapters.

### C5
Tool Broker, policy, Secret Broker, Git identity. Unmediated Cloud privileged calls prohibited.

### C6
Action Journal/checkpoints/recovery. Side effects enabled only after D12 recovery registration.

### C7
Remote compute/vLLM/RunPod. Ollama remains local compatibility.

### C8
Economics/operations/D13 UX complete.

### C9
Full regression/E2E. Identify obsolete flags/paths for deliberate retirement; local 0.4.0 long-term status remains a separate ADR.

---

## 22. Removal Rule

Do not delete an old subsystem merely because a new package exists.

Removal requires:

1. replacement behavior;
2. import/migration where needed;
3. targeted regression;
4. phase acceptance;
5. no remaining caller in supported local mode;
6. documentation update.

---

## 23. Forbidden Migration Patterns

Rejected:

- wholesale rewrite before contract tests;
- equal SQLite + PostgreSQL authority;
- Cloud API treating Workstation task state as canonical;
- Agent directly calling RunPod/GitHub with inherited credentials;
- Qdrant becoming canonical Memory/Evidence;
- process-local model locks reused as distributed scheduling authority;
- hidden direct Git mutation escape hatch after Tool Broker;
- deleting 0.4.0 paths before equivalent Cloud acceptance.

---

## 24. Exit Condition

D11 is satisfied when every major existing subsystem has explicit disposition, target owner, migration phase, authority cutover and retirement condition.

Development should therefore adapt proven Reverend components deliberately rather than rediscover or duplicate them.


---

## 2026-09-16 Cloud-Only Product Cutover Clarification

The Cloud product boundary is now stricter than the historical local compatibility path.

### Production Cloud

Client devices do not execute:

- Ollama/local LLMs;
- embeddings/reranking;
- Workstation scheduler;
- repository builds/tests;
- sandboxes;
- media models;
- required recovery replication.

The Cloud browser/API client is the supported shared two-user product surface.

### Local 0.4.0

Local Workstation/Ollama/SQLite code remains useful during migration for:

- regression reference;
- deterministic development tests;
- adapter compatibility;
- historical data inspection.

It must not shape Cloud authority contracts or create a hybrid execution requirement.

After C9, retirement/archival of product-facing local mode should be evaluated by a separate ADR.

### Conversation migration

Legacy encrypted Workstation conversation history may be imported selectively into D15 Conversations, but is not required for Cloud cutover and never imports old Task authority implicitly.


### Model cache migration

Local Ollama/model caches are **not** migrated into production Cloud authority.

Cloud v1 workers reconstruct approved DeploymentProfiles according to D17:

~~~text
pinned model manifest
→ upstream hydration
→ worker-local verified ephemeral cache
→ runtime load
~~~

The local developer model cache may remain on developer machines for local compatibility or personal archival purposes, but Cloud scheduling does not depend on it.

Do not copy local model blobs into the persistent Control Plane state directory during migration.
