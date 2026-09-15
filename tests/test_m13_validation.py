from __future__ import annotations

from reverend.benchmarks.m13_validation import (
    _portable_security,
    run_validation,
)


def test_portable_m13_security_contract_is_complete():
    report = _portable_security()

    assert report["passed"] is True
    assert all(
        report["assertions"].values()
    )
    assert (
        report["metadata"][
            "project_trust"
        ]
        == "untrusted_repo"
    )
    assert (
        report["metadata"][
            "model_calls"
        ]
        == 0
    )


def test_m13_portable_only_cannot_claim_acceptance(
    tmp_path,
):
    code, summary = (
        run_validation(
            report_root=tmp_path,
            skip_tests=True,
            skip_live_sandbox=True,
        )
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
            "live_sandbox"
        ][
            "skipped"
        ]
        is True
    )


def test_m13_acceptance_requires_live_sandbox(
    tmp_path,
):
    def good_probe():
        return {
            "passed": True,
            "assertions": {
                "live_fixture": True,
            },
            "returncode": 0,
        }

    code, summary = (
        run_validation(
            report_root=tmp_path,
            skip_tests=True,
            live_probe=good_probe,
        )
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
            "overall_ok"
        ]
        is True
    )


def test_m13_failed_live_sandbox_blocks_acceptance(
    tmp_path,
):
    def bad_probe():
        return {
            "passed": False,
            "assertions": {
                "network_namespace_isolated": False,
            },
            "returncode": 1,
        }

    code, summary = (
        run_validation(
            report_root=tmp_path,
            skip_tests=True,
            live_probe=bad_probe,
        )
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
