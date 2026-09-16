# D16 — Research Fabric & Web Context Acquisition

> **Status:** DESIGN ACCEPTED FOR DEVELOPMENT  
> **Research snapshot:** 2026-09-16  
> **Depends on:** A5, A8, A12, D3, D6, D15  
> **Purpose:** Turn the accepted local SearXNG/Brave + restricted-fetch research path into a persistent, provenance-preserving, cloud-capable Research Fabric.

---

## 1. Design Goal

Reverend must answer two questions separately:

~~~text
What does this Project already know?
~~~

and:

~~~text
What new external evidence must be acquired?
~~~

External research is therefore an on-demand acquisition layer, not the default source for every question.

Canonical flow:

~~~text
ResearchRequest
      ↓
Research Coordinator
      ↓
existing Project Evidence sufficient/fresh?
 ┌────┴────┐
 yes       no
 │          │
 │      Search Broker
 │          ↓
 │      candidate sources
 │          ↓
 │      Fetch Broker
 │       ├── structured provider
 │       ├── HTTP fetch
 │       ├── PDF/document fetch
 │       └── Browser fetch
 │          ↓
 │      SourceSnapshot
 │          ↓
 │      Evidence extraction/validation
 │          ↓
 └──────→ ResearchEvidencePack
              ↓
        Context Broker / Agent
~~~

---

## 2. Existing Implementation to Preserve

Current reverend.research already proves:

- Brave and SearXNG provider configuration;
- bounded query length/result counts;
- explicit network opt-in;
- bubblewrap-isolated search/fetch/image workers;
- URL validation;
- source authority/freshness metadata;
- deterministic evidence gating;
- accepted M17/M18 live search/fetch/image behavior.

Cloud implementation must preserve these controls.

Modernization is primarily:

~~~text
single local research service
→ provider-neutral persistent Research Fabric
~~~

---

## 3. Research Components

~~~text
ResearchCoordinator
├── SearchBroker
│   ├── SearXNGProvider
│   ├── BraveProvider (optional)
│   ├── GitHubProvider
│   ├── HuggingFaceProvider
│   ├── AcademicProvider adapters
│   └── future domain providers
│
├── FetchBroker
│   ├── StructuredAPIFetcher
│   ├── RestrictedHTTPFetcher
│   ├── Document/PDF Extractor
│   └── BrowserFetcher
│
├── SourceRegistry
├── SourceCache
├── EvidenceExtractor
├── EvidenceValidator
└── ResearchSynthesizer
~~~

Search discovers candidate locations.

Fetch obtains source content.

Evidence extraction identifies bounded claims/passages.

Synthesis is cognitive and cannot upgrade source authority by itself.

---

## 4. SearchProvider Contract

~~~text
SearchProvider
├── provider_id
├── capabilities
├── search(query, filters, limit)
├── health()
└── rate_metadata()
~~~

Normalized SearchResult:

~~~text
SearchResult
├── canonical_url
├── title
├── snippet
├── provider
├── rank
├── published_at?
├── updated_at?
├── result_metadata
└── provider_provenance
~~~

A search snippet is discovery evidence, not normally sufficient factual authority.

SearXNG remains the preferred self-hostable general search seam because its Search API can return structured results while preserving provider abstraction.

---

## 5. Structured Providers Before Scraping

For important systems, prefer stable structured APIs when they are superior to rendered HTML.

Examples:

~~~text
GitHub
Hugging Face
package registries
Crossref/OpenAlex/arXiv-style scholarly metadata
cloud-provider inventory/pricing
documentation indexes
~~~

Provider adapters return source provenance just like web pages.

Do not scrape a rendered webpage merely because a browser can do so when a stable structured API exists.

---

## 6. RestrictedHTTPFetcher

Static pages use the cheapest safe path first.

Pipeline:

~~~text
canonical URL
↓
URL policy / SSRF validation
↓
DNS resolution + connected-address validation
↓
HTTP request with bounded redirect policy
↓
content-type / byte-limit validation
↓
HTML/document parser
↓
boilerplate removal
↓
main content + metadata
↓
content hash
↓
SourceSnapshot
~~~

Required controls:

- HTTPS preferred;
- approved schemes only;
- private/link-local/metadata endpoints denied;
- redirects revalidated;
- response bytes/time bounded;
- decompression bombs bounded;
- no ambient cookies/credentials;
- content parsed as untrusted data;
- canonicalization reduces duplicate source identities where possible.

Existing bubblewrap/worker isolation remains a valid implementation pattern.

---

## 7. BrowserFetcher

Use browser automation only when static/structured acquisition is insufficient.

Examples:

- client-rendered documentation;
- interactive public dashboards;
- JavaScript-loaded tables;
- frontend verification.

Cloud v1 Browser Worker baseline:

~~~text
Playwright
Chromium first
ephemeral browser profile
task-scoped download directory
no normal Reverend cookies
no Secret Broker access
restricted network policy
bounded tabs/time/download bytes
DOM/text extraction
screenshot
console/network observation where policy permits
~~~

The browser worker is disposable and non-authoritative.

Firefox/WebKit support is optional capability expansion, not a v1 correctness dependency.

---

## 8. Browser Research vs Frontend Test Modes

The same worker implementation may support two separate policies.

### RESEARCH_BROWSER

~~~text
network:
  public approved web only

credentials:
  none by default

outputs:
  SourceSnapshot
  screenshot Artifact
  browser metadata
~~~

### FRONTEND_TEST_BROWSER

~~~text
network:
  target test application + explicitly required dependencies

credentials:
  test-only ephemeral identities

outputs:
  BrowserTestReport
  screenshot/video/trace Artifacts
  console/network diagnostics
~~~

Never reuse a logged-in research browser profile for frontend testing.

---

## 9. SourceRecord and SourceSnapshot

### SourceRecord

Stable logical source:

~~~text
source_id
canonical locator
source type
publisher/domain
provider metadata
authority class
default freshness policy
created_at
~~~

### SourceSnapshot

One fetched version:

~~~text
snapshot_id
source_id
fetched_at
published_at?
updated_at?
content_hash
content_ref
media_type
byte_count
HTTP/provider metadata
trust_class = UNTRUSTED_EXTERNAL unless explicitly stronger
sensitivity
extraction_version
~~~

Evidence cites a snapshot, not merely a URL.

This makes source change representable.

---

## 10. Source Cache

SourceCache is an optimization around SourceSnapshots.

Lookup identity may include:

~~~text
canonical source
provider
representation
language
content-negotiation profile
~~~

Validation uses available evidence:

- ETag;
- Last-Modified;
- provider revision;
- immutable content ID;
- freshness policy.

A retained EvidencePack promotes required source content into durable BlobStore retention instead of leaving it only in disposable cache.

---

## 11. Freshness Policy

Conceptual classes:

~~~text
IMMUTABLE
VERSION_SCOPED
SLOW
NORMAL
FAST
LIVE
~~~

Examples:

~~~text
paper with DOI/revision       VERSION_SCOPED
language specification        VERSION_SCOPED
stable library docs           SLOW/NORMAL
model/runtime compatibility   FAST
provider pricing              FAST/LIVE
GitHub issue/PR state         LIVE
service status                LIVE
~~~

Exact TTL is configuration.

TTL never proves truth; it determines whether Reverend should refresh before relying on a source for a freshness-sensitive Task.

---

## 12. EvidenceClaim

Research Agents should exchange evidence, not browser transcripts.

~~~text
EvidenceClaim
├── claim_id
├── normalized claim / observation
├── source_snapshot_id
├── source locator/span
├── bounded direct quote?
├── evidence_type
├── source authority
├── confidence
├── freshness state
├── extracted_by
└── validation state
~~~

Generated synthesis cannot cite itself as source evidence.

---

## 13. ResearchEvidencePack

~~~text
ResearchEvidencePack
├── research objective
├── search queries
├── source coverage
├── accepted EvidenceClaims
├── contradictory EvidenceClaims
├── unresolved questions
├── freshness summary
├── acquisition failures
├── budget usage
└── source snapshot refs
~~~

Architecture/Product/Model-selection Agents consume this Artifact.

---

## 14. Research Team Strategy

Useful research swarms partition evidence space.

Good:

~~~text
Research Lead
├── Official Source shard
├── Academic shard
├── GitHub/ecosystem shard
├── Benchmark shard
├── Deployment/economics shard
└── Adversarial/counterevidence shard
            ↓
        synthesis
~~~

Bad:

~~~text
5 Agents all search the same generic query
~~~

Team expansion follows minimum-sufficient-team economics.

---

## 15. Query Planning

ResearchPlan:

~~~text
objective
known evidence refs
missing facets
queries
provider strategy
freshness requirement
max sources
max browser pages
max bytes
max wall time
max model calls
max monetary cost
completion/coverage criteria
~~~

The planner cannot turn network OFF/ASK into AUTO.

---

## 16. Acquisition Escalation Ladder

~~~text
existing fresh Evidence
↓ insufficient
structured provider/API
↓ unavailable/insufficient
general search
↓
restricted static fetch
↓ acquisition insufficient
browser fetch
↓
report inaccessible/insufficient evidence
~~~

Browser is intentionally late because it is slower, more expensive and a larger attack surface.

---

## 17. Prompt-Injection Boundary

Every external source is untrusted content.

Source content cannot:

- request Secrets;
- alter ToolPolicy;
- change system instructions;
- authorize network expansion;
- spawn Agents;
- override citation/evidence rules.

Research Agent may reason about malicious text but does not grant it authority.

---

## 18. Crawling / Compliance Policy

Reverend is not a general-purpose indiscriminate crawler.

Default policy:

- acquire pages needed for an explicit Project/Task;
- prefer documented APIs;
- honor authenticated-site and licensing restrictions;
- respect configured provider/site rate limits and terms;
- no CAPTCHA bypass;
- no anti-bot evasion;
- no login credential reuse unless a dedicated approved connector exists;
- cache/reuse results to reduce repeated traffic.

---

## 19. PDF and Document Acquisition

Pipeline:

~~~text
download
→ media/magic verification
→ size/page limits
→ parser in isolated worker
→ text/structure extraction
→ SourceSnapshot + BlobRef
~~~

Native text/structure is preferred to OCR.

Malformed parser input must not run in the Control Plane process.

---

## 20. Storage

Authoritative structured metadata:

~~~text
PostgreSQL
~~~

Durable retained content:

~~~text
BlobStore
~~~

Derived retrieval:

~~~text
Qdrant / lexical index
~~~

Disposable:

~~~text
browser cache
temporary downloads
raw search-result cache
transient parser state
~~~

---

## 21. Research Observability

Record:

- ResearchRequest/Team/Task;
- queries;
- provider;
- candidate sources;
- fetch attempts;
- browser escalations;
- bytes;
- cache hit/miss;
- freshness refresh;
- accepted/rejected evidence;
- failures;
- wall time;
- model calls;
- cost.

Do not record unrestricted source content in operational logs.

---

## 22. Research Economics

Research has a delegated budget covering:

~~~text
search calls
source fetches
browser pages
download bytes
model synthesis calls
wall time
paid API cost
~~~

Independent network/CPU operations may overlap while expensive model synthesis is serialized.

---

## 23. Failure Modes

### Search provider unavailable

Use another configured eligible provider if policy permits; otherwise structured failure.

### Source changed

Create a new SourceSnapshot; retain historical snapshot when referenced.

### Restricted fetch blocked

Escalate to browser only if policy/budget permits.

### CAPTCHA/challenge

Do not bypass; seek alternate evidence.

### Conflicting sources

Retain both and resolve by evidence quality/deterministic data/adjudication.

### Insufficient evidence

Return explicit insufficient-evidence result.

---

## 24. Development Mapping

### C0

Contracts:

~~~text
ResearchRequest
SearchProvider
SearchResult
SourceRecord
SourceSnapshot
EvidenceClaim
ResearchEvidencePack
FetchPolicy
~~~

### C1

PostgreSQL/Blob persistence.

### C4

Research Coordinator, provider registry and Context Broker integration.

### C5

network policy, SSRF, browser trust, credential isolation.

### C7

remote Browser Worker.

### C8

research cache/cost/telemetry.

---

## 25. Acceptance Tests

Must prove:

- fresh existing Evidence avoids unnecessary network;
- search snippet is not silently promoted to page evidence;
- static fetch precedes browser escalation;
- browser worker has no Secret Broker/DB credentials;
- redirect/DNS policy blocks private/metadata networks;
- changed source creates new snapshot;
- retained EvidencePack resolves historical snapshot;
- freshness-sensitive Task refreshes stale source;
- Project A research cannot enter Project B context through similarity;
- research Team partitions source space;
- prompt injection cannot alter ToolPolicy;
- no-evidence path abstains explicitly.

---

## 26. Technology Evidence

The 2026-09-16 technology review confirms:

- SearXNG exposes an HTTP Search API with structured formats;
- Playwright supports automated Chromium, Firefox and WebKit browser control.

These validate the adapter design without making Reverend permanently dependent on either implementation.

---

## 27. Exit Condition

Research Fabric is ready when an Agent can reuse fresh Project evidence, acquire missing evidence through bounded search/static/browser/provider paths, retain source snapshots with provenance, synthesize a typed EvidencePack and feed only authorized evidence into Context Broker.


---

## 28. Recursive Capability Audit — Query Disclosure, Browser SSRF & Cache Scope

The first modernization review identified a major confidentiality risk: even when fetched pages are public, a **search query itself may disclose private Project information**.

### QueryDisclosurePolicy

Before a query leaves the trusted Project domain:

~~~text
planned query
↓
classify source ContextItems and sensitivity
↓
QueryDisclosurePolicy
├── PUBLIC / permitted PROJECT_PRIVATE abstraction
│     → eligible external search
└── RESTRICTED / secret-adjacent / raw proprietary code
      → do not transmit externally
      → generalize locally, use internal knowledge, or require explicit human policy
~~~

Rules:

- never include raw secrets/tokens in external queries;
- never include large raw proprietary code slices in search queries;
- Project identifiers/codenames marked restricted are removed/generalized;
- the exact outbound query is stored as bounded research provenance;
- query sanitization is deterministic/policy-mediated, not trusted solely to an LLM;
- if sanitization removes information essential to the search, block/escalate rather than leak it.

A self-hosted SearXNG frontend still forwards queries to configured engines; it is therefore not automatically a confidentiality boundary for the query.

### Browser request isolation applies to every subresource

Browser SSRF controls apply not only to top-level navigation but also:

- redirects;
- frames;
- scripts/styles/images/fonts;
- fetch/XHR;
- WebSockets;
- service workers;
- downloads;
- DNS rebinding.

Block:

~~~text
file:
localhost / loopback
private address ranges
link-local
cloud metadata endpoints
Control Plane private services
Secret Broker/PostgreSQL/internal worker endpoints
~~~

unless a dedicated FRONTEND_TEST_BROWSER policy explicitly allowlists a test target.

### Browser filesystem boundary

RESEARCH_BROWSER receives no arbitrary host/workspace filesystem mount.

Uploads/file chooser are denied unless a specific test capability supplies an allowlisted Artifact.

### Source-cache partition

A SourceRecord/SourceSnapshot cache key includes an access partition.

For public anonymous material:

~~~text
access_partition = PUBLIC
~~~

For authenticated/private future providers:

~~~text
access_partition = PROJECT:<project_id>:<credential-scope-version>
~~~

Content fetched under one private credential scope may not be reused in another Project merely because canonical URL matches.

### Retention / GC

SourceSnapshot retention:

- referenced by retained EvidenceClaim/EvidencePack → durable root;
- referenced by accepted Decision/Requirement provenance → durable root;
- unreferenced cache snapshots → TTL/size-based GC allowed;
- deletion must not break retained evidence lineage.

Research cache growth is bounded independently from durable evidence storage.


---

## 29. Recursive Capability Audit — Network Enforcement Layer

Application-level URL validation and Playwright request interception are not sufficient as the sole browser/fetch isolation mechanism.

RESEARCH_BROWSER and untrusted document/fetch workers require an OS/network boundary such as:

- isolated network namespace plus controlled egress;
- explicit egress proxy with destination policy;
- firewall/nftables equivalent;
- provider network policy where enforceable.

Application interception remains useful for provenance and early rejection, but network policy must fail closed if a page/script attempts to bypass browser hooks.

Document parsers run with network disabled.

Frontend test browser uses a different allowlist limited to the ephemeral test target and explicitly required resources.


---

## 30. Recursive Capability Audit — Authenticated Sources, Artifacts & Retention

### Authenticated/private research providers

A future GitHub/Hugging Face/enterprise source adapter may access non-public material, but private access is a separate capability from public research.

Requirements:

~~~text
provider mode = PUBLIC or AUTHENTICATED_PROJECT
credential scope explicitly configured
Project/user authorization checked
SourceRecord access_partition non-PUBLIC
outbound target pinned to provider
retrieved material inherits Project/private sensitivity
~~~

Research Fabric must never borrow the immutable Run owner's GitHub credential merely because it exists.

A private repository is normally understood through Repository Intelligence after an authorized clone. Using a personal GitHub API credential for additional private research requires an explicit provider capability/policy.

### Browser/download Artifacts

Screenshots, traces, HAR-like data, DOM snapshots and downloads inherit sensitivity from:

- Project/TestEndpoint;
- page/source access partition;
- input credentials;
- captured content.

Browser outputs are **not public merely because the browser technology is generic**.

Before retention:

- cap size/duration;
- remove known credential/header/cookie fields from traces;
- validate downloaded media/file type;
- store retained outputs as sensitivity-labelled Artifacts;
- keep temporary browser profile/download state disposable.

### Source retention and licensing

SourceSnapshot metadata/provenance may be retained independently from full content.

Full source bytes/text retention follows:

- evidence/reproducibility need;
- source/provider licensing/terms;
- configured retention policy;
- minimum necessary excerpt/snapshot strategy when indefinite full-copy retention is inappropriate.

Reverend does not use the Source Cache as an unbounded mirror of the web.


---

## 31. Recursive Capability Audit — Credentialed Search, Rate Control & Evidence Validation

### Credential-bearing SearchProviders

A paid/credentialed SearchProvider is a trusted adapter operation.

Its API key is resolved by Secret Broker / credential-execution boundary and is never:

- placed in an Agent prompt;
- persisted in ResearchPlan;
- sent to a generic Browser Worker;
- returned in provider error/log output.

Uncredentialed self-hosted SearXNG may be invoked through the restricted research path, but a credentialed provider request remains origin-pinned like other Secret-bearing adapters.

### Research API economics

Paid search/provider calls emit attributable external-service usage/cost events under the requesting Run/Task.

Research budget admission occurs before the paid request.

Rate-limit metadata/backoff is provider-specific but bounded and observable.

### Per-origin concurrency

Fetch Broker applies per-provider/per-origin request concurrency and rate policy.

A Research Team may fan out across independent sources, but cannot create an accidental denial-of-service burst against one domain.

### Published/updated metadata is evidence, not authority

Dates extracted from HTML/search snippets are source-provided metadata and may be wrong.

Reverend records how the date was obtained:

~~~text
provider_metadata
document_metadata
HTTP metadata
inferred/unknown
~~~

Freshness-sensitive claims rely on corroborated source/version identity where required rather than trusting an arbitrary page date string.

### EvidenceClaim structural validation

When an EvidenceClaim references a direct quote/span:

- the referenced snapshot must exist;
- the locator must resolve inside that exact snapshot;
- quoted text must be present after the declared extraction normalization;
- extractor/model may not invent quotation text;
- validation records extractor/version.

This validates source membership/provenance, not semantic entailment.

A model-generated claim remains generated analysis even when attached to a valid source span until the consuming workflow applies its evidence/verification policy.
