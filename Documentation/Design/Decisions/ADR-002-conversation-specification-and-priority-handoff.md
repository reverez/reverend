# ADR-002 — Conversation, Specification and Priority Run Handoff

> **Status:** ACCEPTED  
> **Date:** 2026-09-16  
> **Authors/Reviewers:** project owners  
> **Supersedes:** none  
> **Superseded by:** none

## Context

Reverend is intended to automate the implementation-heavy portion of AI-assisted software development. Human users may use a frontier assistant such as ChatGPT separately for high-value reasoning/design, then manually provide the resulting accepted specification to Reverend.

Cloud v1 intentionally retains **one active top-level Run globally**. The second developer must nevertheless be able to request urgent work without corrupting or discarding the current project.

The primary user experience is conversational.

## Decision

### One global active Run remains

Do not introduce one-Run-per-user or one-Run-per-Project concurrency.

When a queued Run is raised to higher priority, Reverend performs **safe priority handoff**:

1. mark the active Run with a pre-emption request;
2. continue until the next valid safe checkpoint;
3. settle/journal external side effects;
4. preserve valuable workspace state as durable Git/workspace/Artifact state;
5. publish the checkpoint;
6. release paid/transient compute;
7. transition the interrupted Run to RESUME_QUEUED;
8. admit the higher-priority Run;
9. later resume the interrupted Run from its durable checkpoint.

Pre-emption depth remains bounded; priority changes never bypass recovery, approval, ownership or budget rules.

### Conversation is first-class interaction state, not workflow authority

Cloud adds durable Project-scoped Conversations, Messages and Attachments.

Conversation text may propose work or decisions, but it never mutates Project/Run/Task authority by implication.

### BuildSpecification is first-class

A substantial autonomous build begins from an accepted, immutable, versioned `BuildSpecification/v1` Artifact.

It contains, at minimum:

- objective;
- scope and non-goals;
- requirements;
- architecture;
- interfaces;
- invariants;
- constraints;
- implementation guidance;
- references/evidence;
- acceptance criteria;
- verification requirements;
- escalation policy.

Amendment creates a new specification version linked to the prior version.

### GPT is external design input, not a Reverend dependency

Cloud v1 has **no automatic GPT/OpenAI API escalation path**.

Users may manually create/review a specification with any external reasoning tool and upload/paste/accept it into Reverend.

Reverend must remain functional if every external frontier-model service is unavailable.

## Authority Impact

Accepted BuildSpecification and promoted Project Decisions may become authoritative Project inputs through explicit server-side promotion.

Conversation text and external model output are untrusted/non-authoritative until accepted.

## Security / Trust Impact

Attachments are ingested into BlobStore/Artifacts and receive sensitivity/provenance labels.

No external assistant credentials are stored or called by Reverend for Cloud v1.

## Durability / Recovery Impact

Priority handoff relies on D5 safe checkpoint and Action Journal semantics. An interrupted Run is resumable without client state.

## Cost / Capacity Impact

The one-active-Run rule bounds expensive work. Priority switching may incur model/worker cold-start cost; the UI must show that consequence before repeated manual reprioritization where material.

## Observability Impact

Record:

- conversation/message IDs;
- accepted specification version;
- Run→BuildSpecification link;
- pre-emption requester/priority change;
- checkpoint used for handoff;
- resume order.

## Acceptance Tests

- only one top-level Run is RUNNING/STARTING/RECOVERING as defined by the existing global invariant;
- higher-priority queued Run cannot start before the active Run reaches a safe checkpoint;
- interrupted Run resumes from durable state;
- conversation prose cannot directly alter Project decisions or Task state;
- BuildSpecification mutation creates a new version;
- no Cloud v1 code path requires an external frontier-model API.

## Consequences

Reverend remains operationally simple while still serving two developers. Expensive frontier reasoning remains optional and manually supplied; autonomous implementation is owned by Reverend.

## Decision Record

Accepted by the project owner on 2026-09-16.
