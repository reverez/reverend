from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import reverend.benchmarks.m18_validation as m18
from reverend.benchmarks.m18_validation import _run_live_visual,run_validation
from reverend.research.search import (
    WebSearchAuthenticationError,
    WebSearchConfig,
)


ROOT=Path(__file__).resolve().parents[1]


def _release_runner(repository):
    assert Path(repository).resolve()==ROOT.resolve()
    return {
        "passed":True,
        "revision":"fixture",
        "installed":{"ui_ok":True},
    }


def _live_runner():
    return {
        "configured":True,
        "passed":True,
        "provider":"searxng",
        "search_result_count":4,
        "fetched_count":2,
        "accepted_count":1,
        "image":{
            "id":"a"*32,
            "media_type":"image/webp",
            "byte_count":1024,
            "content_hash":"fixture",
        },
    }


def test_m18_portable_only_cannot_claim_live_visual_acceptance(tmp_path):
    code,summary=run_validation(
        repository=ROOT,
        report_root=tmp_path,
        skip_tests=True,
        skip_live=True,
        release_runner=_release_runner,
    )
    assert code==2
    assert summary["portable_ok"] is True
    assert summary["live_ok"] is False
    assert summary["overall_ok"] is False
    assert summary["live_visual"]["skipped"] is True
    assert Path(summary["summary_path"]).is_file()


def test_m18_all_gates_can_accept_with_live_visual_path(tmp_path):
    code,summary=run_validation(
        repository=ROOT,
        report_root=tmp_path,
        skip_tests=True,
        release_runner=_release_runner,
        live_visual_runner=_live_runner,
    )
    assert code==0
    assert summary["portable_ok"] is True
    assert summary["live_ok"] is True
    assert summary["overall_ok"] is True


def test_m18_failed_live_visual_path_blocks_acceptance(tmp_path):
    def failed():
        return {
            "configured":True,
            "passed":False,
            "error_code":"live_image_candidate_unavailable",
        }

    code,summary=run_validation(
        repository=ROOT,
        report_root=tmp_path,
        skip_tests=True,
        release_runner=_release_runner,
        live_visual_runner=failed,
    )
    assert code==1
    assert summary["portable_ok"] is True
    assert summary["live_ok"] is False
    assert summary["overall_ok"] is False


def test_m18_configured_auth_failure_is_reported_as_configured(tmp_path):
    def failed():
        raise WebSearchAuthenticationError("Search provider rejected authentication")

    code,summary=run_validation(
        repository=ROOT,
        report_root=tmp_path,
        skip_tests=True,
        release_runner=_release_runner,
        live_visual_runner=failed,
    )
    assert code==1
    assert summary["live_visual"]["configured"] is True
    assert summary["live_visual"]["passed"] is False
    assert summary["live_visual"]["error_code"]=="network_search_auth_failed"



def test_m18_live_visual_retries_bounded_search_variance(monkeypatch):
    config=WebSearchConfig(
        provider="searxng",
        endpoint="http://127.0.0.1:8888",
    )
    instances=[]

    class Research:
        def __init__(self,path):
            self.calls=0
            self.image_fetches=0
            instances.append(self)

        def discover(self,query,**kwargs):
            self.calls+=1
            source={
                "id":f"source-{self.calls}",
                "url":f"https://example.com/{self.calls}",
                "source_title":"RTX 5070 Laptop GPU review",
                "content":"NVIDIA GeForce RTX 5070 Laptop GPU recent review specifications",
                "search_provider":"searxng",
                "search_rank":1,
                "search_freshness":"month",
            }
            if self.calls==2:
                source["_image_candidate_url"]="https://images.example.com/rtx.webp"
            return {
                "search_result_count":6,
                "fetched_count":1,
                "sources":[source],
            }

        def fetch_image(self,url,*,allow_network,source_id):
            self.image_fetches+=1
            assert allow_network is True
            assert source_id=="source-2"
            return {
                "id":"image-1",
                "media_type":"image/webp",
                "byte_count":12,
                "content_hash":"hash",
            }

        def image(self,identity):
            assert identity=="image-1"
            return {
                "media_type":"image/webp",
                "content":b"x"*12,
            }

        def get(self,identity):
            assert identity=="source-2"
            return {"image_id":"image-1"}

    monkeypatch.setattr(
        m18,
        "select_evidence",
        lambda query,candidates,*a,**k:SimpleNamespace(accepted=list(candidates)),
    )

    result=_run_live_visual(
        config=config,
        research_factory=Research,
        queries=("first relevant query","second relevant query","third relevant query"),
    )

    assert result["passed"] is True
    assert result["probe_attempt_count"]==2
    assert result["attempts"][0]["outcome"]=="no_image_candidate"
    assert result["attempts"][1]["outcome"]=="passed"
    assert instances[0].calls==2
    assert instances[0].image_fetches==1


def test_m18_live_visual_probe_is_bounded(monkeypatch):
    config=WebSearchConfig(
        provider="searxng",
        endpoint="http://127.0.0.1:8888",
    )

    class Research:
        def __init__(self,path):
            self.calls=0

        def discover(self,query,**kwargs):
            self.calls+=1
            return {
                "search_result_count":0,
                "fetched_count":0,
                "sources":[],
            }

    monkeypatch.setattr(
        m18,
        "select_evidence",
        lambda query,candidates,*a,**k:SimpleNamespace(accepted=[]),
    )

    result=_run_live_visual(
        config=config,
        research_factory=Research,
        queries=("one","two","three"),
    )
    assert result["passed"] is False
    assert result["error_code"]=="live_image_candidate_unavailable"
    assert result["probe_attempt_count"]==3

    try:
        _run_live_visual(
            config=config,
            research_factory=Research,
            queries=("one","two","three","four"),
        )
    except ValueError as exc:
        assert "one to three" in str(exc)
    else:
        raise AssertionError("Expected bounded query plan rejection")
