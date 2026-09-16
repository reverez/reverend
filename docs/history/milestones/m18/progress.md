# M18 — Workstation Experience & Visual Artifacts

**Status:** LIVE ACCEPTED

## Mission

Turn the reliable local Reverend runtime into a fluid daily-use workstation: dense enough
for engineering/research, visually calm enough for long conversations, and able to inspect
sources, runtime evidence, searched visuals, and generated artifacts without leaving chat.

## Conversation inspector

Implemented:

- responsive split conversation/inspector workspace;
- persistent Sources, Details, and Preview tabs;
- citations, source cards, and searched-image gallery items open in the inspector;
- Previous / Next navigation preserves the complete response source set;
- source provenance shows trust, provider, freshness, publication and recorded timestamps;
- assistant turns use compact Details / Copy / Retry actions;
- live activity labels distinguish local knowledge retrieval, web search, web reading,
  local reasoning, writing and stopping;
- System Status exposes only safe web-search configuration metadata.

## Safe artifact previews

HTML code blocks can render only inside a sandboxed iframe with an empty sandbox after
DOMPurify sanitization. The preview document receives an inner `default-src 'none'` CSP.
Scripts, nested frames, objects, embeds, remote links, metadata/base elements and forms are
forbidden.

SVG code blocks render only after SVG-profile sanitization with active or remote-capable
elements forbidden.

Preview can expand into a wider artifact workspace without changing the conversation or
granting the artifact additional capabilities.

No remote UI dependency or script origin is introduced.

## Local flowchart rendering

Reverend ships a bounded dependency-free Mermaid-style flowchart renderer for fenced
`mermaid` and `diagram` blocks.

Supported syntax is deliberately narrow:

- `flowchart` / `graph`;
- TD, TB, LR and RL directions;
- rectangle, round and decision nodes;
- `-->` edges with optional labels;
- maximum 40 nodes;
- maximum 80 edges;
- maximum 12,000 source characters.

Rendering uses DOM-created SVG elements and text nodes only. Diagram source never becomes
HTML. Unsupported Mermaid constructs fail visibly instead of being loosely interpreted.

## Search-derived images

Search images preserve the same trust boundary as text evidence.

The path is:

```text
search thumbnail candidate
  -> restricted public page fetch
  -> deterministic evidence gate
  -> accepted FRESH source only
  -> restricted image worker
  -> local SQLite binary cache
  -> opaque image_id in response metadata
  -> authenticated local binary endpoint
  -> browser blob URL
```

Security properties:

- a search result thumbnail is discovery metadata, never evidence by itself;
- irrelevant/rejected search results never trigger an image fetch;
- at most two accepted searched-source images are fetched per response;
- image acquisition is public HTTPS on port 443 only;
- DNS is pinned and private/local/mapped addresses are refused;
- redirects and compressed responses are refused;
- accepted MIME types are PNG, JPEG and WebP only;
- file signatures must match the declared MIME type;
- each image is limited to two megabytes;
- SVG, GIF, HTML and text responses are rejected;
- image acquisition runs through the same bubblewrap/seccomp isolation model;
- raw image bytes live in a separate SQLite image table;
- normal response metadata contains only an opaque local image id and bounded metadata;
- the browser never assigns the remote thumbnail URL to `img.src`;
- the browser fetches the authenticated local endpoint and creates a blob URL;
- Markdown image syntax remains disabled;
- workstation CSP permits `blob:` images but does not permit general remote `https:`
  image loading.

Accepted searched images appear as an inline visual-evidence gallery, compact source-card
thumbnails, and a larger source-inspector preview.

Image acquisition failures are non-blocking: verified textual evidence remains usable and
the response records a warning/count rather than silently weakening evidence requirements.

## Acceptance harness

`python -m reverend.benchmarks.m18_validation` separates portable correctness from a real
searched-image provider/sandbox probe.

Portable gates cover:

- local-only UI dependencies;
- Markdown remote-image refusal;
- authenticated local image proxy and object-URL lifecycle;
- browser remote-image refusal and CSP constraints;
- HTML/SVG artifact sandboxing;
- local bounded flowchart rendering;
- post-evidence image acquisition ordering;
- visual gallery, expanded artifact workspace, source navigation and activity states;
- full test suite and clean release smoke.

CI runs M18 with `--skip-live`. A portable-only run may set `portable_ok=true`, but it
must leave `live_ok=false` and `overall_ok=false`.

### Required live visual acceptance

Configure Brave Search or a supported SearXNG endpoint as documented in `.env.example`,
then run from the real WSL2 environment:

```bash
python -m reverend.benchmarks.m18_validation \
  --repository . \
  --report-root benchmarks/results/vnext/m18/live-validation
```

The live gate performs a real bounded search, fetches candidate pages through Reverend's
restricted public-fetch worker, applies the FRESH evidence gate, requires an accepted source
with a safe image candidate, fetches that image through the restricted image worker and
verifies the cached binary metadata.

A fully accepted M18 run requires exit code 0 with `portable_ok`, `live_ok`, and
`overall_ok` all true.

No merge, tag, release or publication is part of M18 closure.


## M18 live acceptance closure

The final programme validation at revision
`418524b533f6c05587698dffe8b9a5e4f0434093` closed the real visual gate. A searched
FRESH source survived evidence gating, its supported image was acquired through the
restricted image worker, and the local binary cache/proxy metadata validated successfully.
M18 is therefore **LIVE ACCEPTED**.
