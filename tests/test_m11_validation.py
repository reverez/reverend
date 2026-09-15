from __future__ import annotations

from reverend.benchmarks.m11_validation import (
    _live_ok,
    run_validation,
)


def test_live_decision_requires_complete_separated_worker_path():
    accepted = {
        "status": "pass",
        "stop_reason": "complete",
        "workers_used": 3,
        "worker_steps": 3,
        "tool_calls": 0,
        "model_calls": 3,
        "primary_checkout_unchanged": True,
        "worktree_changed": True,
        "coder_verified_by": "coder:verify",
    }

    assert _live_ok(accepted) is True

    rejected = dict(accepted)
    rejected["coder_verified_by"] = None
    assert _live_ok(rejected) is False


def test_portable_validation_cannot_claim_live_acceptance(tmp_path):
    code, summary = run_validation(
        report_root=tmp_path,
        skip_tests=True,
        skip_live_model=True,
    )

    assert code == 2
    assert summary["portable_ok"] is True
    assert summary["overall_ok"] is False
    assert summary["portable_workers"]["failed"] == 0
    assert summary["portable_workers"]["passed"] == 4
    assert summary["live_development"]["skipped"] is True
    assert (
        tmp_path
        / summary["summary_path"].split("/")[-1]
    ).is_file()
