from types import SimpleNamespace as NS

from reverend.maintenance import backfill_chunks
from reverend.registry import connect, initialize


def registry(tmp_path):
    path = tmp_path / 'registry.db'
    initialize(path)
    with connect(path) as db:
        db.execute("INSERT INTO corpora VALUES('test','/tmp',1,'now')")
        db.execute("INSERT INTO documents(source_path,corpus_id,sha256,chunk_count,trust_class,indexed_at) VALUES('/tmp/a.md','test','hash',2,'TRUSTED_PRIMARY','now')")
    return path


class Store:
    def __init__(self):
        self.points = [NS(id=str(i), payload=dict(source='/tmp/a.md', content=f'chunk {i}', section='Heading',
                           content_hash='hash',corpus='test', trust_class='TRUSTED_PRIMARY')) for i in range(2)]
        self.fail = False

    def scroll(self, collection, *, limit, offset, with_payload, with_vectors):
        assert with_payload is True and with_vectors is False
        if offset and self.fail:
            raise RuntimeError('interrupted')
        index = offset or 0
        return self.points[index:index+1], index+1 if index+1 < len(self.points) else None

    def count(self, *args, **kwargs):
        return NS(count=len(self.points))


def test_backfill_idempotent_and_resumes_after_interruption(tmp_path):
    import pytest
    path, store = registry(tmp_path), Store()
    store.fail = True
    with pytest.raises(RuntimeError):
        backfill_chunks(store, 'test', path)
    with connect(path) as db:
        assert db.execute('SELECT count(*) FROM chunks').fetchone()[0] == 1
    store.fail = False
    assert backfill_chunks(store, 'test', path)['ok']
    assert backfill_chunks(store, 'test', path)['materialized_chunks'] == 2


def test_orphan_stale_invalid_are_reported(tmp_path):
    path, store = registry(tmp_path), Store()
    store.points[0].payload['source'] = 'missing'
    store.points[1].payload['content_hash'] = 'stale'
    report = backfill_chunks(store, 'test', path)
    assert not report['ok']
    assert report['orphans'] == report['stale'] == 1
    assert report['materialized_chunks'] == 0
    store.points[0].payload['source'] = '/tmp/a.md'
    store.points[0].payload['content'] = None
    assert backfill_chunks(store, 'test', path)['invalid'] == 1


def test_backfill_cannot_certify_pending_publication(tmp_path):
    path,store=registry(tmp_path),Store()
    with connect(path) as db:
        db.execute("INSERT INTO pending_publications VALUES('/tmp/a.md','test','now')")
    report=backfill_chunks(store,'test',path)
    assert not report['ok'] and report['pending_publications']==1
