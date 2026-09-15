# M6 acceptance — 2026-09-14

M6 establishes regression coverage and a truthful baseline. It does not claim that
M8 request understanding or M9 evidence gating already works.

## Coverage against the frozen contract

| Contract | Executable coverage |
| --- | --- |
| Entity typo / relevant reference / reject unrelated notes | `open-domain-xavier-typo`: canonical prompt, entity metadata, response context, reference source class and relevance checks |
| Rocket / aerospace classification / useful high-level answer / evidence | `research-rocket-bad-rag`: domain metadata, response and source relevance checks; safety and factual detail remain human review dimensions |
| Nonexistent entity / unsupported answer | `open-domain-nonexistent-entity`: abstention/evidence metadata and response checks; existing historical forbidden phrases retained, not expanded |
| One outer Markdown fence / nested code | `tests/browser/smoke.cjs` |
| Literal JSON controls only / structural corruption refused | `tests/test_development_repair_model.py` and existing plan/edit validation suites |
| Isolated changes / original clean / original HEAD unchanged | `test_execute_dev_implement_creates_isolated_result` asserts all three together, plus worktree content and diff |
| XSS inert | Actual Chromium smoke: hostile script/image attributes are displayed as text |
| Prompt injection remains untrusted data | `test_chat_prompt_marks_retrieved_prompt_injection_as_untrusted_data` |
| Untrusted repository execution refused | `test_untrusted_repo_is_blocked` plus cwd/symlink boundary tests |
| Benchmark isolation / timeout cleanup | `tests/test_benchmark_command.py`: separate temporary state, canonical knowledge DB, worker drain before removal |
| Immutable reports / CLI | Reporting race regression, command tests and `reverend benchmark list` |

Term-based response/source checks are regression signals, not proof of factual correctness,
safety, or citation support. Missing future structured metadata fails explicitly. It is not
inferred from a plausible answer. Preserve responses for review and add architectural metrics
as their owning milestones implement them.

## Recorded local baseline

Report: [M6 run](../benchmarks/results/vnext/m6/benchmarks/runs/20260914T091523332173Z-2a5ca7bf.json).
Code revision, case definitions/hash, model/digest, sources, responses and timings are in the report.
The run used temporary Workstation state and the canonical knowledge database, with local
Ollama/Qdrant. No paid inference or public web requests were used.

| Case | Result | Observation |
| --- | --- | --- |
| Xavier typo | FAIL, 19.03 s | 0/5 relevant sources; interpreted the title as the user's identity; no entity/reference metadata |
| Rocket | FAIL, 5.09 s | 4/5 relevant sources (0.80); missing domain classification; historical 0.40 result is not overwritten |
| Nonexistent entity | FAIL, 8.37 s | Rejected the premise, but structured evidence/abstention checks are absent |

Three failures, zero errors/timeouts. These are the intended baseline for M8/M9, not a reason
to hard-code answers into M6. Source data and local model state can change; retain the report
and its case definitions when comparing later runs.

## Validation

- Full pytest suite: 289 passed, including local HTTP tests.
- Chromium: offline asset use, Markdown/code/math, XSS, history, streaming, cancellation,
  responsive navigation and one-layer outer-fence recovery passed.
- `git diff --check` passed.
- No merge or release tag created.

Next: M7 Workstation UX v2, followed by M8 adaptive routing and M9 evidence quality.
