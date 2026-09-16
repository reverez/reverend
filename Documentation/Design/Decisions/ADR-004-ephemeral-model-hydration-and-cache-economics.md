# ADR-004 — Ephemeral Model Hydration and Cache Economics

> **Status:** ACCEPTED  
> **Date:** 2026-09-16  
> **Authors/Reviewers:** project owner  
> **Supersedes:** none  
> **Superseded by:** none

## Context

Reverend Cloud v1 is intended to spend primarily on useful compute rather than permanent storage for reconstructible model weights.

The primary engineering model is large enough that retaining every model revision in paid cloud storage creates a recurring cost even when Reverend is idle. Developer internet upload bandwidth is also materially slower and less reliable than normal datacenter-to-model-repository transfer, especially from university/dorm networks.

Model weights are reconstructible state. They are not Project authority and do not belong in the Control Plane backup set.

## Current Contract

Affected sources:

- A12: persistent authority + disposable compute;
- D4: GPU worker lifecycle and model loading;
- D7: pinned model revision, artifact integrity and runtime profile;
- D8: cost attribution and storage accounting;
- D15/ADR-001: production clients are presentation/input only.

## Decision

### Default Cloud v1 policy

Cloud v1 uses **ephemeral model hydration**.

For a cold worker:

1. provision the required worker;
2. start the pinned Reverend worker image;
3. resolve the exact DeploymentProfile model artifact manifest;
4. check the worker-local ephemeral cache;
5. if missing, pull the exact pinned model revision directly from the approved upstream model repository;
6. verify revision/file identities/checksums;
7. atomically expose the verified local snapshot;
8. load the model into the runtime;
9. run functional smoke health;
10. only then mark the node/profile READY.

The model copy is reconstructible worker state.

When the worker is terminated, Reverend assumes the worker-local model cache may disappear.

### No paid persistent model cache by default

Cloud v1 does not require a persistent RunPod/network-volume/object-store mirror of model weights.

Persistent model caching is an optional cost optimization and starts **disabled**.

It may be proposed only after measured hydration economics show that repeated cold-start cost materially exceeds the recurring storage/cache cost.

Enabling a paid persistent model cache requires an explicit operator decision and a versioned Deployment/operations configuration change.

### Client devices are not the normal hydration source

Reverend does not require either developer laptop to upload model weights during normal cold start.

Developers may keep exact pinned model copies locally as an out-of-band archival/emergency convenience, but Cloud v1 defines no required client-to-worker model-seeding protocol.

A user closing the GUI cannot block model hydration.

### Upstream availability

If the exact pinned model revision cannot be retrieved and no approved cache contains it, the deployment becomes MODEL_HYDRATION_UNAVAILABLE.

Reverend does not substitute a different revision, model or external API silently.

## Alternatives Considered

### Permanent cloud model mirror from day one

Rejected initially because it creates recurring cost for reconstructible data before Reverend has measured enough cold starts to justify it.

### Client-to-worker upload on every cold start

Rejected as the default because residential/dorm upstream bandwidth is a bottleneck, makes startup depend on an online client and spends paid GPU time waiting for a slow edge connection.

### Bake model weights into the worker container image

Rejected because it creates extremely large images, couples runtime releases to model revisions and makes container distribution the model-transfer mechanism.

### Never allow persistent cache

Rejected because frequent cold starts may eventually make a persistent cache cheaper overall.

## Authority Impact

None.

Model weights/cache remain reconstructible deployment state.

PostgreSQL, Artifacts, Git/project state and RecoveryGeneration remain authoritative according to existing contracts.

## Security / Trust Impact

- only approved repositories/sources may hydrate a production profile;
- exact revision is pinned;
- artifact manifest and expected digests/identities are verified;
- remote/custom model code remains disabled under D7 baseline policy;
- hydration credentials/tokens are resolved server-side through Secret Broker;
- worker cache never gains Project authority.

## Durability / Recovery Impact

Model weights are excluded from required disaster-recovery generations.

After worker loss Reverend can reconstruct the runtime by hydrating the pinned revision again.

A Project checkpoint is never considered incomplete merely because model weights are absent.

## Cost / Capacity Impact

Every cold hydration records:

- bytes transferred;
- source;
- start/end time;
- worker/provider billable overlap;
- estimated and reconciled hydration cost;
- load/smoke-test time;
- failure/retry counts.

Reverend compares measured monthly hydration cost against a candidate persistent-cache monthly cost.

Conceptual break-even:

~~~text
monthly_hydration_cost
=
sum(hydration_billable_seconds × provider_rate_per_second)
+ transfer_charges_if_any

monthly_persistent_cache_cost
=
required_cache_GB × storage_rate_per_GB_month
+ transfer/operation_charges_if_any
~~~

Persistent caching is recommended only when expected verified-project economics improve materially after allowing for cache invalidation, revision churn and operational complexity.

## Observability Impact

Add model startup phases/metrics:

~~~text
MODEL_RESOLVING
MODEL_HYDRATING
MODEL_VERIFYING
MODEL_LOADING
MODEL_SMOKE_TEST
MODEL_READY

model_hydration_bytes
model_hydration_seconds
model_hydration_source
model_hydration_cost
model_load_seconds
model_cold_start_total_seconds
~~~

## Acceptance Tests

Must prove:

- an empty worker can hydrate the exact pinned model and become READY;
- hash/revision mismatch prevents READY;
- partial failed hydration is not treated as valid cache;
- model hydration requires no connected developer client;
- no production model weights are required on the persistent Control Plane host;
- worker termination does not lose authoritative Project state;
- next cold worker can reconstruct the same accepted DeploymentProfile;
- hydration time/cost are attributed;
- same compatible live worker may reuse already verified model residency without re-downloading;
- paid persistent model cache is disabled by default;
- enabling persistent cache requires explicit operator configuration.

## Rollout

Implement during C7 after fake/local worker protocol and before the first production Qwen/vLLM acceptance run.

## Consequences

Cold starts become slower than a permanently cached deployment, but recurring idle storage cost is minimized. The system can later promote persistent caching only when Reverend's own telemetry proves it is cheaper.

## Decision Record

Accepted by the project owner on 2026-09-16.
