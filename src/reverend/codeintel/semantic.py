"""Opt-in, reconstructable code_vectors_v1 index; current text remains authoritative."""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import time
from dataclasses import replace
from pathlib import Path

from reverend.config import DATA_ROOT
from reverend.runtime import ModelRole
from .repository import scan_repository
from .retrieval import CodeHit,CodeSearchResult,search_code

INDEX = DATA_ROOT/'code-vectors-v1.db'
SCHEMA = '''
CREATE TABLE IF NOT EXISTS code_indexes_v1(repo_id TEXT PRIMARY KEY,commit_id TEXT NOT NULL,
 model TEXT NOT NULL,digest TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS code_vectors_v1(repo_id TEXT NOT NULL,commit_id TEXT NOT NULL,path TEXT NOT NULL,
 language TEXT,symbol TEXT,content_hash TEXT NOT NULL,chunk_type TEXT NOT NULL,line_start INTEGER NOT NULL,
 line_end INTEGER NOT NULL,vector TEXT NOT NULL,PRIMARY KEY(repo_id,path,line_start));
'''

def _repo_id(root):
    # Git common-dir makes the index usable in isolated worktrees of this repository.
    import subprocess
    result=subprocess.run(['git','-C',str(root),'rev-parse','--path-format=absolute','--git-common-dir'],
        check=True,capture_output=True,text=True,timeout=10)
    return hashlib.sha256(result.stdout.strip().encode()).hexdigest()


def _identity(scheduler):
    resolved=scheduler.registry.resolve(ModelRole.EMBED)
    if not resolved.digest:raise ValueError('Embedding model digest is required for a versioned index')
    return resolved.spec.model,resolved.digest


def _vector(value):
    if not isinstance(value,list) or not value or len(value)>4096:raise ValueError('Invalid embedding dimensions')
    if any(not isinstance(x,(int,float)) or not math.isfinite(x) for x in value):raise ValueError('Invalid embedding values')
    norm=math.sqrt(sum(x*x for x in value))
    if not norm:raise ValueError('Zero embedding vector')
    return [x/norm for x in value]


def build_index(root, scheduler, *, db_path=INDEX, paths=None, max_files=200, max_chunks=256):
    if not 1<=max_files<=500 or not 1<=max_chunks<=1024:raise ValueError('Invalid indexing budget')
    profile=scan_repository(root,history_limit=0)
    if profile.is_dirty:raise ValueError('Index a clean commit; working changes remain a live lexical overlay')
    selected=set(paths) if paths else None
    eligible=[f for f in profile.files if f.language and not f.is_symlink and f.size_bytes<=128000 and (selected is None or f.path in selected)]
    if selected and selected-{f.path for f in eligible}:raise ValueError('Selected paths must be bounded regular source files')
    if len(eligible)>max_files:raise ValueError('Repository exceeds indexing budget; select explicit paths')
    chunks=[];total=0
    for file in eligible:
        target=(profile.root/file.path).resolve()
        if not target.is_relative_to(profile.root.resolve()):continue
        raw=target.read_bytes()
        if len(raw)>128000 or b'\0' in raw:continue
        content=raw.decode('utf-8',errors='replace');lines=content.splitlines();digest=hashlib.sha256(raw).hexdigest()
        for start in range(0,len(lines),60):
            text='\n'.join(lines[start:start+80])[:6000]
            total+=len(text)
            if total>1_000_000 or len(chunks)>=max_chunks:raise ValueError('Repository exceeds chunk budget; select explicit paths')
            # Chunk boundaries and hash are deterministic and independent of the model.
            chunks.append({'path':file.path,'language':file.language,'symbol':None,'content_hash':digest,
                'chunk_type':'line_window_v1','line_start':start+1,'line_end':min(start+80,len(lines)),
                'text':f'{file.path}\n{text}'})
    if not chunks:raise ValueError('No source chunks selected')
    model,digest=_identity(scheduler);vectors=[];started=time.monotonic()
    for start in range(0,len(chunks),16):vectors.extend(_vector(v) for v in scheduler.embed([r['text'] for r in chunks[start:start+16]]))
    if len(vectors)!=len(chunks) or len({len(v) for v in vectors})!=1:raise ValueError('Embedding shape mismatch')
    final=scan_repository(root,history_limit=0)
    if final.head_commit!=profile.head_commit or final.is_dirty or _identity(scheduler)!=(model,digest):
        raise ValueError('Repository or embedding model changed during indexing; nothing published')
    repo_id=_repo_id(profile.root);db_path=Path(db_path);db_path.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(db_path) as db:
        db.executescript(SCHEMA)
        db.execute('DELETE FROM code_vectors_v1 WHERE repo_id=?',(repo_id,))
        db.execute('INSERT OR REPLACE INTO code_indexes_v1(repo_id,commit_id,model,digest) VALUES(?,?,?,?)',(repo_id,profile.head_commit,model,digest))
        for chunk,vector in zip(chunks,vectors):
            db.execute('INSERT INTO code_vectors_v1 VALUES(?,?,?,?,?,?,?,?,?,?)',(repo_id,profile.head_commit,
                chunk['path'],chunk['language'],chunk['symbol'],chunk['content_hash'],chunk['chunk_type'],
                chunk['line_start'],chunk['line_end'],json.dumps(vector)))
    return {'collection':'code_vectors_v1','repo_id':repo_id,'commit':profile.head_commit,'model':model,'digest':digest,
        'files':len(eligible),'chunks':len(chunks),'elapsed_seconds':round(time.monotonic()-started,4)}


def augment(root,query,scheduler,*,db_path=INDEX,limit=12):
    """Blend current lexical/structural results and valid semantic hits with weighted RRF."""
    started=time.monotonic()
    lexical=search_code(root,query,limit=max(limit,50))
    def result(status,search=lexical):
        return replace(search,hits=search.hits[:limit]),{'semantic_status':status,'elapsed_seconds':round(time.monotonic()-started,4)}
    db_path=Path(db_path)
    if not db_path.exists():return result('not indexed; structural and lexical retrieval')
    profile=scan_repository(root,history_limit=0);repo_id=_repo_id(profile.root)
    with sqlite3.connect(db_path.absolute().as_uri()+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        index=db.execute('SELECT * FROM code_indexes_v1 WHERE repo_id=?',(repo_id,)).fetchone()
        if not index:return result('not indexed; structural and lexical retrieval')
        if index['commit_id']!=profile.head_commit:return result('stale commit ignored; rebuild index')
        rows=db.execute('SELECT * FROM code_vectors_v1 WHERE repo_id=? LIMIT 1025',(repo_id,)).fetchall()
    if len(rows)>1024:return result('index exceeds query budget')
    if scheduler is None:return result('semantic query requires local scheduler')
    try:
        if _identity(scheduler)!=(index['model'],index['digest']):return result('stale embedding model ignored; rebuild index')
        query_vector=_vector(scheduler.embed([query[:6000]])[0])
    except Exception:return result('local embeddings unavailable; structural and lexical retrieval')
    current={f.path:f for f in profile.files};hashes={};semantic={};stale=0
    for row in rows:
        path=row['path'];file=current.get(path)
        if file is None or file.is_symlink or file.size_bytes>128000:stale+=1;continue
        if path not in hashes:
            target=(profile.root/path).resolve()
            hashes[path]=hashlib.sha256(target.read_bytes()).hexdigest() if target.is_relative_to(profile.root.resolve()) else None
        if hashes[path]!=row['content_hash']:stale+=1;continue
        vector=_vector(json.loads(row['vector']))
        if len(vector)!=len(query_vector):return result('embedding dimensions changed; rebuild index')
        score=sum(x*y for x,y in zip(vector,query_vector))
        if score>0 and (path not in semantic or score>semantic[path][0]):semantic[path]=(score,row)
    fused={hit.path:[1/(60+rank),hit] for rank,hit in enumerate(lexical.hits,1)}
    for rank,(path,(score,row)) in enumerate(sorted(semantic.items(),key=lambda item:(-item[1][0],item[0])),1):
        if path not in fused:
            file=current[path]
            fused[path]=[0,CodeHit(path,file.language,file.is_test,0,(),(),(row['line_start'],))]
        fused[path][0]+=.7/(60+rank)
        fused[path][1]=replace(fused[path][1],reasons=(*fused[path][1].reasons,f'semantic v1 cosine={score:.3f}; commit={profile.head_commit[:12]}'))
    hits=tuple(replace(hit,score=round(score,6)) for score,hit in sorted(fused.values(),key=lambda item:(-item[0],item[1].path)))
    return result(f'current; {stale} changed/deleted chunks ignored; live lexical overlay',replace(lexical,hits=hits))
