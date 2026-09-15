# M9 Acceptance — Research & Evidence Engine

**Status:** COMPLETE

## Accepted implementation

M9 establishes Reverend's evidence-backed research path with:

- semantic evidence classes: PERSONAL, PROJECT, REFERENCE and FRESH
- corpus-aware retrieval boundaries
- deterministic relevance gating and deduplication
- bounded corrective retrieval
- conservative evidence-backed title/entity resolution
- deterministic abstention when evidence is exhausted
- explicit OFF / ASK / AUTO network policy
- structured evidence/network/citation issues
- retrieval-attempt telemetry and provenance
- citation-label integrity auditing
- bounded offline REFERENCE retrieval through verified Kiwix/openZIM Wikipedia
- no full-corpus SQLite/Qdrant ingestion or embedding

The reference provider uses the external archive:

`wikipedia_en_all_mini_2026-06.zim`

with verified SHA-256:

`1d0f8178709481c831272d95f95dccc030e9193e38e732b86b1938ae2606226e`

The archive is external data and is not committed to Git.

## Validation

Final full Python suite:

- **373 passed**
- 0 failed
- `git diff --check` passed before canonical acceptance

Canonical M9 ReverendBench live run:

- Xavier typo: **PASS**
- Rocket bad-RAG regression: **PASS**
- Nonexistent entity false premise: **PASS**
- Total: **3 passed**
- Failed: **0**
- Errors: **0**
- Timeouts: **0**

Canonical immutable report:

`benchmarks/results/vnext/m9/reference-workstation/benchmarks/runs/20260914T152925166571Z-df3051a8.json`

### Xavier

Real Wikipedia REFERENCE evidence resolved the misspelled query to
`Xavier: Renegade Angel`.

- evidence outcome: relevant
- accepted sources: 1
- evidence class: REFERENCE
- entity resolution: evidence-backed `title_fuzzy`
- citation status: present
- model calls: 1
- retrieval rounds: 1

### Rocket

The query retrieved the real Wikipedia `Rocket` article through exact-title lookup.

- domain: aerospace_engineering
- evidence outcome: relevant
- accepted sources: 1
- evidence class: REFERENCE
- citation status: present
- model calls: 1
- retrieval rounds: 1

Unrelated personal/local evidence did not satisfy the REFERENCE request.

### Nonexistent entity

The fabricated Professor Neral Vossmere premise returned no acceptable evidence.

- evidence outcome: insufficient
- sources: none
- abstained: true
- generation calls: 0
- citation status: not_applicable
- structured blockers: `network_disabled`, `evidence_insufficient`

No historical correction or fabricated evidence was generated.

## Reliability regressions

During final validation a benchmark timeout test was found to contain a
20 ms scheduler-start race. The test was changed to synchronize worker entry
and timeout deterministically rather than increasing the timeout.

The final full suite after that regression fix passed 373 tests.

## Known limitations

- Citation auditing proves Reverend source-label integrity, not claim-level entailment or source truth.
- The Kiwix `all_mini` archive primarily provides article introductions/infobox material rather than complete Wikipedia articles.
- Query-to-web search is not implemented; AUTO continues to report its absence truthfully.
- Reference retrieval is deliberately bounded and does not bulk-embed the Wikipedia archive.
- Broader corpus management, ranking/reranking, caching and Knowledge Fabric architecture belong to M10.
- M13 still owns stronger privacy/encryption/execution-security work.

## Milestone decision

M9 — Research & Evidence Engine: **COMPLETE**

M10 — Knowledge Fabric v2: **NOT STARTED**

M10 may now begin from this accepted M9 checkpoint.
