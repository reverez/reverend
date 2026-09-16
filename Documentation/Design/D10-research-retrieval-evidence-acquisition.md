# D10 — Research, Retrieval & Evidence Acquisition

> **Status:** DESIGN CLOSED / READY FOR C4 IMPLEMENTATION  
> **Depends on:** A5, A12, D3, D6, D8  
> **Purpose:** Define how Reverend acquires, stores, ranks, retrieves and cites external/reference evidence without turning search engines, crawlers, indexes or model synthesis into authority.

---

## 1. Governing Invariant

Research is an evidence-acquisition pipeline, not a second memory system and not a source of execution authority.

~~~text
Task / research question
        ↓
bounded research plan
        ↓
Research Broker
        ↓
search / reference acquisition
        ↓
restricted fetch
        ↓
normalization + provenance
        ↓
immutable EvidenceSource Artifact
        ↓
derived lexical / semantic indexes
        ↓
Context Broker
        ↓
ResearchEvidencePack
~~~

Search results, web pages, repository comments and generated summaries remain data. They never create permissions, mutate workflow state, grant tool authority or bypass D6.

---

## 2. Existing 0.4.0 Capabilities to Preserve

The current repository already contains useful implementation work that should be adapted rather than discarded:

- src/reverend/research/search.py — Brave/SearXNG provider configuration, bounded queries and primary-source search support.
- src/reverend/research/search_worker.py — isolated network worker, endpoint/address validation, provider normalization and freshness support.
- src/reverend/research/worker.py — public-HTTPS validation, DNS/address checks, bounded fetch, text extraction and process-execution denial.
- src/reverend/research/service.py — parent-owned provenance, explicit network opt-in, search/fetch budgets and snippet fallback semantics.
- src/reverend/research/quality.py — deterministic source authority, independence, facets, temporal handling and claim/evidence quality.
- src/reverend/reference.py — bounded offline reference providers, including optional ZIM.
- src/reverend/retrieve.py — lexical+dense retrieval with reciprocal-rank fusion.
- src/reverend/knowledge.py — bounded reranking and lazy embeddings.
- src/reverend/engineering_memory.py — typed project-scoped engineering records.
- src/reverend/qdrant_migrate.py — safe/resumable Qdrant migration ideas.

Cloud v1 keeps these strengths while removing local SQLite/Qdrant stores as competing authority.

---

## 3. Logical Research Components

### Research Broker

Trusted Control Plane-side service that:

- receives a structured ResearchRequest from a Task/Agent;
- validates Project/Run scope;
- applies network and disclosure policy;
- enforces query/fetch/token/cost budgets;
- dispatches only registered research operations;
- persists accepted evidence through the Artifact service;
- never exposes provider credentials to a model or Community worker.

### Search Provider Adapter

Provider-neutral contract:

~~~text
search(
  query,
  freshness,
  locale,
  result_limit,
  provider_profile
) -> SearchResultSet
~~~

Initial provider profiles:

1. SearXNG — preferred self-hosted/private profile where deployed.
2. Brave Search — optional credentialed external provider through Secret Broker.
3. Additional providers only through the same contract and D12 admission process.

No search provider is required for Control Plane readiness.

### Restricted Fetcher

A dedicated low-authority CPU/network worker receives only a URL, bounded fetch policy and opaque request identity.

It never receives PostgreSQL credentials, GitHub credentials, RunPod lifecycle credentials, Secret Broker access, repository write access or unrelated Project state.

The parent service owns persistence.

### Reference Provider

Offline/local reference sources implement:

~~~text
retrieve(query, mode, limit) -> ReferenceResultSet
~~~

Reference evidence is distinct from fresh public-web evidence.

---

## 4. ResearchRequest v1

Recommended contract:

~~~json
{
  "schema_version": 1,
  "research_request_id": "uuid",
  "project_id": "uuid",
  "run_id": "uuid",
  "task_id": "uuid",
  "agent_instance_id": "uuid",
  "question": "bounded research question",
  "evidence_classes": ["REFERENCE", "FRESH"],
  "freshness": "stable",
  "preferred_domains": [],
  "forbidden_domains": [],
  "max_search_calls": 3,
  "max_fetches": 3,
  "max_sources": 6,
  "max_total_bytes": 6000000,
  "deadline_seconds": 60,
  "network_policy": "PUBLIC_READ"
}
~~~

These are upper bounds. Project policy may reduce them.

A model may propose a ResearchRequest. Trusted Reverend code validates and normalizes it before execution.

---

## 5. Query Planning

Query planning may use deterministic rules and/or a model, but:

- query length and count are bounded;
- freshness is explicit;
- domain constraints are explicit;
- query expansion cannot widen Project sensitivity or network authority;
- proposed search terms are data, not authorization;
- research cannot recursively create unbounded search.

Initial Cloud v1 default:

~~~text
small configurable search-call budget
small configurable fetch budget
recursive discovery depth = 0
~~~

Cloud v1 is not a general-purpose crawler.

---

## 6. Search Result Normalization

Provider-specific output is normalized into:

~~~text
SearchResult
├── rank
├── canonical_url
├── title
├── snippet
├── published_at?
├── provider
├── provider_query_id?
├── freshness_window
├── source_authority metadata
└── allowlisted provider metadata
~~~

Provider output is untrusted.

Credential rules:

- Brave credentials resolve only inside a trusted adapter through Secret Broker;
- SearXNG may be credentialless/private;
- credentials never enter SearchResult, Event payloads, model context or worker payloads;
- credential-bearing provider requests reject unexpected origin changes/redirects.

---

## 7. Restricted Fetch Security

D6 SSRF rules are mandatory.

Public fetch must:

- allow only approved schemes;
- reject embedded username/password;
- reject loopback/private/link-local/multicast/metadata-service ranges;
- resolve and validate DNS before connection;
- pin or verify the connected address;
- revalidate redirects;
- bound redirect count, compressed/decompressed bytes and wall time;
- reject unsupported content types;
- strip ambient credentials, cookies and proxy credentials;
- execute no JavaScript;
- reuse no browser session;
- submit no forms automatically;
- execute no downloaded content;
- keep active HTML/SVG outside Reverend's authenticated origin.

A local SearXNG adapter is separately configured. It is not an arbitrary model-controlled private URL exception.

---

## 8. Crawl and Robots Policy

Cloud v1 does not perform open-ended crawling.

Allowed acquisition origins are:

- explicit human URL;
- validated search result;
- configured reference source;
- bounded first-party follow-up selected by deterministic policy.

Automatic traversal beyond the fetched page is disabled by default.

Any future crawler must define, before production admission:

- site/robots policy for the acquisition class;
- per-host rate limits;
- maximum depth/pages;
- parent discovery lineage;
- D12 tool/recovery entry.

---

## 9. EvidenceSource/v1

Durable individual sources are immutable Artifacts, not rows in a new competing authority database.

Artifact type:

~~~text
EvidenceSource/v1
~~~

Recommended metadata:

~~~json
{
  "source_kind": "PUBLIC_WEB",
  "canonical_url": "https://example.org/page",
  "title": "Example",
  "retrieved_at": "timestamp",
  "published_at": null,
  "updated_at": null,
  "provider": "searxng",
  "search_rank": 2,
  "search_query_hash": "sha256:...",
  "freshness_window": "month",
  "trust_class": "UNTRUSTED_EXTERNAL",
  "sensitivity": "PUBLIC",
  "source_authority": "primary",
  "source_independence_key": "example.org",
  "transport": "fetched_page",
  "transport_confidence": 1.0,
  "extractor_version": 1,
  "content_hash": "sha256:...",
  "content_ref": "blob:sha256:...",
  "clipped": false,
  "parent_discovery_ref": "artifact:..."
}
~~~

The normal Artifact envelope owns Project/Run/producer provenance. Large content belongs in BlobStore.

---

## 10. Raw vs Extracted Content

The system distinguishes:

1. transport bytes — optionally retained only when policy/license/storage permits;
2. normalized evidence text — bounded representation used for retrieval/model context;
3. metadata/provenance — durable whenever the source contributes to accepted evidence.

If raw content is not retained, preserve canonical URL, content hash, extractor version, retrieval timestamp, normalized-text hash and transport metadata.

Reverend must not retain arbitrarily large web responses merely because they were fetched.

---

## 11. Search-Snippet Fallback

A snippet may be retained if page fetch fails and the snippet is material to research.

It must remain explicit:

~~~text
transport = search_snippet
transport_confidence < fetched_page
fetch_status = blocked | failed
~~~

A snippet never masquerades as a fetched primary document.

---

## 12. Deduplication and Versioning

Evidence is immutable.

Conceptual dedupe key:

~~~text
Project
+ canonical URL
+ normalized content hash
+ extractor version
~~~

If identical content is reacquired, Reverend may reuse the existing object while retaining the new discovery provenance.

If content changes:

- create a new EvidenceSource Artifact;
- preserve the old Artifact;
- link supersession/derivation where useful.

URL equality alone is not content equality.

---

## 13. Trust, Authority and Prompt Safety

Trust and source authority are separate dimensions.

Examples:

- an official vendor page may be primary authority while remaining UNTRUSTED_EXTERNAL for prompt/tool security;
- Project requirements are trusted Project state but not independent external evidence;
- generated synthesis is not evidence merely because a strong model produced it.

Existing deterministic research-quality logic should be retained and generalized.

Untrusted source text is placed below system/authority instructions and marked as data. Instructions found inside it gain no tool authority.

---

## 14. ResearchEvidencePack/v1

Research output links claims to evidence refs.

~~~text
ResearchEvidencePack/v1
├── question
├── claims[]
│   ├── statement
│   ├── support_type
│   ├── evidence_refs[]
│   ├── contradiction_refs[]
│   ├── confidence_label
│   └── temporal_scope?
├── unresolved_questions[]
├── source_refs[]
└── methodology/provenance
~~~

Rules:

- unsupported claims remain unsupported;
- conflicting sources remain explicit;
- source independence is recorded;
- current claims require suitable freshness;
- citations point to EvidenceSource Artifacts, not model prose.

---

## 15. Retrieval Architecture

Retrieval is demand-driven and authority-aware.

~~~text
durable source objects
      ├───────────────┐
      ▼               ▼
lexical candidates  semantic candidates
      │               │
      └───────┬───────┘
              ▼
      deterministic fusion
              ↓
 scope/trust/sensitivity gate
              ↓
   optional bounded rerank
              ↓
       Context Broker
~~~

### Lexical retrieval

Cloud v1 may use PostgreSQL FTS or another reconstructible lexical index.

It is never workflow authority.

### Semantic retrieval

Qdrant is an allowed derived semantic index.

- it can be rebuilt from authoritative Artifacts/Memory/repository intelligence;
- Qdrant loss does not lose Project truth;
- similarity cannot override scope/trust/sensitivity;
- embedding model/revision is recorded.

### Reranking

Preserve KnowledgeFabric principles:

- rerank only bounded candidates;
- do not bulk-embed an entire reference corpus by default;
- deterministic filters precede expensive ranking where possible.

---

## 16. Retrieval Source Classes

Keep distinct source classes:

~~~text
PROJECT_STATE
EXECUTION_STATE
ARTIFACT
EVIDENCE
MEMORY
REPOSITORY
REFERENCE
INTERACTION_HISTORY
DERIVED_INDEX
~~~

Do not replace these with a generic search-everything memory API.

Authorization and sensitivity gates run before similarity ranking.

---

## 17. Repository Research

Repository intelligence is not public-web research.

Code localization uses pinned Run repository state:

- repository map;
- symbols/references/call graph;
- relevant tests;
- Git state;
- base commit.

Public evidence about a dependency may complement this context but cannot replace the pinned repository state.

---

## 18. Evidence-to-Memory Promotion

Evidence and Memory stay separate:

~~~text
EvidenceSource
     ↓
ResearchEvidencePack
     ↓
MemoryProposal
     ↓
promotion validation
     ↓
MemoryRecord
~~~

Promotion validates evidence, scope, contradiction, sensitivity, expiry and supersession.

Deleting a derived index never deletes promoted Memory.

---

## 19. Freshness

Supported conceptual windows:

~~~text
stable
day
week
month
year
~~~

Provider semantics are normalized.

A current claim is rejected or downgraded when evidence lacks the required freshness provenance.

Retrieved-at time is not equivalent to published-at time.

---

## 20. Sensitivity and Provider Trust

Research output sensitivity is at least the strongest sensitivity of:

- input question/context;
- source content;
- Project disclosure policy.

External public evidence normally starts PUBLIC + UNTRUSTED_EXTERNAL.

Combining it with restricted Project data creates restricted derived output.

A query containing restricted Project material may be sent only to providers allowed by Project/ContextPolicy trust.

---

## 21. Caching

Allowed reconstructible caches:

- search-result cache;
- HTTP evidence cache;
- embedding cache;
- rerank cache.

Caches must not:

- cross Project/sensitivity boundaries;
- turn stale evidence into fresh evidence;
- suppress provenance;
- become the only copy of accepted evidence.

---

## 22. Cost and Budgets

Research may incur search-API, network/CPU, embedding/rerank and synthesis cost.

Paid calls follow D8:

- rate source identified;
- budget admission before call;
- attributable CostEvent;
- reconciliation where provider billing requires it.

Self-hosted/free search still emits operational metrics.

---

## 23. Failure Semantics

Typed examples:

~~~text
search_provider_unavailable
search_auth_failed
search_rate_limited
search_plan_unavailable
search_request_rejected
fetch_policy_rejected
fetch_timeout
fetch_too_large
unsupported_media_type
evidence_insufficient
freshness_insufficient
retrieval_index_unavailable
~~~

Missing evidence never silently becomes invented evidence.

If required evidence cannot be obtained, the Task explicitly proceeds with an allowed gap, requests input, replans/escalates or fails.

---

## 24. Recovery Semantics

Search/fetch/retrieval normally use:

~~~text
side_effect_class = PURE_READ or REPEATABLE_COMPUTE
resume_strategy = RESTART
~~~

Persisting an EvidenceSource Artifact is an idempotent authoritative write after acquisition.

Billable provider calls still need D8 cost idempotency even when logical research is safe to repeat.

---

## 25. Observability

Ordinary logs record metadata, not sensitive source bodies.

Metrics include:

- search calls/latency/result counts by provider;
- fetch attempts/success/failure/bytes;
- SSRF/policy rejections;
- accepted EvidenceSource count;
- snippet fallbacks;
- lexical/semantic candidate counts;
- retrieval/rerank latency;
- cache hits;
- evidence insufficiency;
- cost per Research Task.

Trace lineage:

~~~text
Run → Task → Agent → ResearchRequest
→ provider/fetch → EvidenceSource
→ ResearchEvidencePack → ContextManifest
~~~

---

## 26. Local-to-Cloud Migration

| Current component | Cloud disposition |
|---|---|
| research/search.py | KEEP provider-neutral query/config semantics; move credentials to Secret Broker |
| research/search_worker.py | KEEP/HARDEN restricted network worker |
| research/worker.py | KEEP/HARDEN fetch isolation and SSRF rules |
| research/service.py | ADAPT parent-owned provenance; replace public_sources SQLite with Artifact/BlobStore |
| research/quality.py | KEEP deterministic quality semantics |
| reference.py | KEEP as ReferenceProvider |
| retrieve.py | ADAPT lexical/dense fusion into Cloud Retrieval service |
| knowledge.py | KEEP bounded reranking/lazy embedding principles |
| engineering_memory.py | MIGRATE records to D1 MemoryRecord; future writes through promotion |
| qdrant_migrate.py | KEEP migration ideas; Qdrant remains derived |
| Workstation research endpoints | COMPATIBILITY only; Cloud clients use D2/Task runtime |

---

## 27. Acceptance Tests

C4/D10 must prove:

- search credentials never enter Agent/model context;
- unconfigured search fails explicitly;
- malicious URLs cannot reach private/link-local/metadata ranges;
- redirect/DNS rebinding cannot bypass fetch policy;
- search/fetch budgets cannot be exceeded by model recursion;
- active fetched content cannot execute;
- source authority does not grant execution trust;
- EvidenceSource preserves provenance/hash/freshness;
- identical content can dedupe without losing provenance;
- changed content creates a new immutable version;
- snippet fallback remains lower-confidence transport;
- semantic retrieval cannot cross Project/User scope;
- semantic retrieval cannot downgrade sensitivity;
- Qdrant/index loss is recoverable from durable sources;
- generated synthesis is not evidence without refs;
- current claims enforce freshness;
- paid search is budgeted/attributed;
- ResearchEvidencePack claims retain citations.

---

## 28. Exit Condition

D10 is satisfied when Development can implement research without inventing:

- where web/reference evidence is stored;
- how providers are selected;
- where credentials live;
- how fetching is isolated;
- whether Qdrant is authoritative;
- how evidence differs from Memory;
- how provenance/freshness survives;
- how retrieval is bounded;
- how failure is represented.

Cloud v1 therefore extends the accepted research path rather than replacing it with an unconstrained scraper or LLM-only web agent.


---

## 29. Relationship to D16 Research Fabric

D10 remains the foundational Cloud contract for research/retrieval/evidence semantics inherited from the accepted 0.4.0 system.

D16 is the server-era capability refinement and is authoritative where it adds:

- SourceRecord / SourceSnapshot lifecycle;
- provider-neutral SearchBroker / FetchBroker structure;
- Browser Worker escalation;
- query-disclosure policy;
- authenticated/private source partitions;
- browser subresource/network isolation;
- evidence-span validation;
- source-retention/cache boundaries;
- research-team sharding and cloud economics.

If D10 and D16 appear to overlap, apply:

~~~text
D10 foundational evidence/retrieval invariant
→ D16 capability/runtime/security refinement
→ D20 Context Broker decides when/how the evidence is consumed
~~~

Neither document turns search snippets, cached pages, embeddings or browser output into Project authority.
