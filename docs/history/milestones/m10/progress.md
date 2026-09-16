# M10 Knowledge Fabric v2 — COMPLETE

M6–M10 are COMPLETE. M11–M15 are NOT STARTED. The frozen vNext architecture
remains authoritative.

## First implementation slice

This slice implements the preferred M10 reference path after bounded candidate
generation:

`exact/title → lexical candidates → semantic rerank → lazy embedding/cache → evidence gate`

The existing M9 Kiwix provider remains responsible for exact-title/title-index/
full-text candidate generation. M10 adds `reverend.knowledge.KnowledgeFabric`.

Properties:

- at most 12 candidates enter semantic reranking;
- the existing local `EMBED` role is reused;
- no cloud inference and no new model download;
- candidate embeddings are created lazily, never by walking the corpus;
- only vectors and hashes are cached, not raw source text;
- cache keys include embedding-model identity and exact embedded-passage hash;
- the cache is bounded to 50,000 entries and lives in Workstation state;
- benchmark-isolated Workstations therefore use isolated caches;
- one batch embedding call covers the query plus all cache misses;
- one model call is reserved for answer generation;
- insufficient model budget skips semantic embedding deterministically;
- embedding failure falls back to deterministic title/lexical ranking;
- ranking telemetry survives into source metadata;
- the M9 evidence gate still decides whether ranked material is admissible.

The evidence gate uses `fabric_score` only for ordering candidates that have
already passed class and deterministic relevance checks. Semantic ranking cannot
make irrelevant or wrong-class material authoritative.

## Second implementation slice

The next M10 batch generalizes reference-provider configuration and adds a
repeatable retrieval-quality benchmark.

Reference configuration now supports an optional external
`reference/providers.json` registry. The registry:

- is schema-versioned;
- supports at most eight explicitly enabled providers;
- currently accepts only bounded local ZIM providers;
- rejects path traversal and unknown provider types;
- preserves a stable `reference_provider_id` in provenance;
- interleaves provider ranks so the first provider cannot consume the complete
  candidate window;
- falls back to the accepted M9 `reference/kiwix/provider.json` layout when no
  registry exists.

The new `reverend.benchmarks.reference_fabric` benchmark evaluates twelve
stable reference queries without modifying the production cache. It records:

- baseline and reranked hit@1;
- hit@k;
- MRR@k;
- per-case expected rank;
- provider latency;
- cold and warm semantic-rerank latency;
- cache-hit counts and passage-cache size;
- explicit quality deltas between provider ordering and semantic reranking.

Run it locally against the real Kiwix archive with:

```sh
"$PWD/.venv/bin/python" -m reverend.benchmarks.reference_fabric
```

The committed query set is evaluation data, not a source of production aliases
or query-specific routing.

## Deliberate non-goals of this slice

- no archive-wide embedding;
- no SQLite/Qdrant import of the 12.5 GB Wikipedia ZIM;
- no new external corpus acquisition;
- no query-to-web implementation;
- no M11 workers;
- no dedicated reranker model yet;
- no claim that embedding similarity is factual verification.

A dedicated cross-encoder such as a BGE reranker is an M10 candidate only after
a local quality/latency bake-off demonstrates improvement over the already
installed BGE-M3 embedding path.

## Validation

Final GitHub Actions validation:

- **100 targeted tests passed**
- **391 full portable Python tests passed**
- compile checks passed

Final live workstation validation:

- canonical M9 regression: **3 passed, 0 failed, 0 errors, 0 timeouts**
- reference benchmark: **12 cases**
- Hit@1: **0.500000 → 0.750000**
- Hit@5: **0.750000 → 0.833333**
- MRR@5: **0.611111 → 0.791667**
- warm rerank median: **51.150 ms**
- cold rerank median: **345.313 ms**
- cache entries: **114**
- benchmark decision: `recommended_default: true`
- overall live validation: `overall_ok: true`

Final reports:

- `benchmarks/results/vnext/m10/live-validation/validation-20260914T162751Z.json`
- `benchmarks/results/vnext/m10/live-validation/reference-fabric/20260914T162751Z.json`
- `benchmarks/results/vnext/m10/live-validation/m9-regression/benchmarks/runs/20260914T162751455051Z-bec16108.json`

The current BGE-M3 semantic path is accepted as the M10 default. A dedicated
cross-encoder is deferred unless later M14 bake-offs demonstrate a measured
quality/latency advantage.

See `docs/history/milestones/m10/acceptance.md`.

## Milestone state

M10 is **COMPLETE**.

M11 — Worker Orchestration is **NOT STARTED**.
