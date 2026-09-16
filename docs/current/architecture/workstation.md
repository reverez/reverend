# Local workstation

Launch `reverend gui` (default `http://127.0.0.1:8765`) or specify `--port`.
Run from an installed package or `PYTHONPATH=src .venv/bin/python -m reverend.cli gui`.
The CLI's `reverend dev implement` and GUI call the same development command and engine.

## Current canonical Workstation

The supported browser experience is the stabilized consolidated shell on `main`. Earlier
M5/M7, architecture and 0.4.1 UI branches are historical/design references only; they are
not alternative production frontends.

The current shell provides:

- a collapsible local navigation sidebar with searchable recent conversations;
- conversation rename and delete actions backed by encrypted Workstation state;
- a compact top bar showing the active workflow and, when available, the selected local model;
- Auto / Ask / Reason / Research / Develop workflow selection;
- Normal / Private / Ephemeral privacy modes;
- explicit ASK / OFF / AUTO web policy controls in the composer;
- a persistent Sources / Details / Preview inspector with wide artifact mode;
- compact citation/source cards, provenance, accepted searched-image galleries and source navigation;
- local Markdown, syntax highlighting, KaTeX and bounded Mermaid-style flowchart rendering;
- sanitized sandboxed HTML/SVG artifact previews with remote execution/network access disabled;
- live Route -> Search -> Read -> Answer research activity;
- PLAN -> IMPLEMENT -> VERIFY development activity with diffs, checks and recorded artifacts;
- responsive desktop/mobile layouts and prompt auto-resize.

Default network policy is intentionally workflow-sensitive: Research selects `AUTO`, Develop
selects `OFF`, and normal Auto/Ask/Reason conversations select `ASK` unless the user explicitly
changes the policy. Inference remains local under every policy; the policy governs only public
evidence acquisition.

Ask and Reason stream through the local ModelScheduler; Reason displays the final answer,
not private reasoning. Research retrieves eligible local knowledge and can acquire fresh public
evidence only under the selected network policy. Conversation history and job metadata persist
in `AI_DATA_ROOT/workstation.db` according to privacy mode. Stop closes the model request;
development verification remains bounded and runs to completion. Interrupted GUI jobs are
marked interrupted after restart, not silently resumed.

The browser loads Markdown, highlighting, sanitization, KaTeX and fonts entirely from
packaged assets. Vendor versions, source URLs and SHA-256 checksums are in
`src/reverend/ui/vendor/manifest.json`; each dependency retains its license.
The GUI binds only to loopback and checks Host, Origin and a per-session token.
It has no arbitrary file, shell or merge endpoint. The runtime directory is private local
application data; anyone with access to your OS account can access it.

Register a trusted local Git project, select Develop, describe the change and acceptance
criteria. A clean primary checkout is required. Inspect the plan, isolated branch and
worktree, per-file diffs, every verification attempt, fresh verifier result and output
artifacts in Development tasks. No automatic merge occurs. Untrusted repository execution
is explicitly refused because the normal runner is not an OS sandbox.

Knowledge search offers lexical (no model required), dense and hybrid retrieval. Dense
and hybrid queries use scheduler-controlled local embeddings. The existing knowledge
registry and Qdrant remain the source of evidence; missing services produce visible errors.

## Engineering memory

`engineering-memory.db` stores FACT, DECISION, EXPERIMENT, FAILURE, RESULT and
USER_CONSTRAINT records. Every record requires project, source and evidence; task,
commit, model, confidence and UTC expiry are optional. Model speculation is never
silently promoted to a fact. Development automatically records user acceptance constraints
and engine outcomes, linked to persistent task/run evidence. The related commit for an
outcome is its base commit; changes remain in the task worktree.

Use the Knowledge panel or CLI:

```sh
reverend memory add DECISION PROJECT_ID 'Use SQLite for local jobs' 'user review' 'review:42'
reverend memory search PROJECT_ID 'local jobs'
reverend memory archive MEMORY_ID
```

Retrieval stays project-scoped, uses lexical matching, excludes archived/expired records,
and budgets the entire serialized record. Task prompts receive at most 2,400 characters
of relevant historical evidence, which must be revalidated. The newest 500 records per
project remain active; older records are archived, retained for inspection, and excluded
from default retrieval. Archiving is not deletion or backup management.

## Validation

`PYTHONPATH=src .venv/bin/python -m pytest -q` uses temporary runtime data. HTTP tests
need loopback sockets. The optional browser fixture uses mock inference and now verifies the
canonical modern shell, web-policy controls, persistent inspector, safe artifacts, streaming,
rendering, persistence, cancellation and mobile navigation:

```sh
npm install --prefix .browser-test --no-audit --no-fund playwright@1.58.2
PLAYWRIGHT_BROWSERS_PATH=/tmp/reverend-browser-cache .browser-test/node_modules/.bin/playwright install chromium
PYTHONPATH=src .venv/bin/python tests/browser/demo_server.py
# Separate terminal:
PLAYWRIGHT_BROWSERS_PATH=/tmp/reverend-browser-cache node tests/browser/smoke.cjs
```

Browser dependencies are test-only and are not required to run Reverend.

## Historical M7 experience

M7 established the original Auto composer/transport, compact source cards, citation buttons
and detailed development-task links. At that milestone, source inspection used a drawer-style
presentation and later privacy capabilities had not yet landed. That description is retained
only as milestone history; the current product uses the persistent M18/M19 inspector and the
privacy/network controls described above.

## M18 visual research and artifacts

The conversation inspector keeps Sources, Response Details and Artifact Preview beside the
chat. Open any numbered citation, source card or searched-image gallery item to inspect its
stored excerpt and provenance; Previous / Next moves through the source set for that answer.

Previewable HTML and SVG blocks never execute as normal web content. HTML uses a sanitized,
scriptless sandboxed iframe with an inner deny-by-default CSP. SVG is sanitized separately.
Supported Mermaid-style flowcharts are rendered by Reverend's packaged bounded SVG renderer.
The Preview tab can expand for larger generated interfaces and diagrams.

Fresh web search may show images only when the corresponding searched page has already
survived Reverend's public-fetch and deterministic FRESH evidence gate. The remote thumbnail
URL is never loaded by the browser. A restricted image worker accepts only validated
PNG/JPEG/WebP content up to two megabytes, stores it in local application data, and the GUI
loads it from an authenticated Reverend endpoint as a local blob URL. Markdown remote images
remain disabled.

For portable M18 acceptance:

```sh
python -m reverend.benchmarks.m18_validation \
  --repository . \
  --skip-live \
  --report-root benchmarks/results/vnext/m18/portable-validation
```

For full acceptance on the real WSL2 machine with an explicitly configured search provider:

```sh
python -m reverend.benchmarks.m18_validation \
  --repository . \
  --report-root benchmarks/results/vnext/m18/live-validation
```

The portable-only command intentionally cannot certify live searched-image behavior.
