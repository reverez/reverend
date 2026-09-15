from __future__ import annotations

import time

import pytest

from reverend.workstation.service import Workstation
from reverend.workstation.store import WorkspaceStore
from reverend.workstation.verification import (
    verify_authoritative_response,
)


def _task(tmp_path, requirements=(), criteria=()):
    store = WorkspaceStore(tmp_path / "workstation.db")
    conversation = store.create_conversation()
    task = store.create_authoritative_task(
        conversation,
        "verification task",
        "Requirements and acceptance criteria for verification.",
        immutable_requirements=requirements,
        acceptance_criteria=criteria,
        provenance={
            "requirement_extraction": {
                "high_assurance": True,
            }
        },
    )
    return store, task


def test_exact_list_item_verifier_passes_and_fails(tmp_path):
    store, task = _task(
        tmp_path,
        requirements=("The output MUST contain exactly 2 items.",),
    )
    passed = verify_authoritative_response(
        "- alpha\n- beta",
        task,
    )
    failed = verify_authoritative_response(
        "- alpha\n- beta\n- gamma",
        task,
    )
    assert passed.outcome == "pass"
    assert passed.checks[0].method == "list_item_count"
    assert failed.outcome == "fail"
    assert failed.checks[0].observed == 3


def test_forbidden_literal_and_word_limit_verifiers(tmp_path):
    store, task = _task(
        tmp_path,
        requirements=(
            "DO NOT emit \x22BETA\x22.",
            "The answer must be at most 4 words.",
        ),
    )
    report = verify_authoritative_response(
        "alpha gamma delta",
        task,
    )
    assert report.outcome == "pass"

    broken = verify_authoritative_response(
        "alpha BETA gamma delta epsilon",
        task,
    )
    assert broken.outcome == "fail"
    assert broken.failed_count == 2


def test_semantic_requirement_is_never_falsely_certified(tmp_path):
    store, task = _task(
        tmp_path,
        requirements=(
            "Preserve the mathematical meaning of the proof.",
        ),
    )
    report = verify_authoritative_response(
        "A plausible proof.",
        task,
    )
    assert report.outcome == "unchecked"
    assert report.unchecked_count == 1
    assert report.checks[0].method == "semantic_only"


class RepairScheduler:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def stream(self, role, prompt, cancel=None, **kwargs):
        self.calls.append((role, prompt, kwargs))
        response = self.responses.pop(0)
        yield {
            "response": response,
            "done": True,
            "done_reason": "stop",
            "completion_reason": "complete",
            "output_budget": kwargs.get("predict", 1536),
            "response_chars": len(response),
            "answer_started": bool(response),
            "hidden_reasoning_present": False,
            "thinking_activity_count": 0,
            "cancelled": False,
        }


def _finished(app, identity):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        job = app.store.job(identity)
        if job["status"] not in {
            "queued", "running", "stopping"
        }:
            return job
        time.sleep(.01)
    pytest.fail("Job did not finish")


def test_high_assurance_failure_repairs_once_and_rechecks(tmp_path):
    scheduler = RepairScheduler([
        "- one\n- two\n- three",
        "- one\n- two",
    ])
    app = Workstation(
        tmp_path / "state",
        scheduler_factory=lambda: scheduler,
    )
    specification = (
        "Exercise 11\n"
        "Requirements:\n"
        "- The output MUST contain exactly 2 items."
    )
    try:
        submitted = app.chat(
            specification,
            max_model_calls=3,
        )
        job = _finished(app, submitted["job_id"])

        assert job["status"] == "complete", job
        assert job["response"] == "- one\n- two"
        assert len(scheduler.calls) == 2
        assert job["details"]["verification"]["outcome"] == "pass"
        assert job["details"]["verification"]["repair_attempted"] is True
        assert job["details"]["verification"]["initial_result"][
            "outcome"
        ] == "fail"

        messages = app.store.messages(
            submitted["conversation_id"]
        )
        assert messages[-1]["content"] == "- one\n- two"
    finally:
        app.close()


def test_failed_repair_fails_closed_and_is_typed(tmp_path):
    scheduler = RepairScheduler([
        "- one\n- two\n- three",
        "- one\n- two\n- three",
    ])
    app = Workstation(
        tmp_path / "state-fail",
        scheduler_factory=lambda: scheduler,
    )
    specification = (
        "Exercise 12\n"
        "Requirements:\n"
        "- The output MUST contain exactly 2 items."
    )
    try:
        submitted = app.chat(
            specification,
            max_model_calls=3,
        )
        job = _finished(app, submitted["job_id"])

        assert job["status"] == "failed", job
        assert job["details"]["error_code"] == "verification_failed"
        assert job["details"]["verification"]["repair_attempted"] is True
        assert job["details"]["verification"]["repair_result"][
            "outcome"
        ] == "fail"

        messages = app.store.messages(
            submitted["conversation_id"]
        )
        assert [row["role"] for row in messages] == ["user"]
    finally:
        app.close()



def test_return_exactly_is_machine_checked(tmp_path):
    _, task = _task(
        tmp_path / "return-exact",
        requirements=('Return exactly "OK".',),
    )
    passed = verify_authoritative_response(
        "OK",
        task,
    )
    failed = verify_authoritative_response(
        "OK.",
        task,
    )
    assert passed.outcome == "pass"
    assert passed.checks[0].method == "exact_response"
    assert failed.outcome == "fail"


def test_json_object_and_array_shapes_are_enforced(tmp_path):
    _, object_task = _task(
        tmp_path / "json-object",
        requirements=("Return a valid JSON object.",),
    )
    object_pass = verify_authoritative_response(
        '{"value": 1}',
        object_task,
    )
    object_fail = verify_authoritative_response(
        '[1, 2, 3]',
        object_task,
    )
    assert object_pass.outcome == "pass"
    assert object_pass.checks[0].method == "json_shape"
    assert object_fail.outcome == "fail"
    assert object_fail.checks[0].expected == "object"
    assert object_fail.checks[0].observed == "array"

    _, array_task = _task(
        tmp_path / "json-array",
        requirements=("Return a JSON array.",),
    )
    array_pass = verify_authoritative_response(
        '[1, 2]',
        array_task,
    )
    array_fail = verify_authoritative_response(
        '{"value": 1}',
        array_task,
    )
    assert array_pass.outcome == "pass"
    assert array_fail.outcome == "fail"
