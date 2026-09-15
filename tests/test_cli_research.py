import json

from reverend import cli
from reverend.research.evidence import public_source_candidate


def test_public_source_candidate_preserves_search_provenance():
    row = public_source_candidate(
        {
            "id": "source-1",
            "url": "https://example.test/current",
            "source_title": "Current Jacobian Research",
            "content": "Jacobian derivatives linear maps current research.",
            "search_provider": "searxng",
            "search_rank": 2,
            "search_freshness": "day",
        },
        2,
    )

    assert row["chunk_id"] == "public:source-1"
    assert row["citation_label"] == "W2"
    assert row["trust_class"] == "UNTRUSTED_EXTERNAL"
    assert row["search_provider"] == "searxng"
    assert row["search_freshness"] == "day"


def test_command_research_no_longer_reports_deferred_web(
    monkeypatch,
    capsys,
    tmp_path,
):
    monkeypatch.setattr(cli, "DATA_ROOT", tmp_path)
    monkeypatch.setattr(
        cli,
        "search",
        lambda query, limit=5, **kwargs: [
            {
                "chunk_id": "local-1",
                "source": "vault.md",
                "section": "Jacobians",
                "corpus": "obsidian",
                "trust_class": "TRUSTED_PERSONAL",
                "content": "A Jacobian represents the derivative as a linear map.",
                "relevance": 0.9,
            }
        ],
    )

    code = cli.command_research(
        "Jacobian derivative linear map",
        allow_network=False,
        limit=3,
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["local_evidence_gate"]["accepted_count"] == 1
    assert payload["web"]["attempted"] is False
    assert payload["web"]["sources"] == []
    assert "DEFERRED" not in json.dumps(payload)


def test_command_research_uses_configured_web_search_and_evidence_gate(
    monkeypatch,
    capsys,
    tmp_path,
):
    monkeypatch.setattr(cli, "DATA_ROOT", tmp_path)
    monkeypatch.setattr(cli, "search", lambda query, limit=5, **kwargs: [])

    class FakeResearch:
        def __init__(self, path):
            self.path = path

        def search_status(self):
            return {
                "configured": True,
                "provider": "searxng",
                "endpoint": "http://127.0.0.1:8888",
            }

        def discover(
            self,
            query,
            *,
            allow_network=False,
            freshness="stable",
            limit=3,
        ):
            assert allow_network is True
            assert freshness == "day"
            assert 1 <= limit <= 3
            return {
                "provider": "searxng",
                "freshness": freshness,
                "configuration": {
                    "provider": "searxng",
                    "endpoint": "http://127.0.0.1:8888",
                },
                "search_result_count": 1,
                "fetched_count": 1,
                "fetch_failure_count": 0,
                "failures": [],
                "sources": [
                    {
                        "id": "web-1",
                        "url": "https://example.test/reverend",
                        "source_title": "Reverend AI release today",
                        "content": (
                            "Reverend AI release today includes fresh web "
                            "search evidence and current release details."
                        ),
                        "content_hash": "abc123",
                        "search_provider": "searxng",
                        "search_rank": 1,
                        "search_freshness": freshness,
                    }
                ],
            }

    import reverend.research.service as research_service

    monkeypatch.setattr(research_service, "PublicResearch", FakeResearch)

    code = cli.command_research(
        "Reverend AI release today",
        allow_network=True,
        freshness="day",
        limit=3,
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["web"]["attempted"] is True
    assert payload["web"]["provider"] == "searxng"
    assert payload["web"]["freshness"] == "day"
    assert payload["web"]["evidence_gate"]["accepted_count"] == 1
    assert payload["web"]["sources"][0]["evidence_class"] == "FRESH"
    assert payload["web"]["sources"][0]["citation_label"] == "W1"


def test_current_research_does_not_surface_unrelated_personal_background(
    monkeypatch,
    capsys,
    tmp_path,
):
    monkeypatch.setattr(cli, "DATA_ROOT", tmp_path)
    monkeypatch.setattr(
        cli,
        "search",
        lambda query, limit=5, **kwargs: [
            {
                "chunk_id": "personal-1",
                "source": "responsible-computing.md",
                "section": "NIST AI RMF",
                "corpus": "obsidian",
                "trust_class": "TRUSTED_PERSONAL",
                "content": "NIST announced revision work in April 2026.",
                "relevance": 0.8,
            }
        ],
    )

    class FakeResearch:
        def __init__(self, path):
            self.path = path

        def search_status(self):
            return {"configured": False}

    import reverend.research.service as research_service
    monkeypatch.setattr(research_service, "PublicResearch", FakeResearch)

    code = cli.command_research(
        "What important AI model releases were announced this week?",
        allow_network=False,
        limit=3,
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["local_evidence"] == []
    assert payload["local_evidence_gate"]["requested_classes"] == ["REFERENCE"]
    assert payload["web"]["freshness"] == "week"


def test_command_research_web_survives_local_retrieval_failure(
    monkeypatch,
    capsys,
    tmp_path,
):
    monkeypatch.setattr(cli, "DATA_ROOT", tmp_path)

    def fail_local(*args, **kwargs):
        raise RuntimeError("registry unavailable")

    monkeypatch.setattr(cli, "search", fail_local)

    class FakeResearch:
        def __init__(self, path):
            self.path = path

        def search_status(self):
            return {
                "configured": True,
                "provider": "searxng",
                "endpoint": "http://127.0.0.1:8888",
            }

        def discover(
            self,
            query,
            *,
            allow_network=False,
            freshness="stable",
            limit=3,
        ):
            assert allow_network is True
            return {
                "provider": "searxng",
                "freshness": freshness,
                "configuration": {
                    "provider": "searxng",
                    "endpoint": "http://127.0.0.1:8888",
                },
                "search_result_count": 1,
                "fetched_count": 1,
                "fetch_failure_count": 0,
                "failures": [],
                "sources": [
                    {
                        "id": "web-fallback-1",
                        "url": "https://example.test/current",
                        "source_title": "Current Reverend release",
                        "content": (
                            "Reverend AI release today has current fresh "
                            "web evidence and release details."
                        ),
                        "content_hash": "fallback123",
                        "search_provider": "searxng",
                        "search_rank": 1,
                        "search_freshness": freshness,
                    }
                ],
            }

    import reverend.research.service as research_service
    monkeypatch.setattr(research_service, "PublicResearch", FakeResearch)

    code = cli.command_research(
        "Reverend AI release today",
        allow_network=True,
        freshness="day",
        limit=3,
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["local_evidence"] == []
    assert payload["local_error"]["error_code"] == "local_retrieval_failed"
    assert payload["web"]["attempted"] is True
    assert payload["web"]["evidence_gate"]["accepted_count"] == 1
    assert payload["web"]["sources"][0]["citation_label"] == "W1"
