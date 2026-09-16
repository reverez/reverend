# ADR-003 — Developer Media Asset Fabric

> **Status:** ACCEPTED  
> **Date:** 2026-09-16  
> **Authors/Reviewers:** project owners  
> **Supersedes:** none  
> **Superseded by:** none

## Context

Reverend should be able to build complete user-facing software, including the visual assets required by web/product UX. The goal is not a general audio/video creation platform. It is a developer-oriented asset system integrated with Projects, Artifacts and autonomous frontend work.

## Decision

Cloud v1 adds a **Media/Asset Fabric** and Chat/Studio UX for:

- raster image generation;
- reference-based image editing;
- variants;
- inpainting/outpainting where the selected runtime supports it;
- background removal;
- resizing/cropping/format optimization;
- asset versioning and provenance.

Cloud v1 explicitly excludes:

- audio generation;
- video generation;
- generative 3D pipelines.

### Baseline media model

Initial candidate:

`FLUX.2 [klein] 4B`

It is represented through normal ModelProfile/DeploymentProfile admission and must pass ReverendBench/media acceptance before ELIGIBLE production use.

### Deterministic asset routing

Do not use diffusion for every visual.

Initial routing policy:

- photographic/illustrative raster -> media generation profile;
- raster/reference edit -> media edit profile;
- icons -> approved icon library or generated SVG;
- simple vector/logo -> SVG/code-first;
- charts -> chart/plot code from source data;
- architecture/system diagrams -> Mermaid/Graphviz/SVG;
- UI/layout -> HTML/CSS/component code plus browser screenshot verification.

### Separate capacity

Media generation is a separate ResourceRequest class and may use a cheaper elastic GPU than the primary A100 engineering worker.

Media and engineering GPU pools scale independently.

## Authority Impact

Generated media is an Artifact. It never becomes Project truth merely because a model generated it.

## Security / Trust Impact

Reference images and generated assets inherit Project/sensitivity policy.

Active SVG/HTML previews remain isolated according to D6/D13.

## Durability / Recovery Impact

Accepted media bytes live in BlobStore and are content-addressed. Worker-local generations are not durable until Artifact publication completes.

## Cost / Capacity Impact

Media GPU cost is separately attributable and budgeted. Autonomous low-risk generation may proceed inside delegated budget; exceeding budget or performing external publication remains approval/policy controlled.

## Observability Impact

Record model/deployment revision, references, generation parameters where available, dimensions, content hash, latency, cost and downstream usage refs.

## Acceptance Tests

- raster generation produces immutable MediaAsset Artifact;
- reference edit links parent/reference Artifacts;
- autonomous frontend task can request an asset and consume the accepted result;
- chart/diagram/icon routing does not unnecessarily invoke diffusion;
- media worker loss cannot lose an already-published asset;
- media generation can scale to zero independently of engineering inference;
- no audio/video/3D generator is required for Cloud v1 acceptance.

## Consequences

Reverend can produce more complete UX implementations without turning the core engineering A100 into a permanent media server or expanding scope into a general creative suite.

## Decision Record

Accepted by the project owner on 2026-09-16.
