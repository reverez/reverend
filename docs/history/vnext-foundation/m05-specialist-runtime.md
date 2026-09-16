# M-VNEXT-05 — Specialist Runtime + Context Broker
Branch: `integration/specialist-candidate`

This candidate generalizes existing bounded WorkerRole/WorkerPolicy definitions without replacing the accepted worker orchestrator or Context Compiler.

Implemented:
- versioned SpecialistSpec registry;
- explicit ModelRole, methodology, context, tool, capability, artifact-I/O and authority bindings;
- compatibility conversion from every existing WorkerRole;
- independent-verifier configuration guard;
- budgeted selected-context broker;
- non-evictable system/authoritative-task/current-request layers;
- deterministic optional-context prioritization and omission;
- disallowed context layers cannot become a hidden prompt channel.

The Context Broker is pre-selection only. Canonical Context Compiler V2 remains authoritative for final model-token admission and provider telemetry.
