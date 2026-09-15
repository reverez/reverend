# Local SearXNG for Reverend

Reverend's canonical no-paid-API web-search backend is a **self-hosted SearXNG instance**
bound to loopback.

This keeps model inference local and removes the need for a paid search API. Search itself is
still an Internet operation: SearXNG queries public search services and databases, so this is
**free/local-first**, not offline.

## Why SearXNG

- free and open source;
- no Reverend API key or paid search subscription;
- JSON search API;
- can run entirely on the local machine;
- Reverend already treats every discovered page as untrusted and re-fetches it through the
  restricted public-research worker before it can become evidence.

The Reverend profile enables JSON output because SearXNG disables non-HTML formats unless
they are explicitly listed in `search.formats`.

## Start

Install either Docker Engine or Podman, then from the Reverend repository run:

```bash
scripts/reverend-searxng up
```

The helper:

- uses the pinned official SearXNG container image declared in the script;
- binds **only** `127.0.0.1:8888` on the host;
- mounts `deploy/searxng/settings.yml` read-only;
- generates a random SearXNG secret when the container is first created;
- checks that the JSON API actually returns a result list;
- prints the Reverend environment variables to use.

Load those settings into the current shell:

```bash
eval "$(scripts/reverend-searxng env)"
```

Then verify:

```bash
scripts/reverend-searxng test

python - <<'PY'
from reverend.research.search import configured_web_search
config=configured_web_search()
print(config.safe_metadata() if config else "NOT CONFIGURED")
PY
```

Expected Reverend metadata:

```text
provider: searxng
endpoint_host: 127.0.0.1:8888
credentialed: false
country: GB
language: en
```

## Acceptance

Run M17 first:

```bash
python -m reverend.benchmarks.m17_validation \
  --repository . \
  --skip-tests \
  --report-root benchmarks/results/vnext/m17/live-validation
```

Then M18:

```bash
python -m reverend.benchmarks.m18_validation \
  --repository . \
  --skip-tests \
  --report-root benchmarks/results/vnext/m18/live-validation
```

Finally:

```bash
python -m reverend.benchmarks.final_validation \
  --repository . \
  --report-root benchmarks/results/vnext/final-validation
```

## Freshness semantics

SearXNG's documented search API exposes `day`, `month`, and `year` time ranges. Reverend
also supports a semantic `week` window. For that case Reverend asks SearXNG for the
provider's month window, then retains only results with an ISO publication timestamp within
the last seven days before marking them with week freshness provenance. Undated results do
not qualify for week freshness.

This is intentionally conservative: Reverend would rather fail closed than label a
month-bounded result as week-fresh without proof.

## Operations

```bash
scripts/reverend-searxng status
scripts/reverend-searxng logs
scripts/reverend-searxng stop
scripts/reverend-searxng up
scripts/reverend-searxng rm
```

The container may encounter rate limits, CAPTCHAs, or temporary engine failures because
SearXNG aggregates public upstream engines. Reverend must surface those as search failures
rather than silently inventing fresh evidence.
