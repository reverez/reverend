# M9 Research & Evidence Engine — acceptance validation

M6–M8 COMPLETE. M10–M15 NOT STARTED. The frozen architecture remains unchanged.

## Current slice

`f41e7d7` adds the minimal optional offline ZIM reference provider, generic full-title/named-subject
relevance gating, deterministic tests and recorded acquisition provenance. No M10 corpus
management, bulk SQLite/Qdrant ingestion or archive embedding was introduced.

The authorized `wikipedia_en_all_mini_2026-06.zim` is stored outside Git at
`/home/user/dev/ai-data/reference/kiwix/`, alongside its provenance and
`provider.json`. Size: **12,531,679,311 bytes**. SHA-256:
`1d0f8178709481c831272d95f95dccc030e9193e38e732b86b1938ae2606226e`.
This matches the official Kiwix digest. More than 20 GB free was checked before acquisition;
the transfer remained below the authorized 15 GB ceiling. A timed-out range was recovered
from the retained partial file and the complete hash verified before activation.

The origin is official Kiwix; the final mirror was selected by Kiwix's own redirect service.
[Recorded provenance](m9-reference-provenance.json) includes acquisition time, origin/mirror,
provider digest, actual ZIM metadata, UUID and indexes. The archive has no License metadata key;
its actual article footer supplies the attribution/license notice and links. Those are retained
per article, with a recorded provenance sample. No license text was invented.

Dependency: official **libzim 3.13.0**, installed only in the project `.venv` with no additional
packages and declared as optional `reverend[reference]`. ZIM files/partial payloads are ignored
by Git; the archive is not committed. See [reference-provider.md](../../../current/guides/reference-provider.md).

## Validation

- Initial provider unit tests: **10 passed in 0.87s**.
- First expanded focused run: **124 passed, 1 failed**. The new title filter changed an existing
  low-relevance rejection reason. Gate ordering was corrected to preserve that contract.
- Final focused M9 suites: **125 passed in 5.74s** — `test_reference.py`,
  `test_intelligence_evidence.py`, `test_intelligence_citations.py`, `test_intelligence_routing.py`,
  `test_retrieve.py`, `test_workstation.py`, `test_benchmark_workstation.py`,
  `test_benchmark_evaluator.py`, `test_benchmark_catalog.py`, `test_benchmark_runner.py`.
- `git diff --check`: passed.
- One final full pytest run: **373 passed in 15.70s**, using `"$PWD/.venv/bin/python" -m pytest -q`.
- No browser tests: no UI/browser behavior was changed.

The real archive was queried with all three unchanged canonical prompts before final validation.
It supplied the correct title for the typo, exact Rocket evidence, and no fabricated-person
candidates. The probe exposed incidental partial-title contamination from unrelated music
articles. A generic full-title focus rule now rejects those hits; the regression uses a different
synthetic novel title. Named-subject tests separately reject award/year overlap without the person.

## Canonical live benchmark

Final canonical reference-backed run: **3 passed, 0 failed, 0 errors, 0 timeouts**.

Report:
`benchmarks/results/vnext/m9/reference-workstation/benchmarks/runs/20260914T152925166571Z-df3051a8.json`.

The Xavier and Rocket cases used legitimate Kiwix Wikipedia REFERENCE evidence.
The fabricated entity remained unsupported and abstained with zero generation calls. Canonical prompts, expectations and budgets are unchanged:
120 seconds, two total model calls and one outer retrieval round per case. The provider is
purely local and needs no embedding call. Title/lexical index operations and provenance survive
in source metadata; these are bounded operations inside a single retrieval attempt.

The previous [M9 report](../../../../benchmarks/results/vnext/m9/workstation/benchmarks/runs/20260914T145321512130Z-a8ace495.json)
remains immutable: one pass, two failures, no errors/timeouts before a real reference corpus
was available. The canonical SQLite database remains 8,277 personal documents and three
synthetic fixtures; none were promoted or replaced by the archive.

## Acceptance criteria and limitations

Evidence gating, corrective retrieval, evidence-backed entity resolution, deterministic
unsupported-query abstention, OFF/ASK/AUTO policy, citation/provenance integrity and discovered
failures all have deterministic regression coverage. The final live report satisfied the acceptance criteria.

The provider uses existing title/fulltext indexes, at most six index searches and twelve
candidate articles per call, bounded HTML extraction and a 25-second reader-process timeout.
Whole-file SHA-256 verification runs once per changed file fingerprint, not once per index query.
Provider failures remain structured failed jobs; no personal fallback or answer generation occurs.

Citation auditing measures label integrity only, not claim entailment or completeness. Mini
articles are abbreviated, dated evidence; relevance/title matching remains heuristic and
prompt excerpts use character limits. Wikipedia is not guaranteed factual authority for every
task. No query-to-web provider exists: OFF/ASK/AUTO remain honest and cached/offline evidence
does not grant network permission. Broader corpus UX and semantic indexing remain M10 scope.

M9 acceptance is complete. M10 may now begin from this checkpoint.


## Canonical acceptance achieved

The final live reference-backed ReverendBench run passed all three canonical M9 cases:

- Xavier typo: PASS
- Rocket bad-RAG regression: PASS
- Nonexistent entity: PASS
- 3 passed, 0 failed, 0 errors, 0 timeouts

The final full pytest suite passed 373 tests.

M9 is COMPLETE. See `docs/history/milestones/m09/acceptance.md`.
