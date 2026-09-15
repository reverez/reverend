"""Persistent reports for ReverendBench."""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from reverend.benchmarks.models import BenchmarkResult
from reverend.benchmarks.runner import BenchmarkSummary


_SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9._-]+$")


@dataclass(frozen=True)
class BenchmarkRun:
    run_id: str
    started_at: str
    completed_at: str
    results: tuple[BenchmarkResult, ...]
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: int = 1

    def __post_init__(self) -> None:
        if not self.run_id:
            raise ValueError("run_id must not be empty")

        if not _SAFE_RUN_ID.fullmatch(self.run_id):
            raise ValueError(
                "run_id may contain only letters, numbers, "
                "dot, underscore, and hyphen"
            )

        if not self.started_at:
            raise ValueError("started_at must not be empty")

        if not self.completed_at:
            raise ValueError("completed_at must not be empty")

        if self.schema_version != 1:
            raise ValueError("unsupported benchmark schema_version")

    @property
    def summary(self) -> BenchmarkSummary:
        return BenchmarkSummary.from_results(self.results)

    def to_dict(self) -> dict[str, Any]:
        summary = self.summary

        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "metadata": dict(self.metadata),
            "summary": {
                "total": summary.total,
                "passed": summary.passed,
                "failed": summary.failed,
                "errors": summary.errors,
                "timeouts": summary.timeouts,
                "skipped": summary.skipped,
            },
            "results": [
                {
                    "case_id": result.case_id,
                    "status": result.status.value,
                    "duration_seconds": result.duration_seconds,
                    "response": result.response,
                    "assertions": [
                        {
                            "name": assertion.name,
                            "passed": assertion.passed,
                            "detail": assertion.detail,
                        }
                        for assertion in result.assertions
                    ],
                    "metrics": dict(result.metrics),
                    "error": result.error,
                }
                for result in self.results
            ],
        }


def report_directory(root: Path) -> Path:
    return root / "benchmarks" / "runs"


def report_path(root: Path, run_id: str) -> Path:
    if not _SAFE_RUN_ID.fullmatch(run_id):
        raise ValueError("unsafe benchmark run_id")

    return report_directory(root) / f"{run_id}.json"


def save_run(
    run: BenchmarkRun,
    *,
    root: Path,
) -> Path:
    """Persist one immutable ReverendBench run atomically."""

    destination = report_path(root, run.run_id)
    destination.parent.mkdir(parents=True, exist_ok=True)

    if destination.exists():
        raise FileExistsError(
            f"benchmark run already exists: {destination}"
        )

    payload = json.dumps(
        run.to_dict(),
        indent=2,
        ensure_ascii=False,
        sort_keys=True,
    ) + "\n"

    temporary: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=".benchmark-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())

        # Atomic create-if-absent: concurrent writers cannot replace a report.
        os.link(temporary, destination)
        temporary.unlink()
        temporary = None

    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)

    return destination
