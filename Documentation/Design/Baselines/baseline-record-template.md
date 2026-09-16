# C0 Entry Baseline — YYYY-MM-DD

> **Commit:**  
> **Operator:**  
> **Environment:**  
> **Python:**  

## Repository State

~~~text
git rev-parse HEAD
git status --short
~~~

Result:

## Install

~~~bash
python -m pip install -e '.[dev]'
~~~

Result:

## Complete Python Suite

~~~bash
python -m pytest -q
~~~

Result:

- passed:
- failed:
- skipped:
- duration:

## Portable Final Validation

~~~bash
python -m reverend.benchmarks.final_validation \
  --repository . \
  --skip-live \
  --report-root benchmarks/results/vnext/final-validation
~~~

Result:

- exit code:
- portable_ok:
- live_ok:
- overall_ok:
- report:

## Live Validation

Run only where the supported live local environment is intentionally available.

Command/result or explicit reason not run:

## CI Evidence

Workflow/run reference:

## Known Issues

None / list with issue links.

## C0 Entry Decision

- [ ] baseline clean enough to start C0
- [ ] failures triaged with owners
