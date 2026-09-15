# M-VNEXT-06 — Verification + Integration
Branch: `integration/verification-candidate`

This candidate formalizes existing verification invariants instead of replacing the accepted Workstation/development verifiers.

Implemented:
- shared deterministic/semantic check authority labels;
- producer/verifier identity separation;
- deterministic required failures override semantic approval;
- missing required deterministic evidence remains unverified;
- artifact promotion authorization requires an accepted independent result;
- explicit bounded repair attempts and stop reasons;
- Wave-1 acceptance composition separates portable and required live gates;
- adapters preserve current Workstation and development deterministic evidence.

Final repository-wide Wave-1 validation remains an integration action after M-VNEXT-01 through 05 compose successfully.
