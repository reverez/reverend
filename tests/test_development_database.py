from __future__ import annotations

import sqlite3

import pytest

from reverend.development.database import (
    SCHEMA_VERSION,
    SchemaVersionError,
    connect,
    database,
    initialize,
    transaction,
)


EXPECTED_TABLES = {
    "meta",
    "projects",
    "tasks",
    "task_runs",
    "task_steps",
    "artifacts",
    "verifications",
    "model_runs",
    "decisions",
    "experiments",
}


def test_initialize_creates_development_schema(
    tmp_path,
):
    path = (
        tmp_path
        / "development.db"
    )

    with database(path) as connection:
        tables = {
            row["name"]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                """
            )
        }

        assert EXPECTED_TABLES <= tables

        version = connection.execute(
            "PRAGMA user_version"
        ).fetchone()[0]

        assert version == SCHEMA_VERSION

        foreign_keys = connection.execute(
            "PRAGMA foreign_keys"
        ).fetchone()[0]

        assert foreign_keys == 1

        journal = connection.execute(
            "PRAGMA journal_mode"
        ).fetchone()[0]

        assert journal.lower() == "wal"


def test_initialize_is_idempotent(
    tmp_path,
):
    path = (
        tmp_path
        / "development.db"
    )

    connection = connect(path)

    try:
        initialize(connection)
        initialize(connection)

        version = connection.execute(
            """
            SELECT value
            FROM meta
            WHERE key = 'schema_version'
            """
        ).fetchone()["value"]

        assert version == str(
            SCHEMA_VERSION
        )
    finally:
        connection.close()


def test_foreign_keys_are_enforced(
    tmp_path,
):
    with database(
        tmp_path / "development.db"
    ) as connection:
        with pytest.raises(
            sqlite3.IntegrityError
        ):
            connection.execute(
                """
                INSERT INTO tasks (
                    id,
                    project_id,
                    title,
                    request
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    "task-1",
                    "missing-project",
                    "Example",
                    "Example task",
                ),
            )


def test_transaction_rolls_back_on_error(
    tmp_path,
):
    with database(
        tmp_path / "development.db"
    ) as connection:
        with pytest.raises(
            RuntimeError
        ):
            with transaction(
                connection
            ):
                connection.execute(
                    """
                    INSERT INTO projects (
                        id,
                        name,
                        repo_path,
                        repo_real_path
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        "project-1",
                        "Example",
                        "/example",
                        "/example",
                    ),
                )

                raise RuntimeError(
                    "force rollback"
                )

        count = connection.execute(
            """
            SELECT COUNT(*)
            FROM projects
            """
        ).fetchone()[0]

        assert count == 0


def test_newer_schema_is_rejected(
    tmp_path,
):
    path = (
        tmp_path
        / "development.db"
    )

    connection = connect(path)

    try:
        connection.execute(
            "PRAGMA user_version = 999"
        )

        with pytest.raises(
            SchemaVersionError,
            match="newer than supported",
        ):
            initialize(connection)
    finally:
        connection.close()
