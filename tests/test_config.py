from reverend import config


def test_explicit_ollama_wins(monkeypatch):
    monkeypatch.setenv('OLLAMA_HOST','http://example:11434/')
    assert config.ollama_host() == 'http://example:11434'


def test_server_and_local_modes(monkeypatch, tmp_path):
    config.close_qdrant()
    calls=[]
    class Client:
        def __init__(self, **kwargs):calls.append(kwargs)
        def close(self):pass
    monkeypatch.setattr(config,'QdrantClient',Client)
    monkeypatch.setattr(config,'QDRANT_URL','http://localhost:6333')
    first=config.qdrant_client()
    assert config.qdrant_client() is first
    assert calls[0]['url']=='http://localhost:6333'
    config.close_qdrant()
    monkeypatch.setattr(config,'QDRANT_URL',None)
    monkeypatch.setattr(config,'QDRANT_PATH',tmp_path)
    config.qdrant_client()
    assert calls[1]=={'path':str(tmp_path)}
    config.close_qdrant()


def test_default_data_root_prefers_portable_location(monkeypatch, tmp_path):
    from reverend import config
    monkeypatch.setattr(config.Path, "home", classmethod(lambda cls: tmp_path))
    assert config._default_data_root() == tmp_path / ".local" / "share" / "reverend"


def test_default_data_root_reuses_existing_legacy_state(monkeypatch, tmp_path):
    from reverend import config
    legacy = tmp_path / "reverend-data" / "dev" / "ai-data"
    legacy.mkdir(parents=True)
    monkeypatch.setattr(config.Path, "home", classmethod(lambda cls: tmp_path))
    assert config._default_data_root() == legacy


def test_default_data_root_ignores_non_state_canonical_directory(monkeypatch, tmp_path):
    from reverend import config
    canonical = tmp_path / ".local" / "share" / "reverend"
    legacy = tmp_path / "reverend-data" / "dev" / "ai-data"
    (canonical / "validation" / "stability-run").mkdir(parents=True)
    legacy.mkdir(parents=True)
    (legacy / "platform.db").touch()
    monkeypatch.setattr(config.Path, "home", classmethod(lambda cls: tmp_path))
    assert config._default_data_root() == legacy


def test_default_data_root_prefers_canonical_when_real_state_exists(monkeypatch, tmp_path):
    from reverend import config
    canonical = tmp_path / ".local" / "share" / "reverend"
    legacy = tmp_path / "reverend-data" / "dev" / "ai-data"
    canonical.mkdir(parents=True)
    legacy.mkdir(parents=True)
    (canonical / "platform.db").touch()
    (legacy / "platform.db").touch()
    monkeypatch.setattr(config.Path, "home", classmethod(lambda cls: tmp_path))
    assert config._default_data_root() == canonical


def test_default_data_root_legacy_registry_beats_canonical_auxiliary_state(monkeypatch, tmp_path):
    from reverend import config
    canonical = tmp_path / ".local" / "share" / "reverend"
    legacy = tmp_path / "reverend-data" / "dev" / "ai-data"
    canonical.mkdir(parents=True)
    legacy.mkdir(parents=True)
    (canonical / "workstation.db").touch()
    (canonical / "public-sources.db").touch()
    (legacy / "platform.db").touch()
    monkeypatch.setattr(config.Path, "home", classmethod(lambda cls: tmp_path))
    assert config._default_data_root() == legacy
