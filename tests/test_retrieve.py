from reverend.registry import connect, rebuild_fts
from reverend.retrieve import retrieve_lexical
from test_maintenance import registry


def populated(tmp_path):
    path = registry(tmp_path)
    with connect(path) as db:
        for i, (section, text) in enumerate([
            ('Jacobian matrix', 'The Jacobian is the local linear derivative map.'),
            ('Eigenvectors', 'Eigenvectors and eigenvalues describe invariant directions.'),
        ]):
            db.execute('INSERT INTO chunks VALUES(?,?,?,?,?,?,?)',
                       (str(i), '/tmp/a.md', i, section, None, text, str(i)))
    return path


def test_lexical_terms_punctuation_and_filters(tmp_path):
    path = populated(tmp_path)
    assert retrieve_lexical('Jacobian matrix', db_path=path)[0]['chunk_id'] == '0'
    assert retrieve_lexical('What is a Jacobian? (matrix): "derivative"!', db_path=path)[0]['chunk_id'] == '0'
    assert retrieve_lexical('" OR * : - ()', db_path=path) == []
    assert retrieve_lexical('Jacobian', corpus='absent', db_path=path) == []
    assert retrieve_lexical('Jacobian', trust='UNTRUSTED_EXTERNAL', db_path=path) == []


def test_fts_update_delete_cascade_rebuild(tmp_path):
    path = populated(tmp_path)
    assert rebuild_fts(path)['fts_chunks'] == 2
    with connect(path) as db:
        db.execute("UPDATE chunks SET section='New',text='Topology' WHERE chunk_id='0'")
    assert not retrieve_lexical('Jacobian', db_path=path)
    assert retrieve_lexical('Topology', db_path=path)
    with connect(path) as db:
        db.execute("DELETE FROM chunks WHERE chunk_id='0'")
    assert not retrieve_lexical('Topology', db_path=path)
    with connect(path) as db:
        db.execute('DELETE FROM documents')
    assert not retrieve_lexical('eigenvalues', db_path=path)
    assert rebuild_fts(path)['fts_chunks'] == 0


def test_rrf_scores_dedup_and_provenance():
    from reverend.retrieve import fuse_rrf
    a = dict(chunk_id='a',source='/a.md',content='same',dense_score=.9)
    b = dict(chunk_id='b',source='/b.md',content='same',dense_score=.8)
    rows = fuse_rrf([a,a,b],[{**b,'lexical_score':2}],10)
    assert [r['chunk_id'] for r in rows] == ['b','a']
    assert rows[0]['rrf_score'] == 1/62 + 1/61
    assert rows[0]['dense_rank'] == 2 and rows[0]['lexical_rank'] == 1
    assert len(rows) == 2  # Equal text across sources retains both provenance records.


def test_dense_hydrates_canonical_text_and_filters(tmp_path):
    from types import SimpleNamespace as NS
    from reverend.retrieve import retrieve_dense
    path = populated(tmp_path)
    class Store:
        def query_points(self, *args, **kwargs):
            assert kwargs['with_vectors'] is False
            assert kwargs['with_payload'] == ['content_hash']
            assert kwargs['query_filter'].must[0].match.value == 'test'
            return NS(points=[NS(id='0',score=.9,payload={'content_hash':'hash'})])
    rows=retrieve_dense('Jacobian', corpus='test', db_path=path, store=Store(), query_vector=[1])
    assert rows[0]['content'].startswith('The Jacobian')
    assert rows[0]['dense_score'] == .9


def test_generated_content_excluded(tmp_path):
    from reverend.retrieve import fuse_rrf
    path = populated(tmp_path)
    with connect(path) as db:
        db.execute("UPDATE documents SET trust_class='AI_GENERATED_UNREVIEWED'")
    assert not retrieve_lexical('Jacobian', db_path=path)
    assert not fuse_rrf([dict(chunk_id='x',source='/data/drafts/x.md')],[],5)


def test_search_cli_modes(monkeypatch,capsys):
    from reverend import cli, retrieve
    calls=[]
    def search(query,limit,**kwargs):
        calls.append((query,limit,kwargs));return [{'chunk_id':'ok'}]
    monkeypatch.setattr(retrieve,'retrieve_hybrid',search)
    assert cli.main(['search','topic','--corpus','test','--limit','2'])==0
    assert calls==[('topic',2,{'trust':None,'corpus':'test'})]
    monkeypatch.setattr(retrieve,'retrieve_lexical',search)
    assert cli.main(['search','topic','--mode','lexical'])==0
