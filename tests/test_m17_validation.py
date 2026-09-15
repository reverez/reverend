from __future__ import annotations

from pathlib import Path

from reverend.benchmarks.m17_validation import run_validation
from reverend.research.search import WebSearchAuthenticationError


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
        "search_result_count":3,
        "fetched_count":1,
        "source_count":1,
    }


def test_m17_portable_only_cannot_claim_live_provider_acceptance(tmp_path):
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
    assert summary["live_search"]["skipped"] is True
    assert Path(summary["summary_path"]).is_file()


def test_m17_all_gates_can_accept_with_configured_live_provider(tmp_path):
    code,summary=run_validation(
        repository=ROOT,
        report_root=tmp_path,
        skip_tests=True,
        release_runner=_release_runner,
        live_search_runner=_live_runner,
    )
    assert code==0
    assert summary["portable_ok"] is True
    assert summary["live_ok"] is True
    assert summary["overall_ok"] is True


def test_m17_missing_or_failed_live_provider_blocks_acceptance(tmp_path):
    def failed():
        return {
            "configured":False,
            "passed":False,
            "error_code":"network_search_unavailable",
        }

    code,summary=run_validation(
        repository=ROOT,
        report_root=tmp_path,
        skip_tests=True,
        release_runner=_release_runner,
        live_search_runner=failed,
    )
    assert code==1
    assert summary["portable_ok"] is True
    assert summary["live_ok"] is False
    assert summary["overall_ok"] is False


def test_m17_configured_auth_failure_is_reported_as_configured(tmp_path):
    def failed():
        raise WebSearchAuthenticationError("Search provider rejected authentication")

    code,summary=run_validation(
        repository=ROOT,
        report_root=tmp_path,
        skip_tests=True,
        release_runner=_release_runner,
        live_search_runner=failed,
    )
    assert code==1
    assert summary["live_search"]["configured"] is True
    assert summary["live_search"]["passed"] is False
    assert summary["live_search"]["error_code"]=="network_search_auth_failed"
