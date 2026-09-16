# Reverend Cloud v1 — Complete System Mega-Diagram

> **Status:** Design visualization  
> **Source of truth:** A12 + D0–D14  
> **Purpose:** A single end-to-end decomposition of the Reverend system, including human authority, clients, API, persistence, orchestration, Agents, Teams, context, tools, verification, scheduling, compute, models, recovery, security, Git, secrets, billing, observability, deployment, compatibility and Development gates.

This diagram is intentionally enormous. It is not a replacement for the individual Design specifications; it is a single visual map showing how those contracts fit together.

~~~mermaid
flowchart TB

%% =========================================================
%% STYLES
%% =========================================================
classDef human fill:#e8f0ff,stroke:#3458a4,stroke-width:2px,color:#111;
classDef client fill:#eef7ff,stroke:#3678a8,stroke-width:1.5px,color:#111;
classDef api fill:#e9fff7,stroke:#23855f,stroke-width:1.5px,color:#111;
classDef authority fill:#fff4d6,stroke:#a76b00,stroke-width:2px,color:#111;
classDef domain fill:#fff9e8,stroke:#a7802b,stroke-width:1.5px,color:#111;
classDef agent fill:#f5edff,stroke:#7552a8,stroke-width:1.5px,color:#111;
classDef context fill:#f8f3ff,stroke:#8458aa,stroke-width:1.2px,color:#111;
classDef tool fill:#fff0f0,stroke:#aa4949,stroke-width:1.5px,color:#111;
classDef verify fill:#efffe9,stroke:#4e8a3c,stroke-width:1.5px,color:#111;
classDef sched fill:#eefcf8,stroke:#2f7a68,stroke-width:1.5px,color:#111;
classDef compute fill:#eef4ff,stroke:#4f68a8,stroke-width:1.5px,color:#111;
classDef model fill:#f1ecff,stroke:#5f49a8,stroke-width:1.5px,color:#111;
classDef durable fill:#fff2e5,stroke:#a6642c,stroke-width:1.5px,color:#111;
classDef security fill:#ffecec,stroke:#a73b3b,stroke-width:1.5px,color:#111;
classDef data fill:#f4f4f4,stroke:#666,stroke-width:1.3px,color:#111;
classDef cost fill:#ecfff1,stroke:#3e8b55,stroke-width:1.5px,color:#111;
classDef ops fill:#f2fbff,stroke:#3f7890,stroke-width:1.5px,color:#111;
classDef external fill:#f7f7f7,stroke:#777,stroke-width:1.2px,stroke-dasharray:5 3,color:#111;
classDef dev fill:#fff8ed,stroke:#9b6b23,stroke-width:1.3px,color:#111;
classDef invariant fill:#fffbe6,stroke:#b09121,stroke-width:1.5px,color:#111;

%% =========================================================
%% ROOT
%% =========================================================
ROOT["REVEREND CLOUD v1<br/>Persistent autonomous software-engineering organisation<br/>Two authenticated developers • one active top-level Run • bounded internal parallelism<br/>Persistent authority • disposable expensive compute • deterministic verification"]:::authority

%% =========================================================
%% 0. FROZEN INVARIANTS
%% =========================================================
subgraph INV["0. FROZEN ARCHITECTURAL INVARIANTS"]
direction LR
I1["One authoritative workflow state"]:::invariant
I2["Authenticated human identity"]:::invariant
I3["Immutable Run owner"]:::invariant
I4["Models propose; Reverend executes"]:::invariant
I5["Compute is replaceable"]:::invariant
I6["Typed collaboration"]:::invariant
I7["Selective bounded context"]:::invariant
I8["Verification outranks confidence"]:::invariant
I9["Secrets stay at enforcement boundary"]:::invariant
I10["Costs are attributable + reconcilable"]:::invariant
I11["Community compute is lower-assurance"]:::invariant
I12["Recovery replicas are not authority"]:::invariant
end

ROOT --> I1
ROOT --> I2
ROOT --> I3
ROOT --> I4
ROOT --> I5
ROOT --> I6
ROOT --> I7
ROOT --> I8
ROOT --> I9
ROOT --> I10
ROOT --> I11
ROOT --> I12

%% =========================================================
%% 1. HUMANS / CLIENTS / DEVICES
%% =========================================================
subgraph CLIENTS["1. HUMANS, DEVICES & THIN CLIENTS"]
direction TB

U_A["Developer A<br/>authenticated human"]:::human
U_B["Developer B<br/>authenticated human"]:::human

subgraph CL_A["Developer A devices"]
direction LR
A_GUI["Browser GUI"]:::client
A_CLI["CLI"]:::client
A_IDE["IDE integration"]:::client
A_REC["Recovery-enabled client<br/>encrypted recovery peer"]:::client
end

subgraph CL_B["Developer B devices"]
direction LR
B_GUI["Browser GUI"]:::client
B_CLI["CLI"]:::client
B_IDE["IDE integration"]:::client
B_REC["Recovery-enabled client<br/>encrypted recovery peer"]:::client
end

U_A --> A_GUI
U_A --> A_CLI
U_A --> A_IDE
U_A --> A_REC

U_B --> B_GUI
U_B --> B_CLI
U_B --> B_IDE
U_B --> B_REC

CLIENT_RULE["Client responsibility<br/>presentation • auth session • submit commands • approvals • display state<br/><b>never authoritative for Run/workflow/queue/secrets</b>"]:::client

A_GUI --> CLIENT_RULE
B_GUI --> CLIENT_RULE
A_CLI --> CLIENT_RULE
B_CLI --> CLIENT_RULE
end

ROOT --> U_A
ROOT --> U_B

%% =========================================================
%% 2. NETWORK EDGE / REMOTE ACCESS
%% =========================================================
subgraph EDGE["2. NETWORK EDGE & REMOTE ACCESS"]
direction TB
TS["Tailscale / private network<br/>preferred initial transport"]:::security
TLS["HTTPS / TLS"]:::security
RP["Reverse proxy<br/>Caddy or nginx<br/>request limits • TLS • SSE passthrough"]:::security
PUBAPI["Public Reverend application surface<br/>/api/v1/* + /api/v1/events/stream"]:::api
SSH["SSH<br/>administration only<br/>never application protocol"]:::security
NO_PUBLIC["Not publicly exposed<br/>PostgreSQL • vLLM • Secret Broker • worker internals"]:::security
end

A_GUI --> TS
A_CLI --> TS
A_IDE --> TS
B_GUI --> TS
B_CLI --> TS
B_IDE --> TS
TS --> TLS --> RP --> PUBAPI
SSH -. admin path .-> ROOT
NO_PUBLIC -. boundary .-> ROOT

%% =========================================================
%% 3. CLOUD API / CLIENT CONTRACT
%% =========================================================
subgraph API["3. CLOUD API SERVICE — REST/JSON + SSE"]
direction TB

FASTAPI["ASGI API<br/>FastAPI + Pydantic v2 + Uvicorn"]:::api
REQCTX["RequestContext<br/>request_id • principal_user_id • session_id • device_id?<br/>trace_id • received_at"]:::api
AUTHMW["Authentication middleware<br/>cookie session or CLI bearer session"]:::security
CSRFM["CSRF validation<br/>cookie-authenticated mutations"]:::security
IDEMP["Idempotency service<br/>principal + operation + Idempotency-Key + request hash"]:::api
AUTHZMW["Authorization dependency<br/>capability + resource scope + principal"]:::security

subgraph ROUTES["Versioned /api/v1 routes"]
direction LR
R_AUTH["/auth/login<br/>/auth/logout<br/>/me"]:::api
R_PROJECTS["/projects<br/>/projects/{id}<br/>/projects/{id}/runs"]:::api
R_RUNS["/runs<br/>/runs/{id}<br/>pause • resume • run-now • cancel"]:::api
R_QUEUE["/queue"]:::api
R_APPROVALS["/approvals<br/>approve • reject"]:::api
R_ART["/runs/{id}/artifacts<br/>/artifacts/{id}"]:::api
R_WF["/runs/{id}/workflow<br/>/runs/{id}/agents"]:::api
R_COST["/runs/{id}/costs<br/>/costs/me<br/>/system/rates"]:::api
R_SYS["/system/status<br/>/system/compute<br/>emergency controls"]:::api
R_SSE["/events/stream<br/>SSE + Last-Event-ID replay"]:::api
end

ERR["Stable API error taxonomy<br/>validation_error • unauthenticated • forbidden • not_found • conflict<br/>invalid_state_transition • idempotency_conflict • budget_exceeded<br/>approval_required • recovery_blocked • provider_unavailable"]:::api

BOUNDS["Bounded payloads<br/>JSON ≤ 1 MiB • objective ≤ 100 KiB<br/>approval note ≤ 8 KiB • event ≤ 32 KiB • inline Artifact ≤ 64 KiB"]:::security

FASTAPI --> REQCTX --> AUTHMW --> CSRFM --> IDEMP --> AUTHZMW
AUTHZMW --> R_AUTH
AUTHZMW --> R_PROJECTS
AUTHZMW --> R_RUNS
AUTHZMW --> R_QUEUE
AUTHZMW --> R_APPROVALS
AUTHZMW --> R_ART
AUTHZMW --> R_WF
AUTHZMW --> R_COST
AUTHZMW --> R_SYS
AUTHZMW --> R_SSE
FASTAPI --> ERR
FASTAPI --> BOUNDS
end

PUBAPI --> FASTAPI

%% =========================================================
%% 4. IDENTITY / AUTH / MEMBERSHIP
%% =========================================================
subgraph IDENTITY["4. IDENTITY, SESSIONS, MEMBERSHIP & EXTERNAL IDENTITY"]
direction TB

USER["User<br/>user_id • display_name • status<br/>created_at • updated_at"]:::authority
DEVICE["Device<br/>device_id • user_id • label<br/>credential/public-key ref • recovery_enabled • revoked_at"]:::security
SESSION["AuthSession<br/>session_id • user_id • device_id?<br/>token_hash • csrf_hash • expires_at • revoked_at"]:::security
PROJECT["Project<br/>project_id • name • repository_identity<br/>default_branch • trust_mode • created_by"]:::domain
PMEMBER["ProjectMember<br/>project_id • user_id • role(owner/member)"]:::domain
GITHUBID["GitHubIdentity<br/>identity_id • user_id • github_login<br/>git_author_name/email • credential_ref • repository_scope"]:::security

USER --> DEVICE --> SESSION
USER --> PMEMBER
PROJECT --> PMEMBER
USER --> GITHUBID
end

R_AUTH --> USER
R_PROJECTS --> PROJECT
AUTHMW --> SESSION
A_REC --> DEVICE
B_REC --> DEVICE

%% =========================================================
%% 5. AUTHORITATIVE CONTROL PLANE
%% =========================================================
subgraph CP["5. AUTHORITATIVE CONTROL PLANE — ONE SERVER-SIDE SOURCE OF TRUTH"]
direction TB

CPROOT["Control Plane service<br/>authoritative Project / Run / Workflow / Task / Job / Event / Artifact state"]:::authority

RUN["Run<br/>run_id • project_id • immutable owner_user_id • objective<br/>status • queue_class • priority • checkpoint • interruption_depth<br/>github_identity_ref • resource_policy • budget_policy • row_version"]:::authority

WF["Workflow<br/>workflow_id • run_id • objective • status • trace_id"]:::domain
TASK["Task<br/>task_id • workflow_id • team_id?<br/>kind • objective • status • acceptance_criteria • priority"]:::domain
TDEP["TaskDependency<br/>task_id → depends_on_task_id<br/>acyclic DAG"]:::domain
JOB["Job<br/>job_id • task_id • agent_instance_id?<br/>attempt_number • status • executor_type • node • runtime_epoch<br/>error_code • result_ref"]:::domain

EVENT["Event<br/>append-only sequence • event_id • event_type • occurred_at<br/>user/project/run/workflow/task/job/agent lineage<br/>actor • trace_context • bounded payload"]:::domain

ART["Artifact<br/>artifact_id • type • schema_version • content_ref/inline_content<br/>content_hash • producer job/agent • provenance<br/>validation_state • promotion_state"]:::domain
ARTP["ArtifactParent<br/>derived_from lineage"]:::domain

REQ["Requirement<br/>statement • source_ref • status<br/>priority • acceptance_refs • version • supersession"]:::domain
DEC["Decision<br/>type • title • decision_text • rationale_ref<br/>status • supersession"]:::domain
MEM["MemoryRecord<br/>scope • type • statement • evidence_refs<br/>confidence • status • expiry • supersession"]:::domain

APPROVAL["Approval<br/>run/project • action_type • action_fingerprint<br/>requested_actor • effective_external_identity<br/>resource summary • required policy • state • expiry • decision"]:::security

CHECK["RunCheckpoint<br/>sequence • manifest • status snapshot • journal watermark<br/>hash • complete"]:::durable
ACTION["ActionRecord<br/>journal_sequence • action_id • run/job • actor • tool • operation<br/>arguments_digest • idempotency_key • state • resume_strategy<br/>result_ref • reconciliation metadata"]:::durable

RR["ResourceRequest<br/>job-owned capacity requirement<br/>CPU • RAM • accelerator • runtime • trust • priority • cost ceiling"]:::sched
RL["ResourceLease<br/>request/job/node • runtime_epoch • granted resources<br/>ACTIVE/RELEASED/EXPIRED/REVOKED • TTL • heartbeat"]:::sched
CN["ComputeNode<br/>provider • provider_instance • trust_class • lifecycle<br/>capabilities • runtime profiles • resident models • heartbeat"]:::compute

RATE["RateSnapshot<br/>provider/product/tier • native rate/currency<br/>billing rules • FX source/rate • effective/captured timestamps"]:::cost
COSTEV["CostEvent<br/>category • lineage • quantity/unit • native unit price/currency<br/>rate_snapshot • estimated/actual GBP • source • metadata"]:::cost

IDEMPREC["IdempotencyRecord<br/>principal • operation • key • request_hash<br/>response/resource ref • expiry"]:::domain
RUNTIME_EPOCH["RuntimeEpoch<br/>changes each authoritative backend boot<br/>invalidates stale lease/worker execution authority"]:::durable

CPROOT --> RUN --> WF --> TASK --> JOB
TASK --> TDEP
CPROOT --> EVENT
CPROOT --> ART --> ARTP
PROJECT --> REQ
PROJECT --> DEC
PROJECT --> MEM
RUN --> APPROVAL
RUN --> CHECK
RUN --> ACTION
JOB --> RR --> RL --> CN
CPROOT --> RATE
CPROOT --> COSTEV
CPROOT --> IDEMPREC
CPROOT --> RUNTIME_EPOCH
end

PROJECT --> RUN
RUN -->|owner_user_id| USER
RUN -->|github_identity_ref| GITHUBID
R_RUNS --> CPROOT
R_QUEUE --> CPROOT
R_APPROVALS --> CPROOT
R_ART --> CPROOT
R_WF --> CPROOT
R_SSE --> EVENT
IDEMP --> IDEMPREC

%% =========================================================
%% 6. RUN LIFECYCLE / QUEUE
%% =========================================================
subgraph RUNLIFE["6. RUN LIFECYCLE & TOP-LEVEL QUEUE"]
direction LR

Q["QUEUED"]:::durable
ST["STARTING"]:::durable
RN["RUNNING"]:::durable
PRQ["PAUSE_REQUESTED"]:::durable
PSG["PAUSING"]:::durable
PSD["PAUSED"]:::durable
RQ["RESUME_QUEUED"]:::durable
RSM["RESUMING"]:::durable
AWA["AWAITING_APPROVAL"]:::durable
RCV["RECOVERING"]:::durable
RCB["RECOVERY_BLOCKED"]:::durable
DONE["COMPLETED"]:::verify
FAIL["FAILED"]:::durable
CANCEL["CANCELLED"]:::durable

Q --> ST --> RN
RN --> PRQ --> PSG --> PSD --> RQ --> RSM --> RN
RN --> AWA --> RQ
RN --> RCV --> RQ
RCV --> RCB
RCB --> RQ
RN --> DONE
RN --> FAIL
RN --> CANCEL
ST --> FAIL
RSM --> FAIL

QUEUEPOL["Cloud v1 queue policy<br/>MAX_ACTIVE_TOP_LEVEL_RUNS = 1<br/>classes: ACTIVE • RESUME_NEXT • NORMAL<br/>MAX_PREEMPTION_DEPTH = 1"]:::authority
QUEUEPOL --> Q
QUEUEPOL --> RQ
end

RUN --> RUNLIFE

%% =========================================================
%% 7. EXECUTIVE ORCHESTRATION
%% =========================================================
subgraph ORCH["7. EXECUTIVE ORCHESTRATION & WORKFLOW LOGIC"]
direction TB

EXEC["Executive Orchestrator<br/>cognitive planner constrained by deterministic Control Plane authority"]:::agent
OBJ["Human objective + constraints"]:::agent
REQDERIVE["Requirements / acceptance derivation"]:::agent
PLAN["TaskGraph / TeamPlan proposal"]:::agent
PLANVAL["Trusted plan validation<br/>DAG • authority • budgets • dependencies • bounded fan-out"]:::authority
REPLAN["Dynamic replan<br/>when evidence/failure invalidates current plan"]:::agent
SPECSEL["Specialist selection<br/>task kind • output Artifact • authority • risk • capability"]:::agent
COMPLETE["Completion evaluator<br/>requirements satisfied • deterministic checks • assurance • no blockers"]:::verify

OBJ --> EXEC --> REQDERIVE --> PLAN --> PLANVAL
PLANVAL --> TASK
TASK --> SPECSEL
EXEC --> REPLAN --> PLANVAL
TASK --> COMPLETE
COMPLETE --> DONE
end

RUN --> OBJ

%% =========================================================
%% 8. SPECIALIST / AGENT RUNTIME
%% =========================================================
subgraph AGENTS["8. SPECIALIST, AGENTINSTANCE & AGENTTEAM RUNTIME"]
direction TB

SREG["Specialist Registry<br/>versioned SpecialistSpec"]:::agent
SSPEC["SpecialistSpec<br/>id/version/name • role_family • methodology<br/>ModelRequirement • ContextPolicy • tool policy • capability requirements<br/>input/output Artifact types • authority ceiling • budget policy<br/>completion • verification • escalation • metadata"]:::agent

AINST["AgentInstance<br/>agent_instance_id • run/task/team<br/>specialist id/version • mission<br/>effective authority • budget envelope • context scope<br/>created/closed timestamps"]:::agent

A_BUDGET["AgentBudget<br/>model calls • input/output tokens • tool calls • wall time<br/>retries • dependency requests • max cost"]:::agent
A_AUTH["Effective Authority<br/>Specialist ceiling ∩ Task policy ∩ Project policy<br/>∩ Run-owner authority ∩ emergency state ∩ environment trust"]:::security

ATEAM["AgentTeam<br/>team_id • Run • parent Task • objective • strategy<br/>leader • budget • concurrency • completion/failure/disagreement policy"]:::agent
TPLAN["TeamPlan<br/>versioned members + Control Plane Task IDs + dependencies"]:::agent

STRAT_PIPE["pipeline"]:::agent
STRAT_PAR["parallel_decomposition"]:::agent
STRAT_SHARD["sharded"]:::agent
STRAT_REP["independent_replication"]:::agent
STRAT_ADV["adversarial_review"]:::agent

MINTEAM["Minimum-sufficient-team policy<br/>one Agent when enough<br/>expand only when expected value > coordination + compute cost"]:::agent
MUTSCOPE["MutationScope<br/>workspace • branch • path set<br/>conflict detection before concurrent mutation"]:::security
INTEGTASK["Explicit Integration Task<br/>combines isolated worktrees/Artifacts<br/>never silent cross-agent merge"]:::verify

SREG --> SSPEC --> AINST
SPECSEL --> SREG
AINST --> A_BUDGET
AINST --> A_AUTH
AINST --> ATEAM
ATEAM --> TPLAN
ATEAM --> STRAT_PIPE
ATEAM --> STRAT_PAR
ATEAM --> STRAT_SHARD
ATEAM --> STRAT_REP
ATEAM --> STRAT_ADV
MINTEAM --> ATEAM
AINST --> MUTSCOPE --> INTEGTASK

subgraph ROLES["Specialist organisation — logical roles, not permanent model bindings"]
direction LR
ROLE_RESEARCH["Research Intelligence"]:::agent
ROLE_STAKE["Stakeholder / Product Intelligence"]:::agent
ROLE_UX["UX / Accessibility"]:::agent
ROLE_ARCH["Systems Architect"]:::agent
ROLE_REPO["Repository Analyst"]:::agent
ROLE_DEV["Coding Intelligence / Developer"]:::agent
ROLE_TEST["Test Engineering"]:::agent
ROLE_DEP["Dependency / Migration"]:::agent
ROLE_PERF["Performance Engineering"]:::agent
ROLE_SEC["Security Reviewer"]:::agent
ROLE_VERIFY["Independent Verifier"]:::agent
ROLE_CRITIC["Adversarial Critic"]:::agent
ROLE_FAIL["Failure Investigator"]:::agent
ROLE_INTEG["Integration Governor"]:::agent
ROLE_ASSET["Asset / Media capability worker"]:::agent
ROLE_SIM["Simulation capability worker<br/>CFD / FEA / scientific compute"]:::agent
ROLE_DEPLOY["Deployment / external automation"]:::agent
end

SREG --> ROLE_RESEARCH
SREG --> ROLE_STAKE
SREG --> ROLE_UX
SREG --> ROLE_ARCH
SREG --> ROLE_REPO
SREG --> ROLE_DEV
SREG --> ROLE_TEST
SREG --> ROLE_DEP
SREG --> ROLE_PERF
SREG --> ROLE_SEC
SREG --> ROLE_VERIFY
SREG --> ROLE_CRITIC
SREG --> ROLE_FAIL
SREG --> ROLE_INTEG
SREG --> ROLE_ASSET
SREG --> ROLE_SIM
SREG --> ROLE_DEPLOY
end

TASK --> AINST

%% =========================================================
%% 9. CONTEXT / MEMORY / ARTIFACT FABRIC
%% =========================================================
subgraph CTX["9. CONTEXT, MEMORY, EVIDENCE & ARTIFACT FABRIC"]
direction TB

CTXROOT["Context architecture<br/>authoritative state ≠ shared Artifacts ≠ Agent working context ≠ Memory"]:::context
CB["Context Broker<br/>decides WHAT eligible/relevant information may enter"]:::context
CC["Context Compiler<br/>decides HOW context fits one model invocation"]:::context
CITEM["ContextItem<br/>layer • source type/ref • representation • authority<br/>trust class • sensitivity • freshness • priority • mandatory • tokens • provenance"]:::context
CPOL["ContextPolicy<br/>max tokens • allowed/mandatory layers • max item tokens<br/>retrieval/expansion budget • sensitivity ceiling<br/>provider trust • summary policy • repository disclosure policy"]:::context
CMAN["ContextManifest<br/>compiler version • source refs • omitted refs<br/>token estimates/actuals • trust class • content hash"]:::context
CREQ["ContextRequest<br/>structured request for additional symbol/file/evidence/context slice<br/>authority + trust + budget checked"]:::context

subgraph CSOURCES["Context sources"]
direction LR
C_AUTH["Authoritative Project/Run state"]:::context
C_ART["Typed Artifacts"]:::context
C_EVID["Evidence / sources"]:::context
C_MEM["Project / experience Memory"]:::context
C_REPO["Repository intelligence<br/>repo map • symbols • refs • interfaces • tests • Git state"]:::context
C_HIST["Interaction / conversation history"]:::context
C_IDX["Derived indexes / embeddings<br/>reconstructible"]:::context
end

subgraph ORDER["Compiler priority"]
direction LR
C1["Security/system constraints"]:::context
C2["Task objective"]:::context
C3["Requirements + acceptance"]:::context
C4["Specialist methodology"]:::context
C5["Required parent Artifacts/interfaces"]:::context
C6["Repository slices"]:::context
C7["High-value Evidence"]:::context
C8["Accepted Decisions/Memory"]:::context
C9["Optional history"]:::context
end

CTXROOT --> CB --> CITEM --> CC --> CMAN
CPOL --> CB
CPOL --> CC
CREQ --> CB

C_AUTH --> CB
C_ART --> CB
C_EVID --> CB
C_MEM --> CB
C_REPO --> CB
C_HIST --> CB
C_IDX --> CB

CC --> C1 --> C2 --> C3 --> C4 --> C5 --> C6 --> C7 --> C8 --> C9

ART --> C_ART
REQ --> C_AUTH
DEC --> C_AUTH
MEM --> C_MEM
EVENT --> C_HIST
end

AINST --> CB

%% =========================================================
%% 10. TYPED ARTIFACTS & CONTROL SIGNALS
%% =========================================================
subgraph ARTFAB["10. TYPED ARTIFACTS, PROMOTION & CONTROL SIGNALS"]
direction TB

ATYPES["Canonical Artifact families"]:::domain
AEV["ResearchEvidencePack/v1"]:::domain
AARCH["ArchitectureDecisionPack/v1"]:::domain
ALOC["RepositoryLocalization/v1"]:::domain
AIMPL["ImplementationArtifact/v1"]:::domain
ATEST["TestReport/v1"]:::domain
AFAIL["FailureAnalysis/v1"]:::domain
ASEC["SecurityAssessment/v1"]:::domain
APERF["PerformanceReport/v1"]:::domain
AVER["VerificationReport/v1"]:::domain

VALIDATE["Artifact validation<br/>parse → schema validation → semantic validation → immutable storage"]:::verify
PROMOTE["Explicit promotion<br/>proposal → validated Project truth / Decision / Requirement / Memory / integration candidate"]:::verify

SIG["Structured control signals"]:::agent
SIG_DONE["CompletionSignal"]:::agent
SIG_DEP["DependencyRequest"]:::agent
SIG_CTX["ContextRequest"]:::agent
SIG_CLAR["ClarificationRequest"]:::agent
SIG_APPR["ApprovalRequest"]:::agent
SIG_ESC["EscalationRequest"]:::agent
SIG_CON["ConflictNotice"]:::agent
SIG_FAIL["FailureSignal"]:::agent

MEMPROP["MemoryProposal<br/>type • statement • evidence_refs • scope • confidence • expiry"]:::context
MEMPROM["Memory promotion service<br/>evidence • scope • dedupe • contradiction • supersession"]:::verify

ATYPES --> AEV
ATYPES --> AARCH
ATYPES --> ALOC
ATYPES --> AIMPL
ATYPES --> ATEST
ATYPES --> AFAIL
ATYPES --> ASEC
ATYPES --> APERF
ATYPES --> AVER

AEV --> VALIDATE
AARCH --> VALIDATE
ALOC --> VALIDATE
AIMPL --> VALIDATE
ATEST --> VALIDATE
AFAIL --> VALIDATE
ASEC --> VALIDATE
APERF --> VALIDATE
AVER --> VALIDATE
VALIDATE --> ART
VALIDATE --> PROMOTE

SIG --> SIG_DONE
SIG --> SIG_DEP
SIG --> SIG_CTX
SIG --> SIG_CLAR
SIG --> SIG_APPR
SIG --> SIG_ESC
SIG --> SIG_CON
SIG --> SIG_FAIL

AINST --> ATYPES
AINST --> SIG
AINST --> MEMPROP --> MEMPROM --> MEM
SIG_CTX --> CREQ
SIG_APPR --> APPROVAL
SIG_ESC --> REPLAN
SIG_DEP --> PLANVAL
SIG_FAIL --> REPLAN
end

%% =========================================================
%% 11. BOUNDED AGENT EXECUTION LOOP
%% =========================================================
subgraph AGENTLOOP["11. BOUNDED AGENT LOOP"]
direction LR

LOOP_CTX["Compile bounded context"]:::context
LOOP_MODEL["Invoke eligible model"]:::model
LOOP_PARSE["Parse structured output / proposed tool call"]:::agent
LOOP_TOOLQ["Tool proposed?"]:::agent
LOOP_TOOL["Policy-mediated tool execution"]:::tool
LOOP_OBS["Persist observation / Artifact / Action result"]:::domain
LOOP_MORE["Continue within budget?"]:::agent
LOOP_OUT["Validate Artifact / control signal"]:::verify
LOOP_STOP["Stop<br/>complete • blocked • budget • cancel • approval • failure"]:::durable

LOOP_CTX --> LOOP_MODEL --> LOOP_PARSE --> LOOP_TOOLQ
LOOP_TOOLQ -->|yes| LOOP_TOOL --> LOOP_OBS --> LOOP_MORE
LOOP_MORE -->|yes| LOOP_CTX
LOOP_MORE -->|no| LOOP_STOP
LOOP_TOOLQ -->|no| LOOP_OUT --> LOOP_STOP
end

AINST --> LOOP_CTX
CMAN --> LOOP_MODEL

%% =========================================================
%% 12. POLICY / TOOL / SECRET ENFORCEMENT
%% =========================================================
subgraph ENFORCE["12. POLICY-MEDIATED EXECUTION & SECRET BOUNDARIES"]
direction TB

TOOLBROKER["Tool Broker<br/>single privileged execution gate"]:::security
TOOLDESC["Tool descriptor<br/>input/output schema • capability • risk • side-effect class<br/>recovery strategy • approval policy • environment • timeout"]:::tool
PE["PermissionEvaluator / Policy Engine<br/>default deny • explicit deny precedence<br/>human/Run/Agent/worker/service subjects • scoped capabilities"]:::security
APRCHK["Approval check<br/>state • expiry • Run • owner • identity • fingerprint • target • current policy"]:::security
SECB["Secret Broker<br/>server-side Secret references only"]:::security
SECRET["Secret<br/>SYSTEM / USER / PROJECT / RUN_EPHEMERAL<br/>encrypted_value • key_version • rotation/revocation"]:::security
MASTER["Secret-encryption master key<br/>separate from DB • protected host key material"]:::security

TOOLBROKER --> TOOLDESC --> PE --> APRCHK --> SECB
SECRET --> SECB
MASTER --> SECRET

LOOP_TOOL --> TOOLBROKER
A_AUTH --> PE
APPROVAL --> APRCHK
RUN --> APRCHK
GITHUBID --> SECB
end

%% =========================================================
%% 13. EXECUTION TOOLS / SANDBOX / GIT / RESEARCH
%% =========================================================
subgraph TOOLS["13. EXECUTION TOOL PLANE"]
direction TB

subgraph REPOTOOLS["Repository & filesystem"]
direction LR
T_READ["File read / slices"]:::tool
T_PATCH["Structured edit / patch"]:::tool
T_GREP["grep / glob / repo search"]:::tool
T_SYM["symbol lookup / refs / repo map"]:::tool
T_DIFF["Git diff / status"]:::tool
end

subgraph BUILDTOOLS["Build / test / diagnostics"]
direction LR
T_SHELL["Bounded shell"]:::tool
T_BUILD["Build / compiler"]:::tool
T_TEST["Tests"]:::tool
T_LINT["Lint / static analysis"]:::tool
T_BG["Background process<br/>start • poll • stop"]:::tool
T_PKG["Package/dependency operations"]:::tool
end

subgraph GITTOOLS["Git / GitHub"]
direction LR
T_BRANCH["Run branch / worktree"]:::tool
T_COMMIT["Git commit<br/>Run-owner author identity"]:::tool
T_PUSH["Git push<br/>Run-owner credential"]:::tool
T_PR["Create / update PR"]:::tool
T_MERGE["Merge / protected mutation<br/>approval required"]:::tool
end

subgraph RESEARCHTOOLS["Research / evidence"]
direction LR
T_SEARCH["SearXNG / bounded search"]:::tool
T_FETCH["Restricted public fetch"]:::tool
T_REF["Reference/document evidence"]:::tool
T_IMAGE["Safe image acquisition"]:::tool
end

subgraph FUTURETOOLS["Production capability workers"]
direction LR
T_ASSET["Image / 3D / Blender / ComfyUI / audio"]:::tool
T_SIM["Simulation<br/>CFD / FEA / scientific workloads"]:::tool
T_DEPLOY["Deployment / external app automation"]:::tool
end

SANDBOX["Fail-closed sandbox<br/>bubblewrap • no host home • no ambient env • no Docker socket<br/>network off by default • bounded CPU/RAM/PIDs/files<br/>Run/Task workspace only"]:::security

WORKTREE["Isolated Git worktree<br/>pinned base commit • task/run branch • collision checks"]:::tool

TOOLBROKER --> T_READ
TOOLBROKER --> T_PATCH
TOOLBROKER --> T_GREP
TOOLBROKER --> T_SYM
TOOLBROKER --> T_DIFF
TOOLBROKER --> T_SHELL
TOOLBROKER --> T_BUILD
TOOLBROKER --> T_TEST
TOOLBROKER --> T_LINT
TOOLBROKER --> T_BG
TOOLBROKER --> T_PKG
TOOLBROKER --> T_BRANCH
TOOLBROKER --> T_COMMIT
TOOLBROKER --> T_PUSH
TOOLBROKER --> T_PR
TOOLBROKER --> T_MERGE
TOOLBROKER --> T_SEARCH
TOOLBROKER --> T_FETCH
TOOLBROKER --> T_REF
TOOLBROKER --> T_IMAGE
TOOLBROKER --> T_ASSET
TOOLBROKER --> T_SIM
TOOLBROKER --> T_DEPLOY

T_SHELL --> SANDBOX
T_BUILD --> SANDBOX
T_TEST --> SANDBOX
T_PKG --> SANDBOX
T_PATCH --> WORKTREE
T_BRANCH --> WORKTREE
T_COMMIT --> WORKTREE
end

%% =========================================================
%% 14. SIDE-EFFECT CLASSIFICATION / ACTION JOURNAL
%% =========================================================
subgraph SIDEFX["14. SIDE-EFFECT & RECOVERY SEMANTICS"]
direction TB

SCLASS["Side-effect classes"]:::durable
PURE["PURE_READ"]:::durable
REP["REPEATABLE_COMPUTE"]:::durable
LOCALM["LOCAL_MUTATION"]:::durable
REMOTEI["REMOTE_IDEMPOTENT"]:::durable
REMOTER["REMOTE_RECONCILABLE"]:::durable
HIGH["IRREVERSIBLE_OR_HIGH_RISK"]:::durable

RESUME["Resume strategies"]:::durable
RS1["RESTART"]:::durable
RS2["VERIFY_THEN_RETRY"]:::durable
RS3["REBUILD"]:::durable
RS4["MANUAL_RECOVERY"]:::durable

ASTATE["ActionRecord states"]:::durable
AS_P["PLANNED"]:::durable
AS_S["STARTED"]:::durable
AS_C["COMPLETED"]:::durable
AS_F["FAILED"]:::durable
AS_I["INTERRUPTED"]:::durable
AS_U["UNKNOWN"]:::durable

REC_REG["Tool Recovery Registry<br/>tool + operation → interruptibility + resume strategy + reconciler + result verification"]:::durable

SCLASS --> PURE
SCLASS --> REP
SCLASS --> LOCALM
SCLASS --> REMOTEI
SCLASS --> REMOTER
SCLASS --> HIGH

RESUME --> RS1
RESUME --> RS2
RESUME --> RS3
RESUME --> RS4

ASTATE --> AS_P --> AS_S
AS_S --> AS_C
AS_S --> AS_F
AS_S --> AS_I
AS_S --> AS_U

REC_REG --> RESUME
ACTION --> ASTATE
TOOLDESC --> SCLASS
TOOLDESC --> REC_REG
end

%% =========================================================
%% 15. VERIFICATION / ASSURANCE / INTEGRATION
%% =========================================================
subgraph VERIFY["15. VERIFICATION & ASSURANCE PLANE"]
direction TB

DET["Deterministic checks<br/>tests • compiler • lint • schemas • simulations • measurable acceptance"]:::verify
INDEP["Independent Verifier<br/>logically independent • no implementation mutation tools"]:::verify
SECREV["Security review"]:::verify
PERFREV["Performance validation"]:::verify
CRIT["Adversarial critic"]:::verify
FAILAN["Failure Investigator"]:::verify
INTEG["Integration Governor"]:::verify
ACC["Acceptance evaluator<br/>requirements + acceptance criteria + blockers + evidence"]:::verify
PROMO["Integration / promotion gate"]:::verify

AIMPL --> DET
DET --> INDEP
DET --> SECREV
DET --> PERFREV
INDEP --> ACC
SECREV --> ACC
PERFREV --> ACC
CRIT --> ACC
FAILAN --> REPLAN
INTEG --> PROMO
ACC --> PROMO
PROMO --> COMPLETE
end

ROLE_VERIFY --> INDEP
ROLE_SEC --> SECREV
ROLE_PERF --> PERFREV
ROLE_CRITIC --> CRIT
ROLE_FAIL --> FAILAN
ROLE_INTEG --> INTEG

%% =========================================================
%% 16. WORKFLOW SCHEDULER / COMPUTE SCHEDULER / CAPACITY
%% =========================================================
subgraph SCHED["16. WORKFLOW, COMPUTE & CAPACITY SCHEDULING"]
direction TB

WS["Workflow Scheduler<br/>WHAT work is logically ready?<br/>DAG • Run state • approvals • artifacts • budgets • policy"]:::sched
CS["Compute Scheduler<br/>WHERE may an admitted Job execute?<br/>resources • runtime • model • trust • cost • locality"]:::sched
CAP["Capacity Controller<br/>SHOULD infrastructure start/stop/replace?<br/>sole owner of provider lifecycle credentials"]:::sched

PLACEMENT["Placement eligibility filters<br/>health • trust • CPU/RAM • GPU/VRAM • runtime • model profile<br/>sandbox/network • exclusivity • budget"]:::sched
RANK["Placement ranking<br/>resident model • startup delay • expected cost • VRAM headroom<br/>locality • utilization • critical path / priority"]:::sched

BUDRES["Budget reservation<br/>prevent parallel Jobs double-spending same remaining budget"]:::cost
LEADER["PostgreSQL advisory leader locks<br/>workflow scheduler • capacity controller • recovery controller"]:::sched

TASK --> WS
WS --> JOB
JOB --> RR
RR --> PLACEMENT --> RANK --> CS
CS --> RL
CS -->|no eligible node| CAP
BUDRES --> CS
LEADER --> WS
LEADER --> CAP
end

%% =========================================================
%% 17. COMPUTE FABRIC / NODE / WORKER PROTOCOL
%% =========================================================
subgraph COMPUTE["17. COMPUTE FABRIC & AUTHENTICATED WORKER PROTOCOL"]
direction TB

NODE_REG["ComputeNode Registry<br/>capability + health + trust + runtime + model residency"]:::compute
W_BOOT["One-time worker bootstrap credential<br/>≥256-bit random • hash stored • provider-instance-bound • short TTL"]:::security
W_REG["POST /internal/v1/workers/register<br/>provider_instance + worker version + capabilities + runtime profiles"]:::compute
W_SESSION["Worker session<br/>short-lived • node + runtime_epoch + endpoint scope"]:::security
W_HB["Worker heartbeat<br/>health • CPU/RAM/GPU telemetry • resident models • active lease IDs"]:::compute
W_LONG["Long-poll assignment<br/>GET /assignments/next"]:::compute
W_ACK["Assignment ACK<br/>revalidate worker + node + Job + lease + epoch"]:::compute
W_EXEC["Worker executes bounded assignment"]:::compute
W_RESULT["Result submission<br/>lease + epoch + outcome + metrics + Artifact/result refs"]:::compute

CPUW["CPU sandbox worker<br/>heavy/untrusted CPU execution"]:::compute
GPUW["GPU worker<br/>disposable • non-authoritative"]:::compute

NODE_REG --> W_REG --> W_SESSION --> W_HB
W_SESSION --> W_LONG --> W_ACK --> W_EXEC --> W_RESULT
RL --> W_LONG
W_HB --> CN
CN --> NODE_REG
W_EXEC --> CPUW
W_EXEC --> GPUW
end

CS --> NODE_REG

%% =========================================================
%% 18. RUNPOD PROVIDER / GPU LIFECYCLE
%% =========================================================
subgraph RUNPOD["18. GPU PROVIDER & SCALE-TO-ZERO LIFECYCLE"]
direction TB

RP_ADAPT["RunPod ComputeProvider adapter<br/>provision • inspect • start • stop • terminate • estimate rate"]:::compute
RP_CRED["RunPod API credential<br/>SYSTEM Secret<br/>resolved only by Capacity Controller adapter"]:::security

P_ABS["ABSENT"]:::compute
P_PROV["PROVISIONING"]:::compute
P_BOOT["BOOTING"]:::compute
P_REG["REGISTERING"]:::compute
P_LOAD["LOADING"]:::compute
P_READY["READY"]:::compute
P_BUSY["BUSY"]:::compute
P_IDLE["IDLE_GRACE<br/>default design target 420s"]:::compute
P_DRAIN["DRAINING<br/>no new leases • settle safe work • persist metrics"]:::compute
P_STOP["STOPPING / STOPPED"]:::compute
P_TERM["TERMINATED"]:::compute
P_UNH["UNHEALTHY"]:::compute

CAP --> RP_ADAPT
RP_CRED --> RP_ADAPT
RP_ADAPT --> P_ABS --> P_PROV --> P_BOOT --> P_REG --> P_LOAD --> P_READY --> P_BUSY --> P_IDLE --> P_DRAIN --> P_STOP --> P_TERM
P_PROV --> P_UNH
P_BOOT --> P_UNH
P_REG --> P_UNH
P_BUSY --> P_UNH

RP_ADAPT --> W_BOOT --> W_REG
P_READY --> NODE_REG
end

%% =========================================================
%% 19. MODEL FABRIC / ROUTING / SERVING
%% =========================================================
subgraph MODELS["19. MODEL FABRIC, ROUTING & INFERENCE"]
direction TB

MREQ["ModelRequirement<br/>reasoning • coding • repository reasoning • tool use • structured output<br/>vision • min context • trust • latency • cost class"]:::model
MREG["Model Registry"]:::model
MPROF["ModelProfile<br/>family • model/revision • license • modalities • capabilities<br/>advertised/validated context • runtime compatibility • trust • benchmark status"]:::model
DPROF["DeploymentProfile<br/>model revision • runtime/version • quantization • container digest<br/>context • reasoning effort • hardware requirement • trust<br/>concurrency/batching • benchmark set • cost profile"]:::model
MROUTER["Model Router<br/>filters eligibility then ranks candidates"]:::model

subgraph LOGICAL["Logical requirement profiles"]
direction LR
MR_CONTROL["CONTROL"]:::model
MR_FASTGEN["FAST_GENERAL"]:::model
MR_FASTENG["FAST_ENGINEERING"]:::model
MR_PRIMARY["PRIMARY_ENGINEERING"]:::model
MR_DEEP["DEEP_REASONING"]:::model
MR_ASSURE["ASSURANCE"]:::model
MR_VISION["VISION"]:::model
MR_EMBED["EMBEDDING"]:::model
MR_RERANK["RERANKING"]:::model
MR_MEDIA["MEDIA_GENERATION"]:::model
MR_MAX["MAX_QUALITY_ESCALATION"]:::model
end

MREQ --> MREG --> MPROF --> DPROF --> MROUTER
MREQ --> MR_CONTROL
MREQ --> MR_FASTGEN
MREQ --> MR_FASTENG
MREQ --> MR_PRIMARY
MREQ --> MR_DEEP
MREQ --> MR_ASSURE
MREQ --> MR_VISION
MREQ --> MR_EMBED
MREQ --> MR_RERANK
MREQ --> MR_MEDIA
MREQ --> MR_MAX

BASEMODEL["Cloud v1 baseline profile<br/>Qwen/Qwen3.8-27B<br/>vLLM • A100 SXM 80 GB • 64K context<br/>RunPod Community Cloud"]:::model
COSTDOWN["Cost-down benchmark profile<br/>RTX A6000 48 GB + validated quantized Qwen<br/>or North Mini Code / Nemotron candidate"]:::model
PREMIUM["Premium/headroom profile<br/>RTX Pro 6000 96 GB when benchmarked value exists"]:::model
EXTMODEL["Optional external API profile<br/>EXTERNAL_API trust<br/>policy-permitted non-sensitive context only"]:::external

DPROF --> BASEMODEL
DPROF --> COSTDOWN
DPROF --> PREMIUM
DPROF --> EXTMODEL

VLLM["InferenceRuntime: vLLM<br/>worker-local/private<br/>health • profiles • ensure_loaded • generate • stream • cancel • metrics"]:::model
OLLAMA["InferenceRuntime: Ollama<br/>local compatibility adapter"]:::model
SGLANG["InferenceRuntime: SGLang<br/>future interchangeable adapter"]:::model

BASEMODEL --> VLLM
COSTDOWN --> VLLM
PREMIUM --> VLLM
MPROF --> OLLAMA
MPROF --> SGLANG

MROUTER --> CS
GPUW --> VLLM

INFREQ["InferenceRequest<br/>invocation/job/agent • deployment profile • ContextManifest<br/>prompt ref • output budget • temperature • reasoning effort • schema • timeout"]:::model
INFRESP["InferenceResponse<br/>status • model revision • runtime version • token counts<br/>finish reason • output ref • queue/setup/provider metrics"]:::model

MROUTER --> INFREQ
INFREQ --> VLLM --> INFRESP
INFRESP --> LOOP_PARSE

REASON["Reasoning effort selected per Job<br/>low • medium • high • max where supported"]:::model
CTXPROF["Context profile policy<br/>64K baseline • 128K only if measured • >128K explicit evidence"]:::model
QUANT["Quantization = separate DeploymentProfile<br/>must pass benchmark/quality/verification gates"]:::model
MREQ --> REASON
MREQ --> CTXPROF
DPROF --> QUANT
end

SSPEC --> MREQ

%% =========================================================
%% 20. REVERENDBENCH / MODEL PROMOTION
%% =========================================================
subgraph BENCH["20. REVERENDBENCH & MODEL/PROFILE ADMISSION"]
direction TB

BREG["ReverendBench Registry<br/>benchmark id/version • class • repo fixture • objective<br/>requirements • tool policy • acceptance • budget • repeats • sensitivity"]:::verify
B1["B1 Surgical change"]:::verify
B2["B2 Multi-file feature"]:::verify
B3["B3 Subsystem"]:::verify
B4["B4 Full project"]:::verify
B5["B5 Complex evolving project"]:::verify

BRES["BenchmarkResultSet<br/>deployment profile • Reverend commit • Specialist versions<br/>context compiler version • Task results • verification • interventions<br/>repair rounds • tokens • GPU time • billed time • cost"]:::verify

PROMRULE["Promotion rule<br/>mandatory quality gates + verification + human intervention + fit + trust/license<br/>and materially better GBP / verified successful engineering Task"]:::verify

BREG --> B1
BREG --> B2
BREG --> B3
BREG --> B4
BREG --> B5
B1 --> BRES
B2 --> BRES
B3 --> BRES
B4 --> BRES
B5 --> BRES
BRES --> PROMRULE
PROMRULE --> DPROF
end

%% =========================================================
%% 21. DURABLE EXECUTION / CHECKPOINT / RECOVERY
%% =========================================================
subgraph DURABILITY["21. DURABLE EXECUTION, CHECKPOINTING & RECOVERY"]
direction TB

SAFELOOP["Safe execution boundary<br/>prepare → persist intent → execute → observe → persist result<br/>→ commit workflow state → checkpoint → safe interruption"]:::durable

CPBUILD["Checkpoint publication<br/>build manifest → write blobs → fsync/hash verify<br/>→ insert incomplete → validate refs → complete=true<br/>→ advance active checkpoint + Event"]:::durable

PAUSE["Normal pause<br/>stop new admission → settle current action → checkpoint<br/>→ release leases → PAUSED"]:::durable
APPWAIT["Approval wait<br/>persist Approval + checkpoint → release compute → AWAITING_APPROVAL"]:::durable
APPRSM["Approval resume<br/>decision persisted → RESUME_QUEUED → fresh lease<br/>→ revalidate fingerprint/owner/identity/policy → execute"]:::durable

RECCTRL["Recovery Controller<br/>new runtime_epoch • invalidate stale workers/leases<br/>recover non-terminal Runs"]:::durable

RECALG["Run recovery<br/>newest complete valid checkpoint<br/>→ verify blobs/workspace<br/>→ inspect Action Journal after watermark<br/>→ reconcile STARTED/UNKNOWN<br/>→ PAUSED / AWAITING_APPROVAL / RESUME_QUEUED / RECOVERY_BLOCKED"]:::durable

RBLOCK["RecoveryIssue / RECOVERY_BLOCKED<br/>show ambiguous action • evidence • last checkpoint • safe human choices"]:::durable

RECGEN["RecoveryGeneration<br/>generation number • PostgreSQL backup ref • checkpoints • journal<br/>repository refs • Artifact refs • encrypted Secret backup • hashes • complete"]:::durable
RECACK["RecoveryReplicaAck<br/>device • generation • hash • ACK only after fsync + verification"]:::durable
CLEAN["CleanShutdownRecord<br/>runtime_epoch • final generation • completed_at • reason"]:::durable

SAFELOOP --> ACTION
SAFELOOP --> CHECK
CHECK --> CPBUILD
PAUSE --> CPBUILD
APPWAIT --> CPBUILD
APPROVAL --> APPWAIT --> APPRSM
RECCTRL --> RECALG
CHECK --> RECALG
ACTION --> RECALG
RECALG --> RBLOCK
RECALG --> RECGEN --> RECACK --> CLEAN
end

RN --> SAFELOOP
PRQ --> PAUSE
RCV --> RECCTRL
A_REC --> RECACK
B_REC --> RECACK

%% =========================================================
%% 22. STORAGE / DATABASE / BLOB / WORKSPACE / INDEXES
%% =========================================================
subgraph STORAGE["22. PERSISTENCE & STORAGE LAYERS"]
direction TB

PG["PostgreSQL<br/>Cloud v1 authoritative structured state<br/>transactions • constraints • advisory locks • append-only Events/Cost"]:::data

subgraph PGTABLES["Primary PostgreSQL domains"]
direction LR
PG_ID["users • devices • auth_sessions"]:::data
PG_PROJ["projects • project_members"]:::data
PG_RUN["runs • workflows • tasks • dependencies • jobs"]:::data
PG_EA["events • artifacts • artifact_parents"]:::data
PG_PM["requirements • decisions • memory_records"]:::data
PG_AGENT["agent_specs • agent_instances • agent_teams"]:::data
PG_SEC["approvals • secret metadata"]:::data
PG_DUR["run_checkpoints • action_records • recovery_generations • replica_acks"]:::data
PG_COMP["compute_nodes • resource_requests • resource_leases"]:::data
PG_IDEMP["idempotency_records"]:::data
PG_COST["rate_snapshots • cost_events • power sessions • lease usage"]:::data
end

BLOB["FileBlobStore<br/>content-addressed SHA-256 immutable objects<br/>temp write → fsync → atomic rename → verify"]:::data
WSROOT["Workspace storage<br/>Run/Task worktrees • isolated branches • recoverable diffs/untracked manifests"]:::data
GITREF["Git checkpoint refs<br/>refs/reverend/checkpoints/{run}/{sequence}"]:::data
QDRANT["Qdrant / vector index<br/>derived/reconstructible semantic retrieval state"]:::data
CACHE["Reconstructible caches<br/>model weights • runtime cache • build outputs • embeddings • KV cache"]:::data
BACKUP["Encrypted backup storage<br/>PostgreSQL + BlobStore + recovery metadata + encrypted Secret-store material"]:::data
KEYFILE["Protected host key material<br/>outside repository/DB"]:::security

PG --> PG_ID
PG --> PG_PROJ
PG --> PG_RUN
PG --> PG_EA
PG --> PG_PM
PG --> PG_AGENT
PG --> PG_SEC
PG --> PG_DUR
PG --> PG_COMP
PG --> PG_IDEMP
PG --> PG_COST

CPROOT --> PG
ART --> BLOB
CHECK --> BLOB
RUN --> WSROOT --> GITREF
CB --> QDRANT
DPROF --> CACHE
RECGEN --> BACKUP
MASTER --> KEYFILE
end

%% =========================================================
%% 23. COST / BILLING / BUDGETS
%% =========================================================
subgraph ECON["23. ECONOMICS, BILLING & BUDGET CONTROL"]
direction TB

POWER["PowerSession<br/>provider instance lifecycle + billable interval<br/>deployment profile • native rate • estimated/actual GBP • reconciliation"]:::cost
LEASEUSE["ComputeLeaseUsage<br/>lease • user/project/run/job/node • duration • rate • estimated GBP"]:::cost
FX["FX / provider RateSnapshot<br/>historical rates frozen for settlement"]:::cost
RECON["Provider reconciliation<br/>query actual → compare estimate → append reconciliation CostEvent"]:::cost

subgraph ATTR["Cost attribution policy"]
direction LR
VAR["Variable Run-specific cost<br/>100% Run owner"]:::cost
FIXED["Persistent Control Plane / baseline backup/storage<br/>initially 50/50 shared"]:::cost
TRANSIENT["Boot / warm-up / idle grace / drain overhead<br/>initially 50/50 shared"]:::cost
ZEROCOST["PAUSED / AWAITING_APPROVAL / RESUME_QUEUED<br/>GBP 0 active compute without lease"]:::cost
end

subgraph BUDGETS["Budget hierarchy"]
direction LR
BU["User monthly"]:::cost
BR["Run"]:::cost
BT["Team"]:::cost
BTA["Task"]:::cost
BA["Agent"]:::cost
BJ["Job / operation"]:::cost
end

SOFT["Soft limit<br/>warning + optional workload reduction"]:::cost
HARD["Hard limit<br/>block next charge-bearing action at safe boundary<br/>never interrupt unsafe side effect midway"]:::cost

DASH["Cost dashboard<br/>estimated vs reconciled actual<br/>GPU/CPU/API/shared overhead • remaining budget"]:::cost
METRIC["Primary optimization metric<br/><b>GBP per verified successful engineering Task</b>"]:::cost

RP_ADAPT --> POWER
RL --> LEASEUSE
RATE --> FX
POWER --> COSTEV
LEASEUSE --> COSTEV
FX --> COSTEV
COSTEV --> RECON
RECON --> COSTEV

RUN --> VAR
ROOT --> FIXED
POWER --> TRANSIENT
PSD --> ZEROCOST
AWA --> ZEROCOST
RQ --> ZEROCOST

BU --> BR --> BT --> BTA --> BA --> BJ
BJ --> SOFT
BJ --> HARD
COSTEV --> DASH
DASH --> METRIC
BUDRES --> BUDGETS
end

%% =========================================================
%% 24. OBSERVABILITY / EVENTS / METRICS / HEALTH
%% =========================================================
subgraph OBS["24. OBSERVABILITY, TRACEABILITY & HEALTH"]
direction TB

TRACE["Trace lineage<br/>request • user • Project • Run • Workflow • Task • Agent • Job<br/>lease • node • Action • model invocation"]:::ops
LOG["Structured JSON logs<br/>redacted • no secrets • no raw chain-of-thought"]:::ops
METRICS["Operational metrics<br/>API • scheduler • Run • Agent • model • compute • recovery • cost"]:::ops
AUDIT["Immutable privileged audit Events<br/>principal • capability • scope • Approval • external identity • result"]:::ops
SSEPROJ["SSE presentation projection<br/>durable Event sequence + resumable cursor"]:::ops

HEALTH["Health model"]:::ops
LIVE["Liveness"]:::ops
READY["Readiness<br/>PostgreSQL • schema • Secret key • recovery gate • controllers"]:::ops
FUNC["Functional health<br/>real bounded model/tool smoke"]:::ops
PROVHEALTH["Provider / worker health"]:::ops
RECHEALTH["Recovery health<br/>generation age + replica ACK"]:::ops

ALERT["Alert conditions<br/>DB unavailable • scheduler leader missing • old recovery generation<br/>worker/provision failures • billing mismatch • hard-budget bypass<br/>Secret key missing • RECOVERY_BLOCKED • backup failure • low disk"]:::ops

TRACE --> LOG
TRACE --> METRICS
EVENT --> AUDIT
EVENT --> SSEPROJ
R_SSE --> SSEPROJ

HEALTH --> LIVE
HEALTH --> READY
HEALTH --> FUNC
HEALTH --> PROVHEALTH
HEALTH --> RECHEALTH
LIVE --> ALERT
READY --> ALERT
FUNC --> ALERT
PROVHEALTH --> ALERT
RECHEALTH --> ALERT
end

%% =========================================================
%% 25. GIT / GITHUB AUTHORITY
%% =========================================================
subgraph GITSEC["25. GIT / GITHUB IDENTITY & INTEGRATION AUTHORITY"]
direction TB

GITOWNER["Run → immutable owner_user_id → GitHubIdentity"]:::security
GITAUTHOR["Commit identity<br/>git user.name/email from Run owner"]:::security
GITAUTH["Push / PR authentication<br/>owner credential_ref resolved server-side"]:::security

GALLOW["Automatic within isolated Run branch<br/>inspect • worktree • commit • push Run branch • create/update PR"]:::tool
GAPPROVE["Approval required / repo protection<br/>protected/default mutation • merge • force push • remote branch delete"]:::security
GDENY["Denied<br/>repository delete • org administration • permission escalation"]:::security

RUN --> GITOWNER --> GITHUBID
GITHUBID --> GITAUTHOR
GITHUBID --> GITAUTH
GITAUTHOR --> T_COMMIT
GITAUTH --> T_PUSH
GITAUTH --> T_PR
GALLOW --> T_BRANCH
GALLOW --> T_COMMIT
GALLOW --> T_PUSH
GALLOW --> T_PR
GAPPROVE --> T_MERGE
GDENY -. prevents .-> TOOLBROKER
end

%% =========================================================
%% 26. EMERGENCY CONTROLS
%% =========================================================
subgraph EMERGENCY["26. EMERGENCY / OPERATOR CONTROL"]
direction LR

STOPRUN["STOP_RUN(run_id)<br/>safe stop/cancel one Run"]:::security
STOPPROJ["STOP_PROJECT(project_id)<br/>stop active + block new Project work"]:::security
STOPGLOBAL["STOP_GLOBAL<br/>stop all new model/tool work until authorized clear"]:::security
MAINT["Maintenance mode<br/>reads/auth available • no new Run STARTING • safe drain"]:::security

R_SYS --> STOPRUN
R_SYS --> STOPPROJ
R_SYS --> STOPGLOBAL
R_SYS --> MAINT
STOPRUN --> PE
STOPPROJ --> PE
STOPGLOBAL --> PE
MAINT --> WS
end

%% =========================================================
%% 27. DEPLOYMENT TOPOLOGY
%% =========================================================
subgraph DEPLOY["27. PHYSICAL CLOUD v1 DEPLOYMENT"]
direction TB

HETZ["Persistent Control Plane host<br/>Hetzner CX33-class x86 baseline<br/>4 vCPU • 8 GB RAM • 80 GB NVMe • EU region"]:::compute
SYSTEMD["systemd services / timers<br/>Reverend app • PostgreSQL • backup • recovery replication"]:::ops
DISK["Host storage layout<br/>/var/lib/reverend objects/workspaces/backups/state<br/>/etc/reverend protected config/key material"]:::data
REVPROC["Reverend modular-monolith process<br/>API + orchestration + schedulers + context + policy + cost + recovery coordination"]:::authority
PGHOST["Local/private PostgreSQL"]:::data
RPROXY["Caddy/nginx reverse proxy"]:::security

HETZ --> SYSTEMD
SYSTEMD --> REVPROC
SYSTEMD --> PGHOST
HETZ --> DISK
HETZ --> RPROXY
RPROXY --> REVPROC
REVPROC --> PGHOST
REVPROC --> CPROOT
end

RP --> RPROXY

%% =========================================================
%% 28. EXTERNAL SYSTEMS
%% =========================================================
subgraph EXTERNAL["28. EXTERNAL SYSTEMS / PROVIDERS / SOURCES"]
direction LR

EXT_GH["GitHub<br/>repositories • branches • PRs • remote state"]:::external
EXT_RP["RunPod Community Cloud<br/>baseline disposable GPU provider"]:::external
EXT_RPSEC["RunPod Secure / dedicated class<br/>stronger trust fallback"]:::external
EXT_HETZ["Hetzner Cloud<br/>persistent Control Plane host"]:::external
EXT_TS["Tailscale<br/>private network"]:::external
EXT_WEB["Public web / SearXNG"]:::external
EXT_HF["Model repositories / Hugging Face<br/>pinned revisions / weights / licenses"]:::external
EXT_API["Optional paid external APIs<br/>policy/trust/budget gated"]:::external

T_PUSH --> EXT_GH
T_PR --> EXT_GH
T_MERGE --> EXT_GH
RP_ADAPT --> EXT_RP
CS -. stronger trust job .-> EXT_RPSEC
HETZ --> EXT_HETZ
TS --> EXT_TS
T_SEARCH --> EXT_WEB
T_FETCH --> EXT_WEB
DPROF --> EXT_HF
EXTMODEL --> EXT_API
end

%% =========================================================
%% 29. LOCAL 0.4.0 COMPATIBILITY
%% =========================================================
subgraph LOCAL["29. LOCAL REVEREND 0.4.0 COMPATIBILITY PATH"]
direction TB

LOCALROOT["Current local-first mode<br/>Linux / WSL2"]:::client
LOCALGUI["Loopback Workstation<br/>127.0.0.1:8765<br/>Host/Origin/session-token checks"]:::client
LOCALSQL["SQLite local stores<br/>compatibility / archive / local mode"]:::data
LOCALOLL["Ollama local inference"]:::model
LOCALRES["Process-local resource broker / fcntl scheduling"]:::sched
LOCALSEARCH["Self-hosted loopback SearXNG"]:::tool
LOCALQ["Qdrant embedded/server mode"]:::data

LOCALROOT --> LOCALGUI
LOCALGUI --> LOCALSQL
LOCALGUI --> LOCALOLL
LOCALGUI --> LOCALRES
LOCALGUI --> LOCALSEARCH
LOCALGUI --> LOCALQ

MIGRULE["Migration rule<br/>Cloud implementation extends semantic contracts<br/>without deleting local functionality before equivalent Cloud path exists"]:::dev
LOCALROOT --> MIGRULE
MIGRULE --> CPROOT
end

%% =========================================================
%% 30. POSTGRES MIGRATIONS / CONTRACT VERSIONING
%% =========================================================
subgraph MIGRATION["30. SCHEMA, CONTRACT & MIGRATION VERSIONING"]
direction TB

VERS["Frozen v1 contracts<br/>REST API • SSE Event • Run lifecycle • RunCheckpoint • ActionRecord<br/>RecoveryGeneration • Approval • Artifact • AgentSpec/Instance<br/>ComputeNode • ResourceRequest/Lease • CostEvent/RateSnapshot • worker registration"]:::dev

M001["0001 identity"]:::dev
M002["0002 projects/runs"]:::dev
M003["0003 Control Plane"]:::dev
M004["0004 Artifacts/Agents"]:::dev
M005["0005 approvals/recovery"]:::dev
M006["0006 compute"]:::dev
M007["0007 costs"]:::dev
M008["0008 indexes/constraints"]:::dev

COMPAT["Compatibility rules<br/>additive optional fields stay v1<br/>semantic changes require explicit version/migration<br/>old persisted objects remain readable or deliberately migrated"]:::dev

VERS --> M001 --> M002 --> M003 --> M004 --> M005 --> M006 --> M007 --> M008
VERS --> COMPAT
M008 --> PG
end

%% =========================================================
%% 31. DEVELOPMENT PROGRAMME C0–C9
%% =========================================================
subgraph DEVPHASE["31. DEVELOPMENT PROGRAMME"]
direction LR

C0D["C0<br/>contracts + migration skeleton"]:::dev
C1D["C1<br/>PostgreSQL Control Plane"]:::dev
C2D["C2<br/>identity + API + SSE"]:::dev
C3D["C3<br/>Run + queue + workflow convergence"]:::dev
C4D["C4<br/>Agent + Team + Context runtime"]:::dev
C5D["C5<br/>security + Git + secrets + approvals"]:::dev
C6D["C6<br/>durable execution + recovery"]:::dev
C7D["C7<br/>compute fabric + RunPod + vLLM"]:::dev
C8D["C8<br/>economics + budgets + operational UX"]:::dev
C9D["C9<br/>full Cloud acceptance"]:::dev

C0D --> C1D --> C2D --> C3D --> C4D --> C5D --> C6D --> C7D --> C8D --> C9D
end

%% =========================================================
%% 32. TEST / CI / ACCEPTANCE
%% =========================================================
subgraph TESTING["32. TESTING, CI, FAULT INJECTION & ACCEPTANCE"]
direction TB

UNIT["Unit tests<br/>validation • state transitions • policy • cost math • context"]:::verify
PGINT["PostgreSQL integration<br/>transactions • concurrency • idempotency • immutable events • advisory leadership"]:::verify
APIINT["API/browser integration<br/>auth • CSRF • membership • SSE replay"]:::verify
AGTINT["Agent/Team integration<br/>budgets • context • typed Artifact • mutation isolation"]:::verify
SECINT["Security/adversarial<br/>identity spoofing • secret leakage • trust downgrade • sandbox escape attempts"]:::verify
FAULT["Fault injection<br/>crash around Action • checkpoint • Git push • approval • inference • provider stop • backup"]:::verify
LIVEPROV["Live provider validation<br/>RunPod provisioning • worker auth • vLLM load • Qwen smoke"]:::verify
BILLTEST["Billing reconciliation tests"]:::verify
RESTORE["Blank-host restore test<br/>PostgreSQL + BlobStore + Secret recovery"]:::verify
FULL["Full Cloud E2E acceptance<br/>A12 E2E-01 … E2E-22"]:::verify

UNIT --> PGINT --> APIINT --> AGTINT --> SECINT --> FAULT --> LIVEPROV --> BILLTEST --> RESTORE --> FULL
C9D --> FULL
end

%% =========================================================
%% 33. A12 END-TO-END ACCEPTANCE SCENARIOS
%% =========================================================
subgraph E2E["33. A12 FULL END-TO-END ACCEPTANCE MATRIX"]
direction TB

E01["E2E-01 two-user identity isolation"]:::verify
E02["E2E-02 Run owner / Git identity"]:::verify
E03["E2E-03 one active top-level Run"]:::verify
E04["E2E-04 safe pre-emption"]:::verify
E05["E2E-05 client disconnect survives"]:::verify
E06["E2E-06 GPU scales from zero"]:::verify
E07["E2E-07 GPU worker loss recovery"]:::verify
E08["E2E-08 crash during inference"]:::verify
E09["E2E-09 crash during Git push reconciles remote"]:::verify
E10["E2E-10 ambiguous side effect → RECOVERY_BLOCKED"]:::verify
E11["E2E-11 approval releases compute"]:::verify
E12["E2E-12 secret isolation"]:::verify
E13["E2E-13 cost attribution"]:::verify
E14["E2E-14 hard budget boundary"]:::verify
E15["E2E-15 verification before integration"]:::verify
E16["E2E-16 Control Plane available at zero GPU"]:::verify
E17["E2E-17 Control Plane disaster recovery"]:::verify
E18["E2E-18 context/provenance integrity"]:::verify
E19["E2E-19 bounded AgentTeam expansion"]:::verify
E20["E2E-20 cost-down model promotion only after evidence"]:::verify
E21["E2E-21 Community worker trust isolation"]:::verify
E22["E2E-22 stronger-trust workload rejected from Community node"]:::verify

FULL --> E01
FULL --> E02
FULL --> E03
FULL --> E04
FULL --> E05
FULL --> E06
FULL --> E07
FULL --> E08
FULL --> E09
FULL --> E10
FULL --> E11
FULL --> E12
FULL --> E13
FULL --> E14
FULL --> E15
FULL --> E16
FULL --> E17
FULL --> E18
FULL --> E19
FULL --> E20
FULL --> E21
FULL --> E22
end

%% =========================================================
%% 34. OPERATIONAL RUNBOOKS
%% =========================================================
subgraph RUNBOOKS["34. REQUIRED OPERATIONAL RUNBOOKS"]
direction LR

RB_RESTORE["Restore PostgreSQL / BlobStore"]:::ops
RB_KEY["Rotate master Secret key"]:::ops
RB_GH["Rotate GitHub credential"]:::ops
RB_RP["Rotate RunPod API key"]:::ops
RB_BLOCK["Recover RECOVERY_BLOCKED Run"]:::ops
RB_HOST["Replace Control Plane host"]:::ops
RB_OUT["Handle provider outage"]:::ops
RB_DRAIN["Drain GPU worker"]:::ops
RB_COMP["Disable compromised worker"]:::ops
RB_STOP["Project / Global emergency stop"]:::ops
RB_UP["Cloud upgrade"]:::ops
RB_BILL["Billing mismatch reconciliation"]:::ops
end

OBS --> RUNBOOKS

%% =========================================================
%% 35. CRITICAL CROSS-SYSTEM FLOWS
%% =========================================================

%% Human submission
U_A -->|authenticate| SESSION
SESSION -->|POST Run objective| R_RUNS
R_RUNS -->|create immutable owner| RUN
RUN -->|queue| WS
WS -->|ready Task| AINST

%% Cognitive execution
AINST -->|context request| CB
CC -->|ContextManifest + prompt| MREQ
MROUTER -->|eligible deployment| CS
CS -->|ResourceLease| RL
RL -->|assignment| W_LONG
W_EXEC -->|inference| VLLM
INFRESP -->|structured output| LOOP_PARSE

%% Tool execution
LOOP_PARSE -->|proposed action| TOOLBROKER
PE -->|ALLOW| TOOLS
PE -->|APPROVAL_REQUIRED| APPROVAL
PE -->|DENY| SIG_FAIL

%% Privileged Git
T_PUSH -->|credential request| SECB
SECB -->|bounded credential injection| T_PUSH
T_PUSH -->|remote side effect| EXT_GH
T_PUSH --> ACTION

%% Verification
AIMPL --> DET
DET -->|pass evidence| INDEP
INDEP --> AVER
AVER --> ACC
ACC -->|accepted| PROMO

%% Events/UI
CPROOT -->|transactional state + Event| EVENT
EVENT -->|sequence replay| R_SSE
R_SSE -->|SSE| A_GUI
R_SSE -->|SSE| B_GUI

%% Cost
CAP -->|provider lifecycle| RP_ADAPT
RP_ADAPT --> POWER
RL --> LEASEUSE
POWER --> COSTEV
LEASEUSE --> COSTEV
COSTEV --> DASH

%% Pause / recovery
PRQ --> SAFELOOP
SAFELOOP --> CHECK
CHECK -->|complete checkpoint| PSD
W_HB -->|lost heartbeat| RECCTRL
RECCTRL --> RECALG
RECALG -->|safe| RQ
RECALG -->|ambiguous| RCB

%% Stronger trust
MREQ -->|trust requirement| PLACEMENT
PLACEMENT -->|Community insufficient| EXT_RPSEC

%% Scale to zero
P_IDLE -->|idle grace expires| P_DRAIN
P_DRAIN -->|leases settled + worker non-authoritative| P_STOP
P_STOP -->|GPU count may become zero| READY

%% Backups
PG --> BACKUP
BLOB --> BACKUP
BACKUP --> RECGEN
RECGEN --> A_REC
RECGEN --> B_REC

%% Development lineage
C0D --> VERS
C1D --> PG
C2D --> FASTAPI
C3D --> RUN
C4D --> AINST
C5D --> TOOLBROKER
C6D --> RECCTRL
C7D --> RP_ADAPT
C8D --> COSTEV
C9D --> FULL

%% =========================================================
%% 36. FINAL SYSTEM OUTCOME
%% =========================================================
OUTCOME["SYSTEM OUTCOME<br/>High-level human objective<br/>→ researched + planned + implemented + tested + repaired + independently verified project result<br/>→ reviewable isolated Git state / PR<br/>with durable provenance, recoverable execution, bounded authority, explicit cost and human control"]:::authority

PROMO --> OUTCOME
FULL --> OUTCOME
~~~

## Reading Rule

The diagram should be read from top to bottom:

**human authority → authenticated client/server boundary → authoritative Control Plane → cognitive orchestration → bounded context/model/tool execution → deterministic assurance → replaceable compute → durable recovery → auditable cost/operations → Development and acceptance.**

The most important architectural boundary is that the central PostgreSQL-backed Control Plane remains authoritative while clients, Agents, models, workers, caches and provider resources remain replaceable or derived.
