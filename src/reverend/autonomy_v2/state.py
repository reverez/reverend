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
    accepted_commit: str | None
    attempt_count: int
    updated_at: str


class StateStore:
    """SQLite-backed source of truth for autonomous controller state.

    The store uses WAL mode and explicit transactions so a controller process can
    restart and reconstruct its state without relying on model memory or text files.
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
                """
            )
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
        return IssueState(
            run_id=row["run_id"],
            issue_number=row["issue_number"],
            milestone=row["milestone"],
            title=row["title"],
            phase=IssuePhase(row["phase"]),
            base_commit=row["base_commit"],
            worktree_path=row["worktree_path"],
            branch_name=row["branch_name"],
            accepted_commit=row["accepted_commit"],
            attempt_count=row["attempt_count"],
            updated_at=row["updated_at"],
        )

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
                        {
                            "from": source.value,
                            "to": target.value,
                            **payload,
                        },
                        sort_keys=True,
                    ),
                    now,
                ),
            )
        return self.get_issue(run_id, issue_number)

    def bind_worktree(
        self,
        *,
        run_id: str,
        issue_number: int,
        worktree_path: str,
        branch_name: str,
    ) -> None:
        now = _utc_now()
        with self.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE issues
                SET worktree_path = ?, branch_name = ?, updated_at = ?
                WHERE run_id = ? AND issue_number = ?
                """,
                (worktree_path, branch_name, now, run_id, issue_number),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"unknown issue: {run_id}/{issue_number}")

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
