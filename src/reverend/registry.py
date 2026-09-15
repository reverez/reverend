from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


from .config import DATA_ROOT

REGISTRY_DB = DATA_ROOT / "platform.db"
LEGACY_STATE = DATA_ROOT / "ingestion/state.json"
SCHEMA_VERSION = 4


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(path: Path = REGISTRY_DB) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)

    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA journal_mode = WAL")
    return db


def initialize(path: Path = REGISTRY_DB) -> None:
    with connect(path) as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS corpora (
                id TEXT PRIMARY KEY,
                root_path TEXT NOT NULL DEFAULT '',
                enabled INTEGER NOT NULL DEFAULT 1
                    CHECK (enabled IN (0, 1)),
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS documents (
                source_path TEXT PRIMARY KEY,
                corpus_id TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                chunk_count INTEGER NOT NULL DEFAULT 0,
                trust_class TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'indexed',
                indexed_at TEXT NOT NULL,
                FOREIGN KEY (corpus_id)
                    REFERENCES corpora(id)
            );

            CREATE INDEX IF NOT EXISTS idx_documents_corpus
                ON documents(corpus_id);

            CREATE INDEX IF NOT EXISTS idx_documents_sha256
                ON documents(sha256);

            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id TEXT PRIMARY KEY,
                source_path TEXT NOT NULL,
                ordinal INTEGER,
                section TEXT,
                page INTEGER,
                text TEXT,
                text_hash TEXT,
                FOREIGN KEY (source_path)
                    REFERENCES documents(source_path)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS pending_publications (
                source_path TEXT PRIMARY KEY,
                corpus_id TEXT NOT NULL,
                started_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_chunks_source
                ON chunks(source_path);
            """
        )

        columns = {
            row["name"]
            for row in db.execute("PRAGMA table_info(documents)")
        }

        if "size_bytes" not in columns:
            db.execute(
                "ALTER TABLE documents ADD COLUMN size_bytes INTEGER"
            )

        if "mtime_ns" not in columns:
            db.execute(
                "ALTER TABLE documents ADD COLUMN mtime_ns INTEGER"
            )

        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='chunks_fts'").fetchone():
            db.executescript("""
                BEGIN IMMEDIATE;
                CREATE VIRTUAL TABLE chunks_fts USING fts5(
                    section, text, content='chunks', content_rowid='rowid',
                    tokenize='unicode61 remove_diacritics 2'
                );
                CREATE TRIGGER chunks_ai AFTER INSERT ON chunks BEGIN
                    INSERT INTO chunks_fts(rowid,section,text) VALUES(new.rowid,new.section,new.text);
                END;
                CREATE TRIGGER chunks_ad AFTER DELETE ON chunks BEGIN
                    INSERT INTO chunks_fts(chunks_fts,rowid,section,text)
                    VALUES('delete',old.rowid,old.section,old.text);
                END;
                CREATE TRIGGER chunks_au AFTER UPDATE ON chunks BEGIN
                    INSERT INTO chunks_fts(chunks_fts,rowid,section,text)
                    VALUES('delete',old.rowid,old.section,old.text);
                    INSERT INTO chunks_fts(rowid,section,text) VALUES(new.rowid,new.section,new.text);
                END;
                INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild');
                COMMIT;
            """)

        db.execute(
            """
            INSERT INTO meta(key, value)
            VALUES('schema_version', ?)
            ON CONFLICT(key)
            DO UPDATE SET value = excluded.value
            """,
            (str(SCHEMA_VERSION),),
        )


def import_legacy_state(
    state_path: Path = LEGACY_STATE,
    db_path: Path = REGISTRY_DB,
    *,
    force: bool = False,
) -> dict:
    initialize(db_path)

    state = json.loads(state_path.read_text(encoding="utf-8"))
    sources = state.get("sources", {})

    with connect(db_path) as db:
        existing = db.execute(
            "SELECT COUNT(*) FROM documents"
        ).fetchone()[0]

        if existing and not force:
            raise RuntimeError(
                f"Registry already contains {existing} documents. "
                "Refusing to overwrite without force=True."
            )

        if force:
            db.execute("DELETE FROM chunks")
            db.execute("DELETE FROM documents")
            db.execute("DELETE FROM corpora")

        imported_at = now_utc()

        corpus_ids = sorted(
            {
                str(info.get("corpus") or "unknown")
                for info in sources.values()
            }
        )

        for corpus_id in corpus_ids:
            db.execute(
                """
                INSERT INTO corpora(
                    id,
                    root_path,
                    enabled,
                    created_at
                )
                VALUES (?, '', 1, ?)
                """,
                (corpus_id, imported_at),
            )

        for source_path, info in sources.items():
            db.execute(
                """
                INSERT INTO documents(
                    source_path,
                    corpus_id,
                    sha256,
                    chunk_count,
                    trust_class,
                    status,
                    indexed_at
                )
                VALUES (?, ?, ?, ?, ?, 'indexed', ?)
                """,
                (
                    source_path,
                    str(info.get("corpus") or "unknown"),
                    str(info.get("hash") or ""),
                    int(info.get("chunks") or 0),
                    str(info.get("trust_class") or "UNKNOWN"),
                    imported_at,
                ),
            )

        columns = {
            row["name"]
            for row in db.execute("PRAGMA table_info(documents)")
        }

        if "size_bytes" not in columns:
            db.execute(
                "ALTER TABLE documents ADD COLUMN size_bytes INTEGER"
            )

        if "mtime_ns" not in columns:
            db.execute(
                "ALTER TABLE documents ADD COLUMN mtime_ns INTEGER"
            )

        db.execute(
            """
            INSERT INTO meta(key, value)
            VALUES('legacy_state_imported_at', ?)
            ON CONFLICT(key)
            DO UPDATE SET value = excluded.value
            """,
            (imported_at,),
        )

    return stats(db_path)


def stats(path: Path = REGISTRY_DB) -> dict:
    initialize(path)

    with connect(path) as db:
        corpora = db.execute(
            "SELECT COUNT(*) FROM corpora"
        ).fetchone()[0]

        documents = db.execute(
            "SELECT COUNT(*) FROM documents"
        ).fetchone()[0]

        declared_chunks = db.execute(
            """
            SELECT COALESCE(SUM(chunk_count), 0)
            FROM documents
            """
        ).fetchone()[0]

        materialized_chunks = db.execute(
            "SELECT COUNT(*) FROM chunks"
        ).fetchone()[0]

        by_corpus = {
            row["corpus_id"]: row["count"]
            for row in db.execute(
                """
                SELECT corpus_id, COUNT(*) AS count
                FROM documents
                GROUP BY corpus_id
                ORDER BY corpus_id
                """
            )
        }

        return {
            "schema_version": SCHEMA_VERSION,
            "corpora": corpora,
            "documents": documents,
            "declared_chunks": declared_chunks,
            "materialized_chunks": materialized_chunks,
            "pending_publications": db.execute("SELECT COUNT(*) FROM pending_publications").fetchone()[0],
            "fts_chunks": db.execute("SELECT COUNT(*) FROM chunks_fts_docsize").fetchone()[0],
            "by_corpus": by_corpus,
            "database": str(path),
        }


def rebuild_fts(path: Path = REGISTRY_DB) -> dict:
    with writer_lock(path):
        initialize(path)
        with connect(path) as db:
            db.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')")
            db.execute("INSERT INTO chunks_fts(chunks_fts,rank) VALUES('integrity-check',1)")
        return stats(path)


@contextmanager
def writer_lock(path: Path = REGISTRY_DB):
    """Serialize maintenance and ingestion across local processes; no daemon."""
    import fcntl
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix('.writer.lock').open('a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError('Another knowledge writer is running; retry after it finishes') from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
