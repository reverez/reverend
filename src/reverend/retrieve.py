"""Independent lexical/dense retrieval and transparent reciprocal rank fusion."""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from .registry import REGISTRY_DB


def match_expression(query: str) -> str:
    # Quote individual Unicode words. User punctuation/operators are never FTS syntax.
    words = list(dict.fromkeys(re.findall(r'[^\W_]+', query.lower(), re.UNICODE)))[:64]
    return ' OR '.join('"' + word + '"' for word in words)


def retrieve_lexical(query: str, limit: int = 5, *, corpus: str | None = None,
                     trust: str | None = None, db_path: Path = REGISTRY_DB) -> list[dict]:
    expression = match_expression(query)
    if not expression or limit <= 0:
        return []
    conditions, values = ["chunks_fts MATCH ?", "d.status='indexed'"], [expression]
    for field, value in [('corpus_id', corpus), ('trust_class', trust)]:
        if value:
            conditions.append(f'd.{field}=?')
            values.append(value)
    with sqlite3.connect(db_path.absolute().as_uri() + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute(f'''SELECT c.chunk_id,c.source_path AS source,c.section,c.page,
            c.text AS content,d.sha256 AS content_hash,d.corpus_id AS corpus,d.trust_class,
            bm25(chunks_fts,3.0,1.0) AS bm25_score FROM chunks_fts
            JOIN chunks c ON c.rowid=chunks_fts.rowid JOIN documents d USING(source_path)
            WHERE {' AND '.join(conditions)} ORDER BY bm25_score,c.chunk_id LIMIT ?''',
            [*values, max(limit * 2, 20)]).fetchall()
    result = []
    for rank, row in enumerate(rows, 1):
        item = dict(row)
        if not evidence_allowed(item):
            continue
        item.update(source_title=Path(item['source']).stem, lexical_rank=len(result) + 1,
                    lexical_score=-item.pop('bm25_score'))
        item['relevance'] = item['lexical_score']
        result.append(item)
    return result[:limit]


def evidence_allowed(row: dict) -> bool:
    """Unreviewed AI output is never evidence, regardless of query mode."""
    trust = str(row.get('trust_class', '')).upper()
    source = str(row.get('source', '')).replace('\\', '/').lower()
    return not (trust.startswith(('AI_', 'GENERATED')) or '/drafts/' in source
                or str(row.get('origin', '')).lower() in ('ai-generated', 'ai_generated'))


def source_role(row: dict) -> str:
    source = str(row.get('source', '')).replace('\\', '/').lower()
    if '/source library/' in source or '/source-library/' in source:
        return 'catalogue'
    return 'material'


def retrieve_dense(query: str, limit: int = 5, *, corpus: str | None = None,
                   trust: str | None = None, db_path: Path = REGISTRY_DB,
                   store=None, query_vector=None) -> list[dict]:
    if not query.strip() or limit <= 0:
        return []
    from qdrant_client import models
    from .config import COLLECTION, qdrant_client
    from .cli import embed
    conditions = [models.FieldCondition(key=key, match=models.MatchValue(value=value))
                  for key, value in [('corpus', corpus), ('trust_class', trust)] if value]
    vector = query_vector if query_vector is not None else embed([query])[0]
    points = (store if store is not None else qdrant_client()).query_points(
        COLLECTION, query=vector, query_filter=models.Filter(must=conditions) if conditions else None,
        with_payload=['content_hash'], with_vectors=False, limit=max(limit * 2, 20),
    ).points
    if not points:
        return []
    with sqlite3.connect(db_path.absolute().as_uri() + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        placeholders = ','.join('?' for _ in points)
        rows = db.execute(f'''SELECT c.chunk_id,c.source_path AS source,c.section,c.page,
            c.text AS content,d.sha256 AS content_hash,d.corpus_id AS corpus,d.trust_class
            FROM chunks c JOIN documents d USING(source_path)
            WHERE d.status='indexed' AND c.chunk_id IN ({placeholders})''',
            [str(p.id) for p in points]).fetchall()
    canonical = {r['chunk_id']: dict(r) for r in rows}
    result, stale = [], 0
    for point in points:
        item = canonical.get(str(point.id))
        if item is None or (point.payload or {}).get('content_hash') != item['content_hash']:
            stale += 1
            continue
        if not evidence_allowed(item) or (corpus and item['corpus'] != corpus) or (trust and item['trust_class'] != trust):
            continue
        item.update(source_title=Path(item['source']).stem, dense_score=float(point.score),
                    dense_rank=len(result) + 1, relevance=float(point.score))
        result.append(item)
    if stale:
        import warnings
        warnings.warn(f'{stale} dense candidates missing current SQLite chunks; run backfill/reconciliation', RuntimeWarning)
    return result[:limit]


def fuse_rrf(dense: list[dict], lexical: list[dict], limit: int = 5, k: int = 60) -> list[dict]:
    if k < 1:
        raise ValueError('RRF k must be positive')
    merged = {}
    for mode, rows in [('dense', dense), ('lexical', lexical)]:
        seen = set()
        for row in rows:
            identity = row['chunk_id']
            if identity in seen or not evidence_allowed(row):
                continue
            seen.add(identity)
            rank = len(seen)
            item = merged.setdefault(identity, {**row, 'rrf_score': 0.0})
            item[mode + '_rank'] = rank
            item[mode + '_score'] = row.get(mode + '_score', row.get('relevance'))
            item['rrf_score'] += 1.0 / (k + rank)
    for item in merged.values():
        item['source_role'] = source_role(item)
        item['relevance'] = item['rrf_score']
    # Catalogue records remain searchable, but substantive material ranks first.
    return sorted(merged.values(), key=lambda r: (r['source_role'] == 'catalogue', -r['rrf_score'], r['chunk_id']))[:max(limit, 0)]


def retrieve_hybrid(query: str, limit: int = 5, *, candidates: int = 50, k: int = 60,
                    corpus: str | None = None, trust: str | None = None,
                    db_path: Path = REGISTRY_DB, store=None, query_vector=None) -> list[dict]:
    if not query.strip() or limit <= 0:
        return []
    count = max(limit, candidates)
    dense = retrieve_dense(query, count, corpus=corpus, trust=trust, db_path=db_path,
                           store=store, query_vector=query_vector)
    lexical = retrieve_lexical(query, count, corpus=corpus, trust=trust, db_path=db_path)
    return fuse_rrf(dense, lexical, limit, k)
