from __future__ import annotations

import sqlite3
import time

import pytest

from reverend.workstation.service import Workstation
from reverend.workstation.store import PrivacyMode, WorkspaceStore
from reverend.workstation.task_state import (
    build_chat_checkpoint,
    checkpoint_is_resumable,
    checkpoint_prompt_block,
)


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


def test_checkpoint_contract_is_resumable_and_non_authoritative(tmp_path):
    store = WorkspaceStore(tmp_path / "workstation.db")
    conversation = store.create_conversation()
    task = store.create_authoritative_task(
        conversation,
        "Exercise 13",
        "Exercise 13 — continue the original task.",
    )
    checkpoint = build_chat_checkpoint(
        reason="output_limit_reached",
        partial_response="partial answer",
        source_job_id="job-1",
        role="fast_general",
        output_budget=1536,
        continuation_count=1,
    )
    store.update_authoritative_task(
        task.id,
        checkpoint=checkpoint,
    )
    task = store.authoritative_task(task.id)

    assert checkpoint_is_resumable(task.checkpoint) is True
    block = checkpoint_prompt_block(task)
    assert "NON-AUTHORITATIVE" in block
    assert "partial answer" in block
    assert "continue the original task" not in block


class SequenceScheduler:
    def __init__(self):
        self.calls = []

    def stream(self, role, prompt, cancel=None, **kwargs):
        self.calls.append((role, prompt, kwargs))
        if len(self.calls) == 1:
            yield {
                "response": "partial section",
                "done": True,
                "done_reason": "length",
                "completion_reason": "output_limit_reached",
                "output_budget": kwargs.get("predict", 1536),
                "response_chars": 15,
                "answer_started": True,
                "hidden_reasoning_present": False,
                "thinking_activity_count": 0,
                "cancelled": False,
            }
            return
        yield {
            "response": "continued final section",
            "done": True,
            "done_reason": "stop",
            "completion_reason": "complete",
            "output_budget": kwargs.get("predict", 1536),
            "response_chars": 23,
            "answer_started": True,
            "hidden_reasoning_present": False,
            "thinking_activity_count": 0,
            "cancelled": False,
        }


def test_output_limit_checkpoint_is_used_on_continue_and_cleared(tmp_path):
    scheduler = SequenceScheduler()
    app = Workstation(
        tmp_path / "state",
        scheduler_factory=lambda: scheduler,
    )
    try:
        first = app.chat(
            "Exercise 13 — produce the requested long draft.",
            max_model_calls=1,
        )
        first_job = finished(app, first["job_id"])
        assert first_job["status"] == "complete"
        assert first_job["details"]["completion_reason"] == (
            "output_limit_reached"
        )

        task = app.store.require_authoritative_task(
            first["conversation_id"]
        )
        assert task.checkpoint["reason"] == "output_limit_reached"
        assert task.checkpoint["partial_response"] == "partial section"

        second = app.chat(
            "Continue Exercise 13",
            conversation_id=first["conversation_id"],
        )
        second_job = finished(app, second["job_id"])

        assert second_job["status"] == "complete", second_job
        assert second_job["response"] == "continued final section"
        assert len(scheduler.calls) == 2
        resume_prompt = scheduler.calls[1][1]
        assert "EXECUTION CHECKPOINT — NON-AUTHORITATIVE STATE" in resume_prompt
        assert "partial section" in resume_prompt
        assert resume_prompt.count("partial section") == 1

        task = app.store.require_authoritative_task(
            first["conversation_id"]
        )
        assert task.checkpoint == {}
        assert second_job["details"]["checkpoint"][
            "cleared_after_success"
        ] is True
    finally:
        app.close()


def test_durable_checkpoint_payload_is_encrypted(tmp_path):
    store = WorkspaceStore(tmp_path / "workstation.db")
    conversation = store.create_conversation()
    task = store.create_authoritative_task(
        conversation,
        "Exercise 14",
        "Exercise 14 — persistent task.",
    )
    secret_partial = "SENSITIVE_PARTIAL_OUTPUT_42"
    checkpoint = build_chat_checkpoint(
        reason="in_progress",
        partial_response=secret_partial,
        source_job_id="job-2",
        role="fast_general",
        output_budget=1536,
    )
    store.update_authoritative_task(
        task.id,
        checkpoint=checkpoint,
    )

    with sqlite3.connect(store.path) as db:
        stored = db.execute(
            "SELECT checkpoint FROM authoritative_tasks WHERE id=?",
            (task.id,),
        ).fetchone()[0]

    assert secret_partial not in stored
    restored = store.authoritative_task(task.id)
    assert restored.checkpoint["partial_response"] == secret_partial


def test_ephemeral_checkpoint_never_enters_sqlite(tmp_path):
    app = Workstation(
        tmp_path / "ephemeral",
        scheduler_factory=lambda: SequenceScheduler(),
    )
    try:
        submitted = app.chat(
            "Exercise 15 — produce the requested long draft.",
            privacy_mode=PrivacyMode.EPHEMERAL,
            max_model_calls=1,
        )
        job = finished(app, submitted["job_id"])
        assert job["status"] == "complete"

        task = app.store.require_authoritative_task(
            submitted["conversation_id"]
        )
        assert task.checkpoint["reason"] == "output_limit_reached"

        with sqlite3.connect(app.store.path) as db:
            assert db.execute(
                "SELECT COUNT(*) FROM authoritative_tasks WHERE id=?",
                (task.id,),
            ).fetchone()[0] == 0
    finally:
        app.close()



class PartialOnlyScheduler:
    def __init__(self):
        self.prompts=[]

    def stream(self,role,prompt,cancel=None,**kwargs):
        self.prompts.append(prompt)
        yield {
            'response':'persisted partial after restart',
            'done':True,
            'done_reason':'length',
            'completion_reason':'output_limit_reached',
            'output_budget':kwargs.get('predict',1536),
            'response_chars':31,
            'answer_started':True,
            'hidden_reasoning_present':False,
            'thinking_activity_count':0,
            'cancelled':False,
        }


class FinalOnlyScheduler:
    def __init__(self,response='resumed final answer'):
        self.response=response
        self.prompts=[]

    def stream(self,role,prompt,cancel=None,**kwargs):
        self.prompts.append(prompt)
        yield {
            'response':self.response,
            'done':True,
            'done_reason':'stop',
            'completion_reason':'complete',
            'output_budget':kwargs.get('predict',1536),
            'response_chars':len(self.response),
            'answer_started':True,
            'hidden_reasoning_present':False,
            'thinking_activity_count':0,
            'cancelled':False,
        }


def test_checkpoint_survives_workstation_restart_and_resumes(tmp_path):
    root=tmp_path/'restart-state'
    partial_scheduler=PartialOnlyScheduler()
    first_app=Workstation(
        root,
        scheduler_factory=lambda:partial_scheduler,
    )
    try:
        first=first_app.chat(
            'Exercise 16 — produce the requested long draft.'
        )
        first_job=finished(
            first_app,
            first['job_id'],
        )
        assert first_job['status']=='complete'
        conversation=first['conversation_id']
        first_task=(
            first_app.store
            .require_authoritative_task(
                conversation
            )
        )
        assert first_task.checkpoint['reason']==(
            'output_limit_reached'
        )
        assert (
            first_task.checkpoint['partial_response']
            =='persisted partial after restart'
        )
    finally:
        first_app.close()

    final_scheduler=FinalOnlyScheduler()
    second_app=Workstation(
        root,
        scheduler_factory=lambda:final_scheduler,
    )
    try:
        recovered=(
            second_app.store
            .require_authoritative_task(
                conversation
            )
        )
        assert recovered.checkpoint['reason']==(
            'output_limit_reached'
        )

        continued=second_app.chat(
            'Continue Exercise 16',
            conversation_id=conversation,
        )
        continued_job=finished(
            second_app,
            continued['job_id'],
        )

        assert continued_job['status']=='complete'
        assert continued_job['response']==(
            'resumed final answer'
        )
        assert final_scheduler.prompts
        prompt=final_scheduler.prompts[-1]
        assert (
            'EXECUTION CHECKPOINT — NON-AUTHORITATIVE STATE'
            in prompt
        )
        assert (
            'persisted partial after restart'
            in prompt
        )

        recovered=(
            second_app.store
            .require_authoritative_task(
                conversation
            )
        )
        assert recovered.checkpoint=={}
        assert continued_job['details']['checkpoint'][
            'cleared_after_success'
        ] is True
    finally:
        second_app.close()


class AlwaysInvalidVerificationScheduler:
    def __init__(self):
        self.calls=[]

    def stream(self,role,prompt,cancel=None,**kwargs):
        self.calls.append((role,prompt,kwargs))
        response='- one\n- two\n- three'
        yield {
            'response':response,
            'done':True,
            'done_reason':'stop',
            'completion_reason':'complete',
            'output_budget':kwargs.get('predict',1536),
            'response_chars':len(response),
            'answer_started':True,
            'hidden_reasoning_present':False,
            'thinking_activity_count':0,
            'cancelled':False,
        }


def test_verification_failure_preserves_terminal_checkpoint(
    tmp_path,
):
    scheduler=AlwaysInvalidVerificationScheduler()
    app=Workstation(
        tmp_path/'verification-checkpoint',
        scheduler_factory=lambda:scheduler,
    )
    specification=(
        'Exercise 17\n'
        'Requirements:\n'
        '- The output MUST contain exactly 2 items.'
    )
    try:
        submitted=app.chat(
            specification,
            max_model_calls=3,
        )
        job=finished(
            app,
            submitted['job_id'],
        )

        assert job['status']=='failed', job
        assert job['details']['error_code']==(
            'verification_failed'
        )
        task=app.store.require_authoritative_task(
            submitted['conversation_id']
        )
        assert task.checkpoint['reason']==(
            'verification_failed'
        )
        assert task.checkpoint[
            'continuation_eligible'
        ] is True
        assert (
            task.checkpoint['partial_response']
            =='- one\n- two\n- three'
        )
        assert job['details']['checkpoint']['reason']==(
            'verification_failed'
        )
        assert len(scheduler.calls)==2
    finally:
        app.close()
