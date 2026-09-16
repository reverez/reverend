# Reverend Architecture Decision Records

This directory records deliberate architecture changes discovered during Development.

A12 and D0–D14 are the accepted Cloud v1 design baseline. Implementation must not silently diverge.

## When an ADR Is Required

Create an ADR when a change modifies or intentionally departs from:

- an A12 frozen invariant;
- authority ownership;
- durable contract semantics;
- lifecycle/state-machine semantics;
- security/trust boundary;
- secret/credential boundary;
- side-effect/recovery semantics;
- persistence authority;
- cost attribution;
- a major deployment guarantee.

Ordinary refactors that preserve these contracts do not require an ADR.

## Naming

~~~text
ADR-001-short-decision-name.md
ADR-002-...
~~~

Use ADR-000-template.md as the template.

## Statuses

~~~text
PROPOSED
ACCEPTED
SUPERSEDED
REJECTED
DEPRECATED
~~~

Only accepted ADRs modify the Design baseline.

## Process

1. describe the concrete problem;
2. identify affected A12/D0–D14 contracts;
3. state alternatives;
4. assess security/durability/cost/migration impact;
5. define acceptance tests;
6. review;
7. accept or reject;
8. update affected contracts if accepted;
9. link supersession both ways.

An ADR cannot silently weaken A12. If a frozen invariant changes, architecture acceptance must explicitly acknowledge that decision.


## Accepted Decisions

- [ADR-001 — Cloud-Only Client and Cloud Recovery Boundary](./ADR-001-cloud-only-client-and-cloud-recovery.md)
- [ADR-002 — Conversation, Specification and Priority Run Handoff](./ADR-002-conversation-specification-and-priority-handoff.md)
- [ADR-003 — Developer Media Asset Fabric](./ADR-003-developer-media-asset-fabric.md)

- [ADR-004 — Ephemeral Model Hydration and Cache Economics](./ADR-004-ephemeral-model-hydration-and-cache-economics.md)
