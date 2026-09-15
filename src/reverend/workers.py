"""Typed bounded specialist-worker orchestration for Reverend M11.

Workers exchange validated state only. They do not recursively delegate and the
orchestrator owns all step/tool budgets and verifier scheduling.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Callable, Mapping

from reverend.runtime import ModelRole


MAX_WORKERS = 8
MAX_STATE_BYTES = 64_000


class WorkerRole(str, Enum):
    RESEARCH_SCOUT = "research_scout"
    SOURCE_ANALYST = "source_analyst"
    CODE_LOCALIZER = "code_localizer"
    CODER = "coder"
    REASONER = "reasoner"
    MEMORY_CURATOR = "memory_curator"
    CRITIC_VERIFIER = "critic_verifier"


class WorkerStatus(str, Enum):
    COMPLETE = "complete"
    BLOCKED = "blocked"
    FAILED = "failed"


class WorkerStopReason(str, Enum):
    COMPLETE = "complete"
    NO_WORK = "no_work"
    WORKER_BUDGET_EXHAUSTED = "worker_budget_exhausted"
    STEP_BUDGET_EXHAUSTED = "step_budget_exhausted"
    TOOL_BUDGET_EXHAUSTED = "tool_budget_exhausted"
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"
    WORKER_BLOCKED = "worker_blocked"
    WORKER_FAILED = "worker_failed"
    VERIFIER_REJECTED = "verifier_rejected"


@dataclass(frozen=True)
class WorkerPolicy:
    role: WorkerRole
    model_role: ModelRole
    repository_read: bool = False
    propose_edits: bool = False
    execute_tools: bool = False
    propose_memory: bool = False
    verify: bool = False


_POLICIES = MappingProxyType({
    WorkerRole.RESEARCH_SCOUT: WorkerPolicy(
        WorkerRole.RESEARCH_SCOUT,
        ModelRole.FAST_GENERAL,
    ),
    WorkerRole.SOURCE_ANALYST: WorkerPolicy(
        WorkerRole.SOURCE_ANALYST,
        ModelRole.DEEP_REASON,
    ),
    WorkerRole.CODE_LOCALIZER: WorkerPolicy(
        WorkerRole.CODE_LOCALIZER,
        ModelRole.FAST_CODE,
        repository_read=True,
    ),
    WorkerRole.CODER: WorkerPolicy(
        WorkerRole.CODER,
        ModelRole.STRONG_CODE,
        repository_read=True,
        propose_edits=True,
    ),
    WorkerRole.REASONER: WorkerPolicy(
        WorkerRole.REASONER,
        ModelRole.DEEP_REASON,
    ),
    WorkerRole.MEMORY_CURATOR: WorkerPolicy(
        WorkerRole.MEMORY_CURATOR,
        ModelRole.FAST_GENERAL,
        propose_memory=True,
    ),
    WorkerRole.CRITIC_VERIFIER: WorkerPolicy(
        WorkerRole.CRITIC_VERIFIER,
        ModelRole.CRITIC,
        repository_read=True,
        verify=True,
    ),
})


def worker_policy(role: WorkerRole) -> WorkerPolicy:
    try:
        return _POLICIES[role]
    except KeyError as exc:
        raise ValueError(f"Unknown worker role: {role!r}") from exc


def _validated_state(value: Mapping[str, Any], *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping")
    clean = dict(value)
    try:
        encoded = json.dumps(clean, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must contain JSON-compatible state") from exc
    if len(encoded.encode("utf-8")) > MAX_STATE_BYTES:
        raise ValueError(f"{field_name} exceeds the typed-state budget")
    return clean


@dataclass(frozen=True)
class WorkerTask:
    task_id: str
    role: WorkerRole
    objective: str
    input_state: Mapping[str, Any] = field(default_factory=dict)
    depends_on: tuple[str, ...] = ()
    requires_verification: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.role, WorkerRole):
            raise ValueError("Worker task role is invalid")
        if not isinstance(self.task_id, str) or not self.task_id.strip():
            raise ValueError("Worker task id must not be empty")
        if len(self.task_id) > 120:
            raise ValueError("Worker task id is too long")
        if not isinstance(self.objective, str) or not self.objective.strip():
            raise ValueError("Worker objective must not be empty")
        if len(self.objective) > 4000:
            raise ValueError("Worker objective is too long")
        if self.role is WorkerRole.CRITIC_VERIFIER and self.requires_verification:
            raise ValueError("Verifier workers cannot recursively request verification")
        if (
            not isinstance(self.depends_on, tuple)
            or any(
                not isinstance(value, str)
                or not value
                or len(value) > 120
                for value in self.depends_on
            )
        ):
            raise ValueError("Worker dependencies must be task-id strings")
        if self.task_id in self.depends_on:
            raise ValueError("Worker cannot depend on itself")
        if len(set(self.depends_on)) != len(self.depends_on):
            raise ValueError("Worker dependencies must be unique")
        object.__setattr__(
            self,
            "input_state",
            MappingProxyType(
                _validated_state(self.input_state, field_name="input_state")
            ),
        )


@dataclass(frozen=True)
class WorkerExecution:
    status: WorkerStatus
    output_state: Mapping[str, Any] = field(default_factory=dict)
    steps_used: int = 1
    tool_calls: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.status, WorkerStatus):
            raise ValueError("Worker execution status is invalid")
        if (
            not isinstance(self.steps_used, int)
            or isinstance(self.steps_used, bool)
            or self.steps_used < 1
        ):
            raise ValueError("Worker execution must consume at least one step")
        if (
            not isinstance(self.tool_calls, int)
            or isinstance(self.tool_calls, bool)
            or self.tool_calls < 0
        ):
            raise ValueError("Worker tool-call count is invalid")
        object.__setattr__(
            self,
            "output_state",
            MappingProxyType(
                _validated_state(self.output_state, field_name="output_state")
            ),
        )


@dataclass(frozen=True)
class WorkerBudget:
    max_workers: int = 4
    max_worker_steps: int = 8
    max_tool_calls: int = 8

    def __post_init__(self) -> None:
        values = (
            self.max_workers,
            self.max_worker_steps,
            self.max_tool_calls,
        )
        if any(
            not isinstance(value, int) or isinstance(value, bool)
            for value in values
        ):
            raise ValueError("Worker budgets must be integers")
        if not 0 <= self.max_workers <= MAX_WORKERS:
            raise ValueError(f"max_workers must be 0–{MAX_WORKERS}")
        if not 0 <= self.max_worker_steps <= 32:
            raise ValueError("max_worker_steps must be 0–32")
        if not 0 <= self.max_tool_calls <= 32:
            raise ValueError("max_tool_calls must be 0–32")


@dataclass(frozen=True)
class WorkerRecord:
    task_id: str
    role: WorkerRole
    status: WorkerStatus
    stop_reason: WorkerStopReason
    steps_used: int
    tool_calls: int
    output_state: Mapping[str, Any]
    verified_by: str | None = None


@dataclass(frozen=True)
class OrchestrationResult:
    records: tuple[WorkerRecord, ...]
    stop_reason: WorkerStopReason
    workers_used: int
    worker_steps: int
    tool_calls: int

    @property
    def completed(self) -> bool:
        return self.stop_reason in {
            WorkerStopReason.COMPLETE,
            WorkerStopReason.NO_WORK,
        }


WorkerExecutor = Callable[[WorkerTask, WorkerPolicy], WorkerExecution]
VerifierExecutor = Callable[[WorkerTask, WorkerPolicy], WorkerExecution]


class WorkerOrchestrator:
    """Run a fixed worker plan sequentially under one central budget.

    The executor receives one task at a time and cannot enqueue more workers.
    Verification is scheduled only by this orchestrator through the separate
    verifier callback.
    """

    def __init__(self, budget: WorkerBudget):
        self.budget = budget

    @staticmethod
    def _record(
        task: WorkerTask,
        execution: WorkerExecution,
        reason: WorkerStopReason,
        *,
        verified_by: str | None = None,
    ) -> WorkerRecord:
        return WorkerRecord(
            task_id=task.task_id,
            role=task.role,
            status=execution.status,
            stop_reason=reason,
            steps_used=execution.steps_used,
            tool_calls=execution.tool_calls,
            output_state=execution.output_state,
            verified_by=verified_by,
        )

    def run(
        self,
        tasks: tuple[WorkerTask, ...],
        executor: WorkerExecutor,
        *,
        verifier: VerifierExecutor | None = None,
    ) -> OrchestrationResult:
        if not isinstance(tasks, tuple):
            raise ValueError("Worker plan must be a tuple")
        if len({task.task_id for task in tasks}) != len(tasks):
            raise ValueError("Worker task ids must be unique")
        if len(tasks) > MAX_WORKERS:
            raise ValueError("Worker plan exceeds architectural worker maximum")

        if not tasks:
            return OrchestrationResult(
                records=(),
                stop_reason=WorkerStopReason.NO_WORK,
                workers_used=0,
                worker_steps=0,
                tool_calls=0,
            )

        records: list[WorkerRecord] = []
        completed_outputs: dict[str, Mapping[str, Any]] = {}
        workers_used = 0
        worker_steps = 0
        tool_calls = 0

        def finish(reason: WorkerStopReason) -> OrchestrationResult:
            return OrchestrationResult(
                records=tuple(records),
                stop_reason=reason,
                workers_used=workers_used,
                worker_steps=worker_steps,
                tool_calls=tool_calls,
            )

        for task in tasks:
            if workers_used >= self.budget.max_workers:
                return finish(WorkerStopReason.WORKER_BUDGET_EXHAUSTED)

            missing = [
                dependency
                for dependency in task.depends_on
                if dependency not in completed_outputs
            ]
            if missing:
                return finish(WorkerStopReason.DEPENDENCY_UNAVAILABLE)

            effective_task = task
            if task.depends_on:
                dependency_state = {
                    dependency: dict(completed_outputs[dependency])
                    for dependency in task.depends_on
                }
                effective_task = WorkerTask(
                    task_id=task.task_id,
                    role=task.role,
                    objective=task.objective,
                    input_state={
                        **dict(task.input_state),
                        "dependencies": dependency_state,
                    },
                    depends_on=task.depends_on,
                    requires_verification=task.requires_verification,
                )

            execution = executor(
                effective_task,
                worker_policy(effective_task.role),
            )

            if worker_steps + execution.steps_used > self.budget.max_worker_steps:
                return finish(WorkerStopReason.STEP_BUDGET_EXHAUSTED)
            if tool_calls + execution.tool_calls > self.budget.max_tool_calls:
                return finish(WorkerStopReason.TOOL_BUDGET_EXHAUSTED)

            workers_used += 1
            worker_steps += execution.steps_used
            tool_calls += execution.tool_calls

            if execution.status is WorkerStatus.BLOCKED:
                records.append(
                    self._record(
                        effective_task,
                        execution,
                        WorkerStopReason.WORKER_BLOCKED,
                    )
                )
                return finish(WorkerStopReason.WORKER_BLOCKED)

            if execution.status is WorkerStatus.FAILED:
                records.append(
                    self._record(
                        effective_task,
                        execution,
                        WorkerStopReason.WORKER_FAILED,
                    )
                )
                return finish(WorkerStopReason.WORKER_FAILED)

            completed_outputs[effective_task.task_id] = execution.output_state

            verified_by = None
            if effective_task.requires_verification:
                if verifier is None:
                    records.append(
                        self._record(
                            effective_task,
                            execution,
                            WorkerStopReason.VERIFIER_REJECTED,
                        )
                    )
                    return finish(WorkerStopReason.VERIFIER_REJECTED)

                if workers_used >= self.budget.max_workers:
                    return finish(WorkerStopReason.WORKER_BUDGET_EXHAUSTED)

                verifier_task = WorkerTask(
                    task_id=f"{effective_task.task_id}:verify",
                    role=WorkerRole.CRITIC_VERIFIER,
                    objective=f"Independently verify worker result: {effective_task.objective}",
                    input_state={
                        "subject_task_id": effective_task.task_id,
                        "subject_role": effective_task.role.value,
                        "subject_output": dict(execution.output_state),
                    },
                )
                verdict = verifier(
                    verifier_task,
                    worker_policy(WorkerRole.CRITIC_VERIFIER),
                )

                if worker_steps + verdict.steps_used > self.budget.max_worker_steps:
                    return finish(WorkerStopReason.STEP_BUDGET_EXHAUSTED)
                if tool_calls + verdict.tool_calls > self.budget.max_tool_calls:
                    return finish(WorkerStopReason.TOOL_BUDGET_EXHAUSTED)

                workers_used += 1
                worker_steps += verdict.steps_used
                tool_calls += verdict.tool_calls
                verified_by = verifier_task.task_id

                verifier_passed = (
                    verdict.status is WorkerStatus.COMPLETE
                    and verdict.output_state.get("verdict") == "pass"
                )

                if not verifier_passed:
                    records.append(
                        self._record(
                            task,
                            execution,
                            WorkerStopReason.VERIFIER_REJECTED,
                            verified_by=verified_by,
                        )
                    )
                    records.append(
                        self._record(
                            verifier_task,
                            verdict,
                            WorkerStopReason.VERIFIER_REJECTED,
                        )
                    )
                    return finish(WorkerStopReason.VERIFIER_REJECTED)

                records.append(
                    self._record(
                        effective_task,
                        execution,
                        WorkerStopReason.COMPLETE,
                        verified_by=verified_by,
                    )
                )
                records.append(
                    self._record(
                        verifier_task,
                        verdict,
                        WorkerStopReason.COMPLETE,
                    )
                )
                continue

            records.append(
                self._record(
                    effective_task,
                    execution,
                    WorkerStopReason.COMPLETE,
                )
            )

        return finish(WorkerStopReason.COMPLETE)
