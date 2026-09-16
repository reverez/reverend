# M7 acceptance — 2026-09-14

Implementation: `71b871a`. Auto-first blue/black experience, advanced overrides, project
chips, inline development activity, bounded source excerpts, citation buttons and source
drawers are connected to the existing Workstation service. Detailed model/provenance data
is available on demand. Submission is disabled before the request begins; Stop reports its
pending state. The renderer preserves escaped TeX delimiters and supports the required
highlighting languages, including CUDA through the C++ grammar.

Validation: 290 pytest tests passed. Actual Chromium passed Auto/default disclosure,
source/citation drawer safety, offline assets, Markdown/code/math, history, streaming,
Stop, mobile navigation, XSS and outer-fence recovery. Desktop and mobile renders were
inspected. `git diff --check` passed.

[Local ReverendBench run](../../../../benchmarks/results/vnext/m7/benchmarks/runs/20260914T092328891970Z-b44c7ef7.json):
three expected failures, no errors/timeouts. Xavier remains 0/5 relevant sources; rocket
remains 4/5. No M8/M9 intelligence improvement is claimed for this UX milestone. M6 reports
are preserved unchanged. See `docs/current/architecture/workstation.md` for local-original and legacy-history
limitations. No merge or release was performed.

Next: M8 request understanding, budgeted adaptive routing, escalation and routing telemetry.
