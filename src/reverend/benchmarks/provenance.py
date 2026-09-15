"""Stable regression provenance for ReverendBench reports."""

from __future__ import annotations

import platform
import subprocess
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from reverend import __version__


def _git(root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = result.stdout.strip()
    return value or None


def _runtime_models(results: Iterable[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()

    for result in results:
        metrics = getattr(result, "metrics", {}) or {}
        runs = metrics.get("model_runs", ())
        if not isinstance(runs, (list, tuple)):
            continue

        for run in runs:
            if not isinstance(run, dict):
                continue
            row = {
                key: run.get(key)
                for key in ("role", "model", "digest", "context")
                if run.get(key) is not None
            }
            if not row:
                continue
            identity = tuple(
                row.get(key)
                for key in ("role", "model", "digest", "context")
            )
            if identity in seen:
                continue
            seen.add(identity)
            rows.append(row)

    rows.sort(
        key=lambda row: (
            str(row.get("role", "")),
            str(row.get("model", "")),
            str(row.get("digest", "")),
            int(row.get("context") or 0),
        )
    )
    return rows


def _trace_ids(results: Iterable[Any]) -> list[str]:
    values = {
        trace_id
        for result in results
        for trace_id in [
            (getattr(result, "metrics", {}) or {}).get("trace_id")
        ]
        if isinstance(trace_id, str) and trace_id
    }
    return sorted(values)


def collect_regression_evidence(
    *,
    results: Iterable[Any],
    code_root: str | Path,
    revision: str | None,
    case_sha256: str,
    case_count: int,
) -> dict[str, Any]:
    """Associate one benchmark run with implementation and runtime identity."""

    root = Path(code_root)
    branch = _git(root, "branch", "--show-current")
    dirty_output = _git(root, "status", "--porcelain")
    dirty = None if dirty_output is None else bool(dirty_output)
    result_tuple = tuple(results)

    return {
        "schema_version": 1,
        "implementation": {
            "reverend_version": __version__,
            "code_revision": revision,
            "branch": branch,
            "dirty": dirty,
        },
        "benchmark": {
            "case_count": int(case_count),
            "case_sha256": case_sha256,
        },
        "environment": {
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
        "runtime": {
            "models": _runtime_models(result_tuple),
            "trace_ids": _trace_ids(result_tuple),
        },
    }
