# Reverend 0.4.0 — vNext release-ready

Reverend 0.4.0 is the release identity for the M6–M15 vNext architecture.

This document describes upgrade/recovery expectations for the accepted release-ready
branch. It does not create a Git tag, merge the branch, publish a package or create a
GitHub release.

## What changes from the v3 / 0.3.x baseline

0.4.0 promotes Reverend from the earlier local Knowledge Fabric / M5 Workstation baseline
to the integrated vNext Workstation:

- adaptive request understanding and bounded capability routing;
- evidence gating and public-source research controls;
- Knowledge Fabric v2;
- bounded worker orchestration;
- repository/code intelligence v2;
- encrypted Workstation privacy modes;
- explicit project trust and hardened execution boundaries;
- runtime/model-call/token/cache timing and optimisation;
- permanent ReverendBench milestone acceptance.

The normal release entry point is now:

~~~bash
reverend gui
~~~

Legacy/advanced ingestion, retrieval, note, benchmark and development commands remain
available.

## Upgrade checklist

Before starting 0.4.0 against existing state:

1. stop active Reverend processes and ingestion writers;
2. back up the configured AI_DATA_ROOT;
3. back up the Workstation state key;
4. back up the runtime config;
5. preserve existing Qdrant/knowledge collections for rollback;
6. update/install the 0.4.0 package;
7. run the portable status/doctor checks;
8. start the Workstation and verify local state opens successfully;
9. run the canonical final validator before any destructive migration or release integration.

## Runtime config compatibility

Canonical runtime config:

~~~text
~/.config/reverend/runtime.json
~~~

The legacy config location remains supported when the canonical file does not exist:

~~~text
~/.config/local-ai/runtime.json
~~~

Environment variables continue to take precedence.

Important release variables:

- OLLAMA_HOST
- AI_DATA_ROOT
- REVEREND_RUNTIME_CONFIG
- REVEREND_STATE_KEY_FILE
- QDRANT_PATH
- QDRANT_URL
- QDRANT_COLLECTION

WSL Ollama gateway discovery works when OLLAMA_HOST is not explicitly set.

## Workstation encryption migration

Persistent Workstation state uses authenticated Fernet encryption.

On startup Reverend:

1. creates/updates the Workstation schema;
2. adds the privacy-mode column when required;
3. detects protected legacy plaintext values;
4. encrypts those values with the configured state key;
5. verifies that existing protected state decrypts under that key;
6. uses SQLite secure_delete;
7. if plaintext rows were migrated, checkpoints/truncates WAL and VACUUMs the database.

A wrong/missing key does not produce a silent plaintext fallback.

### State key

Default:

~~~text
~/.config/reverend/state-v1.key
~~~

Override:

~~~text
REVEREND_STATE_KEY_FILE=/secure/path/state-v1.key
~~~

The key and persistent database must both be preserved for recovery.

**If the only copy of the key is lost, encrypted Workstation state is intentionally
unrecoverable.**

## Knowledge/Qdrant migration

0.4.0 does not silently replace or destructively upgrade a Qdrant collection.

For a server/collection migration:

1. stop writers;
2. back up SQLite and the old vector store;
3. migrate/copy/rebuild into a new collection;
4. validate counts, generations and retrieval;
5. explicitly switch configuration;
6. retain the old collection for rollback.

Indexes remain reconstructable from authoritative sources where the relevant source data
is still available.

## Project trust and development

Project registration defaults to untrusted_repo.

Untrusted projects remain inspection-only for the full development workflow.

Trusted development uses isolated Git worktrees and bounded verification. The primary
checkout is not automatically modified or merged.

Upgrading Reverend does not automatically change an existing project's trust mode.

## Network behavior

All inference remains local.

Network policy is explicit:

- OFF
- ASK
- AUTO

Public source text remains untrusted data.

Explicit URL fetch requires opt-in. General query-to-web search is not enabled implicitly.
The canonical no-paid-API backend is the bundled loopback-only self-hosted SearXNG profile;
Brave remains an optional adapter. AUTO reports search unavailability when fresh search is
required but no provider exists.

## Post-upgrade checks

~~~bash
reverend --version
# reverend 0.4.0

reverend status
reverend doctor
python -m pytest -q
python -m reverend.benchmarks.release .
~~~

The M6–M15 baseline retains its accepted M15 evidence at:

~~~text
benchmarks/results/vnext/m15/live-validation/validation-20260914T201903Z.json
~~~

For the current extended branch, start the canonical free search backend first:

~~~bash
scripts/reverend-searxng up
eval "$(scripts/reverend-searxng env)"
~~~

Then the canonical final validation command is:

~~~bash
python -m reverend.benchmarks.final_validation \
  --repository . \
  --report-root benchmarks/results/vnext/final-validation
~~~

This composes M16 runtime/hardware acceptance, M17 live search acceptance and M18 live
searched-image acceptance. Use `--skip-live` only for portable CI-style validation; it
cannot certify the release workstation.

## Rollback

A code rollback alone is not enough if persistent state has already migrated.

Rollback preparation therefore requires the **pre-upgrade** copies of:

- AI_DATA_ROOT;
- the matching Workstation state key;
- runtime config;
- old Qdrant/knowledge storage.

Restore those as one consistent set with Reverend stopped.

Do not mix a restored encrypted database with an unrelated state key.

## 0.4.0 release limitations

- primary validation target is Linux/WSL2;
- full untrusted-repository development remains disabled;
- no general web-search provider is enabled by default;
- large-model inference remains serialized;
- release integration/tagging/publishing remains manual;
- provenance/citations do not guarantee semantic entailment;
- model-generated code and drafts still require human review.
