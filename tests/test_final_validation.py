from __future__ import annotations

from pathlib import Path

from reverend.benchmarks.final_validation import run_validation


ROOT=Path(__file__).resolve().parents[1]


def _release(_repository):
    return {"passed":True,"revision":"fixture"}


def _milestone(portable=True,live=True):
    def run(_repository,_report_root,skip_live):
        return {
            "portable_ok":portable,
            "live_ok":False if skip_live else live,
            "overall_ok":portable and (False if skip_live else live),
        }
    return run


def test_final_portable_only_is_successful_but_not_fully_accepted(tmp_path):
    code,summary=run_validation(
        repository=ROOT,
        report_root=tmp_path,
        skip_tests=True,
        skip_live=True,
        release_runner=_release,
        m16_runner=_milestone(),
        m17_runner=_milestone(),
        m18_runner=_milestone(),
    )
    assert code==2
    assert summary["portable_ok"] is True
    assert summary["live_ok"] is False
    assert summary["overall_ok"] is False
    assert len(summary["remaining_gates"])==3
    assert Path(summary["summary_path"]).is_file()


def test_final_acceptance_requires_all_live_milestones(tmp_path):
    code,summary=run_validation(
        repository=ROOT,
        report_root=tmp_path,
        skip_tests=True,
        release_runner=_release,
        m16_runner=_milestone(),
        m17_runner=_milestone(),
        m18_runner=_milestone(),
    )
    assert code==0
    assert summary["portable_ok"] is True
    assert summary["live_ok"] is True
    assert summary["overall_ok"] is True
    assert summary["remaining_gates"]==[]


def test_one_failed_live_milestone_blocks_final_acceptance(tmp_path):
    code,summary=run_validation(
        repository=ROOT,
        report_root=tmp_path,
        skip_tests=True,
        release_runner=_release,
        m16_runner=_milestone(),
        m17_runner=_milestone(live=False),
        m18_runner=_milestone(),
    )
    assert code==1
    assert summary["portable_ok"] is True
    assert summary["live_ok"] is False
    assert summary["overall_ok"] is False
    assert summary["remaining_gates"]==["M17"]
