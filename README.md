# Reverend

**Reverend 0.4.0** is a local-first AI engineering and knowledge workstation.

It combines conversational assistance, evidence-aware research, local knowledge retrieval,
persistent engineering memory, repository intelligence, isolated software-development
workflows, bounded specialist workers, privacy controls, and ReverendBench evaluation in
one local Workstation.

All model inference remains local. Reverend does not require a paid or cloud inference API.

> Programme status: Reverend **0.4.0 M6–M18 is live-accepted and stabilized** on
> `main`. The retained M16–M18 acceptance report passed **619 tests** plus live local
> inference, `qwen3-coder:30b` residency, SearXNG search and searched-image/sandbox
> probes. Post-acceptance stabilization additionally validated the canonical data root,
> authority-first research, safe primary-source snippet fallback, autonomous development,
> and the modern browser shell. New engineering work branches from `main` and returns
> through review + CI.

## Platform target

The validated development/runtime target is **Linux / WSL2** with:

- Python **3.11+**;
- Git;
- Ollama reachable locally;
- `bubblewrap` / `bwrap` and standard Linux resource limits for the accepted sandbox
  contract;
- enough RAM/VRAM for the local models you enable.

The browser UI binds to **127.0.0.1 only**.

## Local model roles

The default logical roles currently resolve to:

| Role | Default model | Purpose |
| --- | --- | --- |
| FAST_GENERAL / ROUTER | `qwen3.5:4b` | everyday answers and bounded classification |
| FAST_CODE | `qwen2.5-coder:7b` | inexpensive coding work |
| STRONG_CODE | `qwen3-coder:30b` | repository planning/implementation |
| DEEP_REASON / CRITIC | `deepseek-r1:8b` | hard reasoning and independent review |
| EMBED | `bge-m3:latest` | local semantic retrieval |

Logical roles are part of Reverend's architecture; concrete model assignments may evolve.

## Install from a clean checkout

```bash
git clone <your-repository-url>
cd reverend

python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -e '.[dev]'
```

Optional Kiwix/ZIM reference support:

```bash
.venv/bin/pip install -e '.[dev,reference]'
```

Confirm the release identity:

```bash
.venv/bin/reverend --version
# reverend 0.4.0
```

The repository convenience wrapper uses the same environment:

```bash
scripts/reverend --version
```

## Configure Ollama and runtime state

Reverend is environment-first. Copy `.env.example` only if you need overrides.

The important settings are:

- `OLLAMA_HOST` — optional Ollama endpoint. If unset, Reverend uses localhost on native
  Linux and can discover the Windows gateway under WSL.
- `AI_DATA_ROOT` — operational databases, artifacts, worktrees, public-source cache and
  other runtime state. Keep this outside the Git repository.
- `REVEREND_RUNTIME_CONFIG` — optional JSON configuration path. The default is
  `~/.config/reverend/runtime.json`.
- `REVEREND_STATE_KEY_FILE` — optional encrypted-state key path. The default is
  `~/.config/reverend/state-v1.key`.
- `QDRANT_URL` — optional external Qdrant server. If unset, Reverend uses the embedded
  store under the data root.
- `QDRANT_COLLECTION` — optional collection override.

Do not place credentials in the repository or `.env.example`.

Example runtime config:

```json
{
  "data_root": "/home/you/.local/share/reverend",
  "ollama_host": "http://127.0.0.1:11434"
}
```

## Start the Workstation

```bash
.venv/bin/reverend gui
```

Default address:

```text
http://127.0.0.1:8765
```

Choose another local port if required:

```bash
.venv/bin/reverend gui --port 8877
```

The server binds only to loopback, uses a per-process browser/API session token, rejects
cross-site API requests, sends restrictive browser security headers, and does not log
request bodies or tokens.

## Normal Workstation workflow

The normal experience is **Auto**:

1. write the objective in natural language;
2. optionally select a project, knowledge/research context, privacy mode or network policy;
3. Reverend deterministically classifies what it can;
4. low-confidence requests use the bounded local ROUTER;
5. the orchestrator selects the cheapest sufficient local capability;
6. evidence is retrieved only from requested/eligible trust classes;
7. irrelevant evidence is discarded;
8. uncertainty triggers corrective retrieval, clarification, capability escalation or
   abstention;
9. development runs in an isolated task worktree and must pass deterministic verification.

Manual Ask / Reason / Research controls remain advanced overrides.

## Privacy modes

### Normal

Conversation and Workstation state persist in encrypted form.

### Private

Encrypted persistent conversation state is available, but the conversation is not intended
for automatic long-term-memory promotion.

### Ephemeral

Conversation/messages/chat-job state remain process-local and are cleared after use/restart.

Persistent Workstation payloads use versioned authenticated encryption. State files and the
state key are restricted to the current user where the platform supports POSIX ownership
and permissions.

## Network policy

Reverend exposes explicit network policies:

- **OFF** — no fresh network acquisition;
- **ASK** — fresh network use requires explicit approval;
- **AUTO** — the workflow may use configured network capability when fresh evidence is
  required.

Retrieved public content remains **untrusted data**, never instructions.

An explicit public URL can be fetched from the CLI only with network opt-in:

```bash
.venv/bin/reverend web-fetch 'https://example.org/document' --allow-network
```

General query-to-web search is not enabled implicitly. The canonical no-paid-API backend is
a self-hosted SearXNG instance on loopback; start the bundled profile with
`scripts/reverend-searxng up`, then load `eval "$(scripts/reverend-searxng env)"`.
Brave remains an optional adapter rather than a required service. If AUTO needs fresh search
and no provider is configured, Reverend reports `network_search_unavailable` rather than
silently inventing fresh evidence. Reverend normally fetches search results through its
restricted page worker before evidence gating. When a recognized first-party vendor page is
blocked by the remote site, Reverend may retain a bounded title/snippet fallback with explicit
`search_snippet` transport provenance and lower transport confidence; secondary-source
snippets are never promoted by this fallback.

## Projects and software development

Project registration defaults to:

```text
untrusted_repo
```

Untrusted repositories are inspection-only. Reverend does not silently promote trust.

Trusted development retains the accepted isolated flow:

```text
request
→ trust check
→ isolated Git worktree
→ code localization
→ structured plan
→ bounded workers
→ host-controlled structured edits
→ deterministic verification
→ bounded repair
→ independent verification
→ result
```

The primary checkout is not modified by the development engine. Integration is a separate,
explicit human action.

The lower-level CLI development surface remains available:

```bash
.venv/bin/reverend dev implement \
  --project /path/to/clean/repository \
  --request 'Implement the requested change.' \
  --acceptance 'Relevant tests pass.' \
  --json
```

Review generated changes before integrating them.

## Code intelligence

Reverend provides deterministic repository profiling, Python AST symbols/imports, bounded
dependency/call graph expansion and structural/lexical retrieval.

Optional semantic code indexing is reconstructable and never makes vectors authoritative
over current source text:

```bash
.venv/bin/reverend code-index /path/to/repository
.venv/bin/reverend code-search /path/to/repository 'query'
```

## Knowledge and evidence

Reverend separates evidence into:

- **PERSONAL** — your notes/documents;
- **PROJECT** — repository/project evidence;
- **REFERENCE** — stable trusted reference material;
- **FRESH** — explicitly permitted network-derived evidence.

The evidence engine retrieves, deduplicates, ranks and gates candidates before they enter
authoritative answer context. Missing or irrelevant evidence is not forced into an answer.

The earlier Knowledge Fabric ingestion/search surfaces remain available for advanced local
corpora:

```bash
.venv/bin/reverend status
.venv/bin/reverend doctor
.venv/bin/reverend doctor --deep

.venv/bin/reverend sync --dry-run
.venv/bin/reverend sync --apply

.venv/bin/reverend search 'Jacobian matrix'
.venv/bin/reverend search 'vector spaces' --mode lexical --limit 5
```

The AI note compiler still writes external **unreviewed** drafts rather than silently
promoting generated content into source notes.

## Engineering memory

Engineering memory is typed and provenance-backed. Supported operational record classes
include facts, decisions, experiments, failures, results and user constraints.

```bash
.venv/bin/reverend memory search PROJECT_ID 'query'
```

Model hypotheses do not become verified facts merely because a model generated them.

## ReverendBench and validation

Run the complete Python suite:

```bash
.venv/bin/python -m pytest -q
```

List benchmark cases:

```bash
.venv/bin/reverend benchmark list
```

Run deterministic routing acceptance:

```bash
.venv/bin/reverend benchmark routing
```

Run selected/full ReverendBench cases:

```bash
.venv/bin/reverend benchmark run
.venv/bin/reverend benchmark run --case CASE_ID
```

Milestone validation evidence is retained under:

```text
benchmarks/results/vnext/
```

The canonical final acceptance command for the current branch is:

```bash
.venv/bin/python -m reverend.benchmarks.final_validation \
  --repository . \
  --report-root benchmarks/results/vnext/final-validation
```

Use `--skip-live` only for portable software validation. Portable-only success exits 2 by
design and does not certify the real Ollama/search/image paths. The earlier accepted M15
baseline evidence remains under `benchmarks/results/vnext/m15/live-validation/`.

## Backup and recovery

Reverend intentionally separates encrypted persistent state from its encryption key.

Before a migration or destructive maintenance operation, back up:

1. the configured `AI_DATA_ROOT`;
2. the state key, normally `~/.config/reverend/state-v1.key`;
3. the runtime config, normally `~/.config/reverend/runtime.json`;
4. any external source corpora that are not independently backed up.

**Losing the state key makes encrypted persistent Workstation state intentionally
unrecoverable.** Do not store the only copy of the key inside the data directory backup.

For Knowledge Fabric/Qdrant migrations:

- stop active writers;
- preserve SQLite and the old vector collection;
- migrate/copy into a new collection;
- validate counts/generations/retrieval;
- switch configuration only after validation;
- keep the old collection for rollback.

FTS/vector indexes are reconstructable. Source documents remain authoritative.

## Security boundaries

Reverend's accepted vNext invariants include:

- local-only model inference;
- explicit network policy;
- no arbitrary worker shell/filesystem authority;
- typed bounded worker state;
- isolated development worktrees;
- path/hash validation before structured edits;
- deterministic verification over model confidence;
- credential/environment filtering;
- explicit project trust;
- fail-closed command sandbox construction;
- hidden host home/credentials for the accepted untrusted sandbox contract;
- read-only system runtime and bounded writable workspace;
- CPU/RAM/process/file-descriptor/core-dump limits;
- sanitized local browser rendering.

See:

- [vNext architecture](docs/vnext-architecture.md)
- [0.4.0 upgrade and recovery](docs/release-0.4.0.md)
- [safety and recovery](docs/safety.md)
- [repository consolidation](docs/repository-consolidation.md)
- [parallel development workflow](docs/development-workflow.md)

## Known release limitations

- Reverend is currently validated primarily on Linux/WSL2.
- No general web-search provider is enabled implicitly. The supported canonical free
  deployment is bundled self-hosted SearXNG; public upstream search engines may still impose
  rate limits or CAPTCHAs.
- Untrusted repositories remain inspection-only for the full development workflow.
- The accepted sandbox does not claim that arbitrary hostile repository checkout/
  materialization is safe.
- Large-model inference remains serialized unless future hardware evidence supports safe
  concurrency.
- Qdrant server migration must remain explicit and rollback-safe.
- Citations/provenance demonstrate source use, not perfect semantic entailment.
- AI-generated code and drafts still require human review before integration/promotion.

## Release discipline

The M6–M18 programme has a retained **live-accepted** final validation, and the
post-acceptance stabilization pass is complete on `main`. Parallel optimization work must
branch from the stabilized `main` baseline and return only through review + green CI.
Reverend does not automatically:

- merge the branch;
- create a tag;
- publish a GitHub release;
- upload a package;
- integrate generated development changes.

Those are explicit post-acceptance actions.
