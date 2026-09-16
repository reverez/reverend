# ADR-001 — Cloud-Only Client and Cloud Recovery Boundary

> **Status:** ACCEPTED  
> **Date:** 2026-09-16  
> **Authors/Reviewers:** project owners  
> **Supersedes:** client-recovery preference in D5/D8 where a developer device was treated as a preferred off-host recovery target  
> **Superseded by:** none

## Context

Reverend Cloud is a shared two-developer service. The intended client experience is a ChatGPT-like GUI, not a workstation that contributes inference, retrieval, builds, indexing, media generation, scheduling or durability.

Earlier recovery design allowed authenticated developer devices to retain encrypted RecoveryGeneration replicas. That is compatible with server authority, but it creates an operational dependency on client devices that contradicts the desired product boundary.

## Current Contract

Affected sources:

- A12: thin non-authoritative clients, persistent server authority, one active top-level Run;
- D2/D13: authenticated thin clients and server-owned lifecycle state;
- D5/D8: off-host recovery and optional client recovery peers;
- D11: local 0.4.0 compatibility path.

## Decision

Cloud v1 product clients are **presentation/input only**.

A production client may:

- authenticate;
- render the GUI;
- submit messages, commands, approvals and human input;
- upload attachments;
- display/download Artifacts;
- keep bounded non-authoritative presentation cache.

A production client does **not** perform or provide:

- LLM inference;
- embedding/reranking;
- repository indexing;
- builds/tests;
- sandbox execution;
- image/media generation;
- authoritative storage;
- recovery replication required for server operation;
- provider lifecycle control.

All Reverend processing and durable state execute in cloud infrastructure.

Disaster recovery uses an encrypted off-host cloud/object-store target behind the existing BlobStore/recovery abstractions. Client recovery replicas are no longer part of the Cloud v1 required or preferred recovery topology.

The existing local Reverend 0.4.0 path may remain as a development/regression compatibility implementation until deliberately retired. It is not the Cloud product execution model.

## Alternatives Considered

### Developer devices as recovery peers

Rejected for Cloud v1 product operation because it makes shutdown/recovery health depend on laptops that may be offline, replaced or untrusted.

### Hybrid local/cloud inference

Rejected. It complicates scheduling, reproducibility, security, collaboration and support while providing no required capability for the two-user shared service.

## Authority Impact

No authority moves to clients. PostgreSQL-backed Control Plane state remains authoritative.

## Security / Trust Impact

- clients receive no provider credentials;
- clients receive no model/runtime secrets;
- object-store recovery credentials remain server/operator secrets;
- uploaded attachments become server-side Artifacts immediately;
- losing a laptop does not expose authoritative project state beyond the user's authenticated client session/cache policy.

## Durability / Recovery Impact

Recovery health depends on a validated encrypted off-host cloud target, not client ACKs.

Planned authoritative-host shutdown requires:

1. a valid local RecoveryGeneration;
2. durable encrypted off-host copy;
3. hash/integrity verification;
4. recorded acknowledgement from the recovery target.

## Data / Migration Impact

No Project/Run authority migration is required.

D5/D8 client-replica language becomes historical/optional outside the Cloud v1 production profile.

## Cost / Capacity Impact

Adds small persistent object-storage/backup cost. This is preferred to relying on user devices.

## Observability Impact

Expose:

- latest off-host RecoveryGeneration;
- last successful object-store ACK;
- recovery target health;
- recovery-point age.

No client-recovery health indicator is required for Cloud v1.

## Acceptance Tests

- closing every client does not pause/cancel/degrade an active Run;
- a new device can authenticate and reconstruct all required UI from server state;
- no production client endpoint requires local compute;
- backup/restore succeeds with both developer devices offline;
- provider/model credentials never reach client payloads;
- upload persists before originating client disconnect.

## Rollout

Apply during C1/C2/C6/C8 implementation. Preserve local 0.4.0 only as compatibility/development code until a later retirement decision.

## Consequences

The product becomes device-independent and operationally simpler. Server-side storage/recovery becomes more important and must be monitored explicitly.

## Decision Record

Accepted by the project owner on 2026-09-16.
