import json
from pathlib import Path

import pytest
from qdrant_client import QdrantClient, models
from reverend import sync
from reverend.registry import connect, writer_lock
from test_maintenance import registry


def setup(tmp_path, monkeypatch):
    db_path=registry(tmp_path)
    source=tmp_path/'source.md'
    source.write_text('# Old\nOld evidence')
    with connect(db_path) as db:
        db.execute('DELETE FROM documents')
    store=QdrantClient(':memory:')
    store.create_collection(sync.COLLECTION,vectors_config=models.VectorParams(size=2,distance=models.Distance.COSINE))
    monkeypatch.setattr(sync,'client',lambda:store)
    monkeypatch.setattr(sync,'embed',lambda texts:[[1.,0.] for _ in texts])
    monkeypatch.setattr(sync,'save_state',lambda state:None)
    corpus={'id':'test','trust_class':'TRUSTED_PRIMARY'}
    sync._apply_document(str(source),corpus,db_path)
    return db_path,source,store,corpus


def test_embedding_failure_preserves_last_generation(tmp_path,monkeypatch):
    db,path,store,corpus=setup(tmp_path,monkeypatch)
    old=store.scroll(sync.COLLECTION)[0][0]
    path.write_text('# New\nNew evidence')
    def fail(texts):raise RuntimeError('embedding failure')
    monkeypatch.setattr(sync,'embed',fail)
    with pytest.raises(RuntimeError):sync._apply_document(str(path),corpus,db)
    assert store.scroll(sync.COLLECTION)[0][0].id==old.id
    with connect(db) as conn:
        assert conn.execute('SELECT text FROM chunks').fetchone()[0]=='# Old\nOld evidence'
    store.close()


def test_failed_publication_and_retry_cleanup(tmp_path,monkeypatch):
    db,path,store,corpus=setup(tmp_path,monkeypatch)
    path.write_text('# New\nNew evidence')
    original=store.upsert
    def partial(*args,**kwargs):
        original(*args,**kwargs)
        raise RuntimeError('publication interrupted')
    monkeypatch.setattr(store,'upsert',partial)
    with pytest.raises(RuntimeError):sync._apply_document(str(path),corpus,db)
    assert store.count(sync.COLLECTION).count==2
    with connect(db) as conn:
        assert conn.execute('SELECT text FROM chunks').fetchone()[0]=='# Old\nOld evidence'
    monkeypatch.setattr(store,'upsert',original)
    path.write_text('# Third\nA later source generation')
    sync._apply_document(str(path),corpus,db)
    assert store.count(sync.COLLECTION).count==1
    assert store.scroll(sync.COLLECTION)[0][0].payload['content']=='# Third\nA later source generation'
    # Same digest / changed trust must retain its points.
    sync._apply_document(str(path),{**corpus,'trust_class':'TRUSTED_PERSONAL'},db)
    assert store.count(sync.COLLECTION).count==1
    path.write_text('')
    sync._apply_document(str(path),corpus,db)
    assert store.count(sync.COLLECTION).count==0
    sync._delete_document(str(path),db)
    sync._delete_document(str(path),db)
    store.close()


def test_source_edit_during_embedding_never_publishes(tmp_path,monkeypatch):
    db,path,store,corpus=setup(tmp_path,monkeypatch)
    def edit(texts):
        path.write_text('Changed during embedding')
        return [[1.,0.] for _ in texts]
    monkeypatch.setattr(sync,'embed',edit)
    with pytest.raises(RuntimeError,match='Source changed'):
        sync._apply_document(str(path),corpus,db)
    assert store.scroll(sync.COLLECTION)[0][0].payload['content']=='# Old\nOld evidence'
    store.close()


def test_legacy_ingest_uses_registry_and_does_not_delete_siblings(tmp_path,monkeypatch):
    db,path,store,corpus=setup(tmp_path,monkeypatch)
    sibling=tmp_path/'sibling.md';sibling.write_text('Sibling')
    sync._apply_document(str(sibling),corpus,db)
    report=sync.ingest_path(path,'TRUSTED_PRIMARY','test',db)
    assert report['files_skipped']==1 and report['removed']==0
    assert store.count(sync.COLLECTION).count==2
    path.write_text('---\norigin: AI-generated\nreview_status: unreviewed\n---\nGenerated')
    report=sync.ingest_path(path,'TRUSTED_PRIMARY','test',db)
    assert report['errors'] and report['files_indexed']==0
    assert store.count(sync.COLLECTION).count==2
    store.close()


def test_writer_lock_rejects_competing_writers(tmp_path):
    path=tmp_path/'db'
    with writer_lock(path):
        with pytest.raises(RuntimeError,match='writer'):
            with writer_lock(path):pass


def test_legacy_state_atomic_failure_preserves_old_file(tmp_path,monkeypatch):
    from reverend import cli
    state=tmp_path/'state.json';state.write_text('{"old":true}')
    monkeypatch.setattr(cli,'STATE',state)
    def fail(*args):raise OSError('rename failure')
    monkeypatch.setattr(cli.os,'replace',fail)
    with pytest.raises(OSError):cli.save_state({'sources':{}})
    assert json.loads(state.read_text())=={'old':True}
    assert list(tmp_path.iterdir())==[state]


def test_interrupted_publication_is_reconciled_even_if_source_reverts_or_disappears(tmp_path,monkeypatch):
    db,path,store,corpus=setup(tmp_path,monkeypatch)
    original=store.delete
    def fail(*args,**kwargs):raise RuntimeError('cleanup failed')
    monkeypatch.setattr(store,'delete',fail)
    path.write_text('# New\nNew evidence')
    with pytest.raises(RuntimeError):sync._apply_document(str(path),corpus,db)
    path.write_text('# Old\nOld evidence')
    scan_corpus={**corpus,'root':tmp_path,'extensions':['.md']}
    report=sync.scan_corpus(scan_corpus,db)
    assert report['changed']==1 and report['unchanged']==0
    path.unlink()
    report=sync.scan_corpus(scan_corpus,db)
    assert report['_deleted_paths']==[str(path)]
    monkeypatch.setattr(store,'delete',original)
    sync._delete_document(str(path),db)
    assert store.count(sync.COLLECTION).count==0
    with connect(db) as conn:
        assert conn.execute('SELECT count(*) FROM pending_publications').fetchone()[0]==0
    store.close()
