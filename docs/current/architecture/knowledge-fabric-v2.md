# Local Knowledge Fabric V2

Raw source files are authoritative. SQLite (`platform.db`) owns document state,
chunk text, provenance, FTS5 and pending publication recovery. Qdrant owns dense
vectors; its full text payload is temporarily retained for compatibility and
recovery. `ingestion/state.json` is an atomically replaced export of SQLite,
not an independent ingestion authority. Indexes remain rebuildable from sources.

The core is SQLite + Qdrant, with Windows-native Ollama serving BGE-M3 (1024
dimensions) and local generation models. No extra database, broker, daemon,
server installation or cloud fallback is introduced.

## Ingestion and recovery

`ai sync --dry-run|--record-baseline|--apply` uses configured corpus membership.
`rg --files -0` remains authoritative. For `/mnt/<drive>` roots, one UTF-8
PowerShell traversal supplies NTFS size/timestamps concurrently with rg.
Windows-only files cannot enter membership. Unmatched metadata or a failed
provider falls back to `stat`; Linux roots use `stat`. Provider and fallback
counts are visible. Unchanged metadata avoids content hashing. No-op sync never
opens Qdrant or calls embeddings.

Both `ai ingest` and sync use one replacement path:

1. Parse and batch embeddings; verify the source did not change.
2. Journal the pending publication in SQLite.
3. Upsert deterministic UUID5 IDs (`source:digest:ordinal`), waiting for success.
4. Delete all superseded generations, including interrupted publications.
5. Commit document/chunks/FTS and clear the journal in one SQLite transaction.
6. Atomically regenerate the transitional JSON export.

A pending source is retried even if its bytes revert or it disappears. Deletion
is Qdrant-first and retry-safe. SQLite never declares publication success before
Qdrant succeeds. A local file lock rejects concurrent ingestion/maintenance.
There is no distributed transaction: interrupted generations remain recoverable
via the journal. Dense retrieval excludes candidates without current SQLite
chunks and warns about reconciliation problems.

Schema v4 contains `meta`, `corpora`, `documents`, `chunks`,
`pending_publications` and FTS tables/triggers. A source path belongs to one
corpus. Current parser/chunker and embedding identifiers preserve the existing
index contract; changing their semantics requires an explicit collection rebuild.

## Materialization and lexical search

`ai backfill-chunks` scrolls payloads in batches without requesting vectors,
re-embedding or rereading sources. Transactions are batch-sized; restarting
from the beginning is idempotent. Legacy ordinals may be NULL. Unknown sources,
stale/invalid payloads and per-document count mismatches fail reconciliation.
The production pre-migration SQLite backup lives in the external data root.

FTS5 is an external-content index over canonical chunk section/text, maintained
by insert/update/delete triggers, including document cascades. BM25 weights
section 3:1 relative to text. Queries become quoted Unicode tokens joined by OR;
user punctuation never becomes raw MATCH syntax. `ai rebuild-fts` rebuilds and
checks integrity against canonical content. SQLite chunk text can rebuild FTS
without Qdrant. Dense vectors can be rebuilt by embedding canonical/source text;
there is no standalone bulk vector-rebuild command yet.

## Retrieval

`reverend.retrieve` independently exposes dense, lexical and hybrid retrieval.
Dense queries embed with BGE-M3, ask Qdrant for IDs/generation hashes, and hydrate
text/provenance from SQLite. Corpus/trust filters work in both modes. Hybrid
combines 50 candidates per mode using RRF, `sum(1/(60+rank))`. Scores and ranks
remain visible. Deduplication is by stable chunk ID; equal text in separate
sources retains separate provenance. Catalogue records rank after substantive
material in hybrid. Known generated trust classes and draft paths are excluded.

`ai search` defaults to hybrid after the real 28-query benchmark. Dense and
lexical modes remain explicit. Hybrid improves aggregate recall/MRR over dense;
lexical has higher recall and lower latency on this title-heavy sample. Two
per-query top-five regressions and incomplete judgments are documented in
`benchmarks/results/v2-retrieval.md`; this is not a held-out quality guarantee.

## Notes and trust

The compiler resolves topics generically, derives metadata conservatively,
loads the live Master Note Template every run, and parses its Individual Note
layout. It creates a JSON coverage plan and retrieves evidence per section with
batched query embeddings. Catalogue records, metadata scaffolding, known AI
output and untrusted external material are excluded from note evidence. Primary
material precedes personal notes when available. Evidence packs are bounded.

Local synthesis returns structured claims with section-specific evidence IDs
and verbatim supporting excerpts. Code validates IDs, quote membership and
structure, then renders Markdown deterministically. Unsupported sections state
insufficient evidence. This validates provenance, not semantic entailment;
human review remains necessary. Drafts and their provenance sidecars are created
exclusively outside the vault with `origin: AI-generated`, `review_status:
unreviewed`, and `active: false`. Dry-run performs retrieval but no generation
or file writes. No topic-specific retrieval branches remain. Live acceptance
produced five supported claims from four evidence chunks and five unsupported
sections. The compiler is functional but comprehensive synthesis quality remains
unproven; its longest-topic-term gate is a conservative heuristic.

## Configuration and operations

`AI_DATA_ROOT` defaults to `~/.local/share/reverend` for new installations. If that portable location is absent but the previous legacy data directory already exists, Reverend adopts the existing state rather than silently presenting an empty workspace. Explicit environment/runtime configuration always wins.
`QDRANT_URL` selects server mode; otherwise `QDRANT_PATH` defaults to its existing
`qdrant` directory. `QDRANT_COLLECTION` defaults to `local_knowledge_v2`.
`QDRANT_API_KEY` is optional and read only from the environment. A single client
is reused and closed per process. `OLLAMA_HOST` wins; WSL otherwise discovers
its Windows gateway from `/proc/net/route`, with the historical host fallback.
Native Linux defaults to localhost.

`ai status` reads SQLite offline, including counts, corpus state, publication
journal and successful-sync freshness. It does not invent a current Qdrant count.
Normal doctor checks registry/template/Ollama availability without inference.
`doctor --deep` adds embedding/query/count and SQLite integrity/foreign-key checks.

Qdrant remains embedded. It loads vectors into memory during client startup even
when a scroll requests no vectors; the backfill itself is batch-bounded. The
measured cold startup was 16 seconds. Server configuration is unit-tested, but
no real server migration has been performed. Future migration: stop writers,
back up SQLite and embedded storage, create a new server collection, copy or
re-embed in batches, verify counts/generations and this benchmark, then explicitly
switch configuration. Retain the old collection for rollback; never destructively
upgrade the live collection. A transfer/rebuild utility is still future work.

The Windows-owned vault stays on `/mnt/c`. Future AI-managed corpora belong on
WSL ext4 under the data root. Wikipedia needs article/title then section
retrieval; structured Wikidata/OpenAlex and symbol-aware code are future adapters,
not reasons to flatten everything into one vector collection.
