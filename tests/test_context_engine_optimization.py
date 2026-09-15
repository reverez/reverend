from __future__ import annotations

import time

import pytest

from reverend.workstation.context import (
    ContextBudgetExceededError,
    apply_provider_prompt_tokens,
    compile_chat_prompt_v2,
    compute_context_budget,
    estimate_chat_tokens,
)
from reverend.workstation.service import Workstation


class Scheduler:
    def __init__(self):
        self.prompts = []

    def stream(self, role, prompt, cancel=None, **kwargs):
        self.prompts.append(prompt)
        yield {
            "response": "answer",
            "done": True,
            "done_reason": "stop",
            "completion_reason": "complete",
            "prompt_tokens": estimate_chat_tokens(prompt) - 8,
            "generated_tokens": 2,
            "output_budget": kwargs.get("predict", 1536),
            "response_chars": 6,
            "answer_started": True,
            "hidden_reasoning_present": False,
            "thinking_activity_count": 0,
            "cancelled": False,
        }


def finished(app, identity):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        job = app.store.job(identity)
        if job["status"] not in {
            "queued",
            "running",
            "stopping",
        }:
            return job
        time.sleep(.01)
    pytest.fail("Job did not finish")


def test_role_budget_preserves_output_and_safety_reserves():
    fast = compute_context_budget(
        context_window=8192,
        output_reserve_tokens=1536,
    )
    strong = compute_context_budget(
        context_window=16384,
        output_reserve_tokens=4096,
    )

    assert fast.input_budget_tokens == 6144
    assert strong.input_budget_tokens == 11776
    assert (
        strong.input_budget_tokens
        + strong.output_reserve_tokens
        + strong.safety_margin_tokens
        == strong.context_window
    )


def test_estimator_is_conservative_for_code_and_unicode_shapes():
    prose = "alpha beta gamma " * 100
    code = "value = items[index] + mapping.get(key, 0)\n" * 100
    unicode_text = "矩阵向量计算🙂 " * 100

    assert estimate_chat_tokens(prose) >= len(prose) / 2.5
    assert estimate_chat_tokens(code) >= len(code) / 2.5
    assert estimate_chat_tokens(unicode_text) >= (
        len(unicode_text.encode("utf-8")) / 3
    )


def test_strong_code_can_compile_request_far_above_legacy_12k_ceiling():
    request = (
        "BEGIN_CRITICAL\n"
        + "A" * 26000
        + "\nEND_CRITICAL"
    )

    prompt, metadata = compile_chat_prompt_v2(
        instruction="System security instruction.",
        current_request=request,
        context_window=16384,
        output_reserve_tokens=4096,
        model_role="strong_code",
    )

    assert len(request) > 12000
    assert "BEGIN_CRITICAL" in prompt
    assert "END_CRITICAL" in prompt
    assert metadata["model_role"] == "strong_code"
    assert metadata["estimated_prompt_tokens"] <= 11776
    assert metadata["generation_reserve_tokens"] == 4096
    assert metadata["safety_margin_tokens"] == 512


def test_same_required_request_fails_explicitly_on_smaller_role():
    request = "A" * 26000

    with pytest.raises(
        ContextBudgetExceededError
    ) as captured:
        compile_chat_prompt_v2(
            instruction="System security instruction.",
            current_request=request,
            context_window=8192,
            output_reserve_tokens=1536,
            model_role="fast_general",
        )

    error = captured.value
    assert error.code == "context_budget_exceeded"
    assert error.details["model_role"] == "fast_general"
    assert error.details["required_estimate"] > error.details["maximum"]
    assert error.details["maximum"] == 6144


def test_authoritative_beginning_and_end_survive_optional_pressure():
    task = (
        "AUTHORITATIVE TASK — TRUSTED USER STATE\n"
        "BEGIN_ACCEPTANCE_ALPHA\n"
        + "requirement " * 700
        + "\nEND_ACCEPTANCE_OMEGA"
    )

    prompt, metadata = compile_chat_prompt_v2(
        instruction="SYSTEM_SECURITY_INVARIANT",
        current_request="Continue exactly.",
        authoritative_task=task,
        context_window=8192,
        output_reserve_tokens=1536,
        checkpoint_context="checkpoint " * 3000,
        evidence_sources=[
            {
                "source": "reference://one",
                "content": "evidence " * 4000,
                "trust_class": "TRUSTED_REFERENCE",
            }
        ],
        project_context="project " * 4000,
        memory_context="memory " * 2000,
        recent_messages=[
            {
                "role": "user",
                "content": "history " * 2000,
            }
            for _ in range(12)
        ],
        retrieved_messages=[
            {
                "role": "user",
                "content": "older " * 2000,
            }
        ],
        summary="summary " * 2000,
    )

    assert "SYSTEM_SECURITY_INVARIANT" in prompt
    assert "BEGIN_ACCEPTANCE_ALPHA" in prompt
    assert "END_ACCEPTANCE_OMEGA" in prompt
    assert "Continue exactly." in prompt
    assert metadata["non_evictable_context_items"] == (
        "system_instruction",
        "authoritative_task",
        "current_request",
    )
    assert (
        metadata["clipped_context_items"]
        or metadata["omitted_context_items"]
    )
    assert metadata["estimated_prompt_tokens"] <= metadata[
        "input_budget_tokens"
    ]



def test_structured_first_turn_deduplication_avoids_duplicate_authority():
    request = "Build this exact task once."

    prompt, metadata = compile_chat_prompt_v2(
        instruction="System.",
        current_request=request,
        authoritative_task=(
            "AUTHORITATIVE TASK — TRUSTED USER STATE\n"
            + request
        ),
        current_request_is_authoritative_task=True,
        context_window=8192,
        output_reserve_tokens=1536,
    )

    assert prompt.count(request) == 1
    assert (
        "CURRENT USER REQUEST — TRUSTED USER INSTRUCTION"
        not in prompt
    )
    assert metadata["non_evictable_context_items"] == (
        "system_instruction",
        "authoritative_task",
    )


def test_substring_continuation_remains_explicit_and_non_evictable():
    prompt, metadata = compile_chat_prompt_v2(
        instruction="System.",
        current_request="continue",
        authoritative_task=(
            "AUTHORITATIVE TASK — TRUSTED USER STATE\n"
            "Do not continue past phase three without verification."
        ),
        context_window=8192,
        output_reserve_tokens=1536,
    )

    assert (
        "CURRENT USER REQUEST — TRUSTED USER INSTRUCTION\ncontinue"
        in prompt
    )
    assert metadata["non_evictable_context_items"] == (
        "system_instruction",
        "authoritative_task",
        "current_request",
    )


def test_workstation_deduplicates_only_task_created_from_current_turn(
    tmp_path,
):
    scheduler = Scheduler()
    app = Workstation(
        tmp_path / "state",
        scheduler_factory=lambda: scheduler,
    )
    try:
        specification = (
            "Implement this multi-step requirements plan.\n"
            "Do not continue past phase three without verification.\n"
            + "requirement " * 220
        )

        first = app.chat(
            specification,
            mode="ask",
        )
        first_job = finished(
            app,
            first["job_id"],
        )
        assert first_job["status"] == "complete", first_job["details"]

        first_prompt = scheduler.prompts[-1]
        assert first_prompt.count(specification.strip()) == 1
        assert (
            "CURRENT USER REQUEST — TRUSTED USER INSTRUCTION"
            not in first_prompt
        )

        second = app.chat(
            "continue",
            conversation_id=first["conversation_id"],
            mode="ask",
        )
        second_job = finished(
            app,
            second["job_id"],
        )
        assert second_job["status"] == "complete", second_job["details"]

        second_prompt = scheduler.prompts[-1]
        assert (
            "CURRENT USER REQUEST — TRUSTED USER INSTRUCTION\ncontinue"
            in second_prompt
        )
    finally:
        app.close()

def test_long_history_cannot_evict_short_current_request():
    prompt, metadata = compile_chat_prompt_v2(
        instruction="System.",
        current_request="CURRENT_REQUEST_SENTINEL",
        context_window=8192,
        output_reserve_tokens=1536,
        recent_messages=[
            {
                "role": "user",
                "content": f"old-{index} " + "x" * 4000,
            }
            for index in range(20)
        ],
    )

    assert "CURRENT_REQUEST_SENTINEL" in prompt
    assert metadata["current_request_tokens"] > 0
    assert "recent_history" in metadata["clipped_context_items"]


def test_provider_prompt_truth_is_telemetry_only():
    _, metadata = compile_chat_prompt_v2(
        instruction="System.",
        current_request="Hello.",
        context_window=8192,
        output_reserve_tokens=1536,
    )
    estimate = metadata["estimated_prompt_tokens"]

    apply_provider_prompt_tokens(
        metadata,
        max(1, estimate - 3),
    )

    assert metadata["actual_provider_prompt_tokens"] == max(
        1,
        estimate - 3,
    )
    assert metadata["prompt_token_estimate_delta"] >= 0
    assert metadata["prompt_token_estimator_conservative"] is True


def test_workstation_accepts_more_than_12000_chars_when_safe(tmp_path):
    scheduler = Scheduler()
    app = Workstation(
        tmp_path / "state",
        scheduler_factory=lambda: scheduler,
    )
    try:
        request = (
            "Summarize this safely.\n"
            + "alpha " * 2150
        )
        assert len(request) > 12000

        submitted = app.chat(
            request,
            mode="ask",
        )
        job = finished(
            app,
            submitted["job_id"],
        )

        assert job["status"] == "complete", job["details"]
        assert scheduler.prompts
        assert request.strip() in scheduler.prompts[-1]
        assert job["details"]["context_compiler"] == "v2"
        assert (
            job["details"]["actual_provider_prompt_tokens"]
            > 0
        )
    finally:
        app.close()


def test_workstation_reports_structured_context_overflow(tmp_path):
    scheduler = Scheduler()
    app = Workstation(
        tmp_path / "state",
        scheduler_factory=lambda: scheduler,
    )
    try:
        submitted = app.chat(
            "Oversized request.\n" + "x" * 50000,
            mode="ask",
        )
        job = finished(
            app,
            submitted["job_id"],
        )

        assert job["status"] == "failed", job["details"]
        assert job["details"].get("error_code") == (
            "context_budget_exceeded"
        ), job["details"]
        details = job["details"]["error_details"]
        assert details["required_estimate"] > details["maximum"]
        assert details["context_window"] == 8192
        assert details["model_role"] == "fast_general"
        assert scheduler.prompts == []
    finally:
        app.close()
