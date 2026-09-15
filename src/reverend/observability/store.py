"""SQLite persistence for bounded local Reverend traces."""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any


_SCHEMA = """
CREATE TABLE IF NOT EXISTS traces (
    trace_id TEXT PRIMARY KEY,
    workflow_id TEXT,
    task_id TEXT,
    job_id TEXT,
    level TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    duration_seconds REAL,
    attributes_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS spans (
    span_id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL REFERENCES traces(trace_id) ON DELETE CASCADE,
    parent_span_id TEXT,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    duration_seconds REAL,
    workflow_id TEXT,
    task_id TEXT,
    job_id TEXT,
    model TEXT,
    tool_name TEXT,
    error_type TEXT,
    error_code TEXT,
    artifact_ids_json TEXT NOT NULL DEFAULT '[]',
    attributes_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_spans_trace ON spans(trace_id, started_at);
CREATE INDEX IF NOT EXISTS idx_spans_job ON spans(job_id);
CREATE INDEX IF NOT EXISTS idx_spans_task ON spans(task_id);
CREATE INDEX IF NOT EXISTS idx_spans_kind ON spans(kind);
"""


class SQLiteTraceStore:
    """Small append/update store for operational traces only."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript(_SCHEMA)
        self._secure_files()

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA secure_delete=ON")
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA synchronous=NORMAL")
            with db:
                yield db
        finally:
            db.close()
            self._secure_files()

    def _secure_files(self) -> None:
        try:
            os.chmod(self.path.parent, 0o700)
        except OSError:
            pass
        for candidate in (
            self.path,
            Path(str(self.path) + "-wal"),
            Path(str(self.path) + "-shm"),
        ):
            try:
                if candidate.exists():
                    os.chmod(candidate, 0o600)
            except OSError:
                pass

    def start_trace(
        self,
        *,
        trace_id: str,
        workflow_id: str | None,
        task_id: str | None,
        job_id: str | None,
        level: str,
        started_at: str,
        attributes: dict[str, Any],
    ) -> None:
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO traces (
                    trace_id, workflow_id, task_id, job_id, level,
                    status, started_at, attributes_json
                ) VALUES (?, ?, ?, ?, ?, 'running', ?, ?)
                ON CONFLICT(trace_id) DO UPDATE SET
                    workflow_id=COALESCE(excluded.workflow_id,traces.workflow_id),
                    task_id=COALESCE(excluded.task_id,traces.task_id),
                    job_id=COALESCE(excluded.job_id,traces.job_id)
                """,
                (
                    trace_id,
                    workflow_id,
                    task_id,
                    job_id,
                    level,
                    started_at,
                    json.dumps(attributes, sort_keys=True),
                ),
            )
        self._secure_files()

    def link_trace(
        self,
        trace_id: str,
        *,
        workflow_id: str | None = None,
        task_id: str | None = None,
        job_id: str | None = None,
    ) -> None:
        assignments = []
        values: list[Any] = []
        for column, value in (
            ("workflow_id", workflow_id),
            ("task_id", task_id),
            ("job_id", job_id),
        ):
            if value is not None:
                assignments.append(f"{column}=?")
                values.append(value)

        if not assignments:
            return

        values.append(trace_id)
        with self._connect() as db:
            db.execute(
                "UPDATE traces SET " + ", ".join(assignments) + " WHERE trace_id=?",
                values,
            )
        self._secure_files()

    def finish_trace(
        self,
        trace_id: str,
        *,
        status: str,
        completed_at: str,
        duration_seconds: float,
    ) -> None:
        with self._connect() as db:
            db.execute(
                """
                UPDATE traces
                SET status=?, completed_at=?, duration_seconds=?
                WHERE trace_id=?
                """,
                (status, completed_at, duration_seconds, trace_id),
            )
        self._secure_files()

    def start_span(
        self,
        *,
        span_id: str,
        trace_id: str,
        parent_span_id: str | None,
        kind: str,
        name: str,
        started_at: str,
        workflow_id: str | None,
        task_id: str | None,
        job_id: str | None,
        model: str | None,
        tool_name: str | None,
        attributes: dict[str, Any],
    ) -> None:
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO spans (
                    span_id, trace_id, parent_span_id, kind, name, status,
                    started_at, workflow_id, task_id, job_id, model, tool_name,
                    attributes_json
                ) VALUES (?, ?, ?, ?, ?, 'running', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    span_id,
                    trace_id,
                    parent_span_id,
                    kind,
                    name,
                    started_at,
                    workflow_id,
                    task_id,
                    job_id,
                    model,
                    tool_name,
                    json.dumps(attributes, sort_keys=True),
                ),
            )
        self._secure_files()

    def finish_span(
        self,
        span_id: str,
        *,
        status: str,
        completed_at: str,
        duration_seconds: float,
        error_type: str | None,
        error_code: str | None,
        model: str | None,
        tool_name: str | None,
        artifact_ids: tuple[str, ...],
        attributes: dict[str, Any],
    ) -> None:
        with self._connect() as db:
            db.execute(
                """
                UPDATE spans
                SET status=?, completed_at=?, duration_seconds=?,
                    error_type=?, error_code=?, model=COALESCE(?, model),
                    tool_name=COALESCE(?, tool_name),
                    artifact_ids_json=?, attributes_json=?
                WHERE span_id=?
                """,
                (
                    status,
                    completed_at,
                    duration_seconds,
                    error_type,
                    error_code,
                    model,
                    tool_name,
                    json.dumps(list(artifact_ids)),
                    json.dumps(attributes, sort_keys=True),
                    span_id,
                ),
            )
        self._secure_files()

    @staticmethod
    def _decode_row(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        for source, target in (
            ("attributes_json", "attributes"),
            ("artifact_ids_json", "artifact_ids"),
        ):
            if source in result:
                raw = result.pop(source)
                try:
                    result[target] = json.loads(raw or ("[]" if target == "artifact_ids" else "{}"))
                except json.JSONDecodeError:
                    result[target] = [] if target == "artifact_ids" else {}
        return result

    def trace(self, trace_id: str) -> dict[str, Any]:
        with self._connect() as db:
            trace = db.execute(
                "SELECT * FROM traces WHERE trace_id=?",
                (trace_id,),
            ).fetchone()
            if trace is None:
                raise KeyError("Unknown trace")
            spans = db.execute(
                "SELECT * FROM spans WHERE trace_id=? ORDER BY started_at, rowid",
                (trace_id,),
            ).fetchall()

        return {
            "trace": self._decode_row(trace),
            "spans": [self._decode_row(row) for row in spans],
        }

    def list_traces(self, *, limit: int = 50) -> list[dict[str, Any]]:
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 500:
            raise ValueError("Trace limit must be between 1 and 500")
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT * FROM traces
                ORDER BY started_at DESC, rowid DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._decode_row(row) for row in rows]

    def trace_for_job(self, job_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute(
                """
                SELECT trace_id FROM traces
                WHERE job_id=?
                ORDER BY started_at DESC, rowid DESC
                LIMIT 1
                """,
                (job_id,),
            ).fetchone()
        return self.trace(row["trace_id"]) if row is not None else None
