"""Persistent task, run and step state for Reverend development work."""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from .database import transaction
from .models import (
    RunStatus,
    StepStatus,
    TaskState,
)
from .projects import (
    get_project,
    inspect_repository,
)


class TaskServiceError(RuntimeError):
    """Base task-service error."""


class TaskNotFoundError(TaskServiceError):
    """Raised when a task does not exist."""


class TaskRunNotFoundError(TaskServiceError):
    """Raised when a task run does not exist."""


class TaskStepNotFoundError(TaskServiceError):
    """Raised when a task step does not exist."""


class InvalidTaskTransitionError(TaskServiceError):
    """Raised when a task state transition is illegal."""


class InvalidRunTransitionError(TaskServiceError):
    """Raised when a task-run transition is illegal."""


class InvalidStepTransitionError(TaskServiceError):
    """Raised when a step transition is illegal."""


class DirtyRepositoryError(TaskServiceError):
    """Raised when task creation sees uncommitted repository state."""


class ProjectUnavailableError(TaskServiceError):
    """Raised when a registered project cannot be used."""


@dataclass(frozen=True)
class TaskRecord:
    id: str
    project_id: str
    title: str
    request: str
    acceptance_criteria: str | None
    state: TaskState
    base_commit: str | None
    branch_name: str | None
    worktree_path: str | None
    attempt_budget: int
    error_message: str | None
    created_at: str
    updated_at: str
    started_at: str | None
    completed_at: str | None


@dataclass(frozen=True)
class TaskRunRecord:
    id: str
    task_id: str
    run_number: int
    status: RunStatus
    model_role: str | None
    model_name: str | None
    base_commit: str | None
    summary: str | None
    started_at: str
    finished_at: str | None


@dataclass(frozen=True)
class TaskStepRecord:
    id: str
    run_id: str
    sequence: int
    kind: str
    status: StepStatus
    input_summary: str | None
    output_summary: str | None
    started_at: str | None
    finished_at: str | None


TASK_TRANSITIONS: dict[
    TaskState,
    set[TaskState],
] = {
    TaskState.PENDING: {
        TaskState.PREPARING,
        TaskState.CANCELLED,
    },
    TaskState.PREPARING: {
        TaskState.RUNNING,
        TaskState.BLOCKED,
        TaskState.FAILED,
        TaskState.CANCELLED,
    },
    TaskState.RUNNING: {
        TaskState.VERIFYING,
        TaskState.BLOCKED,
        TaskState.FAILED,
        TaskState.CANCELLED,
    },
    TaskState.VERIFYING: {
        TaskState.COMPLETE,
        TaskState.RUNNING,
        TaskState.BLOCKED,
        TaskState.FAILED,
        TaskState.CANCELLED,
    },
    TaskState.BLOCKED: {
        TaskState.PREPARING,
        TaskState.CANCELLED,
    },
    TaskState.FAILED: {
        TaskState.PREPARING,
        TaskState.CANCELLED,
    },
    TaskState.COMPLETE: set(),
    TaskState.CANCELLED: set(),
}


RUN_TRANSITIONS: dict[
    RunStatus,
    set[RunStatus],
] = {
    RunStatus.PENDING: {
        RunStatus.RUNNING,
        RunStatus.CANCELLED,
    },
    RunStatus.RUNNING: {
        RunStatus.COMPLETE,
        RunStatus.FAILED,
        RunStatus.CANCELLED,
    },
    RunStatus.COMPLETE: set(),
    RunStatus.FAILED: set(),
    RunStatus.CANCELLED: set(),
}


STEP_TRANSITIONS: dict[
    StepStatus,
    set[StepStatus],
] = {
    StepStatus.PENDING: {
        StepStatus.RUNNING,
        StepStatus.SKIPPED,
    },
    StepStatus.RUNNING: {
        StepStatus.COMPLETE,
        StepStatus.FAILED,
        StepStatus.SKIPPED,
    },
    StepStatus.COMPLETE: set(),
    StepStatus.FAILED: set(),
    StepStatus.SKIPPED: set(),
}


def _now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def _task_from_row(
    row: sqlite3.Row,
) -> TaskRecord:
    return TaskRecord(
        id=row["id"],
        project_id=row["project_id"],
        title=row["title"],
        request=row["request"],
        acceptance_criteria=row[
            "acceptance_criteria"
        ],
        state=TaskState(row["state"]),
        base_commit=row["base_commit"],
        branch_name=row["branch_name"],
        worktree_path=row["worktree_path"],
        attempt_budget=row[
            "attempt_budget"
        ],
        error_message=row[
            "error_message"
        ],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        started_at=row["started_at"],
        completed_at=row[
            "completed_at"
        ],
    )


def _run_from_row(
    row: sqlite3.Row,
) -> TaskRunRecord:
    return TaskRunRecord(
        id=row["id"],
        task_id=row["task_id"],
        run_number=row["run_number"],
        status=RunStatus(row["status"]),
        model_role=row["model_role"],
        model_name=row["model_name"],
        base_commit=row["base_commit"],
        summary=row["summary"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
    )


def _step_from_row(
    row: sqlite3.Row,
) -> TaskStepRecord:
    return TaskStepRecord(
        id=row["id"],
        run_id=row["run_id"],
        sequence=row["sequence"],
        kind=row["kind"],
        status=StepStatus(row["status"]),
        input_summary=row[
            "input_summary"
        ],
        output_summary=row[
            "output_summary"
        ],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
    )


def get_task(
    connection: sqlite3.Connection,
    task_id: str,
) -> TaskRecord | None:
    row = connection.execute(
        """
        SELECT *
        FROM tasks
        WHERE id = ?
        """,
        (task_id,),
    ).fetchone()

    if row is None:
        return None

    return _task_from_row(row)


def list_tasks(
    connection: sqlite3.Connection,
    *,
    project_id: str | None = None,
    state: TaskState | None = None,
) -> list[TaskRecord]:
    sql = """
        SELECT *
        FROM tasks
        WHERE 1 = 1
    """

    values: list[str] = []

    if project_id is not None:
        sql += " AND project_id = ?"
        values.append(project_id)

    if state is not None:
        sql += " AND state = ?"
        values.append(state.value)

    sql += """
        ORDER BY
            created_at,
            id
    """

    rows = connection.execute(
        sql,
        values,
    ).fetchall()

    return [
        _task_from_row(row)
        for row in rows
    ]


def create_task(
    connection: sqlite3.Connection,
    project_id: str,
    *,
    title: str,
    request: str,
    acceptance_criteria: str | None = None,
    attempt_budget: int = 3,
    allow_dirty: bool = False,
) -> TaskRecord:
    project = get_project(
        connection,
        project_id,
    )

    if project is None:
        raise ProjectUnavailableError(
            f"Unknown project: {project_id}"
        )

    clean_title = title.strip()
    clean_request = request.strip()

    if not clean_title:
        raise TaskServiceError(
            "Task title cannot be empty."
        )

    if not clean_request:
        raise TaskServiceError(
            "Task request cannot be empty."
        )

    if attempt_budget < 1:
        raise TaskServiceError(
            "attempt_budget must be at least 1."
        )

    snapshot = inspect_repository(
        project.repo_real_path
    )

    if (
        snapshot.is_dirty
        and not allow_dirty
    ):
        raise DirtyRepositoryError(
            "Repository contains uncommitted "
            "changes. Commit/stash them or "
            "explicitly allow dirty task creation."
        )

    task_id = str(uuid.uuid4())

    with transaction(connection):
        connection.execute(
            """
            INSERT INTO tasks (
                id,
                project_id,
                title,
                request,
                acceptance_criteria,
                state,
                base_commit,
                attempt_budget
            )
            VALUES (
                ?, ?, ?, ?, ?,
                'pending',
                ?,
                ?
            )
            """,
            (
                task_id,
                project_id,
                clean_title,
                clean_request,
                acceptance_criteria,
                snapshot.head_commit,
                attempt_budget,
            ),
        )

    task = get_task(
        connection,
        task_id,
    )

    if task is None:
        raise TaskServiceError(
            "Task could not be read back."
        )

    return task


def transition_task(
    connection: sqlite3.Connection,
    task_id: str,
    target: TaskState,
    *,
    error_message: str | None = None,
) -> TaskRecord:
    task = get_task(
        connection,
        task_id,
    )

    if task is None:
        raise TaskNotFoundError(
            f"Unknown task: {task_id}"
        )

    if target == task.state:
        return task

    allowed = TASK_TRANSITIONS[
        task.state
    ]

    if target not in allowed:
        raise InvalidTaskTransitionError(
            f"Illegal task transition: "
            f"{task.state.value} -> "
            f"{target.value}"
        )

    now = _now()

    started_at = task.started_at
    completed_at = task.completed_at

    if (
        target == TaskState.RUNNING
        and started_at is None
    ):
        started_at = now

    if target in {
        TaskState.COMPLETE,
        TaskState.FAILED,
        TaskState.CANCELLED,
    }:
        completed_at = now
    elif target == TaskState.PREPARING:
        completed_at = None

    if target == TaskState.COMPLETE:
        error_message = None

    with transaction(connection):
        connection.execute(
            """
            UPDATE tasks
            SET
                state = ?,
                error_message = ?,
                started_at = ?,
                completed_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                target.value,
                error_message,
                started_at,
                completed_at,
                now,
                task_id,
            ),
        )

    updated = get_task(
        connection,
        task_id,
    )

    if updated is None:
        raise TaskServiceError(
            "Task disappeared after transition."
        )

    return updated


def start_run(
    connection: sqlite3.Connection,
    task_id: str,
    *,
    model_role: str | None = None,
    model_name: str | None = None,
) -> TaskRunRecord:
    task = get_task(
        connection,
        task_id,
    )

    if task is None:
        raise TaskNotFoundError(
            f"Unknown task: {task_id}"
        )

    if task.state != TaskState.RUNNING:
        raise InvalidRunTransitionError(
            "Task must be in RUNNING state "
            "before a run can start."
        )

    run_id = str(uuid.uuid4())
    now = _now()

    with transaction(connection):
        next_number = connection.execute(
            """
            SELECT
                COALESCE(
                    MAX(run_number),
                    0
                ) + 1
            FROM task_runs
            WHERE task_id = ?
            """,
            (task_id,),
        ).fetchone()[0]

        connection.execute(
            """
            INSERT INTO task_runs (
                id,
                task_id,
                run_number,
                status,
                model_role,
                model_name,
                base_commit,
                started_at
            )
            VALUES (
                ?, ?, ?,
                'running',
                ?, ?, ?, ?
            )
            """,
            (
                run_id,
                task_id,
                next_number,
                model_role,
                model_name,
                task.base_commit,
                now,
            ),
        )

    run = get_run(
        connection,
        run_id,
    )

    if run is None:
        raise TaskServiceError(
            "Run could not be read back."
        )

    return run


def get_run(
    connection: sqlite3.Connection,
    run_id: str,
) -> TaskRunRecord | None:
    row = connection.execute(
        """
        SELECT *
        FROM task_runs
        WHERE id = ?
        """,
        (run_id,),
    ).fetchone()

    if row is None:
        return None

    return _run_from_row(row)


def transition_run(
    connection: sqlite3.Connection,
    run_id: str,
    target: RunStatus,
    *,
    summary: str | None = None,
) -> TaskRunRecord:
    run = get_run(
        connection,
        run_id,
    )

    if run is None:
        raise TaskRunNotFoundError(
            f"Unknown run: {run_id}"
        )

    if target == run.status:
        return run

    if target not in RUN_TRANSITIONS[
        run.status
    ]:
        raise InvalidRunTransitionError(
            f"Illegal run transition: "
            f"{run.status.value} -> "
            f"{target.value}"
        )

    finished_at = run.finished_at

    if target in {
        RunStatus.COMPLETE,
        RunStatus.FAILED,
        RunStatus.CANCELLED,
    }:
        finished_at = _now()

    with transaction(connection):
        connection.execute(
            """
            UPDATE task_runs
            SET
                status = ?,
                summary = ?,
                finished_at = ?
            WHERE id = ?
            """,
            (
                target.value,
                summary,
                finished_at,
                run_id,
            ),
        )

    updated = get_run(
        connection,
        run_id,
    )

    if updated is None:
        raise TaskServiceError(
            "Run disappeared after transition."
        )

    return updated


def create_step(
    connection: sqlite3.Connection,
    run_id: str,
    *,
    kind: str,
    input_summary: str | None = None,
) -> TaskStepRecord:
    run = get_run(
        connection,
        run_id,
    )

    if run is None:
        raise TaskRunNotFoundError(
            f"Unknown run: {run_id}"
        )

    clean_kind = kind.strip()

    if not clean_kind:
        raise TaskServiceError(
            "Step kind cannot be empty."
        )

    step_id = str(uuid.uuid4())

    with transaction(connection):
        sequence = connection.execute(
            """
            SELECT
                COALESCE(
                    MAX(sequence),
                    0
                ) + 1
            FROM task_steps
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()[0]

        connection.execute(
            """
            INSERT INTO task_steps (
                id,
                run_id,
                sequence,
                kind,
                status,
                input_summary
            )
            VALUES (
                ?, ?, ?, ?,
                'pending',
                ?
            )
            """,
            (
                step_id,
                run_id,
                sequence,
                clean_kind,
                input_summary,
            ),
        )

    step = get_step(
        connection,
        step_id,
    )

    if step is None:
        raise TaskServiceError(
            "Step could not be read back."
        )

    return step


def get_step(
    connection: sqlite3.Connection,
    step_id: str,
) -> TaskStepRecord | None:
    row = connection.execute(
        """
        SELECT *
        FROM task_steps
        WHERE id = ?
        """,
        (step_id,),
    ).fetchone()

    if row is None:
        return None

    return _step_from_row(row)


def transition_step(
    connection: sqlite3.Connection,
    step_id: str,
    target: StepStatus,
    *,
    output_summary: str | None = None,
) -> TaskStepRecord:
    step = get_step(
        connection,
        step_id,
    )

    if step is None:
        raise TaskStepNotFoundError(
            f"Unknown step: {step_id}"
        )

    if target == step.status:
        return step

    if target not in STEP_TRANSITIONS[
        step.status
    ]:
        raise InvalidStepTransitionError(
            f"Illegal step transition: "
            f"{step.status.value} -> "
            f"{target.value}"
        )

    now = _now()

    started_at = step.started_at
    finished_at = step.finished_at

    if (
        target == StepStatus.RUNNING
        and started_at is None
    ):
        started_at = now

    if target in {
        StepStatus.COMPLETE,
        StepStatus.FAILED,
        StepStatus.SKIPPED,
    }:
        finished_at = now

    with transaction(connection):
        connection.execute(
            """
            UPDATE task_steps
            SET
                status = ?,
                output_summary = ?,
                started_at = ?,
                finished_at = ?
            WHERE id = ?
            """,
            (
                target.value,
                output_summary,
                started_at,
                finished_at,
                step_id,
            ),
        )

    updated = get_step(
        connection,
        step_id,
    )

    if updated is None:
        raise TaskServiceError(
            "Step disappeared after transition."
        )

    return updated
