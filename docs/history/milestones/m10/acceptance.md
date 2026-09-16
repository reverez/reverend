# M10 Acceptance — Knowledge Fabric v2

**Status:** COMPLETE

## Accepted implementation

M10 turns the accepted M9 REFERENCE seam into a bounded local Knowledge Fabric.

The accepted reference path is:

`exact/title → bounded lexical candidates → semantic rerank → lazy cache → evidence gate`

Implemented behavior:

- at most 12 reference candidates enter semantic reranking;
- the existing local `EMBED` role (BGE-M3 on the accepted workstation) is reused;
- no cloud inference and no paid inference dependency;
- candidate passages are embedded lazily rather than by walking the reference corpus;
- passage vectors are cached by embedding-model identity and exact passage hash;
- raw reference text is not duplicated into the vector cache;
- the cache is bounded to 50,000 entries;
- one batched embedding request covers the query plus uncached candidates;
- answer-generation budget is reserved before reranking;
- unavailable/failed embedding falls back to deterministic title/lexical ordering;
- ranking telemetry and cache state survive into source provenance;
- the M9 evidence gate remains authoritative and semantic similarity cannot admit irrelevant or wrong-class evidence.

M10 also generalizes local reference configuration through optional
`reference/providers.json`:

- schema version 1;
- at most eight explicitly enabled providers;
- currently supports bounded local ZIM providers;
- rejects unknown provider types and path traversal;
- preserves `reference_provider_id`;
- interleaves provider ranks to prevent first-provider starvation;
- retains the M9 `reference/kiwix/provider.json` layout as a backwards-compatible fallback.

## Retrieval-quality benchmark

M10 adds the reproducible twelve-query reference benchmark:

`benchmarks/reference-fabric-queries.json`

and runner:

`python -m reverend.benchmarks.reference_fabric`

The benchmark compares provider ordering with semantic reranking while recording
quality, latency and cache behavior.

Final live report:

`benchmarks/results/vnext/m10/live-validation/reference-fabric/20260914T162751Z.json`

### Quality

| Metric | Baseline | Semantic rerank | Delta |
| --- | ---: | ---: | ---: |
| Hit@1 | 0.500000 | 0.750000 | +0.250000 |
| Hit@5 | 0.750000 | 0.833333 | +0.083333 |
| MRR@5 | 0.611111 | 0.791667 | +0.180556 |

The benchmark decision was:

- quality non-regression: true
- quality improved: true
- recommended default: true

BGE-M3 semantic reranking is therefore accepted as the M10 default. A separate
cross-encoder is not added in M10 because no measured evidence currently shows
that its additional model/dependency/latency cost is justified. Future model
bake-offs belong to M14.

### Latency and cache

Final live workstation measurements:

- provider median: **993.395 ms**
- provider mean: **1028.570 ms**
- provider maximum: **1310.232 ms**
- cold semantic-rerank median: **345.313 ms**
- cold semantic-rerank mean: **296.979 ms**
- cold semantic-rerank maximum: **415.418 ms**
- warm semantic-rerank median: **51.150 ms**
- warm semantic-rerank mean: **48.472 ms**
- warm semantic-rerank maximum: **57.677 ms**
- cold cache hits: **0**
- warm cache hits: **51**
- cached passage entries: **114**

These are acceptance measurements for this workstation and query set, not universal
performance guarantees.

## Regression validation

Final live M9 regression under the M10 Knowledge Fabric:

- Xavier typo: **PASS**
- Rocket bad-RAG regression: **PASS**
- Nonexistent entity: **PASS**
- total: **3 passed**
- failed: **0**
- errors: **0**
- timeouts: **0**

Canonical regression report:

`benchmarks/results/vnext/m10/live-validation/m9-regression/benchmarks/runs/20260914T162751455051Z-bec16108.json`

Overall validation summary:

`benchmarks/results/vnext/m10/live-validation/validation-20260914T162751Z.json`

The final summary records `overall_ok: true`.

During live validation, Xavier exposed a citation-audit false negative: the local
model emitted `[[K1]]` while the deterministic audit accepted only `[K1]`.
The parser now accepts the citation-shaped double-bracket variant without treating
ordinary wiki-style links as citations, and the generation prompt explicitly requests
canonical single-bracket labels. The regression then passed without weakening
retrieval or evidence requirements.

## CI validation

GitHub Actions on the final accepted branch state passed:

- targeted Python suite: **100 passed**
- complete portable Python suite: **391 passed**
- compile checks: passed

The full CI suite is portable across GitHub runners. Historical hard-coded vault
and note-template host paths were made environment-configurable, with an isolated
CI fixture.

## Preserved invariants

M10 preserves the frozen vNext architecture:

- all inference remains local;
- the 12.5 GB Wikipedia ZIM remains external to Git;
- no archive-wide SQLite/Qdrant import;
- no archive-wide embedding;
- no query-specific production aliases from benchmark cases;
- bad retrieval is still rejected by the deterministic evidence gate;
- unsupported entities still abstain without generation;
- provenance and trust labels survive ranking;
- provider failures remain structured failures rather than fabricated answers;
- M11 worker orchestration has not been started.

## Known limitations

- The twelve-query ranking benchmark is intentionally small; it proves a measured
  improvement on the accepted reference set, not universal retrieval superiority.
- Embedding similarity is a ranking signal, not factual verification or entailment.
- The provider registry currently supports ZIM providers only.
- Kiwix all-mini contains abbreviated reference material rather than full articles.
- Query-to-web search remains unavailable; network policy behavior is unchanged.
- Citation auditing verifies source-label integrity, not whether every generated claim
  is entailed by its source.
- Production cache/privacy hardening remains subject to later security work in M13.
- Broader local-model/reranker bake-offs belong to M14.

## Milestone decision

M10 — Knowledge Fabric v2: **COMPLETE**

M11 — Worker Orchestration: **NOT STARTED**

M11 may begin from this accepted checkpoint.
