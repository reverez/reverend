from __future__ import annotations

from reverend.benchmarks.m14_validation import (
    _ambiguous_guard_ok,
    _clear_fact_ok,
    _runtime_report,
    run_validation,
)


def _clear_job():
    return {
        "status": "complete",
        "response": "Ada Lovelace was a 19th-century mathematician.",
        "details": {
            "understanding": {
                "method": "deterministic",
            },
            "routing": {
                "model_role": "fast_general",
                "output_tokens": 1536,
            },
            "model_calls": 1,
            "generation_calls": 1,
            "embedding_calls": 0,
            "inventory_provider_reads": 1,
            "inventory_cache_hits": 1,
            "total_prompt_tokens": 120,
            "total_generated_tokens": 40,
            "total_provider_seconds": 0.5,
            "total_queue_wait_seconds": 0.0,
            "total_setup_seconds": 0.01,
            "model_runs": [
                {
                    "role": "fast_general",
                }
            ],
        },
    }


def test_m14_clear_fact_acceptance_requires_one_efficient_answer_call():
    assert (
        _clear_fact_ok(
            _clear_job(),
            wall_seconds=0.7,
        )
        is True
    )

    bad = _clear_job()
    bad["details"][
        "model_calls"
    ] = 2

    assert (
        _clear_fact_ok(
            bad,
            wall_seconds=0.7,
        )
        is False
    )


def test_m14_ambiguity_gate_requires_router_or_fail_closed_clarification():
    local_router = {
        "status": "complete",
        "details": {
            "understanding": {
                "method": "local_router",
            },
            "model_calls": 2,
            "model_runs": [
                {
                    "role": "router",
                },
                {
                    "role": "fast_general",
                },
            ],
        },
    }

    assert (
        _ambiguous_guard_ok(
            local_router
        )
        is True
    )

    clarification = {
        "status": "complete",
        "details": {
            "understanding": {
                "method": "deterministic",
            },
            "clarification_required": True,
            "model_calls": 1,
            "model_runs": [
                {
                    "role": "router",
                }
            ],
        },
    }

    assert (
        _ambiguous_guard_ok(
            clarification
        )
        is True
    )

    bypass = {
        "status": "complete",
        "details": {
            "understanding": {
                "method": "deterministic",
            },
            "model_calls": 1,
            "model_runs": [
                {
                    "role": "fast_general",
                }
            ],
        },
    }

    assert (
        _ambiguous_guard_ok(
            bypass
        )
        is False
    )


def test_m14_portable_runtime_contract_passes():
    report = (
        _runtime_report()
    )

    assert (
        report["failed"]
        == 0
    )
    assert (
        report["passed"]
        == 3
    )


def test_m14_portable_only_cannot_claim_acceptance(
    tmp_path,
):
    code, summary = (
        run_validation(
            report_root=tmp_path,
            skip_tests=True,
            skip_live_workstation=True,
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


def test_m14_live_workstation_is_required_for_acceptance(
    tmp_path,
):
    def live_runner():
        return {
            "passed": True,
            "clear_fact": {
                "passed": True,
            },
            "ambiguous_guard": {
                "passed": True,
            },
        }

    code, summary = (
        run_validation(
            report_root=tmp_path,
            skip_tests=True,
            live_runner=live_runner,
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
            "live_workstation"
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


def test_m14_failed_live_workstation_blocks_acceptance(
    tmp_path,
):
    def live_runner():
        return {
            "passed": False,
            "clear_fact": {
                "passed": False,
            },
            "ambiguous_guard": {
                "passed": True,
            },
        }

    code, summary = (
        run_validation(
            report_root=tmp_path,
            skip_tests=True,
            live_runner=live_runner,
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
