# Reverend Design Diagrams

This directory contains the Mermaid views for the Reverend Cloud v1 architecture.

## Canonical files

- [`00-system-overview.mmd`](./00-system-overview.mmd) — small navigational overview of the complete architecture.
- [`system-complete-mermaid-diagram.mmd`](./system-complete-mermaid-diagram.mmd) — complete render-compatible architecture map. This remains the canonical Mermaid mega-diagram.
- [`Subsystems/`](./Subsystems/) — focused views extracted from the complete diagram so individual areas can be inspected without extreme zoom.

The prose design specifications D0–D17 and accepted A12 architecture remain the semantic source of truth. D10–D14 close research/retrieval, migration, tool recovery, client UX and development-entry details without creating a second architectural authority. These diagrams are visual projections of the system contracts.

## Focused subsystem views

Each focused file contains one numbered subsystem from the complete diagram. Cross-subsystem references are intentionally left as small interface nodes where useful; the full graph contains the complete cross-system wiring.

| # | Subsystem | File |
|---:|---|---|
| 00 | FROZEN INVARIANTS | [`00-frozen-invariants.mmd`](./Subsystems/00-frozen-invariants.mmd) |
| 01 | HUMANS / CLIENTS / DEVICES | [`01-humans-clients-devices.mmd`](./Subsystems/01-humans-clients-devices.mmd) |
| 02 | NETWORK EDGE / REMOTE ACCESS | [`02-network-edge-remote-access.mmd`](./Subsystems/02-network-edge-remote-access.mmd) |
| 03 | CLOUD API / CLIENT CONTRACT | [`03-cloud-api-client-contract.mmd`](./Subsystems/03-cloud-api-client-contract.mmd) |
| 04 | IDENTITY / AUTH / MEMBERSHIP | [`04-identity-auth-membership.mmd`](./Subsystems/04-identity-auth-membership.mmd) |
| 05 | AUTHORITATIVE CONTROL PLANE | [`05-authoritative-control-plane.mmd`](./Subsystems/05-authoritative-control-plane.mmd) |
| 06 | RUN LIFECYCLE / QUEUE | [`06-run-lifecycle-queue.mmd`](./Subsystems/06-run-lifecycle-queue.mmd) |
| 07 | EXECUTIVE ORCHESTRATION | [`07-executive-orchestration.mmd`](./Subsystems/07-executive-orchestration.mmd) |
| 08 | SPECIALIST / AGENT RUNTIME | [`08-specialist-agent-runtime.mmd`](./Subsystems/08-specialist-agent-runtime.mmd) |
| 09 | CONTEXT / MEMORY / ARTIFACT FABRIC | [`09-context-memory-artifact-fabric.mmd`](./Subsystems/09-context-memory-artifact-fabric.mmd) |
| 10 | TYPED ARTIFACTS & CONTROL SIGNALS | [`10-typed-artifacts-and-control-signals.mmd`](./Subsystems/10-typed-artifacts-and-control-signals.mmd) |
| 11 | BOUNDED AGENT EXECUTION LOOP | [`11-bounded-agent-execution-loop.mmd`](./Subsystems/11-bounded-agent-execution-loop.mmd) |
| 12 | POLICY / TOOL / SECRET ENFORCEMENT | [`12-policy-tool-secret-enforcement.mmd`](./Subsystems/12-policy-tool-secret-enforcement.mmd) |
| 13 | EXECUTION TOOLS / SANDBOX / GIT / RESEARCH | [`13-execution-tools-sandbox-git-research.mmd`](./Subsystems/13-execution-tools-sandbox-git-research.mmd) |
| 14 | SIDE-EFFECT CLASSIFICATION / ACTION JOURNAL | [`14-side-effect-classification-action-journal.mmd`](./Subsystems/14-side-effect-classification-action-journal.mmd) |
| 15 | VERIFICATION / ASSURANCE / INTEGRATION | [`15-verification-assurance-integration.mmd`](./Subsystems/15-verification-assurance-integration.mmd) |
| 16 | WORKFLOW SCHEDULER / COMPUTE SCHEDULER / CAPACITY | [`16-workflow-scheduler-compute-scheduler-capacity.mmd`](./Subsystems/16-workflow-scheduler-compute-scheduler-capacity.mmd) |
| 17 | COMPUTE FABRIC / NODE / WORKER PROTOCOL | [`17-compute-fabric-node-worker-protocol.mmd`](./Subsystems/17-compute-fabric-node-worker-protocol.mmd) |
| 18 | RUNPOD PROVIDER / GPU LIFECYCLE | [`18-runpod-provider-gpu-lifecycle.mmd`](./Subsystems/18-runpod-provider-gpu-lifecycle.mmd) |
| 19 | MODEL FABRIC / ROUTING / SERVING | [`19-model-fabric-routing-serving.mmd`](./Subsystems/19-model-fabric-routing-serving.mmd) |
| 20 | REVERENDBENCH / MODEL PROMOTION | [`20-reverendbench-model-promotion.mmd`](./Subsystems/20-reverendbench-model-promotion.mmd) |
| 21 | DURABLE EXECUTION / CHECKPOINT / RECOVERY | [`21-durable-execution-checkpoint-recovery.mmd`](./Subsystems/21-durable-execution-checkpoint-recovery.mmd) |
| 22 | STORAGE / DATABASE / BLOB / WORKSPACE / INDEXES | [`22-storage-database-blob-workspace-indexes.mmd`](./Subsystems/22-storage-database-blob-workspace-indexes.mmd) |
| 23 | COST / BILLING / BUDGETS | [`23-cost-billing-budgets.mmd`](./Subsystems/23-cost-billing-budgets.mmd) |
| 24 | OBSERVABILITY / EVENTS / METRICS / HEALTH | [`24-observability-events-metrics-health.mmd`](./Subsystems/24-observability-events-metrics-health.mmd) |
| 25 | GIT / GITHUB AUTHORITY | [`25-git-github-authority.mmd`](./Subsystems/25-git-github-authority.mmd) |
| 26 | EMERGENCY CONTROLS | [`26-emergency-controls.mmd`](./Subsystems/26-emergency-controls.mmd) |
| 27 | DEPLOYMENT TOPOLOGY | [`27-deployment-topology.mmd`](./Subsystems/27-deployment-topology.mmd) |
| 28 | EXTERNAL SYSTEMS | [`28-external-systems.mmd`](./Subsystems/28-external-systems.mmd) |
| 29 | LOCAL 0.4.0 COMPATIBILITY | [`29-local-0-4-0-compatibility.mmd`](./Subsystems/29-local-0-4-0-compatibility.mmd) |
| 30 | POSTGRES MIGRATIONS / CONTRACT VERSIONING | [`30-postgres-migrations-contract-versioning.mmd`](./Subsystems/30-postgres-migrations-contract-versioning.mmd) |
| 31 | DEVELOPMENT PROGRAMME C0–C9 | [`31-development-programme-c0-c9.mmd`](./Subsystems/31-development-programme-c0-c9.mmd) |
| 32 | TEST / CI / ACCEPTANCE | [`32-test-ci-acceptance.mmd`](./Subsystems/32-test-ci-acceptance.mmd) |
| 33 | A12 END-TO-END ACCEPTANCE SCENARIOS | [`33-a12-end-to-end-acceptance-scenarios.mmd`](./Subsystems/33-a12-end-to-end-acceptance-scenarios.mmd) |
| 34 | OPERATIONAL RUNBOOKS | [`34-operational-runbooks.mmd`](./Subsystems/34-operational-runbooks.mmd) |

## Regenerating the focused views

If the complete Mermaid source changes, regenerate the subsystem projections from the repository root with:

```bash
python3 Documentation/Design/Diagrams/generate_subsystem_diagrams.py
```

Then review the generated diff before committing.

## Viewing

Open any `.mmd` file in a Mermaid-capable editor/viewer. For normal architecture work, start with `00-system-overview.mmd` and open only the subsystem you need. Use the complete diagram when checking cross-system relationships.


## Product-extension views

The following hand-maintained focused views capture D15/D16 additions that were accepted after the original generated D0–D14 subsystem set:

- [Conversation, Specification & Priority Handoff](./Subsystems/35-conversation-specification-priority-handoff.mmd)
- [Developer Media & Asset Studio](./Subsystems/36-developer-media-asset-studio.mmd)
- [Model Hydration, Cold Start & Cache Economics](./Subsystems/37-model-hydration-cold-start-cache-economics.mmd)

These are semantic projections of D15–D17 and ADR-001..004. The generator for the original numbered subsystem projections does not currently synthesize these two extension views.
