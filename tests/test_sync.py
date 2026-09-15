from __future__ import annotations

import hashlib
from pathlib import Path

from reverend.registry import (
    connect,
    initialize,
    now_utc,
)
from reverend.sync import scan_corpus


def digest(text: str) -> str:
    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def test_sync_baseline_and_change_detection(
    tmp_path: Path,
):
    root = tmp_path / "corpus"
    root.mkdir()

    original = root / "a.md"
    original.write_text(
        "alpha\n",
        encoding="utf-8",
    )

    db_path = tmp_path / "platform.db"
    initialize(db_path)

    with connect(db_path) as db:
        db.execute(
            """
            INSERT INTO corpora(
                id,
                root_path,
                enabled,
                created_at
            )
            VALUES (?, ?, 1, ?)
            """,
            (
                "test",
                str(root),
                now_utc(),
            ),
        )

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
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(original),
                "test",
                digest("alpha\n"),
                1,
                "TRUSTED_PERSONAL",
                "indexed",
                now_utc(),
            ),
        )

    corpus = {
        "id": "test",
        "root": root,
        "extensions": [".md"],
        "trust_class": "TRUSTED_PERSONAL",
    }

    first = scan_corpus(
        corpus,
        db_path,
        record_baseline=False,
    )

    assert first["unchanged"] == 1
    assert first["hashed_files"] == 1
    assert first["fast_unchanged"] == 0

    baseline = scan_corpus(
        corpus,
        db_path,
        record_baseline=True,
    )

    assert baseline["unchanged"] == 1
    assert baseline["metadata_recorded"] == 1

    second = scan_corpus(
        corpus,
        db_path,
        record_baseline=False,
    )

    assert second["unchanged"] == 1
    assert second["fast_unchanged"] == 1
    assert second["hashed_files"] == 0

    original.write_text(
        "alpha changed\n",
        encoding="utf-8",
    )

    changed = scan_corpus(
        corpus,
        db_path,
        record_baseline=False,
    )

    assert changed["changed"] == 1
    assert changed["hashed_files"] == 1

    new_file = root / "b.md"
    new_file.write_text(
        "new file\n",
        encoding="utf-8",
    )

    with_new = scan_corpus(
        corpus,
        db_path,
        record_baseline=False,
    )

    assert with_new["new"] == 1

    original.unlink()

    deleted = scan_corpus(
        corpus,
        db_path,
        record_baseline=False,
    )

    assert deleted["deleted"] == 1


def test_sync_detects_trust_change(
    tmp_path: Path,
):
    root = tmp_path / "corpus"
    root.mkdir()

    document = root / "a.md"
    document.write_text(
        "alpha\n",
        encoding="utf-8",
    )

    db_path = tmp_path / "platform.db"
    initialize(db_path)

    stat = document.stat()

    with connect(db_path) as db:
        db.execute(
            """
            INSERT INTO corpora(
                id,
                root_path,
                enabled,
                created_at
            )
            VALUES (?, ?, 1, ?)
            """,
            (
                "test",
                str(root),
                now_utc(),
            ),
        )

        db.execute(
            """
            INSERT INTO documents(
                source_path,
                corpus_id,
                sha256,
                chunk_count,
                trust_class,
                status,
                indexed_at,
                size_bytes,
                mtime_ns
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(document),
                "test",
                digest("alpha\n"),
                1,
                "OLD_TRUST",
                "indexed",
                now_utc(),
                stat.st_size,
                stat.st_mtime_ns,
            ),
        )

    corpus = {
        "id": "test",
        "root": root,
        "extensions": [".md"],
        "trust_class": "NEW_TRUST",
    }

    report = scan_corpus(
        corpus,
        db_path,
        record_baseline=False,
    )

    assert report["changed"] == 1
    assert report["unchanged"] == 0


def test_registry_cascade_removes_chunks(
    tmp_path: Path,
):
    db_path = tmp_path / "platform.db"
    initialize(db_path)

    with connect(db_path) as db:
        db.execute(
            """
            INSERT INTO corpora(
                id,
                root_path,
                enabled,
                created_at
            )
            VALUES ('test', '/tmp', 1, ?)
            """,
            (now_utc(),),
        )

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
            VALUES (
                '/tmp/a.md',
                'test',
                'abc',
                1,
                'TRUSTED_PERSONAL',
                'indexed',
                ?
            )
            """,
            (now_utc(),),
        )

        db.execute(
            """
            INSERT INTO chunks(
                chunk_id,
                source_path,
                ordinal,
                section,
                page,
                text,
                text_hash
            )
            VALUES (
                'chunk-1',
                '/tmp/a.md',
                0,
                'A',
                NULL,
                'hello',
                'hash'
            )
            """
        )

        db.execute(
            """
            DELETE FROM documents
            WHERE source_path = '/tmp/a.md'
            """
        )

        remaining = db.execute(
            "SELECT COUNT(*) FROM chunks"
        ).fetchone()[0]

    assert remaining == 0
