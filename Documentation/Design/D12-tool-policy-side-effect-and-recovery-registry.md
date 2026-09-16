# D12 — Tool Policy, Side-Effect & Recovery Registry

> **Status:** DESIGN CLOSED / NORMATIVE TOOL SAFETY CONTRACT  
> **Depends on:** D3, D5, D6, D8, D10  
> **Companion manifest:** D12-tool-policy-recovery-registry.yaml  
> **Purpose:** Centralize production rules for every agent-accessible or autonomous side-effecting operation.

---

## 1. Governing Rule

A tool is production-eligible only when all of these are defined:

~~~text
typed input/output
+ required capability
+ risk class
+ side-effect class
+ trusted executor
+ network/sandbox policy
+ secret policy
+ approval policy
+ Action Journal rule
+ interruption rule
+ resume strategy
+ reconciler/result verification
+ cost behavior
~~~

No ad-hoc subprocess/HTTP/Git/provider call may bypass this registry.

---

## 2. ToolDescriptor v1

~~~text
ToolDescriptor
├── tool_name
├── operation
├── schema_version
├── input_schema
├── output_schema
├── required_capability
├── risk_class
├── side_effect_class
├── trusted_executor
├── allowed_trust_classes
├── sandbox_profile
├── mutation_scope_required
├── network_policy
├── secret_classes
├── approval_policy
├── action_journal
├── checkpoint_policy
├── interruptibility
├── resume_strategy
├── reconciler
├── result_verifier
├── timeout_policy
├── cost_category
└── observability_policy
~~~

Agents receive a reduced schema. Enforcement-only fields remain trusted.

---

## 3. Side-Effect and Resume Classes

D5 classes remain canonical:

~~~text
PURE_READ
REPEATABLE_COMPUTE
LOCAL_MUTATION
REMOTE_IDEMPOTENT
REMOTE_RECONCILABLE
IRREVERSIBLE_OR_HIGH_RISK
~~~

Resume strategies:

~~~text
RESTART
VERIFY_THEN_RETRY
REBUILD
MANUAL_RECOVERY
~~~

Any operation capable of UNKNOWN must have a reconciler or intentionally produce RECOVERY_BLOCKED.

---

## 4. Capability Direction

Cloud capabilities should be operation-specific rather than rely indefinitely on compatibility-level tool.execute.

Target examples:

~~~text
repo.read
repo.mutate
process.execute
network.search
network.fetch
reference.read
git.branch
git.commit
git.push_run_branch
github.pr.write
git.protected_mutate
compute.infer
compute.embed
provider.lifecycle
recovery.write
deployment.external_mutate
system.emergency_control
~~~

Existing policy/adapters.py remains a migration input until C5.

---

## 5. Canonical Operation Matrix

| Operation | Side effect | Approval | Journal | Resume | Secret | Boundary |
|---|---|---|---|---|---|---|
| file/repository read | PURE_READ | none | optional | RESTART | none | repository adapter |
| grep/glob/symbol lookup | PURE_READ | none | optional | RESTART | none | repository intelligence |
| Git status/diff/history | PURE_READ | none | optional | RESTART | none | trusted Git adapter |
| structured patch/edit | LOCAL_MUTATION | none in isolated allowed scope | required if duplicate matters | VERIFY_THEN_RETRY | none | isolated worktree |
| bounded shell/build/test/lint | REPEATABLE_COMPUTE | policy | optional | RESTART | none | fail-closed sandbox |
| package/dependency mutation | LOCAL_MUTATION | Project policy | required | REBUILD | registry secret if configured | sandbox + restricted registry network |
| background process start/stop | LOCAL_MUTATION | policy | required when state matters | REBUILD / VERIFY_THEN_RETRY | none | sandbox supervisor |
| create worktree/Run branch | LOCAL_MUTATION | none | required | VERIFY_THEN_RETRY | none | trusted Git adapter |
| commit Run branch | LOCAL_MUTATION | none | required | VERIFY_THEN_RETRY | author identity only | trusted Git adapter |
| push Run branch | REMOTE_RECONCILABLE | none default | required | VERIFY_THEN_RETRY | Run-owner GitHub | Control Plane adapter |
| create/update PR | REMOTE_RECONCILABLE | none default | required | VERIFY_THEN_RETRY | Run-owner GitHub | Control Plane adapter |
| merge/default-branch mutation | IRREVERSIBLE_OR_HIGH_RISK | required | required | VERIFY_THEN_RETRY | authorized GitHub | Control Plane adapter |
| force push | IRREVERSIBLE_OR_HIGH_RISK | elevated; normally disabled | required | MANUAL_RECOVERY or explicit reconciler | authorized GitHub | Control Plane only |
| delete remote branch | IRREVERSIBLE_OR_HIGH_RISK | required | required | VERIFY_THEN_RETRY | authorized GitHub | Control Plane only |
| repo/org permission change | IRREVERSIBLE_OR_HIGH_RISK | deny | n/a | n/a | n/a | unavailable |
| repository delete | IRREVERSIBLE_OR_HIGH_RISK | deny | n/a | n/a | n/a | unavailable |
| public web search | PURE_READ | network policy | optional; cost when paid | RESTART | provider API | restricted research adapter |
| public web fetch | PURE_READ | network policy | optional | RESTART | none | SSRF-hardened worker |
| reference retrieval | PURE_READ | none | optional | RESTART | none | reference adapter |
| image acquisition | PURE_READ | network policy | optional | RESTART | none | restricted media worker |
| model inference | REPEATABLE_COMPUTE | none | Job/lease lineage | RESTART | none | eligible model worker |
| embedding/rerank | REPEATABLE_COMPUTE | none | metrics/Job lineage | RESTART | none | eligible worker |
| RunPod provision/start | REMOTE_RECONCILABLE | Capacity policy | required | VERIFY_THEN_RETRY | SYSTEM RunPod | Capacity Controller only |
| RunPod stop/terminate | REMOTE_RECONCILABLE | safety/economic policy | required | VERIFY_THEN_RETRY | SYSTEM RunPod | Capacity Controller only |
| recovery replication | REMOTE_RECONCILABLE | system policy | system Action required | VERIFY_THEN_RETRY | recovery target | Recovery service |
| external deployment | IRREVERSIBLE_OR_HIGH_RISK | required unless future narrow policy | required | adapter-specific; default MANUAL | deployment secret | typed adapter only |
| emergency stop | control effect | authorized operator | durable control Event; Action for external cleanup | VERIFY_THEN_RETRY | cleanup only | Control Plane |
| plaintext secret export | IRREVERSIBLE_OR_HIGH_RISK | deny default | security audit | n/a | Secret Broker | no generic Agent tool |

---

## 6. MutationScope

Every filesystem/Git mutation requires an effective MutationScope:

- Project;
- Run;
- workspace/worktree;
- branch/ref;
- allowed path set;
- protected exclusions.

Enforce before resolution, during execution and after execution by diff verification.

Passing tests never excuses out-of-scope mutation.

---

## 7. Network Profiles

Minimum profiles:

~~~text
NETWORK_OFF
PUBLIC_SEARCH_ONLY
PUBLIC_FETCH_RESTRICTED
PACKAGE_REGISTRY_RESTRICTED
PROVIDER_ADAPTER_ONLY
GITHUB_ADAPTER_ONLY
~~~

A generic shell does not gain public network merely because an Agent requests it.

Network-enabled work uses a dedicated descriptor/adapter.

---

## 8. Secret Classes

Tools declare secret classes, not plaintext:

~~~text
USER_GITHUB
SYSTEM_RUNPOD
SEARCH_PROVIDER_API
PACKAGE_REGISTRY
DEPLOYMENT_PROVIDER
RECOVERY_TARGET
RUN_EPHEMERAL
~~~

Secret Broker validates service identity, scope, operation, destination, Approval, revocation and action fingerprint.

---

## 9. Approval Binding

Approval is not a reusable boolean.

Immediately before effect validate:

- Approval state/expiry;
- Run/Project;
- immutable owner when relevant;
- effective external identity;
- action fingerprint;
- target;
- current Project policy;
- remote precondition such as expected Git HEAD.

Consumption and Action intent are atomic where D5 requires.

---

## 10. Action Journal Rule

ActionRecord is mandatory before:

- remote side effect;
- local durable mutation whose duplicate matters;
- provider lifecycle;
- protected Git;
- recovery/backup external effects;
- external deployment.

Pure reads/repeatable compute normally rely on Job/trace/cost lineage without ActionRecord unless a specific descriptor needs one.

---

## 11. Provider Lifecycle Is Not an Agent Tool

Agents may create demand, not provider authority:

~~~text
Task / Job
→ ResourceRequest
→ Compute Scheduler
→ Capacity Controller
→ provider.lifecycle descriptor
~~~

Only Capacity Controller resolves provider lifecycle credentials.

---

## 12. Git Remote Side Effects

Remote Git/GitHub actions use trusted server adapters.

Run branch push:

1. persist Action intent;
2. resolve immutable Run-owner GitHub identity;
3. pin repository/ref/expected head;
4. execute;
5. query/verify remote state;
6. persist exact result;
7. reconcile before any retry after interruption.

Credential-bearing remotes never pass through arbitrary model/shell strings.

---

## 13. Package Operations

Package mutation:

- isolated workspace only;
- registry-restricted network, not general web;
- visible lockfile/diff;
- build scripts sandboxed;
- scoped registry credential only when required;
- uncertain environment rebuilt after crash.

---

## 14. Background Processes

Process handles are not durable authority.

Persist only metadata needed to poll/stop while alive and to classify the process as lost after worker failure.

Durable Task state reconstructs required work; arbitrary process memory is never recovered.

---

## 15. External Deployment

Cloud v1 has no generic autonomous production-deployment capability.

A future deployment adapter must define target, precondition, rollback/reconciliation, approval, credential, cost, health verification and ambiguity semantics.

Until then deployment.external_mutate is disabled by default.

---

## 16. New Tool Admission

Any new operation requires:

1. typed descriptor;
2. D12 manifest entry;
3. capability registration;
4. policy tests;
5. sandbox/network review;
6. secret scope if needed;
7. D5 recovery classification/reconciler;
8. cost integration if paid;
9. observability/redaction definition;
10. fault injection for side effects;
11. ADR if architecture changes.

Missing mandatory data means not production eligible.

---

## 17. Machine-Readable Manifest

D12-tool-policy-recovery-registry.yaml is the design inventory.

During C0/C5 it should be parsed/validated by tests and compared with or used to seed code descriptors.

The YAML itself is not runtime authorization. PostgreSQL policy/Approval state plus trusted enforcement code remain authoritative.

---

## 18. Recovery Testing

For each REMOTE_RECONCILABLE/high-risk operation inject failures:

- before effect;
- after effect before result persistence;
- during result verification;
- after completion before checkpoint.

Final outcome must be safe retry, verified completion, explicit failure or RECOVERY_BLOCKED — never silent duplicate execution.

---

## 19. Exit Condition

D12 is satisfied when a developer adding a tool does not need to invent approval, secret, network, journal, resume, execution, reconciliation or cost semantics.


---

## 20. Capability-Modernization Registry Addendum

D16–D20 introduce additional capability operations that remain subject to this registry.

| Operation | Side effect | Boundary |
|---|---|---|
| Repository Intelligence query / LSP read | PURE_READ | isolated Repository Intelligence adapter |
| dependency acquisition | REPEATABLE_COMPUTE | isolated CPU worker + restricted registry network |
| browser research acquisition | PURE_READ | RESEARCH_BROWSER + public egress policy |
| frontend browser verification | REPEATABLE_COMPUTE | FRONTEND_TEST_BROWSER + task-scoped TestEndpoint |
| large Artifact upload | REMOTE_IDEMPOTENT | Job-scoped Blob capability |

Rules:

- browser automation is not a generic network bypass;
- LSP/Tree-sitter analysis does not gain arbitrary process execution;
- dependency acquisition is distinct from editing dependency manifests;
- Browser Test credentials are test-only and lease/task scoped;
- large-Artifact upload grants one bounded object operation, not general BlobStore credentials.

The companion YAML manifest is extended with these operations and remains a design-time executable safety registry for C0/C5 implementation.
