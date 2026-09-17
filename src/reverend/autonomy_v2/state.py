from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterator


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


class IssuePhase(StrEnum):
    PENDING = "PENDING"
    CONTEXT_READY = "CONTEXT_READY"
    PLANNED = "PLANNED"
    IMPLEMENTING = "IMPLEMENTING"
    VERIFYING = "VERIFYING"
    REVIEWING = "REVIEWING"
    REPAIRING = "REPAIRING"
    ACCEPTED = "ACCEPTED"
    BLOCKED = "BLOCKED"
    QUARANTINED = "QUARANTINED"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"


TERMINAL_PHASES = {
    IssuePhase.ACCEPTED,
    IssuePhase.BLOCKED,
    IssuePhase.QUARANTINED,
    IssuePhase.HUMAN_REVIEW_REQUIRED,
}

_ALLOWED_TRANSITIONS: dict[IssuePhase, set[IssuePhase]] = {
    IssuePhase.PENDING: {IssuePhase.CONTEXT_READY, IssuePhase.BLOCKED},
    IssuePhase.CONTEXT_READY: {IssuePhase.PLANNED, IssuePhase.BLOCKED},
    IssuePhase.PLANNED: {IssuePhase.IMPLEMENTING, IssuePhase.BLOCKED},
    IssuePhase.IMPLEMENTING: {
        IssuePhase.VERIFYING,
        IssuePhase.REPAIRING,
        IssuePhase.BLOCKED,
        IssuePhase.QUARANTINED,
    },
    IssuePhase.VERIFYING: {
        IssuePhase.REVIEWING,
        IssuePhase.REPAIRING,
        IssuePhase.BLOCKED,
        IssuePhase.QUARANTINED,
    },
    IssuePhase.REVIEWING: {
        IssuePhase.ACCEPTED,
        IssuePhase.REPAIRING,
        IssuePhase.BLOCKED,
        IssuePhase.HUMAN_REVIEW_REQUIRED,
        IssuePhase.QUARANTINED,
    },
    IssuePhase.REPAIRING: {
        IssuePhase.VERIFYING,
        IssuePhase.BLOCKED,
        IssuePhase.HUMAN_REVIEW_REQUIRED,
        IssuePhase.QUARANTINED,
    },
    IssuePhase.ACCEPTED: set(),
    IssuePhase.BLOCKED: set(),
    IssuePhase.QUARANTINED: set(),
    IssuePhase.HUMAN_REVIEW_REQUIRED: set(),
}


class TransitionError(RuntimeError):
    pass


@dataclass(frozen=True)
class IssueState:
    run_id: str
    issue_number: int
    milestone: str
    title: str
    phase: IssuePhase
    base_commit: str
    worktree_path: str | None
    branch_name: str | None
    packet_path: str | None
    accepted_commit: str | None
    attempt_count: int
    updated_at: str


@dataclass(frozen=True)
class AttemptState:
    id: int
    run_id: str
    issue_number: int
    kind: str
    ordinal: int
    status: str
    model: str | None
    started_at: str
    ended_at: str | None
    detail: dict[str, Any]


class StateStore:
    """SQLite-backed source of truth for autonomous controller state.

    WAL mode plus explicit transactions makes the controller restartable without
    relying on model memory, tmux scrollback, or ad-hoc status files.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize_schema(self) -> None:
        connection = self._connect()
        try:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    base_commit TEXT NOT NULL,
                    status TEXT NOT NULL,
                    queue_json TEXT NOT NULL,
                    heartbeat_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS issues (
                    run_id TEXT NOT NULL,
                    issue_number INTEGER NOT NULL,
                    milestone TEXT NOT NULL,
                    title TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    base_commit TEXT NOT NULL,
                    worktree_path TEXT,
                    branch_name TEXT,
                    packet_path TEXT,
                    accepted_commit TEXT,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (run_id, issue_number),
                    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    issue_number INTEGER NOT NULL,
                    kind TEXT NOT NULL,
                    ordinal INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    model TEXT,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    detail_json TEXT NOT NULL DEFAULT '{}',
                    UNIQUE (run_id, issue_number, kind, ordinal),
                    FOREIGN KEY (run_id, issue_number)
                        REFERENCES issues(run_id, issue_number) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    issue_number INTEGER,
                    kind TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_events_run_issue
                    ON events(run_id, issue_number, id);
                CREATE INDEX IF NOT EXISTS idx_issues_run_phase
                    ON issues(run_id, phase, issue_number);
                """
            )
            columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(issues)").fetchall()
            }
            if "packet_path" not in columns:
                connection.execute("ALTER TABLE issues ADD COLUMN packet_path TEXT")
            connection.commit()
        finally:
            connection.close()

    def create_run(
        self,
        *,
        run_id: str,
        base_commit: str,
        queue: list[dict[str, Any]],
        status: str = "RUNNING",
    ) -> None:
        now = _utc_now()
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO runs(
                    run_id, base_commit, status, queue_json,
                    heartbeat_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    base_commit,
                    status,
                    json.dumps(queue, sort_keys=True),
                    now,
                    now,
                    now,
                ),
            )

    def set_run_status(self, run_id: str, status: str) -> None:
        now = _utc_now()
        with self.transaction() as connection:
            cursor = connection.execute(
                "UPDATE runs SET status = ?, updated_at = ? WHERE run_id = ?",
                (status, now, run_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"unknown run_id: {run_id}")

    def heartbeat(self, run_id: str) -> None:
        now = _utc_now()
        with self.transaction() as connection:
            cursor = connection.execute(
                "UPDATE runs SET heartbeat_at = ?, updated_at = ? WHERE run_id = ?",
                (now, now, run_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"unknown run_id: {run_id}")

    def add_issue(
        self,
        *,
        run_id: str,
        issue_number: int,
        milestone: str,
        title: str,
        base_commit: str,
    ) -> None:
        now = _utc_now()
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO issues(
                    run_id, issue_number, milestone, title, phase,
                    base_commit, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    issue_number,
                    milestone,
                    title,
                    IssuePhase.PENDING.value,
                    base_commit,
                    now,
                ),
            )

    @staticmethod
    def _issue_from_row(row: sqlite3.Row) -> IssueState:
        return IssueState(
            run_id=row["run_id"],
            issue_number=row["issue_number"],
            milestone=row["milestone"],
            title=row["title"],
            phase=IssuePhase(row["phase"]),
            base_commit=row["base_commit"],
            worktree_path=row["worktree_path"],
            branch_name=row["branch_name"],
            packet_path=row["packet_path"],
            accepted_commit=row["accepted_commit"],
            attempt_count=row["attempt_count"],
            updated_at=row["updated_at"],
        )

    def get_issue(self, run_id: str, issue_number: int) -> IssueState:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT * FROM issues WHERE run_id = ? AND issue_number = ?",
                (run_id, issue_number),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            raise KeyError(f"unknown issue: {run_id}/{issue_number}")
        return self._issue_from_row(row)

    def list_issues(self, run_id: str) -> tuple[IssueState, ...]:
        connection = self._connect()
        try:
            rows = connection.execute(
                "SELECT * FROM issues WHERE run_id = ? ORDER BY issue_number",
                (run_id,),
            ).fetchall()
        finally:
            connection.close()
        return tuple(self._issue_from_row(row) for row in rows)

    def transition_issue(
        self,
        *,
        run_id: str,
        issue_number: int,
        target: IssuePhase,
        payload: dict[str, Any] | None = None,
    ) -> IssueState:
        payload = payload or {}
        now = _utc_now()
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT phase FROM issues WHERE run_id = ? AND issue_number = ?",
                (run_id, issue_number),
            ).fetchone()
            if row is None:
                raise KeyError(f"unknown issue: {run_id}/{issue_number}")
            source = IssuePhase(row["phase"])
            if target not in _ALLOWED_TRANSITIONS[source]:
                raise TransitionError(f"illegal transition: {source} -> {target}")
            connection.execute(
                """
                UPDATE issues
                SET phase = ?, updated_at = ?
                WHERE run_id = ? AND issue_number = ?
                """,
                (target.value, now, run_id, issue_number),
            )
            self._insert_transition_event(
                connection,
                run_id=run_id,
                issue_number=issue_number,
                source=source,
                target=target,
                payload=payload,
                now=now,
            )
        return self.get_issue(run_id, issue_number)

    def mark_context_ready(
        self,
        *,
        run_id: str,
        issue_number: int,
        worktree_path: str,
        branch_name: str,
        packet_path: str,
    ) -> IssueState:
        """Atomically bind runtime assets and move PENDING -> CONTEXT_READY."""
        now = _utc_now()
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT phase FROM issues WHERE run_id = ? AND issue_number = ?",
                (run_id, issue_number),
            ).fetchone()
            if row is None:
                raise KeyError(f"unknown issue: {run_id}/{issue_number}")
            source = IssuePhase(row["phase"])
            if source is not IssuePhase.PENDING:
                raise TransitionError(
                    f"context may only be prepared from PENDING, got {source}"
                )
            connection.execute(
                """
                UPDATE issues
                SET phase = ?, worktree_path = ?, branch_name = ?, packet_path = ?,
                    updated_at = ?
                WHERE run_id = ? AND issue_number = ?
                """,
                (
                    IssuePhase.CONTEXT_READY.value,
                    worktree_path,
                    branch_name,
                    packet_path,
                    now,
                    run_id,
                    issue_number,
                ),
            )
            self._insert_transition_event(
                connection,
                run_id=run_id,
                issue_number=issue_number,
                source=source,
                target=IssuePhase.CONTEXT_READY,
                payload={"packet_path": packet_path, "worktree_path": worktree_path},
                now=now,
            )
        return self.get_issue(run_id, issue_number)

    @staticmethod
    def _insert_transition_event(
        connection: sqlite3.Connection,
        *,
        run_id: str,
        issue_number: int,
        source: IssuePhase,
        target: IssuePhase,
        payload: dict[str, Any],
        now: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO events(run_id, issue_number, kind, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                run_id,
                issue_number,
                "issue_transition",
                json.dumps(
                    {"from": source.value, "to": target.value, **payload},
                    sort_keys=True,
                ),
                now,
            ),
        )

    def start_attempt(
        self,
        *,
        run_id: str,
        issue_number: int,
        kind: str,
        model: str | None,
    ) -> AttemptState:
        if not kind.strip():
            raise ValueError("attempt kind must not be empty")
        now = _utc_now()
        with self.transaction() as connection:
            row = connection.execute(
                """
                SELECT COALESCE(MAX(ordinal), 0) + 1 AS next_ordinal
                FROM attempts
                WHERE run_id = ? AND issue_number = ? AND kind = ?
                """,
                (run_id, issue_number, kind),
            ).fetchone()
            ordinal = int(row["next_ordinal"])
            cursor = connection.execute(
                """
                INSERT INTO attempts(
                    run_id, issue_number, kind, ordinal, status, model, started_at
                ) VALUES (?, ?, ?, ?, 'RUNNING', ?, ?)
                """,
                (run_id, issue_number, kind, ordinal, model, now),
            )
            connection.execute(
                """
                UPDATE issues
                SET attempt_count = attempt_count + 1, updated_at = ?
                WHERE run_id = ? AND issue_number = ?
                """,
                (now, run_id, issue_number),
            )
            attempt_id = int(cursor.lastrowid)
        return self.get_attempt(attempt_id)

    def get_attempt(self, attempt_id: int) -> AttemptState:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT * FROM attempts WHERE id = ?", (attempt_id,)
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            raise KeyError(f"unknown attempt: {attempt_id}")
        return AttemptState(
            id=row["id"],
            run_id=row["run_id"],
            issue_number=row["issue_number"],
            kind=row["kind"],
            ordinal=row["ordinal"],
            status=row["status"],
            model=row["model"],
            started_at=row["started_at"],
            ended_at=row["ended_at"],
            detail=json.loads(row["detail_json"]),
        )

    def finish_attempt(
        self,
        attempt_id: int,
        *,
        status: str,
        detail: dict[str, Any] | None = None,
    ) -> AttemptState:
        if not status.strip():
            raise ValueError("attempt status must not be empty")
        with self.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE attempts
                SET status = ?, ended_at = ?, detail_json = ?
                WHERE id = ? AND ended_at IS NULL
                """,
                (
                    status,
                    _utc_now(),
                    json.dumps(detail or {}, sort_keys=True),
                    attempt_id,
                ),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"attempt is unknown or already finished: {attempt_id}")
        return self.get_attempt(attempt_id)

    def mark_accepted_commit(
        self,
        *,
        run_id: str,
        issue_number: int,
        commit: str,
    ) -> None:
        state = self.get_issue(run_id, issue_number)
        if state.phase is not IssuePhase.ACCEPTED:
            raise TransitionError("accepted commit can only be recorded after ACCEPTED")
        now = _utc_now()
        with self.transaction() as connection:
            connection.execute(
                """
                UPDATE issues
                SET accepted_commit = ?, updated_at = ?
                WHERE run_id = ? AND issue_number = ?
                """,
                (commit, now, run_id, issue_number),
            )

    def record_event(
        self,
        *,
        run_id: str,
        kind: str,
        payload: dict[str, Any],
        issue_number: int | None = None,
    ) -> None:
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO events(run_id, issue_number, kind, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    issue_number,
                    kind,
                    json.dumps(payload, sort_keys=True),
                    _utc_now(),
                ),
            )
