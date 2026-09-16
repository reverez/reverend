# Research Quality RQ1 — Evidence Intelligence

**Branch:** `work/research-quality`  
**Baseline:** `072c418cd5371a25a29ad6282356e22b5ecc4d22`  
**Scope:** research/evidence quality only; no runtime, development-agent, GUI or model-selection redesign.

## Objective

RQ1 strengthens Reverend's existing M17 public-research path without replacing its accepted
security boundary. Search remains provider-neutral, public pages remain
`UNTRUSTED_EXTERNAL`, network use remains policy-gated, and restricted workers remain the
only acquisition path.

The optimization target is narrower:

> retrieve the right source for the claim, preserve what the source actually says, separate
> event dates from page/search dates, identify independent corroboration and conflicts, and
> abstain when a requested temporal claim is not directly supported.

## Baseline audit

The stabilized baseline was already strong on acquisition safety and provenance:

- explicit OFF / ASK / AUTO network policy;
- sandboxed provider search and HTTPS page acquisition;
- first-party domain preference for recognized vendors;
- coarse `primary / community / secondary / unknown` source classification;
- strict primary-source search-snippet fallback when page fetch is blocked;
- lexical relevance gating before answer context;
- freshness-window provenance for current claims;
- source-label citation integrity checks;
- hard cap of three surfaced public sources per discovery call.

The audit identified quality gaps above that layer:

1. authority was coarse and not typed by source kind;
2. source authority and transport confidence were not explicitly separated;
3. the pipeline did not represent claim-level direct/indirect/unsupported support;
4. source count could not establish organizational independence;
5. announcement, preview, rollout, API availability and broad availability were not separate
   temporal facets;
6. provider/search-result dates could occupy the same `published_at` field as fetched-page
   publication metadata;
7. no deterministic same-event contradiction detector existed;
8. confidence/abstention was evidence-set level rather than claim-facet level;
9. there was no adversarial benchmark dedicated to research quality;
10. page-fetch attempts after failures were bounded only by the finite search-result set, not
    by an explicit research-quality budget.

## RQ1 architecture

RQ1 adds `reverend.research.quality` above the canonical search/fetch path.

### Query decomposition

Temporal/release queries are decomposed into at most four deterministic facets. Supported
event semantics include:

- announcement;
- research preview;
- initial rollout;
- limited access;
- API availability;
- ChatGPT availability;
- broad availability;
- general availability;
- release.

Multi-entity comparisons for recognized vendors or quoted entities receive separate subject
facets so two organizations' different release dates are not misclassified as a conflict.

Exact event dates are required only when the request is date-seeking (for example, “when” or
“release dates”). A request such as “Which version was released in the last 30 days?” can be
directly supported by event text without inventing an exact calendar date.

### Authority model

Legacy compatibility fields remain intact, but public evidence can additionally carry a typed
authority kind:

- official documentation;
- official announcement;
- official developer/API documentation;
- official release notes;
- official safety/model card;
- government/regulator;
- standards body;
- peer-reviewed publication;
- preprint;
- official dataset;
- reputable independent reporting;
- specialist technical reporting;
- community;
- aggregator;
- unknown.

Authority is query-relative. A vendor's own page remains primary for its release date but is
down-weighted as self-asserted evidence for comparative claims such as “best model”.

### Claim support and transport

Each accepted source can carry:

- claim facet ID and event;
- direct / corroborating / indirect / contradicting / unsupported support type;
- event date;
- page publication date;
- page update date;
- search-result date;
- retrieval date;
- authority type and claim-authority fit;
- source-independence key;
- transport type and confidence;
- bounded rationale.

`search_snippet` remains a strict primary-source fallback, but it is represented at lower
transport confidence than a fetched page. Snippet-only primary evidence can be reported; it
cannot be labelled as fetched-primary confirmation.

### Corroboration and contradiction

Corroboration counts independent organizational domains, not URLs or subdomains. For example,
`openai.com` and `help.openai.com` are one organization for corroboration purposes.

A contradiction exists only when direct evidence for the **same subject + same event facet**
states different explicit event dates. Announcement versus later broad availability is not a
conflict.

### Confidence and abstention

Deterministic evidence outcomes are:

- `confirmed_by_primary_source`;
- `strongly_supported`;
- `corroborated`;
- `reported`;
- `conflicting_evidence`;
- `insufficient_evidence`.

Research mode hard-abstains before generation when a requested date/event facet is unsupported.
Conflicting evidence remains available to synthesis with an explicit warning so Reverend can
explain the disagreement instead of silently selecting one date.

## Network and acquisition budgets

One `PublicResearch.discover` call now exposes explicit hard budgets:

| Budget | RQ1 limit |
| --- | ---: |
| logical search calls | 3 |
| page-fetch attempts | 3 |
| surfaced sources | 3 |
| claim follow-up searches | at most 1 missing facet per discovery call |

The normal strategy remains authority-first search (when a first-party domain is known) plus
the general query. A third search is allowed only for one missing temporal facet. This is a
quality improvement within a fixed cap, not open-ended recursive browsing.

## Temporal provenance

RQ1 separates:

- `published_at` — fetched page publication metadata;
- `updated_at` — fetched page modification metadata;
- `search_result_date` — date supplied by the search result/provider;
- `created_at` / `retrieved_at` — Reverend acquisition time;
- claim `event_date` — an explicit date in source text tied to the requested event.

An event date is never inferred from page publication/update metadata alone. Candidate dates
must also be valid Gregorian calendar dates within the accepted year bounds; impossible dates
such as non-leap-year February 29 or month/day overflow are discarded before support/conflict
evaluation.

## ResearchBench-RQ1

Run:

```bash
python -m reverend.benchmarks.research_quality
```

The fixture-backed adversarial catalog contains 14 categories:

A. primary source vs low-authority aggregator  
B. conflicting dates for the same event  
C. announcement date vs broad-availability date  
D. first-party page blocked from direct fetch  
E. community subdomain demotion  
F. independent corroboration vs same-organization duplicates  
G. event date vs publication/update/search-result dates  
H. unsupported requested claim  
I. search-snippet-only primary evidence  
J. no adequate evidence  
K. multi-entity comparison  
L. peer-reviewed vs preprint source typing  
M. real-calendar date validation, including leap-day handling  
N. scholarly article specificity vs publisher news/landing pages

The catalog includes the GPT-6 Astra shaped hard query from the workstream specification. All
fixtures are synthetic and deterministic; benchmark success does **not** assert that GPT-6
Astra or any fixture claim exists in the real world.

## Before / after metrics

| Quality dimension | Stabilized baseline | RQ1 |
| --- | --- | --- |
| adversarial research-quality catalog | absent | 14 deterministic categories |
| public authority representation | 4 coarse compatibility classes | 15 typed kinds plus compatibility fields |
| claim support representation | absent | 5 support types |
| temporal event semantics | generic freshness/relevance | 9 event kinds + general |
| independent corroboration | absent | registered-domain/authority-domain key |
| contradiction resolution | model-dependent | deterministic same-facet date conflict |
| evidence confidence labels | implicit evidence gate | 6 explicit outcomes |
| page/search temporal fields | search/page dates could share `published_at` | publication, update, search-result and retrieval separated |
| logical search-call hard cap per discovery | no explicit research-quality constant | 3 |
| page-fetch-attempt hard cap per discovery | finite result set only | 3 |
| unsupported explicit temporal claim | could reach generation if source was generally relevant | pre-generation abstention |

## Invariants preserved

RQ1 does not weaken:

- local-only inference;
- explicit network policy;
- public content as untrusted data;
- bubblewrap/seccomp worker isolation;
- HTTPS/SSRF restrictions;
- credential handling;
- current freshness-window provenance;
- primary-only snippet fallback;
- bounded context and model budgets;
- no automatic merge or release.

## Known limitations / follow-up

- authority typing is deterministic and intentionally conservative; it is not a universal
  source-reputation database, and peer review is claimed only when a scholarly publisher page
  has article/publication-specific URL or title evidence rather than publisher-domain membership alone;
- organizational independence is approximated by registered/authority domain and does not
  detect syndication, common ownership, or copied reporting;
- claim support is intentionally strongest for event/date questions; general semantic
  entailment remains bounded lexical assessment plus model synthesis;
- HTML date extraction depends on common metadata keys and cannot recover dates hidden behind
  client-side rendering;
- snippet fallback remains lower-confidence discovery evidence and should not be presented as
  full-page verification;
- live-provider quality still requires real-machine smoke after portable CI.

## Validation

The workstream must pass, at minimum:

```bash
python -m pytest -q tests/test_research_quality.py tests/test_benchmark_research_quality.py
python -m pytest -q tests/test_public_research.py tests/test_intelligence_evidence.py tests/test_cli_research.py tests/test_workstation.py
python -m reverend.benchmarks.research_quality
python -m pytest -q
```

Pull-request CI also runs compile checks, targeted tests, the full unit suite, release smoke,
M16/M17/M18 portable contracts and final portable validation.

A separate live search smoke is still required before integration because this branch changes
research acquisition and Workstation research behavior.


## Milestone tracking

| Stage | Status | Evidence / note |
| --- | --- | --- |
| RQ1 — Audit current research/evidence pipeline | complete | canonical search, fetch, persistence, evidence gate, Workstation, CLI, docs and stabilization history audited |
| RQ2 — Establish adversarial baseline benchmark | complete | baseline contracts recorded; ResearchBench-RQ1 fixture rubric established without asserting fixture facts are real |
| RQ3 — Formalize authority + support semantics | complete | typed query-relative authority, support, transport and confidence semantics implemented |
| RQ4 — Implement claim-level evidence foundations | complete | bounded query facets and per-source claim-support records added |
| RQ5 — Improve temporal/conflict handling | complete | event/publication/update/search/retrieval dates separated; same-facet conflict handling added |
| RQ6 — Improve bounded query decomposition/corroboration | complete | max-four facets, one missing-facet follow-up, organization-level independence and fixed network caps |
| RQ7 — Improve confidence/abstention behavior | complete | deterministic confidence outcomes plus pre-generation abstention for unsupported explicit temporal claims |
| RQ8 — Expand ResearchBench | complete | 12 adversarial fixture categories plus focused regressions |
| RQ9 — Live smoke + regression validation | partial | portable CI/benchmarks exercised; branch-specific live provider smoke remains coordinator/real-machine work |
| RQ10 — Integration handoff | ready after final portable CI | branch is merged from current main, not merged into main; PR remains review-only |

## Decision records

### Authority hierarchy

**DECISION**  
Keep the legacy `primary / community / secondary / unknown` compatibility surface and add a
query-relative typed authority model above it.

**RATIONALE**  
Existing callers and tests rely on the compatibility fields, while research-quality decisions
need to distinguish official announcements, developer docs, release notes, safety/model cards,
government/standards, academic sources, independent reporting, community and aggregators.

**ALTERNATIVES**  
Replace the old authority contract; maintain a large domain reputation database; delegate
authority classification to an LLM.

**MEASURED EVIDENCE**  
The adversarial catalog exercises primary-vs-aggregator, community demotion and academic source
typing. Typed research authority is also a deterministic evidence-ranking key.

**COMPATIBILITY IMPACT**  
Existing first-party authority fields and the strict snippet-fallback contract remain available.

**RISKS**  
Deterministic typing is conservative and cannot encode every publisher or ownership relationship.

### Claim support types

**DECISION**  
Represent support as a small enum: direct, corroborating, indirect, contradicting, unsupported.

**RATIONALE**  
Source-level acceptance cannot show which part of a multi-claim question a source actually
supports.

**ALTERNATIVES**  
A full claim graph; unrestricted model entailment judgments; source-level relevance only.

**MEASURED EVIDENCE**  
ResearchBench covers unsupported claims, same-event contradictions, announcement-vs-availability
separation and snippet-only support.

**COMPATIBILITY IMPACT**  
The existing evidence gate still decides whether a row is eligible; claim support is additional
metadata used for quality/confidence decisions.

**RISKS**  
General semantic entailment remains intentionally bounded; temporal/event claims receive the
strongest deterministic treatment.

### Confidence semantics

**DECISION**  
Use deterministic evidence-set outcomes:
`confirmed_by_primary_source`, `strongly_supported`, `corroborated`, `reported`,
`conflicting_evidence`, `insufficient_evidence`.

**RATIONALE**  
A model should not invent certainty independently of provenance, authority and transport.

**ALTERNATIVES**  
A single numeric confidence score; free-form LLM certainty language.

**MEASURED EVIDENCE**  
Fixture cases verify primary fetched confirmation, snippet downgrade, corroboration, conflict and
insufficient-evidence outcomes.

**COMPATIBILITY IMPACT**  
No existing model role, scheduler or network-policy contract changes.

**RISKS**  
These labels describe evidence support, not the metaphysical probability that a claim is true.

### Corroboration requirements

**DECISION**  
Count organization-level independence keys, not URLs or subdomains; known related first-party
domains can map to one organization key.

**RATIONALE**  
Two pages from one organization are not two independent confirmations.

**ALTERNATIVES**  
Raw source count; a costly publisher/syndication graph crawler.

**MEASURED EVIDENCE**  
Fixtures verify that `openai.com` and `help.openai.com` count once and that known Google /
DeepMind first-party domains do not fake independence.

**COMPATIBILITY IMPACT**  
No additional network request is required to estimate independence.

**RISKS**  
Domain ownership, syndication and copied reporting can still evade this approximation.

### Query budget

**DECISION**  
Bound one discovery operation to at most three logical search calls, three page-fetch attempts,
three surfaced sources, at most four claim facets and at most one missing-facet follow-up.

**RATIONALE**  
Query decomposition is useful only if it does not become an uncontrolled browsing loop.

**ALTERNATIVES**  
Recursive research agents; always issuing four or more search variants; no follow-up query.

**MEASURED EVIDENCE**  
Unit regressions assert the search/fetch hard caps and missing-facet behavior.

**COMPATIBILITY IMPACT**  
Authority-first + general search remain the normal path; the third search is optional.

**RISKS**  
A difficult query may need more breadth than this branch permits; the system should expose
insufficiency rather than silently exceed the budget.

### Contradiction policy

**DECISION**  
Treat different explicit dates as a contradiction only within the same subject + lifecycle-event
facet. Distinct events such as announcement and broad availability are not conflicts.

**RATIONALE**  
Release research commonly contains multiple legitimate dates for different lifecycle events.

**ALTERNATIVES**  
Pick the highest-ranked date; treat every differing date as conflict; let synthesis reconcile
without structured evidence.

**MEASURED EVIDENCE**  
ResearchBench separately tests same-event conflict, announcement-vs-availability and multi-entity
release comparisons. Event-date extraction uses local event zones to prevent one lifecycle date
from leaking into a neighboring event.

**COMPATIBILITY IMPACT**  
Conflicting evidence remains visible to synthesis instead of forcing a fabricated resolution.

**RISKS**  
Complex prose can still express temporal relations that a deterministic event parser cannot fully
recover.

### Abstention policy

**DECISION**  
Hard-abstain before model generation when an explicitly date-seeking research request has a
required temporal facet with no direct support; do not require an exact calendar date when the
user only asks which event/version occurred within a freshness window.

**RATIONALE**  
This prevents model memory from filling unsupported researched facts while preserving useful
current-event answers that do not ask for an exact date.

**ALTERNATIVES**  
Always generate with a warning; abstain for every indirect source; require dates for all release
queries.

**MEASURED EVIDENCE**  
Workstation regressions cover both the current-release non-date case and the missing broad-
availability-date abstention case.

**COMPATIBILITY IMPACT**  
Existing missing-evidence/freshness abstention remains intact; this adds a narrower claim-support
gate.

**RISKS**  
A source can directly support a date using wording outside the bounded event vocabulary and be
treated conservatively as insufficient.


### Calendar validity hardening

**DECISION**  
Normalize candidate event dates through the standard Gregorian calendar implementation before
they can become claim evidence.

**RATIONALE**  
ISO-shaped strings and named-month dates are syntax, not proof that the calendar date exists.
Impossible dates must never influence support, contradiction or confidence.

**ALTERNATIVES**  
Keep regex-only validation; manually encode month lengths/leap-year rules.

**MEASURED EVIDENCE**  
Research regressions and ResearchBench case M accept 2024-02-29 / February 29, 2024 and reject
2026-02-29, February 31, 2026 and 2026-99-99.

**COMPATIBILITY IMPACT**  
The existing 1900–2200 year bound is preserved; only impossible calendar values are removed.

**RISKS**  
The parser still intentionally supports a bounded set of date formats rather than natural-language
relative dates.

### Peer-review specificity hardening

**DECISION**  
Publisher-domain membership alone is insufficient for `peer_reviewed_publication`. Require
article/publication-specific URL structure or explicit scholarly page-title evidence.

**RATIONALE**  
Nature, Science, ACM, IEEE, Springer and similar domains also host news, organization pages,
landing pages and other non-peer-reviewed content.

**ALTERNATIVES**  
Trust the publisher domain; use a remote bibliographic database lookup for every source.

**MEASURED EVIDENCE**  
Positive fixtures cover Nature article, Science DOI, ACM DOI, IEEE document, ScienceDirect
article and Springer article pages. Negative fixtures cover publisher news/home/about pages.
ResearchBench case N verifies the distinction.

**COMPATIBILITY IMPACT**  
Positive scholarly article fixtures remain peer-reviewed; ambiguous publisher pages now fall
back to lower-certainty authority instead of claiming peer review.

**RISKS**  
Unusual but genuine scholarly URL structures can be conservatively under-classified until a
supported page-level pattern is added.
