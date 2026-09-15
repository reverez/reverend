from __future__ import annotations

from pathlib import Path

from reverend.benchmarks.m15_validation import (
    run_validation,
)


ROOT = Path(__file__).resolve().parents[1]


def _release_runner(repository):
    assert Path(repository).resolve() == ROOT.resolve()
    return {
        "passed": True,
        "version": "0.4.0",
        "revision": "fixture",
        "wheel": "reverend-0.4.0-py3-none-any.whl",
        "installed": {
            "ui_ok": True,
            "state_isolated": True,
        },
    }


def _sandbox_runner():
    return {
        "passed": True,
        "assertions": {
            "host_home_hidden": True,
        },
    }


def _inference_runner():
    return {
        "passed": True,
        "version": "0.4.0",
        "model_calls": 1,
        "embedding_calls": 0,
    }


def test_m15_portable_only_cannot_claim_release_acceptance(
    tmp_path,
):
    code, summary = run_validation(
        repository=ROOT,
        report_root=tmp_path,
        skip_tests=True,
        skip_live=True,
        release_runner=_release_runner,
    )

    assert code == 2
    assert (
        summary[
            "portable_ok"
        ]
        is True
    )
    assert (
        summary[
            "overall_ok"
        ]
        is False
    )
    assert (
        summary[
            "version"
        ]
        == "0.4.0"
    )


def test_m15_all_release_gates_can_accept(
    tmp_path,
):
    code, summary = run_validation(
        repository=ROOT,
        report_root=tmp_path,
        skip_tests=True,
        release_runner=_release_runner,
        sandbox_runner=_sandbox_runner,
        inference_runner=_inference_runner,
    )

    assert code == 0
    assert (
        summary[
            "portable_ok"
        ]
        is True
    )
    assert (
        summary[
            "live_sandbox"
        ][
            "passed"
        ]
        is True
    )
    assert (
        summary[
            "live_inference"
        ][
            "passed"
        ]
        is True
    )
    assert (
        summary[
            "overall_ok"
        ]
        is True
    )


def test_m15_live_failure_blocks_release_acceptance(
    tmp_path,
):
    def failed_inference():
        return {
            "passed": False,
            "model_calls": 1,
        }

    code, summary = run_validation(
        repository=ROOT,
        report_root=tmp_path,
        skip_tests=True,
        release_runner=_release_runner,
        sandbox_runner=_sandbox_runner,
        inference_runner=failed_inference,
    )

    assert code == 1
    assert (
        summary[
            "portable_ok"
        ]
        is True
    )
    assert (
        summary[
            "overall_ok"
        ]
        is False
    )
