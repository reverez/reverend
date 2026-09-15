import pytest

from reverend.runtime import ModelRole
from reverend.workers import (
    OrchestrationResult,
    WorkerBudget,
    WorkerExecution,
    WorkerOrchestrator,
    WorkerRole,
    WorkerStatus,
    WorkerStopReason,
    WorkerTask,
    worker_policy,
)


def test_worker_policy_matches_frozen_permissions():
    coder = worker_policy(WorkerRole.CODER)
    assert coder.model_role is ModelRole.STRONG_CODE
    assert coder.repository_read is True
    assert coder.propose_edits is True
    assert coder.execute_tools is False
    assert coder.verify is False

    verifier = worker_policy(WorkerRole.CRITIC_VERIFIER)
    assert verifier.model_role is ModelRole.CRITIC
    assert verifier.repository_read is True
    assert verifier.propose_edits is False
    assert verifier.execute_tools is False
    assert verifier.verify is True


def test_typed_worker_plan_runs_without_recursive_delegation():
    seen = []

    def execute(task, policy):
        seen.append((task.task_id, task.role, policy.role))
        return WorkerExecution(
            status=WorkerStatus.COMPLETE,
            output_state={'result': task.objective},
            steps_used=1,
            tool_calls=0,
        )

    result = WorkerOrchestrator(
        WorkerBudget(max_workers=3, max_worker_steps=3, max_tool_calls=1)
    ).run(
        (
            WorkerTask(
                'localize',
                WorkerRole.CODE_LOCALIZER,
                'Find relevant files',
                {'request': 'fix parser'},
            ),
            WorkerTask(
                'reason',
                WorkerRole.REASONER,
                'Assess edge cases',
                {'files': ['parser.py']},
            ),
        ),
        execute,
    )

    assert isinstance(result, OrchestrationResult)
    assert result.completed is True
    assert result.stop_reason is WorkerStopReason.COMPLETE
    assert result.workers_used == 2
    assert result.worker_steps == 2
    assert [item[0] for item in seen] == ['localize', 'reason']
    assert [record.task_id for record in result.records] == ['localize', 'reason']


def test_worker_budget_stops_before_unapproved_extra_worker():
    calls = []

    def execute(task, policy):
        calls.append(task.task_id)
        return WorkerExecution(
            status=WorkerStatus.COMPLETE,
            output_state={},
        )

    result = WorkerOrchestrator(
        WorkerBudget(max_workers=1, max_worker_steps=4, max_tool_calls=4)
    ).run(
        (
            WorkerTask('one', WorkerRole.REASONER, 'first'),
            WorkerTask('two', WorkerRole.REASONER, 'second'),
        ),
        execute,
    )

    assert calls == ['one']
    assert result.stop_reason is WorkerStopReason.WORKER_BUDGET_EXHAUSTED
    assert result.workers_used == 1


def test_step_and_tool_budgets_fail_closed_without_recording_unaccepted_usage():
    def too_many_steps(task, policy):
        return WorkerExecution(
            status=WorkerStatus.COMPLETE,
            output_state={},
            steps_used=3,
            tool_calls=0,
        )

    step_result = WorkerOrchestrator(
        WorkerBudget(max_workers=2, max_worker_steps=2, max_tool_calls=2)
    ).run(
        (WorkerTask('one', WorkerRole.REASONER, 'reason'),),
        too_many_steps,
    )

    assert step_result.stop_reason is WorkerStopReason.STEP_BUDGET_EXHAUSTED
    assert step_result.workers_used == 0
    assert step_result.records == ()

    def too_many_tools(task, policy):
        return WorkerExecution(
            status=WorkerStatus.COMPLETE,
            output_state={},
            steps_used=1,
            tool_calls=2,
        )

    tool_result = WorkerOrchestrator(
        WorkerBudget(max_workers=2, max_worker_steps=2, max_tool_calls=1)
    ).run(
        (WorkerTask('one', WorkerRole.REASONER, 'reason'),),
        too_many_tools,
    )

    assert tool_result.stop_reason is WorkerStopReason.TOOL_BUDGET_EXHAUSTED
    assert tool_result.workers_used == 0
    assert tool_result.records == ()


def test_blocked_and_failed_workers_publish_deterministic_stop_reasons():
    def blocked(task, policy):
        return WorkerExecution(
            status=WorkerStatus.BLOCKED,
            output_state={'reason': 'missing context'},
        )

    blocked_result = WorkerOrchestrator(
        WorkerBudget()
    ).run(
        (WorkerTask('one', WorkerRole.SOURCE_ANALYST, 'analyse'),),
        blocked,
    )

    assert blocked_result.stop_reason is WorkerStopReason.WORKER_BLOCKED
    assert blocked_result.records[0].stop_reason is WorkerStopReason.WORKER_BLOCKED

    def failed(task, policy):
        return WorkerExecution(
            status=WorkerStatus.FAILED,
            output_state={'error': 'bad output'},
        )

    failed_result = WorkerOrchestrator(
        WorkerBudget()
    ).run(
        (WorkerTask('one', WorkerRole.SOURCE_ANALYST, 'analyse'),),
        failed,
    )

    assert failed_result.stop_reason is WorkerStopReason.WORKER_FAILED
    assert failed_result.records[0].stop_reason is WorkerStopReason.WORKER_FAILED


def test_verifier_is_separate_typed_worker_and_cannot_recursively_verify():
    calls = []

    def execute(task, policy):
        calls.append(('worker', task.role))
        return WorkerExecution(
            status=WorkerStatus.COMPLETE,
            output_state={'patch': 'proposal-only'},
        )

    def verify(task, policy):
        calls.append(('verifier', task.role))
        assert task.role is WorkerRole.CRITIC_VERIFIER
        assert policy.verify is True
        assert policy.propose_edits is False
        assert task.input_state['subject_role'] == 'coder'
        return WorkerExecution(
            status=WorkerStatus.COMPLETE,
            output_state={'verdict': 'pass', 'summary': 'checks passed'},
        )

    result = WorkerOrchestrator(
        WorkerBudget(max_workers=2, max_worker_steps=2, max_tool_calls=0)
    ).run(
        (
            WorkerTask(
                'coder',
                WorkerRole.CODER,
                'Propose a bounded edit',
                requires_verification=True,
            ),
        ),
        execute,
        verifier=verify,
    )

    assert result.completed is True
    assert result.workers_used == 2
    assert result.records[0].verified_by == 'coder:verify'
    assert result.records[1].role is WorkerRole.CRITIC_VERIFIER
    assert calls == [
        ('worker', WorkerRole.CODER),
        ('verifier', WorkerRole.CRITIC_VERIFIER),
    ]

    with pytest.raises(ValueError, match='cannot recursively'):
        WorkerTask(
            'bad',
            WorkerRole.CRITIC_VERIFIER,
            'verify verifier',
            requires_verification=True,
        )


def test_verifier_rejection_stops_orchestration():
    def execute(task, policy):
        return WorkerExecution(
            status=WorkerStatus.COMPLETE,
            output_state={'result': 'candidate'},
        )

    def reject(task, policy):
        return WorkerExecution(
            status=WorkerStatus.COMPLETE,
            output_state={'verdict': 'fail'},
        )

    result = WorkerOrchestrator(
        WorkerBudget(max_workers=3, max_worker_steps=3, max_tool_calls=0)
    ).run(
        (
            WorkerTask(
                'reason',
                WorkerRole.REASONER,
                'Solve',
                requires_verification=True,
            ),
            WorkerTask('later', WorkerRole.REASONER, 'must not run'),
        ),
        execute,
        verifier=reject,
    )

    assert result.stop_reason is WorkerStopReason.VERIFIER_REJECTED
    assert result.workers_used == 2
    assert [record.task_id for record in result.records] == [
        'reason',
        'reason:verify',
    ]


def test_worker_state_must_be_bounded_json_compatible():
    with pytest.raises(ValueError, match='JSON-compatible'):
        WorkerTask(
            'bad',
            WorkerRole.REASONER,
            'reason',
            {'bad': object()},
        )

    with pytest.raises(ValueError, match='typed-state budget'):
        WorkerTask(
            'huge',
            WorkerRole.REASONER,
            'reason',
            {'payload': 'x' * 70_000},
        )


def test_duplicate_task_ids_are_rejected():
    task = WorkerTask('same', WorkerRole.REASONER, 'reason')
    with pytest.raises(ValueError, match='unique'):
        WorkerOrchestrator(WorkerBudget()).run(
            (task, task),
            lambda *_: WorkerExecution(
                status=WorkerStatus.COMPLETE,
                output_state={},
            ),
        )



def test_worker_dependencies_are_injected_as_typed_state():
    seen = {}

    def execute(task, policy):
        seen[task.task_id] = dict(task.input_state)
        if task.task_id == 'localize':
            return WorkerExecution(
                status=WorkerStatus.COMPLETE,
                output_state={
                    'plan': {
                        'summary': 'Edit parser',
                        'files': ['parser.py'],
                    }
                },
            )
        return WorkerExecution(
            status=WorkerStatus.COMPLETE,
            output_state={'ok': True},
        )

    result = WorkerOrchestrator(
        WorkerBudget(max_workers=2, max_worker_steps=2, max_tool_calls=0)
    ).run(
        (
            WorkerTask(
                'localize',
                WorkerRole.CODE_LOCALIZER,
                'Find files',
            ),
            WorkerTask(
                'coder',
                WorkerRole.CODER,
                'Implement change',
                depends_on=('localize',),
            ),
        ),
        execute,
    )

    assert result.completed is True
    assert seen['coder']['dependencies']['localize']['plan']['files'] == [
        'parser.py'
    ]


def test_missing_worker_dependency_fails_closed_before_execution():
    calls = []

    result = WorkerOrchestrator(
        WorkerBudget(max_workers=2, max_worker_steps=2, max_tool_calls=0)
    ).run(
        (
            WorkerTask(
                'coder',
                WorkerRole.CODER,
                'Implement change',
                depends_on=('localize',),
            ),
        ),
        lambda task, policy: calls.append(task.task_id),
    )

    assert calls == []
    assert result.stop_reason is WorkerStopReason.DEPENDENCY_UNAVAILABLE
    assert result.workers_used == 0
    assert result.records == ()
