# Adaptive intelligence

M8 defines typed request understanding, execution plans and resource budgets separately
from UI rendering. Classification can describe intent, domain, evidence need, freshness,
complexity and ambiguity; it cannot supply shell commands or grant execution permission.

The deterministic capability ladder uses FAST_GENERAL for ordinary conversation and text
transforms, FAST_CODE for small code questions, DEEP_REASON for difficult reasoning, and
STRONG_CODE for complex coding. Explicit workflow overrides remain available. Development
requires a selected project, an explicit change request, the existing trust/worktree checks,
and enough budget for planning, implementation and independent verification.

The escalation policy distinguishes missing evidence from weak reasoning: missing or
irrelevant evidence requests another bounded retrieval round, then abstention. It does not
try to manufacture facts by switching to a larger model. Model escalation is limited by
remaining call budget. Network policy is typed OFF/ASK/AUTO; classification alone cannot
turn it on. M9 now executes local evidence gating and bounded corrective retrieval.

Workstation Auto now consumes the policy. Clear requests use deterministic understanding;
ambiguous open-domain requests may use one bounded ROUTER call through the existing local
scheduler. ROUTER reuses FAST_GENERAL's physical model; CRITIC reuses DEEP_REASON. Invalid
structured classifications or low confidence produce clarification without a speculative
answer. Model-supplied execution directives are rejected.

The installed model registry informs fallback. A missing required development or explicit
Reason model fails clearly. Automatic fallback records a capability limitation. Development
continues through the existing isolated engine with a shared per-job call budget.

Per-request accounting includes embeddings and generation, attempted/failed calls, model
identity/digest where returned, available token counts and elapsed time. Calls stop before
exceeding the budget. Chat defaults to four total calls; manual development defaults to eight.
Output generation is capped at 1,536 tokens, matching the existing prompt reserve. Classifier
requests have a 30-second bound. Existing provider cancellation and serialized execution apply.

ReverendBench now passes and checks model-call budgets. The three historical RAG cases
explicitly permit two calls: one embedding request and one answer. Earlier reports preserved
a one-call declaration but did not count/enforce embeddings; they remain immutable. The new
accounting changes the measurement contract, not the number of inference operations in the
legacy RAG path. Retrieval-round counts are also checked when available.

## M9 evidence and observability (accepted)

Research and explicit knowledge retrieval use `ExecutionPlan.corpora`. PERSONAL notes and
synthetic TRUSTED_PRIMARY fixtures cannot satisfy REFERENCE requests. Candidates are
classified, deduplicated and deterministically gated; accepted titles can support conservative
entity correction. These lexical signals measure relevance, not factual truth.

Local correction tries hybrid, then lexical only after insufficient/irrelevant evidence,
within the requested round budget. At most two distinct strategies exist even if a caller
permits four rounds; `corrective_strategy_exhausted` explains early exhaustion. Research
requiring REFERENCE/FRESH evidence abstains deterministically when no usable context remains,
without calling the answer model. Other chat modes retain their existing synthesis behavior.

`evidence.attempts` records mode, 1-based round, candidate count, accepted count and outcome
for each actual local attempt. Counts are per attempt before cumulative selection; duplicate
candidates can therefore contribute to candidate counts but not accepted counts. Running or
failed retrieval has unknown counts (`null`) until results are available; exceptions retain
an `error` attempt, `retrieval_failed` issue and failed job status. Escalations identify the
actual next round; selecting a cached public source is not a network search or retrieval round.

Bounded prompt compilation places accepted evidence before project background. Each included
source retains its full header and a bounded body; response `sources` contain only included
sources with exactly those body excerpts, citation labels, trust, class and available provenance.
`context_clipped`, `evidence.context_count` and `context_omitted_count` expose truncation. Public
source hashes, timestamps and original clipping flags survive selection. A hash describes the
original fetched content, not the shortened excerpt. Evidence unable to fit yields
`evidence_context_unavailable` and Research abstention. This is character budgeting, not
query-aware passage compression or exact token accounting.

## Citation and Bench contracts

The deterministic post-synthesis `citation` audit has scope `source_label_integrity`. Statuses:
`not_applicable` (no sources or citation labels), `missing` (sources but no labels), `present`
(at least one valid label and no unknown labels), and `unknown_source` (any unknown label,
including mixed valid/unknown citations). It publishes `citation_missing` or
`citation_unknown_source` issues, cited labels, resolved valid labels and unknown labels.
Numeric source-drawer aliases such as `[1]` are accepted alongside `[K1]` or public IDs.
Cancelled streams carry `citation.complete=false`; their partial audit is not a completed answer.

This is a bounded lexical check of standalone `[A-Za-z0-9_-]` labels, excluding common fenced
and inline code, math, escaped brackets and Markdown links. It is not a full Markdown parser,
claim-level entailment, source authenticity verification or proof that every claim is cited.
A plain bracketed identifier can be flagged as unknown. Unlabelled project/background context
is outside this audit. Citation warnings do not rewrite or silently repair the answer.

Bench supports first-class `citation_status`, required `issue_codes` and
`forbidden_issue_codes`. Missing/malformed issue metadata fails these expectations. Failed
and timed-out Workstation jobs retain their last response, issues and usage in ERROR/TIMEOUT
reports; they cannot become passing abstentions. The nonexistent-entity case requires a
completed, nonempty, source-free abstention with insufficient evidence, the OFF blocker and
zero generation calls. Xavier/rocket require present citations as well as their existing
entity/domain/relevance behavior. Historical reports remain unchanged.

## Network boundary and remaining data requirement

OFF performs no network acquisition. ASK requires explicit approval; it does not fetch while
waiting. AUTO permits a configured capability but cannot create one: no query-to-web provider
exists, so exhausted reference requests report `network_search_unavailable`. Stable exhausted
queries now expose the same policy blockers as fresh queries. No larger model is selected to
compensate for missing evidence. Selected, previously fetched public sources can be used under
any policy after relevance gating, always as UNTRUSTED_EXTERNAL.

`PublicResearch.fetch(url, allow_network=True)` remains the explicit-URL network capability,
using the restricted bubblewrap worker. No query-to-web provider was added.

## Authorized offline reference provider

The September 2026 M9 continuation authorized the official Kiwix English Wikipedia all-mini
June 2026 archive and optional official `libzim==3.13.0` binding. The archive lives outside Git,
with a recorded SHA-256 matching Kiwix's published digest and actual ZIM metadata/attribution.
See [reference-provider.md](../guides/reference-provider.md) and
[m9-reference-provenance.json](../../history/milestones/m09/reference-provenance.json).

Configured REFERENCE requests use a typed provider seam with exact/title lookup followed by
bounded indexed lexical queries, including generic single-token omission for typo recovery.
Each local query has a 25-second worker timeout, at most six index searches and twelve article
candidates. The outer retrieval mode is the requested strategy; source metadata records the
actual index operations/method. Corrective lexical mode skips title lookup and changes query
order. Archive integrity is verified once per file fingerprint before querying; no full-corpus
embedding or registry import is performed. The original SQLite personal corpus is unchanged.

A strong full-title resolution for a short query rejects unrelated partial-title matches.
Named-subject coverage prevents award/date overlaps from supporting an invented person.
These remain deterministic relevance heuristics, not factual or entailment verification.
Provider failure publishes `reference_provider_failed`, fails the job, and generates no answer;
Bench preserves the error instead of treating infrastructure failure as successful abstention.

Pure archive retrieval uses zero embedding calls. A supported canonical Research answer needs
one answer-generation call; unsupported queries need none. The canonical budget remains two
total calls and one outer retrieval round. Historical embedding-inclusive measurements remain
in their immutable reports. M9 and M10 are accepted; M11 Worker Orchestration has not started.


## M10 bounded semantic Knowledge Fabric

M10 preserves the accepted M9 reference provider as candidate generation and
adds a separate bounded ranking layer. Hybrid REFERENCE retrieval can now use:

`exact/title → lexical candidates → semantic rerank → lazy vector cache → evidence gate`

At most twelve candidates are reranked. Reverend reuses the existing local
`EMBED` role and batches the query plus uncached candidate passages into one
embedding call. It never walks or vectorizes the complete ZIM archive. Candidate
vectors are cached lazily in Workstation state by embedding-model identity and
exact embedded-passage hash. Raw reference text is not copied into this cache,
and the cache is bounded.

One model call is reserved for answer generation. If the request budget cannot
spare a rerank call, semantic ranking is skipped deterministically. If an
embedding attempt fails, already-valid candidate evidence falls back to
deterministic title/lexical ranking rather than being silently discarded.
The selected method, semantic score, cache-hit state and fabric score remain in
source provenance.

The M9 evidence gate remains authoritative. `fabric_score` only orders material
that already passed trust/class and deterministic relevance checks; semantic
similarity cannot promote wrong-class or irrelevant material into authoritative
context. The accepted twelve-query live benchmark improved Hit@1 from 0.50 to 0.75,
Hit@5 from 0.75 to 0.833333 and MRR@5 from 0.611111 to 0.791667. Warm
reranking measured a 51.150 ms median on the accepted workstation. BGE-M3
semantic reranking is therefore the accepted M10 default. A dedicated
cross-encoder is deferred to later model/runtime bake-offs unless it can
demonstrate a measured Pareto improvement.


M10 acceptance is recorded in `m10-acceptance.md`. The final live validation
preserved all three canonical M9 regressions and recorded `overall_ok: true`.
