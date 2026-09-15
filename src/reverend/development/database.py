"""Persistent database for Reverend software-development state."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from reverend.config import DATA_ROOT


SCHEMA_VERSION = 1

DEFAULT_DATABASE_PATH = (
    DATA_ROOT / "development.db"
)


class DevelopmentDatabaseError(RuntimeError):
    """Base error for the development database."""


class SchemaVersionError(
    DevelopmentDatabaseError
):
    """Raised when the database schema is newer than Reverend."""


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    repo_path TEXT NOT NULL UNIQUE,
    repo_real_path TEXT NOT NULL UNIQUE,
    default_branch TEXT,
    trust_mode TEXT NOT NULL
        DEFAULT 'trusted_repo'
        CHECK (
            trust_mode IN (
                'trusted_repo',
                'untrusted_repo'
            )
        ),
    created_at TEXT NOT NULL
        DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL
        DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    title TEXT NOT NULL,
    request TEXT NOT NULL,
    acceptance_criteria TEXT,
    state TEXT NOT NULL
        DEFAULT 'pending'
        CHECK (
            state IN (
                'pending',
                'preparing',
                'running',
                'verifying',
                'complete',
                'blocked',
                'failed',
                'cancelled'
            )
        ),
    base_commit TEXT,
    branch_name TEXT,
    worktree_path TEXT,
    attempt_budget INTEGER NOT NULL
        DEFAULT 3
        CHECK (attempt_budget >= 1),
    error_message TEXT,
    created_at TEXT NOT NULL
        DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL
        DEFAULT CURRENT_TIMESTAMP,
    started_at TEXT,
    completed_at TEXT,

    FOREIGN KEY (project_id)
        REFERENCES projects(id)
        ON DELETE CASCADE,

    UNIQUE (
        project_id,
        branch_name
    )
);

CREATE TABLE IF NOT EXISTS task_runs (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    run_number INTEGER NOT NULL
        CHECK (run_number >= 1),
    status TEXT NOT NULL
        DEFAULT 'pending'
        CHECK (
            status IN (
                'pending',
                'running',
                'complete',
                'failed',
                'cancelled'
            )
        ),
    model_role TEXT,
    model_name TEXT,
    base_commit TEXT,
    summary TEXT,
    started_at TEXT NOT NULL
        DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT,

    FOREIGN KEY (task_id)
        REFERENCES tasks(id)
        ON DELETE CASCADE,

    UNIQUE (
        task_id,
        run_number
    )
);

CREATE TABLE IF NOT EXISTS task_steps (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    sequence INTEGER NOT NULL
        CHECK (sequence >= 1),
    kind TEXT NOT NULL,
    status TEXT NOT NULL
        DEFAULT 'pending'
        CHECK (
            status IN (
                'pending',
                'running',
                'complete',
                'failed',
                'skipped'
            )
        ),
    input_summary TEXT,
    output_summary TEXT,
    started_at TEXT,
    finished_at TEXT,

    FOREIGN KEY (run_id)
        REFERENCES task_runs(id)
        ON DELETE CASCADE,

    UNIQUE (
        run_id,
        sequence
    )
);

CREATE TABLE IF NOT EXISTS artifacts (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    run_id TEXT,
    step_id TEXT,
    kind TEXT NOT NULL,
    path TEXT,
    content_hash TEXT,
    metadata_json TEXT NOT NULL
        DEFAULT '{}',
    created_at TEXT NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (task_id)
        REFERENCES tasks(id)
        ON DELETE CASCADE,

    FOREIGN KEY (run_id)
        REFERENCES task_runs(id)
        ON DELETE SET NULL,

    FOREIGN KEY (step_id)
        REFERENCES task_steps(id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS verifications (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    run_id TEXT,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    command TEXT,
    exit_code INTEGER,
    summary TEXT,
    details_json TEXT NOT NULL
        DEFAULT '{}',
    created_at TEXT NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (task_id)
        REFERENCES tasks(id)
        ON DELETE CASCADE,

    FOREIGN KEY (run_id)
        REFERENCES task_runs(id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS model_runs (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    run_id TEXT,
    step_id TEXT,
    role TEXT NOT NULL,
    model TEXT NOT NULL,
    digest TEXT,
    context INTEGER,
    prompt_tokens INTEGER,
    generated_tokens INTEGER,
    elapsed_seconds REAL,
    success INTEGER NOT NULL
        CHECK (success IN (0, 1)),
    metadata_json TEXT NOT NULL
        DEFAULT '{}',
    created_at TEXT NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (task_id)
        REFERENCES tasks(id)
        ON DELETE CASCADE,

    FOREIGN KEY (run_id)
        REFERENCES task_runs(id)
        ON DELETE SET NULL,

    FOREIGN KEY (step_id)
        REFERENCES task_steps(id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS decisions (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    category TEXT NOT NULL,
    summary TEXT NOT NULL,
    rationale TEXT,
    verification_status TEXT NOT NULL
        DEFAULT 'unverified'
        CHECK (
            verification_status IN (
                'unverified',
                'verified',
                'rejected'
            )
        ),
    created_at TEXT NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (task_id)
        REFERENCES tasks(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS experiments (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    run_id TEXT,
    name TEXT NOT NULL,
    hypothesis TEXT,
    outcome TEXT,
    status TEXT NOT NULL
        DEFAULT 'pending'
        CHECK (
            status IN (
                'pending',
                'complete',
                'failed'
            )
        ),
    metadata_json TEXT NOT NULL
        DEFAULT '{}',
    created_at TEXT NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (task_id)
        REFERENCES tasks(id)
        ON DELETE CASCADE,

    FOREIGN KEY (run_id)
        REFERENCES task_runs(id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_project
    ON tasks(project_id);

CREATE INDEX IF NOT EXISTS idx_tasks_state
    ON tasks(state);

CREATE INDEX IF NOT EXISTS idx_task_runs_task
    ON task_runs(task_id);

CREATE INDEX IF NOT EXISTS idx_task_steps_run
    ON task_steps(run_id);

CREATE INDEX IF NOT EXISTS idx_artifacts_task
    ON artifacts(task_id);

CREATE INDEX IF NOT EXISTS idx_verifications_task
    ON verifications(task_id);

CREATE INDEX IF NOT EXISTS idx_model_runs_task
    ON model_runs(task_id);

CREATE INDEX IF NOT EXISTS idx_decisions_task
    ON decisions(task_id);

CREATE INDEX IF NOT EXISTS idx_experiments_task
    ON experiments(task_id);
"""


def connect(
    path: str | Path | None = None,
) -> sqlite3.Connection:
    """Open the development database with Reverend's safety pragmas."""

    if path is None:
        database_path = DEFAULT_DATABASE_PATH
    else:
        database_path = Path(path)

    database_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        str(database_path),
        timeout=30.0,
        isolation_level=None,
    )

    connection.row_factory = sqlite3.Row

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    connection.execute(
        "PRAGMA busy_timeout = 5000"
    )

    connection.execute(
        "PRAGMA journal_mode = WAL"
    )

    connection.execute(
        "PRAGMA synchronous = NORMAL"
    )

    return connection


def initialize(
    connection: sqlite3.Connection,
) -> None:
    """Create or validate the current development schema."""

    version = int(
        connection.execute(
            "PRAGMA user_version"
        ).fetchone()[0]
    )

    if version > SCHEMA_VERSION:
        raise SchemaVersionError(
            "development.db schema "
            f"{version} is newer than supported "
            f"schema {SCHEMA_VERSION}"
        )

    connection.executescript(
        SCHEMA_SQL
    )

    connection.execute(
        f"PRAGMA user_version = "
        f"{SCHEMA_VERSION}"
    )

    connection.execute(
        """
        INSERT INTO meta (
            key,
            value
        )
        VALUES (
            'schema_version',
            ?
        )
        ON CONFLICT(key)
        DO UPDATE SET
            value = excluded.value
        """,
        (
            str(SCHEMA_VERSION),
        ),
    )


@contextmanager
def database(
    path: str | Path | None = None,
) -> Iterator[sqlite3.Connection]:
    """Open an initialized development database."""

    connection = connect(path)

    try:
        initialize(connection)
        yield connection
    finally:
        connection.close()


@contextmanager
def transaction(
    connection: sqlite3.Connection,
) -> Iterator[sqlite3.Connection]:
    """Execute one atomic development-state transaction."""

    if connection.in_transaction:
        raise DevelopmentDatabaseError(
            "A transaction is already active."
        )

    connection.execute(
        "BEGIN IMMEDIATE"
    )

    try:
        yield connection
    except BaseException:
        connection.rollback()
        raise
    else:
        connection.commit()
