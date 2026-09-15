# M-VNEXT-01 — Runtime Kernel + Artifact System
Branch: `integration/runtime-artifact-candidate`

This candidate introduces the frozen Workflow/Task/Job/Event/Artifact semantics without rewriting accepted Workstation or development databases.

The generic authority is `reverend.controlplane.ControlPlaneStore`. Its default persistence path is resolved only through `reverend.config.DATA_ROOT` as `DATA_ROOT/control-plane.db`.

Implemented invariants:
- deterministic Workflow/Task/Job lifecycle;
- workflow-local acyclic Task dependencies;
- distinct retained Job attempts for retries;
- append-only Events enforced by SQLite triggers;
- typed/versioned/hashed Artifacts with lineage;
- separate validation and promotion state;
- no Knowledge Fabric auto-promotion;
- bounded JSON/inline payloads;
- read-only compatibility snapshots for current Workstation/development state;
- no new service/process/network dependency.

Migration posture: additive schema version 1 in a dedicated central-DataRoot database. Existing accepted databases remain untouched until an explicit adapter/migration is integration-tested.
