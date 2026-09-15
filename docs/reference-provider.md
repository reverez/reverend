# Offline reference providers (M9 → M10)

Install the optional official binding with project Python:

```sh
"$PWD/.venv/bin/python" -m pip install 'libzim==3.13.0'
```

The package extra is `reverend[reference]`. Core installation does not require libzim.
Network/dependency installation still requires authorization; the M9 continuation explicitly
approved this binding and one English Wikipedia all-mini archive, not arbitrary acquisitions.

The accepted Wikipedia archive and `provider.json` remain outside Git under the canonical data
root's `reference/kiwix/`. Workstation locates reference configuration relative to
`knowledge_db_path.parent`, so isolated benchmark state uses its own state while unit tests use
temporary roots. An injected `ReferenceProvider` implements `retrieve(query, mode=..., limit=...)`.

M10 adds an optional registry at `reference/providers.json`. Schema version 1 contains at most
eight explicitly enabled providers. Each entry has `id`, `type` and `manifest`; currently only
`type: "zim"` is accepted. Manifest paths must resolve inside the external `reference/` root.
Unknown provider types, path traversal and missing enabled manifests fail closed. When the
registry is absent, the accepted M9 `reference/kiwix/provider.json` layout remains the backwards-
compatible default. A composite provider preserves `reference_provider_id` in result provenance
and deduplicates stable source identities across providers.

Example external registry:

```json
{
  "schema_version": 1,
  "providers": [
    {
      "id": "wikipedia-en-mini-2026-06",
      "type": "zim",
      "manifest": "kiwix/provider.json",
      "enabled": true
    }
  ]
}
```

Required manifest fields: `path`, `byte_size`, `sha256`, `origin`, `acquired_at`, `zim_metadata`.
Use actual acquisition/archive metadata. Do not invent licenses or classify personal notes as
references. The archive SHA-256 is verified once per path/size/mtime/ctime/inode fingerprint
in each process; changed files are reverified. This is a sequential integrity read, not corpus
indexing or embedding. The manifest is local trusted configuration, not remote source input.

Each query runs in a separate local libzim reader process with a 25-second timeout. Lookup
uses existing archive title and fulltext indexes: bounded exact-title candidates first, then
title suggestions and lexical queries. Single-token omission provides bounded typo recovery;
no hand-written entity aliases exist. A corrective lexical round bypasses title lookup and
starts with the bounded alternative query order. The outer request's retrieval-round limit
still applies. At most six index searches and twelve candidate articles are used per call.
No article iteration, archive-wide vectorization or SQLite/Qdrant import is performed.

Only HTML/plaintext items of at most 1 MB are extracted, with 12,000 characters of text per
article. The existing evidence gate runs before the answer prompt, which supplies at most
1,400 characters per accepted source within its total context budget. Scripts, styles and
navigation are stripped. Source text remains untrusted instruction data even though its
provenance class is TRUSTED_REFERENCE. Named-subject queries additionally require subject
coverage, preventing a matching award/year from standing in for an unsupported person.
Short title-like queries with a confident full-title resolution reject incidental partial-title
hits (`resolved_title_mismatch`); this was prompted by real archive results, not an entity alias.

Returned metadata preserves archive path/hash/filename, actual ZIM metadata, acquisition origin,
timestamp, article path/title, raw article content hash, attribution footer/links and lookup method.
The acquired archive has no License metadata key; actual article footer notices and license
links are recorded directly, including a sample in `m9-reference-provenance.json`. Stable identities are
`zim://<archive-sha256>/<article-path>`. The current UI can display/copy that identity and its
provenance; this slice adds no archive browser or corpus management UX. Provider failures are
structured `reference_provider_failed` issues on failed retrieval jobs, with no answer generation
and no fallback to personal material. An unconfigured optional provider leaves existing local
registry retrieval available; an explicitly configured missing/bad archive fails closed.

Citation auditing remains source-label integrity, not entailment. Wikipedia mini extracts are
abbreviated and dated; they are not current news or guaranteed sufficient for every question.
No query-to-web search provider is introduced. M10 keeps archive candidate generation bounded
and adds semantic reranking/lazy passage-vector caching outside the provider itself. The provider
therefore remains independently usable without embeddings and never owns an archive-wide vector
index.

M10 also ships `python -m reverend.benchmarks.reference_fabric`, which compares provider ordering
against semantic reranking on `benchmarks/reference-fabric-queries.json`. It records hit@1,
hit@k, MRR, provider latency, cold/warm rerank latency and passage-cache hits. Its cache is a
temporary benchmark cache under the external data root; it does not mutate the production cache.
