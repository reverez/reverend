from __future__ import annotations

from pathlib import Path

from reverend.benchmarks.m16_validation import run_validation


ROOT=Path(__file__).resolve().parents[1]


def _release_runner(repository):
    assert Path(repository).resolve()==ROOT.resolve()
    return {
        "passed":True,
        "revision":"fixture",
        "installed":{"ui_ok":True},
    }


def _workstation_runner():
    return {
        "passed":True,
        "probes":[
            {"name":"fast_general","passed":True},
            {"name":"deep_reason","passed":True},
        ],
    }


def _strong_runner():
    return {
        "passed":True,
        "model":"qwen3-coder:30b",
        "context":16384,
        "exclusive_memory":True,
    }


def test_m16_portable_only_cannot_claim_live_acceptance(tmp_path):
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
    assert Path(summary["summary_path"]).is_file()


def test_m16_all_gates_can_accept(tmp_path):
    code,summary=run_validation(
        repository=ROOT,
        report_root=tmp_path,
        skip_tests=True,
        release_runner=_release_runner,
        live_workstation_runner=_workstation_runner,
        strong_code_runner=_strong_runner,
    )
    assert code==0
    assert summary["portable_ok"] is True
    assert summary["live_workstation"]["passed"] is True
    assert summary["live_strong_code"]["passed"] is True
    assert summary["overall_ok"] is True


def test_m16_live_reasoning_failure_blocks_acceptance(tmp_path):
    def failed_workstation():
        return {
            "passed":False,
            "probes":[
                {
                    "name":"deep_reason",
                    "passed":False,
                    "completion_reason":"reasoning_budget_exhausted_before_answer",
                }
            ],
        }

    code,summary=run_validation(
        repository=ROOT,
        report_root=tmp_path,
        skip_tests=True,
        release_runner=_release_runner,
        live_workstation_runner=failed_workstation,
        strong_code_runner=_strong_runner,
    )
    assert code==1
    assert summary["portable_ok"] is True
    assert summary["live_ok"] is False
    assert summary["overall_ok"] is False


def test_m16_strong_code_failure_blocks_acceptance(tmp_path):
    def failed_strong():
        return {
            "passed":False,
            "model":"qwen3-coder:30b",
            "context":16384,
        }

    code,summary=run_validation(
        repository=ROOT,
        report_root=tmp_path,
        skip_tests=True,
        release_runner=_release_runner,
        live_workstation_runner=_workstation_runner,
        strong_code_runner=failed_strong,
    )
    assert code==1
    assert summary["portable_ok"] is True
    assert summary["live_ok"] is False
