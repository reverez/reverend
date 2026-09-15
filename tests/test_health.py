from reverend import cli
from reverend.health import snapshot,check
from test_retrieve import populated


def test_status_is_offline_and_never_opens_qdrant(tmp_path,monkeypatch):
    def forbidden(*args,**kwargs):raise AssertionError('expensive operation')
    monkeypatch.setattr(cli,'api',forbidden)
    monkeypatch.setattr('reverend.config.qdrant_client',forbidden)
    result=snapshot(populated(tmp_path))
    assert result['documents']==1 and result['chunks']==result['fts_chunks']==2
    assert result['qdrant_points'] is None


def test_normal_doctor_does_not_embed_or_load_qdrant(tmp_path,monkeypatch):
    monkeypatch.setattr(cli,'api',lambda *args,**kwargs:{'models':[]})
    def forbidden(*args,**kwargs):raise AssertionError('expensive operation')
    monkeypatch.setattr(cli,'embed',forbidden)
    monkeypatch.setattr('reverend.config.qdrant_client',forbidden)
    assert check(False,populated(tmp_path))['ok']
