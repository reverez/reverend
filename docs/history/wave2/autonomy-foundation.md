# Wave 2 — Executive Orchestrator + Integration Governor foundation

The Executive Orchestrator owns coordination, not specialist expertise.

Canonical software DAG:

Research
→ optional Product
→ Architect
→ Development
→ Verification + Security
→ Integration Governor
→ promotion decision

The orchestrator only creates/advances authoritative Workflow/Task state. Specialist execution remains injected through their own runtimes.

The Integration Governor is distinct from the task verifier. It requires explicit evidence for:
schemas, configuration, dependencies, duplicate implementations, migrations, backwards compatibility, cross-subsystem contracts, and whole-system tests.

Missing evidence yields UNVERIFIED. A blocking failure yields BLOCK. Only complete passing evidence yields ACCEPT.
