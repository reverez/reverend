"""Explicit, restart-safe index maintenance. Run with ingestion stopped."""
from __future__ import annotations

import hashlib
import time
from pathlib import Path

from .registry import REGISTRY_DB, connect, initialize, now_utc, stats, writer_lock


def _backfill_chunks(store, collection: str, db_path: Path = REGISTRY_DB, batch_size: int = 512) -> dict:
    if batch_size < 1:
        raise ValueError('batch_size must be positive')
    initialize(db_path)
    started = time.monotonic()
    offset = None
    report = dict(scrolled=0, upserted=0, orphans=0, stale=0, invalid=0, examples=[])
    while True:
        points, next_offset = store.scroll(
            collection, limit=batch_size, offset=offset, with_payload=True, with_vectors=False,
        )
        with connect(db_path) as db:
            for point in points:
                report['scrolled'] += 1
                payload = point.payload or {}
                source, content = payload.get('source'), payload.get('content')
                row = db.execute(
                    'SELECT sha256, corpus_id, trust_class FROM documents WHERE source_path=?', (source,),
                ).fetchone()
                problem = None
                if row is None:
                    problem = 'orphans'
                elif not isinstance(content, str) or not content.strip() or payload.get('chunk_id', str(point.id)) != str(point.id):
                    problem = 'invalid'
                elif (payload.get('content_hash') != row['sha256']
                      or payload.get('corpus') != row['corpus_id']
                      or payload.get('trust_class') != row['trust_class']):
                    problem = 'stale'
                if problem:
                    report[problem] += 1
                    if len(report['examples']) < 20:
                        report['examples'].append({'id': str(point.id), 'problem': problem})
                    continue
                db.execute('''INSERT INTO chunks(chunk_id,source_path,ordinal,section,page,text,text_hash)
                    VALUES(?,?,NULL,?,?,?,?) ON CONFLICT(chunk_id) DO UPDATE SET
                    source_path=excluded.source_path,section=excluded.section,page=excluded.page,
                    text=excluded.text,text_hash=excluded.text_hash''',
                    (str(point.id), source, payload.get('section'), payload.get('page'), content,
                     hashlib.sha256(content.encode('utf-8')).hexdigest()))
                report['upserted'] += 1
        if next_offset is None:
            break
        if next_offset == offset:
            raise RuntimeError('Qdrant scroll cursor did not advance')
        offset = next_offset
    with connect(db_path) as db:
        mismatch = db.execute('''SELECT d.source_path,d.chunk_count,COUNT(c.chunk_id) AS actual
            FROM documents d LEFT JOIN chunks c USING(source_path)
            GROUP BY d.source_path HAVING d.chunk_count != COUNT(c.chunk_id)''').fetchall()
        report['document_count_mismatches'] = len(mismatch)
        report['qdrant_points'] = store.count(collection, exact=True).count
        report.update(stats(db_path))
        report['ok'] = (
            not any(report[k] for k in ('orphans', 'stale', 'invalid', 'document_count_mismatches', 'pending_publications'))
            and report['scrolled'] == report['qdrant_points'] == report['materialized_chunks'] == report['declared_chunks']
        )
        if report['ok']:
            db.execute("INSERT OR REPLACE INTO meta VALUES('chunk_backfill_verified_at',?)", (now_utc(),))
    report['elapsed_seconds'] = round(time.monotonic() - started, 3)
    return report


def backfill_chunks(store, collection: str, db_path: Path = REGISTRY_DB, batch_size: int = 512) -> dict:
    with writer_lock(db_path):
        return _backfill_chunks(store, collection, db_path, batch_size)
