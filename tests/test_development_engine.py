from __future__ import annotations

from types import SimpleNamespace

import pytest

import reverend.development.engine as engine_module
from reverend.development.engine import (
    DevelopmentEngineError,
    run_development_task,
)
from reverend.workers import (
    WorkerRole,
    WorkerStopReason,
)


class DummyConnection:
    pass


def task():
    return SimpleNamespace(
        id="task-1",
        worktree_path="/tmp/worktree",
    )


def plan_run(
    *,
    more=False,
):
    return SimpleNamespace(
        plan=SimpleNamespace(
            needs_more_context=more,
        )
    )


def implementation_run(
    *,
    more=False,
):
    return SimpleNamespace(
        needs_more_context=more,
        proposals=("proposal",),
    )


def fresh_result(
    verdict="pass",
):
    return SimpleNamespace(
        verdict=verdict,
    )


def patch_common(
    monkeypatch,
    *,
    plan_more=False,
    implementation_more=False,
    verdict="pass",
):
    monkeypatch.setattr(
        engine_module,
        "get_task",
        lambda connection, task_id: task(),
    )

    monkeypatch.setattr(
        engine_module,
        "generate_coding_plan",
        lambda *args, **kwargs: plan_run(
            more=plan_more
        ),
    )

    monkeypatch.setattr(
        engine_module,
        "generate_implementation_proposals",
        lambda *args, **kwargs: implementation_run(
            more=implementation_more
        ),
    )

    monkeypatch.setattr(
        engine_module,
        "apply_edits",
        lambda *args, **kwargs: SimpleNamespace(
            changed_paths=("value.py",)
        ),
    )

    monkeypatch.setattr(
        engine_module,
        "discover_verification_plan",
        lambda *args, **kwargs: (
            SimpleNamespace(
                name="pytest"
            ),
        ),
    )

    monkeypatch.setattr(
        engine_module,
        "make_local_repair_strategy",
        lambda *args, **kwargs: (
            lambda request: ()
        ),
    )

    monkeypatch.setattr(
        engine_module,
        "run_repair_loop",
        lambda *args, **kwargs: SimpleNamespace(
            passed=True,
            repairs_used=0,
        ),
    )

    monkeypatch.setattr(
        engine_module,
        "run_fresh_verifier",
        lambda *args, **kwargs: fresh_result(
            verdict
        ),
    )


def test_complete_pass(
    monkeypatch,
):
    patch_common(
        monkeypatch,
        verdict="pass",
    )

    result = run_development_task(
        DummyConnection(),
        "task-1",
        object(),
    )

    assert result.passed
    assert result.status == "pass"
    assert result.repair.repairs_used == 0
    assert result.orchestration.stop_reason is WorkerStopReason.COMPLETE
    assert result.orchestration.workers_used == 3
    assert result.orchestration.worker_steps == 3
    assert result.orchestration.tool_calls == 0
    assert [record.role for record in result.orchestration.records] == [
        WorkerRole.CODE_LOCALIZER,
        WorkerRole.CODER,
        WorkerRole.CRITIC_VERIFIER,
    ]
    coder = next(
        record
        for record in result.orchestration.records
        if record.role is WorkerRole.CODER
    )
    assert coder.verified_by == "coder:verify"


def test_stage_events_mark_entry_and_completion(
    monkeypatch,
):
    patch_common(
        monkeypatch,
        verdict="pass",
    )
    monkeypatch.setattr(
        engine_module,
        "asdict",
        lambda value: {
            "needs_more_context": bool(
                getattr(value, "needs_more_context", False)
            )
        },
    )
    events=[]

    result=run_development_task(
        DummyConnection(),
        "task-1",
        object(),
        on_event=lambda phase,payload: events.append(
            (phase, payload)
        ),
    )

    assert result.status=="pass"
    assert [phase for phase,_ in events]==[
        "plan",
        "localization",
        "acceptance",
        "plan",
        "implementation",
        "edits",
        "verification",
        "verification",
        "repair",
        "fresh_verifier",
        "fresh_verifier",
        "workers",
    ]
    assert events[0][1]["stage_status"]=="running"
    assert events[3][1]["stage_status"]=="complete"
    assert events[4][1]["stage_status"]=="running"
    assert events[5][1]["stage_status"]=="complete"
    assert events[6][1]["stage_status"]=="running"
    assert events[7][1]["stage_status"]=="complete"
    assert events[9][1]["stage_status"]=="running"
    assert events[10][1]["stage_status"]=="complete"


def test_final_fail_is_propagated(
    monkeypatch,
):
    patch_common(
        monkeypatch,
        verdict="fail",
    )

    result = run_development_task(
        DummyConnection(),
        "task-1",
        object(),
    )

    assert not result.passed
    assert result.status == "fail"
    assert (
        result.orchestration.stop_reason
        is WorkerStopReason.VERIFIER_REJECTED
    )


def test_unverified_is_propagated(
    monkeypatch,
):
    patch_common(
        monkeypatch,
        verdict="unverified",
    )

    result = run_development_task(
        DummyConnection(),
        "task-1",
        object(),
    )

    assert result.status == "unverified"
    assert (
        result.orchestration.stop_reason
        is WorkerStopReason.VERIFIER_REJECTED
    )


def test_plan_more_context_blocks_before_edits(
    monkeypatch,
):
    called = False

    monkeypatch.setattr(
        engine_module,
        "get_task",
        lambda connection, task_id: task(),
    )

    monkeypatch.setattr(
        engine_module,
        "generate_coding_plan",
        lambda *args, **kwargs: plan_run(
            more=True
        ),
    )

    def edits(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(
        engine_module,
        "apply_edits",
        edits,
    )

    result = run_development_task(
        DummyConnection(),
        "task-1",
        object(),
    )

    assert result.status == "blocked"
    assert not called
    assert (
        result.orchestration.stop_reason
        is WorkerStopReason.WORKER_BLOCKED
    )
    assert result.orchestration.workers_used == 1


def test_implementation_more_context_blocks_before_edits(
    monkeypatch,
):
    monkeypatch.setattr(
        engine_module,
        "get_task",
        lambda connection, task_id: task(),
    )

    monkeypatch.setattr(
        engine_module,
        "generate_coding_plan",
        lambda *args, **kwargs: plan_run(),
    )

    monkeypatch.setattr(
        engine_module,
        "generate_implementation_proposals",
        lambda *args, **kwargs: implementation_run(
            more=True
        ),
    )

    called = False

    def edits(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(
        engine_module,
        "apply_edits",
        edits,
    )

    result = run_development_task(
        DummyConnection(),
        "task-1",
        object(),
    )

    assert result.status == "blocked"
    assert not called
    assert (
        result.orchestration.stop_reason
        is WorkerStopReason.WORKER_BLOCKED
    )
    assert result.orchestration.workers_used == 2


def test_no_checks_returns_unverified(
    monkeypatch,
):
    patch_common(
        monkeypatch,
    )

    monkeypatch.setattr(
        engine_module,
        "discover_verification_plan",
        lambda *args, **kwargs: (),
    )

    result = run_development_task(
        DummyConnection(),
        "task-1",
        object(),
    )

    assert (
        result.status
        == "unverified"
    )

    assert (
        result.verifier
        is None
    )
    assert (
        result.orchestration.stop_reason
        is WorkerStopReason.WORKER_BLOCKED
    )
    assert result.orchestration.workers_used == 2


def test_missing_worktree_rejected(
    monkeypatch,
):
    monkeypatch.setattr(
        engine_module,
        "get_task",
        lambda connection, task_id: SimpleNamespace(
            id=task_id,
            worktree_path=None,
        ),
    )

    with pytest.raises(
        DevelopmentEngineError
    ):
        run_development_task(
            DummyConnection(),
            "task-1",
            object(),
        )



def test_fresh_verifier_failure_triggers_one_bounded_corrective_cycle(
    monkeypatch,
):
    monkeypatch.setattr(
        engine_module,
        "get_task",
        lambda connection, task_id: task(),
    )

    feedbacks=[]
    def planner(*args,**kwargs):
        feedbacks.append(kwargs.get("corrective_feedback"))
        return plan_run()

    monkeypatch.setattr(
        engine_module,
        "generate_coding_plan",
        planner,
    )
    monkeypatch.setattr(
        engine_module,
        "generate_implementation_proposals",
        lambda *args,**kwargs: implementation_run(),
    )
    monkeypatch.setattr(
        engine_module,
        "apply_edits",
        lambda *args,**kwargs: SimpleNamespace(
            changed_paths=("value.py",)
        ),
    )
    monkeypatch.setattr(
        engine_module,
        "discover_verification_plan",
        lambda *args,**kwargs:(
            SimpleNamespace(name="pytest"),
        ),
    )
    monkeypatch.setattr(
        engine_module,
        "make_local_repair_strategy",
        lambda *args,**kwargs:(lambda request:()),
    )
    monkeypatch.setattr(
        engine_module,
        "run_repair_loop",
        lambda *args,**kwargs:SimpleNamespace(
            passed=True,
            repairs_used=0,
        ),
    )

    verifier_results=iter((
        SimpleNamespace(
            verdict="fail",
            summary="The requested application was not implemented.",
            findings=(),
            risks=(),
        ),
        SimpleNamespace(
            verdict="pass",
            summary="The corrective implementation satisfies the task.",
            findings=(),
            risks=(),
        ),
    ))
    monkeypatch.setattr(
        engine_module,
        "run_fresh_verifier",
        lambda *args,**kwargs:next(verifier_results),
    )

    result=run_development_task(
        DummyConnection(),
        "task-1",
        object(),
        max_repairs=2,
    )

    assert result.status=="pass"
    assert result.semantic_repairs_used==1
    assert result.total_repairs_used==1
    assert result.orchestration.stop_reason is WorkerStopReason.COMPLETE
    assert result.orchestration.workers_used==6
    assert feedbacks[0] is None
    assert "requested application was not implemented" in feedbacks[1]


def test_semantic_repair_respects_zero_repair_budget(
    monkeypatch,
):
    patch_common(
        monkeypatch,
        verdict="fail",
    )

    result=run_development_task(
        DummyConnection(),
        "task-1",
        object(),
        max_repairs=0,
    )

    assert result.status=="fail"
    assert result.semantic_repairs_used==0
    assert result.total_repairs_used==0
    assert result.orchestration.workers_used==3


def test_development_trace_exposes_structured_stage_events(monkeypatch):
    patch_common(monkeypatch, verdict="pass")
    events = []

    result = run_development_task(
        DummyConnection(),
        "task-1",
        object(),
        on_event=lambda name, payload: events.append((name, payload)),
    )

    assert result.passed
    names = [name for name, _ in events]
    assert "localization" in names
    assert "acceptance" in names
    assert "plan" in names
    assert "edits" in names
    assert "verification" in names
    assert "repair" in names
    assert "fresh_verifier" in names
    assert "workers" in names

    verification = next(payload for name, payload in events if name == "verification")
    assert verification["checks"][0]["name"] == "pytest"


def test_whitespace_edit_validation_retries_within_repair_budget(monkeypatch):
    patch_common(monkeypatch,verdict="pass")

    feedbacks=[]
    def generate(*args,**kwargs):
        feedbacks.append(kwargs.get("corrective_feedback"))
        return implementation_run()
    monkeypatch.setattr(
        engine_module,
        "generate_implementation_proposals",
        generate,
    )

    edit_calls={"count":0}
    def edits(*args,**kwargs):
        edit_calls["count"]+=1
        if edit_calls["count"]==1:
            raise engine_module.EditApplyError(
                "Applied edits failed Git whitespace validation: "
                "value.py:9: trailing whitespace."
            )
        return SimpleNamespace(
            changed_paths=("value.py",),
            diff="",
        )
    monkeypatch.setattr(engine_module,"apply_edits",edits)

    result=run_development_task(
        DummyConnection(),
        "task-1",
        object(),
        max_repairs=2,
    )

    assert result.status=="pass"
    assert edit_calls["count"]==2
    assert feedbacks[0] is None
    assert "trailing whitespace" in feedbacks[1]
    assert result.total_repairs_used==1


def test_non_whitespace_edit_apply_error_remains_fatal(monkeypatch):
    patch_common(monkeypatch,verdict="pass")
    calls={"implement":0}

    def generate(*args,**kwargs):
        calls["implement"]+=1
        return implementation_run()
    monkeypatch.setattr(
        engine_module,
        "generate_implementation_proposals",
        generate,
    )
    monkeypatch.setattr(
        engine_module,
        "apply_edits",
        lambda *args,**kwargs: (_ for _ in ()).throw(
            engine_module.EditApplyError(
                "Edit application failed and rollback was incomplete."
            )
        ),
    )

    with pytest.raises(engine_module.EditApplyError):
        run_development_task(
            DummyConnection(),
            "task-1",
            object(),
            max_repairs=2,
        )
    assert calls["implement"]==1


def test_whitespace_retry_respects_zero_repair_budget(monkeypatch):
    patch_common(monkeypatch,verdict="pass")
    calls={"implement":0}

    def generate(*args,**kwargs):
        calls["implement"]+=1
        return implementation_run()
    monkeypatch.setattr(
        engine_module,
        "generate_implementation_proposals",
        generate,
    )
    monkeypatch.setattr(
        engine_module,
        "apply_edits",
        lambda *args,**kwargs: (_ for _ in ()).throw(
            engine_module.EditApplyError(
                "Applied edits failed Git whitespace validation: "
                "value.py:9: trailing whitespace."
            )
        ),
    )

    with pytest.raises(engine_module.EditApplyError):
        run_development_task(
            DummyConnection(),
            "task-1",
            object(),
            max_repairs=0,
        )
    assert calls["implement"]==1


def test_empty_implementation_response_retries_within_repair_budget(monkeypatch):
    patch_common(monkeypatch,verdict="pass")
    calls=[]

    def generate(*args,**kwargs):
        calls.append(kwargs.get("corrective_feedback"))
        if len(calls)==1:
            raise engine_module.ImplementationResponseError(
                "Repair response contains no edits."
            )
        return implementation_run()

    monkeypatch.setattr(
        engine_module,
        "generate_implementation_proposals",
        generate,
    )

    result=run_development_task(
        DummyConnection(),
        "task-1",
        object(),
        max_repairs=2,
    )

    assert result.status=="pass"
    assert len(calls)==2
    assert calls[0] is None
    assert "no usable edits" in calls[1]
    assert "edits=[]" in calls[1]
    assert result.total_repairs_used==1


def test_empty_implementation_response_respects_zero_repair_budget(monkeypatch):
    patch_common(monkeypatch,verdict="pass")
    calls={"count":0}

    def generate(*args,**kwargs):
        calls["count"]+=1
        raise engine_module.ImplementationResponseError(
            "Repair response contains no edits."
        )

    monkeypatch.setattr(
        engine_module,
        "generate_implementation_proposals",
        generate,
    )

    with pytest.raises(
        engine_module.ImplementationResponseError,
        match="no edits",
    ):
        run_development_task(
            DummyConnection(),
            "task-1",
            object(),
            max_repairs=0,
        )
    assert calls["count"]==1


def test_other_implementation_contract_errors_remain_fatal(monkeypatch):
    patch_common(monkeypatch,verdict="pass")
    calls={"count":0}

    def generate(*args,**kwargs):
        calls["count"]+=1
        raise engine_module.ImplementationResponseError(
            "Implementation edits do not match approved plan paths."
        )

    monkeypatch.setattr(
        engine_module,
        "generate_implementation_proposals",
        generate,
    )

    with pytest.raises(
        engine_module.ImplementationResponseError,
        match="approved plan paths",
    ):
        run_development_task(
            DummyConnection(),
            "task-1",
            object(),
            max_repairs=2,
        )
    assert calls["count"]==1
