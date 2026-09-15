# M-VNEXT-04 — Policy + Execution Runtime
Branch: `integration/policy-candidate`

This candidate adds explicit Capability/Permission policy resolution without replacing existing trust, network, worktree, bubblewrap or prlimit enforcement.

Rules:
- capabilities name actions only when a concrete enforcement adapter exists;
- registration grants nothing;
- permissions are subject/scope bounded and time bounded when configured;
- default is deny;
- explicit deny outranks approval/allow; approval_required outranks allow;
- model/classifier/prompt output is rejected as an authority source;
- WorkerPolicy converts only its existing booleans into corresponding grants;
- NetworkPolicy OFF/ASK/AUTO maps deterministically to deny/approval_required/allow;
- project trust is exposed as scope metadata and never silently grants capabilities.

This is an additive policy runtime. Existing fail-closed sandboxing remains the execution boundary.
