from __future__ import annotations

from benchmarks.evaluate_workstation_context import (
    _cases,
    evaluate,
)


def test_portable_long_context_benchmark_contract():
    rows = [
        evaluate(case)
        for case in _cases()
    ]
    by_name = {
        row["name"]: row
        for row in rows
    }

    assert set(by_name) == {
        "very_short",
        "medium",
        "near_8k_role",
        "near_16k_strong_code",
        "oversized_request",
        "long_history_short_current",
        "evidence_with_acceptance_criteria",
    }

    assert by_name["very_short"]["new_admission"] is True
    assert by_name["medium"]["new_admission"] is True

    eight = by_name["near_8k_role"]
    assert eight["new_admission"] is True
    assert eight["legacy_12000_char_admission"] is False
    assert eight["sentinels_preserved"] == eight[
        "sentinels_required"
    ]

    strong = by_name["near_16k_strong_code"]
    assert strong["new_admission"] is True
    assert strong["legacy_12000_char_admission"] is False
    assert strong["context_window"] == 16384
    assert strong["sentinels_preserved"] == strong[
        "sentinels_required"
    ]

    oversized = by_name["oversized_request"]
    assert oversized["new_admission"] is False
    assert oversized["status"] == "context_budget_exceeded"
    assert oversized["error"]["required_estimate"] > (
        oversized["error"]["maximum"]
    )

    history = by_name["long_history_short_current"]
    assert history["new_admission"] is True
    assert "recent_history" in history[
        "clipped_context_items"
    ]
    assert history["sentinels_preserved"] == history[
        "sentinels_required"
    ]

    evidence = by_name[
        "evidence_with_acceptance_criteria"
    ]
    assert evidence["new_admission"] is True
    assert evidence["sentinels_preserved"] == evidence[
        "sentinels_required"
    ]

    for row in rows:
        if row["new_admission"]:
            assert row[
                "estimated_prompt_tokens"
            ] <= row["input_budget_tokens"]
