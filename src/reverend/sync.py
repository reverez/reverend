from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
import uuid
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

from .metadata import bulk_metadata
from pathlib import Path

import yaml
from qdrant_client import models

from .cli import (
    COLLECTION,
    client,
    embed,
    save_state,
    text_chunks,
)

from .registry import (
    REGISTRY_DB,
    connect,
    initialize,
    now_utc,
    writer_lock,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "config/corpora.yaml"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


def load_corpora(
    config_path: Path = DEFAULT_CONFIG,
) -> dict[str, dict]:
    data = yaml.safe_load(
        config_path.read_text(encoding="utf-8")
    ) or {}

    corpora = data.get("corpora", {})

    if not isinstance(corpora, dict):
        raise ValueError(
            "corpora.yaml must contain a 'corpora' mapping."
        )

    result: dict[str, dict] = {}

    for corpus_id, config in corpora.items():
        if not isinstance(config, dict):
            continue

        if not config.get("enabled", True):
            continue

        raw_root = os.path.expandvars(
            os.path.expanduser(
                str(config.get("root", ""))
            )
        )

        root = Path(raw_root)

        if not root.is_absolute():
            root = PROJECT_ROOT / root

        extensions = [
            extension
            if str(extension).startswith(".")
            else f".{extension}"
            for extension in config.get(
                "extensions",
                [".md"],
            )
        ]

        result[str(corpus_id)] = {
            "id": str(corpus_id),
            "root": root.absolute(),
            "extensions": extensions,
            "trust_class": str(
                config.get(
                    "trust_class",
                    "TRUSTED_PERSONAL",
                )
            ),
        }

    return result


def enumerate_files(
    root: Path,
    extensions: list[str],
) -> list[Path]:
    if not root.exists():
        raise FileNotFoundError(
            f"Corpus root does not exist: {root}"
        )

    ripgrep = shutil.which("rg")

    if ripgrep:
        command = [
            ripgrep,
            "--files",
            "-0",
        ]

        for extension in extensions:
            command.extend(
                ["-g", f"*{extension}"]
            )

        process = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            check=False,
        )

        if process.returncode not in (0, 1):
            raise RuntimeError(
                process.stderr.decode(
                    "utf-8",
                    errors="replace",
                )
            )

        result = []

        for raw in process.stdout.split(b"\0"):
            if not raw:
                continue

            relative = raw.decode(
                "utf-8",
                errors="surrogateescape",
            )

            result.append(root / relative)

        return sorted(result)

    # Portable fallback. Normally rg will be used.
    wanted = {
        extension.lower()
        for extension in extensions
    }

    result = []

    for directory, directories, filenames in os.walk(root):
        directories[:] = [
            item
            for item in directories
            if item not in {
                ".git",
                ".obsidian",
                ".venv",
                "__pycache__",
            }
        ]

        base = Path(directory)

        for filename in filenames:
            path = base / filename

            if path.suffix.lower() in wanted:
                result.append(path)

    return sorted(result)


def _ensure_corpus(
    corpus_id: str,
    root: Path,
    db_path: Path,
) -> None:
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
            ON CONFLICT(id)
            DO UPDATE SET
                root_path = excluded.root_path,
                enabled = 1
            """,
            (
                corpus_id,
                str(root),
                now_utc(),
            ),
        )


def scan_corpus(
    corpus: dict,
    db_path: Path = REGISTRY_DB,
    *,
    record_baseline: bool = False,
) -> dict:
    started = time.monotonic()

    corpus_id = corpus["id"]
    root: Path = corpus["root"]
    extensions = corpus["extensions"]

    _ensure_corpus(
        corpus_id,
        root,
        db_path,
    )

    with ThreadPoolExecutor(max_workers=2) as pool:
        pending_metadata = pool.submit(bulk_metadata, root)
        files = enumerate_files(root, extensions)
        metadata, provider, metadata_error = pending_metadata.result()
    fallback_stats = 0

    current = {
        str(path): path
        for path in files
    }

    with connect(db_path) as db:
        stored = {
            row["source_path"]: dict(row)
            for row in db.execute(
                """
                SELECT
                    source_path,
                    sha256,
                    chunk_count,
                    trust_class,
                    size_bytes,
                    mtime_ns
                FROM documents
                WHERE corpus_id = ?
                """,
                (corpus_id,),
            )
        }

    with connect(db_path) as db:
        pending = {r[0] for r in db.execute(
            'SELECT source_path FROM pending_publications WHERE corpus_id=?', (corpus_id,))}

    unchanged = 0
    fast_unchanged = 0
    hash_verified_unchanged = 0
    changed = []
    new = []
    metadata_updates = []
    hashed_files = 0
    errors = []

    for source_path, path in current.items():
        old = stored.get(source_path)

        if old is None:
            new.append(source_path)
            continue

        if source_path in pending:
            changed.append(source_path)
            continue

        try:
            entry = metadata.get(source_path)
            if entry is None:
                stat = path.stat()
                size, mtime_ns = stat.st_size, stat.st_mtime_ns
                fallback_stats += 1
            else:
                size, mtime_ns = entry

            old_size = old.get("size_bytes")
            old_mtime = old.get("mtime_ns")

            if (
                old_size is not None
                and old_mtime is not None
                and int(old_size) == size
                and int(old_mtime) == mtime_ns
                and old.get("trust_class") == corpus["trust_class"]
            ):
                unchanged += 1
                fast_unchanged += 1
                continue

            digest = sha256_file(path)
            hashed_files += 1

            if digest == old["sha256"]:
                if old.get("trust_class") != corpus["trust_class"]:
                    changed.append(source_path)
                    continue

                unchanged += 1
                hash_verified_unchanged += 1

                if record_baseline:
                    metadata_updates.append(
                        (
                            size,
                            mtime_ns,
                            source_path,
                        )
                    )
            else:
                changed.append(source_path)

        except Exception as exc:
            errors.append(
                {
                    "path": source_path,
                    "error": str(exc),
                }
            )

    deleted = sorted(
        (set(stored) | pending)
        - set(current)
    )

    if record_baseline and metadata_updates:
        with connect(db_path) as db:
            db.executemany(
                """
                UPDATE documents
                SET
                    size_bytes = ?,
                    mtime_ns = ?
                WHERE source_path = ?
                """,
                metadata_updates,
            )

    return {
        "corpus": corpus_id,
        "root": str(root),
        "seen": len(current),
        "metadata_provider": provider,
        "metadata_fallback_stats": fallback_stats,
        "metadata_error": metadata_error,
        "registry_documents": len(stored),
        "unchanged": unchanged,
        "fast_unchanged": fast_unchanged,
        "hash_verified_unchanged": (
            hash_verified_unchanged
        ),
        "changed": len(changed),
        "new": len(new),
        "deleted": len(deleted),
        "hashed_files": hashed_files,
        "metadata_recorded": len(metadata_updates),
        "changed_paths": changed[:20],
        "new_paths": new[:20],
        "deleted_paths": deleted[:20],

        # Internal complete path lists used by --apply.
        # These are stripped before JSON is printed.
        "_changed_paths": list(changed),
        "_new_paths": list(new),
        "_deleted_paths": list(deleted),

        "errors": errors,
        "elapsed_seconds": round(
            time.monotonic() - started,
            3,
        ),
    }



def _source_filter(
    source_path: str,
    content_hash: str | None = None,
) -> models.Filter:
    conditions = [
        models.FieldCondition(
            key="source",
            match=models.MatchValue(
                value=source_path,
            ),
        )
    ]

    if content_hash is not None:
        conditions.append(
            models.FieldCondition(
                key="content_hash",
                match=models.MatchValue(
                    value=content_hash,
                ),
            )
        )

    return models.Filter(
        must=conditions,
    )


def _text_hash(text: str) -> str:
    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def _prepare_document(
    path: Path,
    *,
    corpus_id: str,
    trust_class: str,
) -> dict:
    """
    Parse and embed a document without mutating SQLite or Qdrant.

    This deliberately completes all expensive model work first so an
    embedding failure cannot destroy the previous working index.
    """
    source_path = str(path)
    stat = path.stat()
    digest = sha256_file(path)
    chunks = text_chunks(path)
    from .config import DATA_ROOT
    if path.resolve().is_relative_to((DATA_ROOT / 'drafts').resolve()):
        raise ValueError('Generated drafts cannot be ingested as evidence')
    if chunks and chunks[0][1].startswith('---'):
        parts = chunks[0][1].split('---', 2)
        metadata = yaml.safe_load(parts[1]) if len(parts) == 3 else None
        if isinstance(metadata, dict) and str(metadata.get('origin', '')).lower() in ('ai-generated', 'ai_generated'):
            raise ValueError('AI-generated notes require an explicit reviewed-source promotion before ingestion')
    if trust_class.upper().startswith(('AI_', 'GENERATED')):
        raise ValueError('AI-generated trust classes cannot be indexed as evidence')

    vectors: list[list[float]] = []

    for start in range(
        0,
        len(chunks),
        32,
    ):
        batch = chunks[
            start:start + 32
        ]

        vectors.extend(
            embed(
                [
                    content
                    for _, content, _ in batch
                ]
            )
        )

    if len(vectors) != len(chunks):
        raise RuntimeError(
            "Embedding count does not match chunk count "
            f"for {source_path}: "
            f"{len(vectors)} != {len(chunks)}"
        )

    after = path.stat()
    if (stat.st_size, stat.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or sha256_file(path) != digest:
        raise RuntimeError('Source changed during preparation; retry without publishing')

    ingested_at = datetime.now(
        timezone.utc
    ).isoformat()

    rows = []
    points = []

    for index, (
        (section, content, page),
        vector,
    ) in enumerate(
        zip(chunks, vectors)
    ):
        point_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"{source_path}:{digest}:{index}",
            )
        )

        payload = {
            "chunk_id": point_id,
            "source": source_path,
            "source_type": (
                path.suffix.lower().lstrip(".")
            ),
            "source_title": path.stem,
            "section": section,
            "page": page,
            "content_hash": digest,
            "modified_time": (
                datetime.fromtimestamp(
                    stat.st_mtime,
                    timezone.utc,
                ).isoformat()
            ),
            "ingestion_time": ingested_at,
            "trust_class": trust_class,
            "corpus": corpus_id,

            # Keep text in Qdrant during the compatibility phase.
            # Later SQLite becomes the canonical chunk-text store.
            "content": content,
        }

        points.append(
            models.PointStruct(
                id=point_id,
                vector=vector,
                payload=payload,
            )
        )

        rows.append(
            (
                point_id,
                source_path,
                index,
                section,
                page,
                content,
                _text_hash(content),
            )
        )

    return {
        "source_path": source_path,
        "sha256": digest,
        "size_bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "chunks": chunks,
        "rows": rows,
        "points": points,
        "corpus_id": corpus_id,
        "trust_class": trust_class,
        "ingested_at": ingested_at,
    }


def _apply_document(
    source_path: str,
    corpus: dict,
    db_path: Path,
) -> dict:
    path = Path(source_path)

    if not path.exists():
        raise FileNotFoundError(
            source_path
        )

    corpus_id = corpus["id"]
    trust_class = corpus["trust_class"]

    # --------------------------------------------------------------
    # Stage 1:
    # Complete parsing + embeddings before changing the live index.
    # --------------------------------------------------------------

    prepared = _prepare_document(
        path,
        corpus_id=corpus_id,
        trust_class=trust_class,
    )

    new_hash = prepared["sha256"]
    points = prepared["points"]

    # --------------------------------------------------------------
    # Stage 2:
    # Publish new points first.
    #
    # Deterministic UUIDs make this operation idempotent.
    # --------------------------------------------------------------

    # Journal before crossing stores. Even if the source later reverts/disappears,
    # a retry must reconcile vectors instead of accepting a metadata-only no-op.
    with connect(db_path) as db:
        db.execute('INSERT OR REPLACE INTO pending_publications VALUES(?,?,?)',
                   (source_path, corpus_id, now_utc()))

    if points:
        store = client()

        for start in range(
            0,
            len(points),
            256,
        ):
            store.upsert(
                COLLECTION,
                points=points[
                    start:start + 256
                ],
                wait=True,
            )

        # Remove all other generations, including a partial publication from an
        # interrupted earlier attempt. Never remove the generation just published.
        store.delete(COLLECTION, points_selector=models.FilterSelector(filter=models.Filter(
            must=_source_filter(source_path).must,
            must_not=[models.FieldCondition(key='content_hash', match=models.MatchValue(value=new_hash))],
        )), wait=True)
    else:
        # A successfully prepared empty document removes every old generation.
        client().delete(COLLECTION, points_selector=models.FilterSelector(
            filter=_source_filter(source_path)), wait=True)

    # --------------------------------------------------------------
    # Stage 3:
    # Commit canonical V2 metadata/chunk text only after Qdrant succeeds.
    # --------------------------------------------------------------

    with connect(db_path) as db:
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
            VALUES (?, ?, ?, ?, ?, 'indexed', ?, ?, ?)
            ON CONFLICT(source_path)
            DO UPDATE SET
                corpus_id = excluded.corpus_id,
                sha256 = excluded.sha256,
                chunk_count = excluded.chunk_count,
                trust_class = excluded.trust_class,
                status = 'indexed',
                indexed_at = excluded.indexed_at,
                size_bytes = excluded.size_bytes,
                mtime_ns = excluded.mtime_ns
            """,
            (
                source_path,
                corpus_id,
                new_hash,
                len(prepared["rows"]),
                trust_class,
                prepared["ingested_at"],
                prepared["size_bytes"],
                prepared["mtime_ns"],
            ),
        )

        db.execute(
            """
            DELETE FROM chunks
            WHERE source_path = ?
            """,
            (source_path,),
        )

        if prepared["rows"]:
            db.executemany(
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
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                prepared["rows"],
            )

        db.execute('DELETE FROM pending_publications WHERE source_path=?', (source_path,))

    return {
        "source": source_path,
        "sha256": new_hash,
        "chunks": len(prepared["rows"]),
    }


def _delete_document(
    source_path: str,
    db_path: Path,
) -> None:
    # Qdrant first.
    #
    # If the process dies after this operation but before SQLite commits,
    # the next sync still sees the stale registry row and safely retries
    # the same deletion.
    store = client()

    store.delete(
        COLLECTION,
        points_selector=(
            models.FilterSelector(
                filter=_source_filter(
                    source_path
                )
            )
        ),
    )

    with connect(db_path) as db:
        db.execute(
            """
            DELETE FROM documents
            WHERE source_path = ?
            """,
            (source_path,),
        )
        db.execute('DELETE FROM pending_publications WHERE source_path=?', (source_path,))


def _reconcile_legacy_state(
    db_path: Path,
) -> None:
    """
    Keep V1 state.json synchronized during the transition period.

    status(), doctor(), and the older ingest command still read this file.
    SQLite remains the new authoritative registry.
    """
    with connect(db_path) as db:
        rows = db.execute(
            """
            SELECT
                source_path,
                sha256,
                chunk_count,
                corpus_id,
                trust_class
            FROM documents
            WHERE status = 'indexed'
            """
        ).fetchall()

    sources = {}

    for row in rows:
        sources[row["source_path"]] = {
            "hash": row["sha256"],
            "chunks": row["chunk_count"],
            "corpus": row["corpus_id"],
            "trust_class": row["trust_class"],
        }

    save_state(
        {
            "sources": sources,
        }
    )


def _apply_corpus(
    corpus: dict,
    report: dict,
    db_path: Path,
) -> dict:
    indexed = []
    deleted = []
    errors = []

    work = (
        report["_new_paths"]
        + report["_changed_paths"]
    )

    # Deduplicate while preserving discovery order.
    work = list(
        dict.fromkeys(work)
    )

    for source_path in work:
        try:
            indexed.append(
                _apply_document(
                    source_path,
                    corpus,
                    db_path,
                )
            )
        except Exception as exc:
            errors.append(
                {
                    "path": source_path,
                    "operation": "index",
                    "error": str(exc),
                }
            )

    for source_path in report["_deleted_paths"]:
        try:
            _delete_document(
                source_path,
                db_path,
            )

            deleted.append(
                source_path
            )

        except Exception as exc:
            errors.append(
                {
                    "path": source_path,
                    "operation": "delete",
                    "error": str(exc),
                }
            )

    return {
        "indexed_documents": len(indexed),
        "indexed_chunks": sum(
            item["chunks"]
            for item in indexed
        ),
        "deleted_documents": len(deleted),
        "indexed": indexed[:20],
        "deleted": deleted[:20],
        "errors": errors,
    }


def _public_report(
    report: dict,
) -> dict:
    return {
        key: value
        for key, value in report.items()
        if not key.startswith("_")
    }


def _command_sync(
    *,
    dry_run: bool,
    record_baseline: bool,
    apply: bool,
    config_path: Path = DEFAULT_CONFIG,
    db_path: Path = REGISTRY_DB,
) -> int:
    modes = sum(
        bool(value)
        for value in (
            dry_run,
            record_baseline,
            apply,
        )
    )

    if modes != 1:
        print(
            "Choose exactly one of "
            "--dry-run, --record-baseline, or --apply."
        )
        return 2

    corpora = load_corpora(
        config_path
    )

    reports = []
    apply_reports = []

    for corpus in corpora.values():
        report = scan_corpus(
            corpus,
            db_path,
            record_baseline=(
                record_baseline
                or apply
            ),
        )

        reports.append(
            report
        )

        if apply:
            apply_reports.append(
                {
                    "corpus": corpus["id"],
                    **_apply_corpus(
                        corpus,
                        report,
                        db_path,
                    ),
                }
            )

    if apply:
        # Repair/rebuild the legacy state file every apply run, even when
        # there were no file changes. This makes dual-write failures
        # recoverable on the next run.
        _reconcile_legacy_state(
            db_path
        )

    public_reports = [
        _public_report(report)
        for report in reports
    ]

    payload = {
        "mode": (
            "apply"
            if apply
            else (
                "record-baseline"
                if record_baseline
                else "dry-run"
            )
        ),
        "corpora": public_reports,
        "apply": apply_reports,
        "totals": {
            "seen": sum(
                item["seen"]
                for item in reports
            ),
            "unchanged": sum(
                item["unchanged"]
                for item in reports
            ),
            "changed": sum(
                item["changed"]
                for item in reports
            ),
            "new": sum(
                item["new"]
                for item in reports
            ),
            "deleted": sum(
                item["deleted"]
                for item in reports
            ),
            "hashed_files": sum(
                item["hashed_files"]
                for item in reports
            ),
            "metadata_recorded": sum(
                item["metadata_recorded"]
                for item in reports
            ),
            "indexed_documents": sum(
                item["indexed_documents"]
                for item in apply_reports
            ),
            "indexed_chunks": sum(
                item["indexed_chunks"]
                for item in apply_reports
            ),
            "deleted_documents": sum(
                item["deleted_documents"]
                for item in apply_reports
            ),
        },
    }

    print(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        )
    )

    scan_errors = any(
        report["errors"]
        for report in reports
    )

    apply_errors = any(
        report["errors"]
        for report in apply_reports
    )

    if apply and not scan_errors and not apply_errors:
        with connect(db_path) as db:
            for corpus in corpora.values():
                db.execute('INSERT OR REPLACE INTO meta VALUES(?,?)',
                           ('last_sync_' + corpus['id'], now_utc()))

    return (
        1
        if scan_errors or apply_errors
        else 0
    )


def command_sync(*, dry_run: bool, record_baseline: bool, apply: bool,
                 config_path: Path = DEFAULT_CONFIG, db_path: Path = REGISTRY_DB) -> int:
    with writer_lock(db_path):
        return _command_sync(dry_run=dry_run, record_baseline=record_baseline, apply=apply,
                             config_path=config_path, db_path=db_path)


def ingest_path(root: Path, trust: str, corpus_id: str, db_path: Path = REGISTRY_DB) -> dict:
    """Legacy ingest API, now using SQLite and the safe replacement protocol."""
    root = root.absolute()
    if not root.exists():
        raise FileNotFoundError(root)
    from .cli import source_files
    with writer_lock(db_path):
        _ensure_corpus(corpus_id, root.parent if root.is_file() else root, db_path)
        files = ([root] if root.is_file() else enumerate_files(root, ['.md'])
                 if corpus_id == 'obsidian' else source_files(root))
        current = {str(p):p for p in files}
        with connect(db_path) as db:
            stored = {r['source_path']:dict(r) for r in db.execute('SELECT * FROM documents')}
            pending = {r['source_path']:dict(r) for r in db.execute('SELECT * FROM pending_publications')}
        corpus = {'id':corpus_id,'trust_class':trust}
        report = {'files_seen':len(files),'files_indexed':0,'files_skipped':0,
                  'chunks_written':0,'removed':0,'errors':[]}
        for key,path in current.items():
            try:
                old=stored.get(key)
                if (key not in pending and old and old['sha256']==sha256_file(path) and old['trust_class']==trust
                        and old['corpus_id']==corpus_id):
                    report['files_skipped']+=1
                    continue
                result=_apply_document(key,corpus,db_path)
                report['files_indexed']+=1
                report['chunks_written']+=result['chunks']
            except Exception as exc:
                report['errors'].append({'path':key,'operation':'index','error':str(exc)})
        # A single-file ingest must never delete sibling documents.
        for key,old in {**pending, **stored}.items():
            if old['corpus_id']==corpus_id and Path(key).is_relative_to(root) and key not in current:
                try:
                    _delete_document(key,db_path)
                    report['removed']+=1
                except Exception as exc:
                    report['errors'].append({'path':key,'operation':'delete','error':str(exc)})
        _reconcile_legacy_state(db_path)
        return report
