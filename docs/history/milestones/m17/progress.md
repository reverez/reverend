# M17 — Fresh Web Evidence & Frontier Detection

**Status:** LIVE ACCEPTED

## M17.1a — sandboxed search-provider foundation

Implemented provider-neutral bounded search configuration with:

- **self-hosted SearXNG JSON search as the canonical free/local-first backend**;
- Brave Search retained only as an optional adapter.

Security and trust invariants:

- no provider is enabled implicitly;
- Brave credentials are read from environment variables and never returned in status data;
- Brave credentials are pinned to the official Brave Search endpoint;
- plain HTTP SearXNG endpoints are accepted only on loopback;
- search runs in the same bubblewrap-style restricted network sandbox model as public
  source acquisition;
- search results are discovery metadata only, never prompt evidence;
- only HTTPS result URLs are eligible for downstream acquisition;
- at most three discovered pages are fetched per discovery operation;
- fetched pages retain `UNTRUSTED_EXTERNAL` trust and must still pass the normal evidence
  relevance gate;
- the user query and provider credential are not persisted with fetched source records.

This slice intentionally does not change chat orchestration yet. Automatic AUTO-policy
search and frontier-sensitive freshness classification are the next slice.


## M17.1b — AUTO orchestration and freshness windows

In progress.

The Workstation now reserves a bounded retrieval slot for web search only when:

- network policy is AUTO;
- a provider is configured;
- no manually selected public source is supplied; and
- fresh evidence is required, or Research mode has exhausted local reference evidence.

Fresh/current requests now fail closed unless at least one FRESH source survives both the
deterministic relevance gate and final context compilation. A stale trusted reference can
supplement a current answer but cannot substitute for the required fresh source.

Freshness detection now recognizes deterministic relative/frontier windows including:

- today / last 24 hours;
- this week / past 7 days;
- this month / last 30–31 days;
- longer recent windows up to one year;
- latest/current/recent/newest;
- newly or just released/announced/discovered/published.

Historical absolute-date questions remain stable unless they contain a relative/frontier
signal. The detected window is passed to the configured provider as a bounded date filter.


## M17.1c — freshness provenance integrity

In progress.

`UNTRUSTED_EXTERNAL` remains the trust/evidence class for public pages, but it no longer
proves temporal freshness by itself.

Search-discovered sources now persist a `search_freshness` provenance field recording the
provider window used for discovery. Current-answer acceptance requires that at least one
FRESH context source was discovered under an equal-or-tighter window than the user's
request:

- day satisfies day/week/month/year;
- week satisfies week/month/year;
- month satisfies month/year;
- year satisfies year only;
- a manually fetched or cached external page with no search-window provenance cannot by
  itself ground a current claim.

This prevents stale external material from satisfying a frontier query merely because it
came from the web.


## M17.2a — ReverendBench frontier regressions

In progress.

A separate fixture-backed M17 ReverendBench catalog now locks the core frontier contracts:

- a 30-day query must be classified current and use month-bounded fresh web evidence;
- a cached/manual external page without freshness provenance must fail closed;
- ASK policy must require approval instead of invoking automatic search;
- stable research with sufficient trusted local reference must remain local-first and avoid
  unnecessary web search.

The frontier benchmark deliberately fails if a current-answer case contains only REFERENCE
evidence even when the answer is otherwise non-empty and cited.


## M17.2b — acceptance harness

In progress.

`python -m reverend.benchmarks.m17_validation` now separates portable M17 correctness from
a real configured provider probe.

Portable gates cover the frontier classifier, freshness-provenance ordering, search-provider
security contracts, the four M17 ReverendBench cases, the full unit suite and release smoke.

The live gate uses the explicitly configured provider to perform a bounded search and then
requires at least one result page to survive Reverend's existing restricted public-fetch
sandbox with preserved `UNTRUSTED_EXTERNAL`, provider and freshness provenance.

`--skip-live` can establish `portable_ok=true` but cannot set `overall_ok=true`.
No API key or provider credential is written into the validation report.


## M17 portable software closure

Portable M17 implementation is complete on the development branch. GitHub CI now executes
the M17 validator in portable-only mode and requires all of the following simultaneously:

- `portable_ok == true`;
- `live_ok == false`;
- `overall_ok == false`;
- the live provider probe is explicitly skipped.

This means a CI runner without an explicitly configured public-search provider cannot
accidentally certify live web-search behavior.

### Required live provider acceptance

Configure either a self-hosted SearXNG JSON endpoint or Brave Search as documented in
`.env.example`, then run from WSL2:

```bash
python -m reverend.benchmarks.m17_validation \
  --repository . \
  --report-root benchmarks/results/vnext/m17/live-validation
```

A fully accepted M17 run requires exit code 0 with `portable_ok`, `live_ok`, and
`overall_ok` all true. The live report must show at least one searched page successfully
acquired through Reverend's restricted public-fetch sandbox.

No merge, tag, release, or publication is part of M17 closure.


## Free deployment closure

The canonical Reverend deployment no longer depends on a paid search API.

Repository support now includes:

- `deploy/searxng/settings.yml` with JSON output enabled;
- `scripts/reverend-searxng` for loopback-only container lifecycle and health checks;
- a pinned official SearXNG container image for reproducibility;
- no search API credential;
- a conservative seven-day post-filter for Reverend's semantic `week` window because the
  documented SearXNG API exposes only day/month/year provider ranges.

See [Local SearXNG for Reverend](../../../current/guides/searxng-local.md).

Brave is optional and is not required for M17/M18 acceptance.


## M17 live acceptance closure

The final programme validation at revision
`418524b533f6c05587698dffe8b9a5e4f0434093` closed the provider gate against the
configured loopback SearXNG deployment. Search discovery and restricted public-page
acquisition passed with preserved FRESH provenance. M17 is therefore **LIVE ACCEPTED**.
