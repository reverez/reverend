"""Cheap offline status; expensive model/vector validation is opt-in."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from .config import COLLECTION, QDRANT_URL
from .registry import REGISTRY_DB


def snapshot(db_path: Path = REGISTRY_DB) -> dict:
    result = {'qdrant_mode':'server' if QDRANT_URL else 'embedded', 'collection':COLLECTION,
              'qdrant_points':None, 'qdrant_points_note':'Not opened; use doctor --deep for a live count',
              'database':str(db_path)}
    if not db_path.exists():
        return {**result,'registry':'missing'}
    with sqlite3.connect(db_path.absolute().as_uri()+'?mode=ro',uri=True) as db:
        tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        result.update(registry='ready',schema_version=int(db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]),
                      documents=db.execute('SELECT COUNT(*) FROM documents').fetchone()[0],
                      chunks=db.execute('SELECT COUNT(*) FROM chunks').fetchone()[0],
                      declared_chunks=db.execute('SELECT COALESCE(SUM(chunk_count),0) FROM documents').fetchone()[0],
                      last_indexed_at=db.execute('SELECT MAX(indexed_at) FROM documents').fetchone()[0],
                      corpora=dict(db.execute('SELECT corpus_id,COUNT(*) FROM documents GROUP BY corpus_id')),
                      fts_chunks=db.execute('SELECT COUNT(*) FROM chunks_fts_docsize').fetchone()[0] if 'chunks_fts_docsize' in tables else None,
                      pending_publications=db.execute('SELECT COUNT(*) FROM pending_publications').fetchone()[0] if 'pending_publications' in tables else 0)
        result['last_sync_at']=dict(db.execute("SELECT key,value FROM meta WHERE key LIKE 'last_sync_%'"))
    return result


def check(deep: bool = False, db_path: Path = REGISTRY_DB) -> dict:
    from .cli import TEMPLATE, api, embed
    result={'status':snapshot(db_path),'checks':{},'deep':deep}
    checks=result['checks']
    checks['registry']=result['status'].get('registry')=='ready'
    checks['template']=TEMPLATE.is_file()
    if checks['registry']:
        checks['chunk_counts']=(result['status']['chunks']==result['status']['declared_chunks']==result['status']['fts_chunks'])
        checks['no_pending_publications']=result['status']['pending_publications']==0
    try:
        checks['ollama_reachable']=isinstance(api('/api/tags',timeout=5).get('models'),list)
    except Exception as exc:
        checks['ollama_reachable']=type(exc).__name__
    if deep:
        from .config import qdrant_client
        from .retrieve import retrieve_dense
        try:
            vector=embed(['knowledge health check'])[0]
            checks['embedding_dimensions']=len(vector)==1024
            store=qdrant_client()
            count=store.count(COLLECTION,exact=True).count
            result['status']['qdrant_points']=count
            checks['qdrant_counts']=count==result['status'].get('chunks')
            checks['dense_query']=bool(retrieve_dense('knowledge health check',1,db_path=db_path,store=store,query_vector=vector))
        except Exception as exc:
            checks['dense_query']=type(exc).__name__
        if checks['registry']:
            with sqlite3.connect(db_path.absolute().as_uri()+'?mode=ro',uri=True) as db:
                checks['sqlite_integrity']=db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
                checks['foreign_keys']=not db.execute('PRAGMA foreign_key_check').fetchall()
    result['ok']=all(value is True for value in checks.values())
    return result
