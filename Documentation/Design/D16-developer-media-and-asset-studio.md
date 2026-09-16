# D16 — Developer Media & Asset Studio

> **Status:** DESIGN ACCEPTED FOR DEVELOPMENT  
> **Depends on:** D1, D2, D3, D4, D6, D7, D8, D13, D15, ADR-003  
> **Purpose:** Define cloud-native visual asset generation/editing for software projects without expanding Reverend into a general audio/video/3D creative platform.

---

## 1. Goal

Reverend should be able to implement user-facing products that need original visual assets.

The target experience is a lightweight developer-oriented creative studio integrated with:

- Chat;
- Projects;
- autonomous frontend Agents;
- BlobStore/Artifacts;
- model routing;
- cost/budget controls.

It is inspired by unified creative tools, but optimized for software development rather than general content production.

---

## 2. Cloud v1 Scope

Included:

- text-to-image raster generation;
- reference-image editing;
- variants;
- inpaint/outpaint where supported;
- background removal;
- resize/crop;
- format conversion/optimization;
- transparent output where supported;
- asset history/version lineage;
- autonomous asset requests from implementation Tasks.

Excluded:

- audio generation;
- music;
- voice;
- video generation;
- generative 3D/modeling pipelines.

These exclusions are deliberate Cloud v1 scope controls.

---

## 3. Asset Routing Principle

The Media Fabric does not mean "send every visual to diffusion."

Reverend first classifies the required asset.

Canonical initial routing:

~~~text
photographic / illustrative raster
    → MEDIA_GENERATION

reference-based raster edit
    → MEDIA_EDIT

icon
    → approved icon library or SVG/code

simple logo / vector graphic
    → SVG/code-first

chart / data visualization
    → plotting/chart code from authoritative data

architecture / system diagram
    → Mermaid / Graphviz / SVG

application UI/layout
    → component code + CSS + browser rendering

screenshot understanding
    → primary multimodal engineering model

text-heavy marketing raster
    → future optional specialized media profile if justified
~~~

Deterministic/code-native output is preferred when it provides better precision, accessibility, editability or factual accuracy.

---

## 4. MediaAsset/v1

Generated/edited durable visual content uses the normal Artifact envelope with semantic type:

~~~text
MediaAsset/v1
~~~

Recommended payload/metadata:

~~~text
asset_id
project_id
purpose
asset_kind
media_type
width
height
alpha
prompt
negative_constraints?
reference_artifact_ids[]
parent_asset_id?
generation_operation
deployment_profile_id
model_revision
generation_parameters
content_hash
content_ref
producer_job_id
producer_agent_instance_id?
created_by_user_id?
accepted_state
usage_refs[]
license/provenance metadata
created_at
~~~

Binary bytes live in BlobStore.

---

## 5. MediaGenerationRequest

Agent/user-facing request:

~~~text
MediaGenerationRequest
├── project_id
├── purpose
├── operation
├── prompt
├── reference_artifact_ids[]
├── target_dimensions
├── aspect_ratio?
├── transparency?
├── format_preferences[]
├── style_constraints
├── must_preserve[]
├── destination_hint?
├── quality_requirement
├── max_variants
└── budget_envelope
~~~

The request does not name a GPU SKU.

The Model/Compute routers select an eligible DeploymentProfile and capacity.

---

## 6. Operations

Initial operation identifiers:

~~~text
GENERATE_RASTER
EDIT_RASTER
CREATE_VARIANTS
INPAINT
OUTPAINT
REMOVE_BACKGROUND
RESIZE
CROP
FORMAT_CONVERT
OPTIMIZE_WEB
GENERATE_SVG
GENERATE_DIAGRAM
GENERATE_CHART
~~~

Only operations supported by an eligible tool/profile may be admitted.

---

## 7. Baseline Raster Model

Initial candidate:

~~~text
FLUX.2 [klein] 4B
~~~

This is a candidate, not a permanent semantic binding.

Production admission requires:

- pinned immutable model revision;
- reviewed license;
- pinned runtime/image;
- successful media-specific ReverendBench suite;
- acceptable latency/cost;
- reference-edit reliability where advertised;
- safety/security review.

The model may later be replaced without changing `MediaGenerationRequest`.

---

## 8. Media Compute

Media workloads are independent ResourceRequest classes.

Recommended topology:

~~~text
persistent Control Plane
      │
      ├── engineering GPU capacity
      │      └── A100-class / Qwen workhorse
      │
      ├── media GPU capacity
      │      └── cheaper compatible GPU / media runtime
      │
      └── CPU build/tool capacity
~~~

Media workers:

- provision on demand;
- authenticate like other workers;
- receive no unnecessary secrets;
- publish accepted output before release;
- scale to zero independently from engineering inference.

The A100 may run media work only when routing/cost policy explicitly selects it; media is not assumed to share the engineering worker.

---

## 9. Human Studio UX

Primary tab:

~~~text
STUDIO
~~~

Minimum flows:

### Generate

- prompt;
- aspect ratio/dimensions;
- optional references;
- number of variants;
- project destination;
- generate.

### Edit

- select Asset;
- provide edit instruction;
- optionally add references;
- preserve parent lineage.

### Iterate

~~~text
asset-v1
  ↓ edit
asset-v2
  ↓ variant
asset-v3
~~~

### Use in Project

A user can mark/select an asset for a target use. This produces an explicit usage relation or implementation Task rather than merely copying an opaque file.

---

## 10. Autonomous Asset Use

An Agent implementing UI may issue a MediaGenerationRequest when:

- the accepted specification permits original assets;
- the asset is required or materially improves acceptance criteria;
- the operation falls within delegated tool authority;
- remaining budget admits the request.

Normal low-risk generation does not require human approval merely because it invokes a media model.

Policy/approval may still be required for:

- budget override;
- external publication;
- trademark-sensitive use;
- high-sensitivity external provider routing;
- operations otherwise registered as privileged.

---

## 11. Visual Feedback Loop for UI

UI generation should use actual rendered output.

Recommended loop:

~~~text
implement component
      ↓
browser worker renders
      ↓
screenshot Artifact
      ↓
multimodal engineering model reviews
      ↓
identify visual/accessibility mismatch
      ↓
edit component
      ↓
rerender
~~~

Diffusion output is used for image assets, not as a substitute for functional UI implementation.

---

## 12. Charts and Diagrams

### Charts

Charts are produced from authoritative data/code.

A model may write configuration/code, but the renderer uses actual data.

Generated raster charts with invented numbers are prohibited as engineering evidence.

### Diagrams

Preferred tools:

- Mermaid;
- Graphviz;
- SVG;
- other deterministic diagram renderer approved by Tool Registry.

Generated diagrams may still be previewed as Artifacts.

---

## 13. Icons and Vectors

Preferred order:

1. existing approved project icon set/library;
2. generated SVG;
3. raster generation only when an illustrative raster is intentionally desired.

This reduces inconsistent styling and improves accessibility/resolution.

---

## 14. Provenance and Reproducibility

Record when available:

- model/profile revision;
- runtime/container identity;
- references;
- prompt;
- generation parameters;
- operation;
- parent Asset;
- seed where exposed;
- dimensions/format;
- content hash;
- cost;
- producer identity.

Exact pixel reproduction is not guaranteed unless the runtime/model supports it, but lineage must remain auditable.

---

## 15. Asset Acceptance

Generated output states:

~~~text
CANDIDATE
ACCEPTED
REJECTED
SUPERSEDED
~~~

Autonomous implementation may automatically accept an asset only when:

- Project policy permits;
- deterministic format/size checks pass;
- required visual checks pass;
- budget policy permits;
- no human-only acceptance rule applies.

Human users can accept/reject/replace candidates from Studio.

---

## 16. Usage Relations

Asset usage should be discoverable.

Examples:

~~~text
MediaAsset hero-v3
  → used_by src/components/HomeHero.tsx

MediaAsset logo-v2.svg
  → used_by public/brand/logo.svg
~~~

Implementation may derive usage through repository indexing and/or explicit Artifact relations.

This supports safe regeneration and dead-asset cleanup.

---

## 17. Security

- reference uploads inherit Artifact sensitivity;
- Community media workers receive only permitted inputs;
- active SVG/HTML preview is isolated from authenticated origin;
- image metadata is stripped/sanitized where policy requires;
- output is scanned/validated before Project publication;
- external URLs are not fetched by a media worker unless mediated by approved acquisition tooling.

---

## 18. Cost

Each media request records:

- provider;
- node/power session;
- deployment profile;
- generation duration;
- estimated/actual cost;
- requesting Run/Task/user.

Autonomous frontend work consumes media cost from delegated Run/Task budget.

Media idle grace is separately tuned from LLM inference idle grace.

---

## 19. ReverendBench Media Suite

Benchmark classes should include:

- prompt adherence;
- aspect/dimension correctness;
- reference preservation;
- edit locality;
- transparency/background removal;
- web asset size/quality;
- latency;
- cost;
- downstream UI acceptance.

A visually attractive result does not pass if it violates explicit specification constraints.

---

## 20. API Direction

D2 should expose equivalent operations:

~~~text
POST /api/v1/projects/{project_id}/media/generations
GET  /api/v1/media/generations/{generation_id}
POST /api/v1/artifacts/{asset_id}/media/edit
POST /api/v1/artifacts/{asset_id}/accept
GET  /api/v1/projects/{project_id}/media/assets
~~~

Large binary content uses Artifact/blob download/upload paths.

---

## 21. SSE Direction

Useful bounded events:

~~~text
MediaGenerationQueued
MediaGenerationStarted
MediaCandidateCreated
MediaGenerationCompleted
MediaGenerationFailed
MediaAssetAccepted
MediaAssetSuperseded
~~~

---

## 22. Development Programme

Recommended placement:

### C0
Contracts/enums for MediaGenerationRequest and MediaAsset metadata.

### C1
Artifact persistence already provides base storage; add required usage/provenance relations.

### C2
Studio/media APIs and SSE schemas may land after core auth/chat API.

### C4
Agent-facing media request tool contract.

### C5
Tool Broker permissions/sensitivity.

### C7
Media worker protocol/provider/runtime implementation after engineering worker path proves stable.

### C8
Studio UX, costs, budgets and asset browser.

### C9
End-to-end autonomous frontend + generated asset acceptance.

Media support must not delay the core C0–C6 engineering/control-plane path.

---

## 23. Acceptance Scenario

Representative Cloud acceptance:

~~~text
accepted web-product BuildSpecification
        ↓
Reverend implements frontend
        ↓
Task determines original hero raster is required
        ↓
MediaGenerationRequest
        ↓
media worker provisions
        ↓
multiple candidates generated
        ↓
eligible candidate accepted
        ↓
asset stored/versioned
        ↓
frontend references accepted asset
        ↓
browser render + screenshot review
        ↓
tests/accessibility/verification
        ↓
media worker scales to zero
~~~

The Run remains the single top-level authority throughout.

---

## 24. Exit Condition

D16 is satisfied when Reverend can create, edit, version, budget and integrate visual assets required by software projects while using deterministic/code-native generation for charts, diagrams, vectors and UI wherever appropriate, with no Cloud v1 dependency on audio, video or generative 3D systems.
