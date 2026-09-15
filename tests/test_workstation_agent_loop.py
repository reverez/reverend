from __future__ import annotations

import time

import pytest

from reverend.workstation.agent_loop import (
    MAX_AUTO_CONTINUATIONS_PER_REQUEST,
    MAX_TOTAL_TASK_CONTINUATIONS,
    can_auto_continue,
    merge_continuation,
)
from reverend.workstation.service import Workstation


def finished(app, identity):
    deadline=time.monotonic()+5
    while time.monotonic()<deadline:
        job=app.store.job(identity)
        if job["status"] not in {
            "queued","running","stopping"
        }:
            return job
        time.sleep(.01)
    pytest.fail("Job did not finish")


def test_merge_continuation_removes_overlap_and_detects_no_progress():
    merged=merge_continuation(
        "alpha beta gamma",
        "beta gamma delta epsilon zeta eta theta",
    )
    assert merged.text=="alpha beta gamma delta epsilon zeta eta theta"
    assert merged.overlap_chars==10
    assert merged.progress is True

    repeated=merge_continuation(
        merged.text,
        "delta epsilon zeta",
    )
    assert repeated.text==merged.text
    assert repeated.progress is False


def test_continuation_decision_is_hard_bounded():
    allowed,reason=can_auto_continue(
        completion_reason="output_limit_reached",
        answer="partial answer",
        cancelled=False,
        active_task=True,
        model_calls=1,
        max_model_calls=4,
        auto_continuations=0,
        continuation_count=0,
    )
    assert allowed is True
    assert reason=="continue"

    allowed,reason=can_auto_continue(
        completion_reason="output_limit_reached",
        answer="partial answer",
        cancelled=False,
        active_task=True,
        model_calls=1,
        max_model_calls=4,
        auto_continuations=MAX_AUTO_CONTINUATIONS_PER_REQUEST,
        continuation_count=0,
    )
    assert allowed is False
    assert reason=="auto_continuation_cap"

    allowed,reason=can_auto_continue(
        completion_reason="output_limit_reached",
        answer="partial answer",
        cancelled=False,
        active_task=True,
        model_calls=1,
        max_model_calls=4,
        auto_continuations=0,
        continuation_count=MAX_TOTAL_TASK_CONTINUATIONS,
    )
    assert allowed is False
    assert reason=="task_continuation_cap"


class AutoScheduler:
    def __init__(self,responses):
        self.responses=list(responses)
        self.calls=[]

    def stream(self,role,prompt,cancel=None,**kwargs):
        self.calls.append((role,prompt,kwargs))
        response,completion=self.responses.pop(0)
        yield {
            "response":response,
            "done":True,
            "done_reason":(
                "length"
                if completion=="output_limit_reached"
                else "stop"
            ),
            "completion_reason":completion,
            "output_budget":kwargs.get("predict",1536),
            "response_chars":len(response),
            "answer_started":bool(response),
            "hidden_reasoning_present":False,
            "thinking_activity_count":0,
            "cancelled":False,
        }


def test_output_limit_auto_continues_and_merges(tmp_path):
    scheduler=AutoScheduler([
        (
            "Part one establishes the premise and bridge phrase.",
            "output_limit_reached",
        ),
        (
            "bridge phrase. Part two completes the answer safely.",
            "complete",
        ),
    ])
    app=Workstation(
        tmp_path/"state",
        scheduler_factory=lambda:scheduler,
    )
    try:
        submitted=app.chat(
            "Exercise 21 — produce a long structured answer.",
            max_model_calls=3,
        )
        job=finished(app,submitted["job_id"])

        assert job["status"]=="complete",job
        assert len(scheduler.calls)==2
        assert job["details"]["completion_reason"]=="complete"
        assert job["details"]["incomplete"] is False
        assert job["details"]["agent_loop"]["auto_continuations"]==1
        assert job["details"]["agent_loop"]["stop_reason"]=="natural_completion"
        assert job["response"]==(
            "Part one establishes the premise and bridge phrase. "
            "Part two completes the answer safely."
        )
        task=app.store.require_authoritative_task(
            submitted["conversation_id"]
        )
        assert task.checkpoint=={}
    finally:
        app.close()


def test_auto_continuation_stops_when_model_budget_is_exhausted(tmp_path):
    scheduler=AutoScheduler([
        (
            "This is a partial answer that needs more text.",
            "output_limit_reached",
        ),
    ])
    app=Workstation(
        tmp_path/"budget",
        scheduler_factory=lambda:scheduler,
    )
    try:
        submitted=app.chat(
            "Exercise 22 — produce a long answer.",
            max_model_calls=1,
        )
        job=finished(app,submitted["job_id"])

        assert job["status"]=="complete",job
        assert len(scheduler.calls)==1
        assert job["details"]["incomplete"] is True
        assert job["details"]["agent_loop"]["stop_reason"]==(
            "model_budget_exhausted"
        )
        assert job["details"]["checkpoint"]["available"] is True
    finally:
        app.close()


def test_auto_continuation_stops_on_no_progress(tmp_path):
    partial="Repeated partial answer long enough to count as original progress."
    scheduler=AutoScheduler([
        (partial,"output_limit_reached"),
        (partial,"output_limit_reached"),
    ])
    app=Workstation(
        tmp_path/"no-progress",
        scheduler_factory=lambda:scheduler,
    )
    try:
        submitted=app.chat(
            "Exercise 23 — produce a long answer.",
            max_model_calls=3,
        )
        job=finished(app,submitted["job_id"])

        assert job["status"]=="complete",job
        assert len(scheduler.calls)==2
        assert job["response"]==partial
        assert job["details"]["agent_loop"]["stop_reason"]=="no_progress"
        assert job["details"]["incomplete"] is True
        assert job["details"]["checkpoint"]["available"] is True
    finally:
        app.close()


def test_auto_continuation_hits_per_request_cap(tmp_path):
    scheduler=AutoScheduler([
        ("Segment one has enough novel output for progress.","output_limit_reached"),
        ("Segment two has enough novel output for progress.","output_limit_reached"),
        ("Segment three has enough novel output for progress.","output_limit_reached"),
    ])
    app=Workstation(
        tmp_path/"cap",
        scheduler_factory=lambda:scheduler,
    )
    try:
        submitted=app.chat(
            "Exercise 24 — produce a very long answer.",
            max_model_calls=4,
        )
        job=finished(app,submitted["job_id"])

        assert job["status"]=="complete",job
        assert len(scheduler.calls)==3
        assert job["details"]["agent_loop"]["auto_continuations"]==2
        assert job["details"]["agent_loop"]["stop_reason"]==(
            "auto_continuation_cap"
        )
        assert job["details"]["incomplete"] is True
        assert "Segment three" in job["response"]
    finally:
        app.close()
