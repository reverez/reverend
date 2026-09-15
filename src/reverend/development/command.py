"""User-facing development commands for Reverend."""

from __future__ import annotations

import json
import subprocess
import sys
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .coder import (
    create_local_scheduler,
)
from .database import (
    database,
)
from .engine import (
    DevelopmentRunResult,
    run_development_task,
)
from .models import (
    RunStatus,
    TaskState,
)
from .projects import (
    get_project_by_path,
    register_project,
)
from .tasks import (
    create_task,
    start_run,
    transition_run,
    transition_task,
)
from .worktrees import (
    create_task_worktree,
)


class DevelopmentCommandError(
    RuntimeError
):
    """Base error for Reverend development CLI execution."""


@dataclass(frozen=True)
class DevImplementResult:
    status: str
    task_id: str
    project_id: str
    base_commit: str
    branch: str
    worktree: str
    changed_paths: tuple[str, ...]
    repairs_used: int
    plan_summary: str | None
    verifier_verdict: str | None
    verifier_summary: str | None
    message: str
    worker_stop_reason: str | None = None
    workers_used: int = 0
    worker_steps: int = 0
    worker_tool_calls: int = 0

    @property
    def passed(self) -> bool:
        return self.status == "pass"


def _changed_paths(
    root: Path,
) -> tuple[str, ...]:
    paths: list[str] = []

    commands = (
        (
            "git",
            "-C",
            str(root),
            "diff",
            "--name-only",
            "HEAD",
            "--",
        ),
        (
            "git",
            "-C",
            str(root),
            "ls-files",
            "--others",
            "--exclude-standard",
        ),
    )

    for argv in commands:
        result = subprocess.run(
            argv,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30.0,
            check=False,
        )

        if result.returncode != 0:
            continue

        for line in result.stdout.splitlines():
            path = line.strip()

            if (
                path
                and not path.startswith(".reverend-build/")
                and path not in paths
            ):
                paths.append(
                    path
                )

    return tuple(
        paths
    )


def _finalize_task(
    connection,
    task_id: str,
    status: str,
) -> None:
    if status == "pass":
        task = transition_task(
            connection,
            task_id,
            TaskState.VERIFYING,
        )

        transition_task(
            connection,
            task.id,
            TaskState.COMPLETE,
        )

        return

    if status == "fail":
        transition_task(
            connection,
            task_id,
            TaskState.FAILED,
        )

        return

    if status == "blocked":
        transition_task(
            connection,
            task_id,
            TaskState.BLOCKED,
        )

        return

    if status == "unverified":
        task = transition_task(
            connection,
            task_id,
            TaskState.VERIFYING,
        )

        transition_task(
            connection,
            task.id,
            TaskState.BLOCKED,
        )

        return

    raise DevelopmentCommandError(
        f"Unknown development result status: {status}"
    )


def execute_dev_implement(
    project_path: str | Path,
    request: str,
    *,
    acceptance: str | None = None,
    max_repairs: int = 2,
    database_path: str | Path | None = None,
    scheduler_factory: Callable | None = None,
    engine: Callable | None = None,
    on_task_created: Callable[[str], None] | None = None,
    on_event: Callable | None = None,
) -> DevImplementResult:
    """Execute one autonomous Reverend development task."""

    if not request.strip():
        raise DevelopmentCommandError(
            "Development request cannot be empty."
        )

    if not 0 <= max_repairs <= 10:
        raise DevelopmentCommandError(
            "max_repairs must be between 0 and 10."
        )

    root = Path(
        project_path
    ).expanduser().resolve()

    if not root.exists():
        raise DevelopmentCommandError(
            f"Project path does not exist: {root}"
        )

    scheduler_factory = (
        scheduler_factory
        or create_local_scheduler
    )

    engine = (
        engine
        or run_development_task
    )

    if database_path is None:
        manager = database()
    else:
        manager = database(
            Path(
                database_path
            )
        )

    with manager as connection:
        project = get_project_by_path(
            connection,
            root,
        )

        if project is None:
            project = register_project(
                connection,
                root,
            )

        task = create_task(
            connection,
            project.id,
            title=request.strip()[
                :120
            ],
            request=request.strip(),
            acceptance_criteria=(
                acceptance.strip()
                if acceptance
                and acceptance.strip()
                else None
            ),
            attempt_budget=max(
                3,
                max_repairs + 1,
            ),
        )

        task = transition_task(
            connection,
            task.id,
            TaskState.PREPARING,
        )

        worktree = create_task_worktree(
            connection,
            task.id,
        )

        task = transition_task(
            connection,
            task.id,
            TaskState.RUNNING,
        )

        run = start_run(
            connection,
            task.id,
            model_role="strong_code",
            model_name="qwen3-coder:30b",
        )

        try:
            from reverend.engineering_memory import for_development
            memory=for_development(connection)
            if memory and acceptance and acceptance.strip():
                memory.add('USER_CONSTRAINT',acceptance.strip()[:2000],project.id,'user request',
                    f'development.db/tasks/{task.id}',task_id=task.id,related_commit=task.base_commit)
            if on_task_created is not None:
                on_task_created(task.id)
            scheduler = (
                scheduler_factory()
            )

            result: DevelopmentRunResult = (
                engine(
                    connection,
                    task.id,
                    scheduler,
                    run_id=run.id,
                    max_repairs=max_repairs,
                    python_executable=(
                        sys.executable
                    ),
                    **({"on_event":on_event} if on_event else {}),
                )
            )

        except BaseException:
            try:
                transition_run(
                    connection,
                    run.id,
                    RunStatus.FAILED,
                    summary=(
                        "Autonomous development "
                        "execution raised an error."
                    ),
                )
            except Exception:
                pass

            try:
                transition_task(
                    connection,
                    task.id,
                    TaskState.FAILED,
                )
            except Exception:
                pass

            raise

        transition_run(
            connection,
            run.id,
            RunStatus.COMPLETE,
            summary=result.message,
        )

        _finalize_task(
            connection,
            task.id,
            result.status,
        )

        if memory:
            memory.add('RESULT' if result.status=='pass' else 'FAILURE',
                f'{result.status}: {result.message}'[:2000],project.id,'development engine',
                f'development.db/task_runs/{run.id}',task_id=task.id,related_commit=task.base_commit)

        changed = _changed_paths(
            Path(
                worktree.path
            )
        )

        repairs_used = int(
            getattr(
                result,
                "total_repairs_used",
                (
                    (
                        result.repair.repairs_used
                        if result.repair is not None
                        else 0
                    )
                    + int(
                        getattr(
                            result,
                            "semantic_repairs_used",
                            0,
                        )
                    )
                ),
            )
        )

        plan_summary = (
            result.plan.plan.summary
            if result.plan
            is not None
            else None
        )

        verifier_verdict = (
            result.verifier.verdict
            if result.verifier
            is not None
            else None
        )

        verifier_summary = (
            result.verifier.summary
            if result.verifier
            is not None
            else None
        )

        orchestration = getattr(
            result,
            "orchestration",
            None,
        )

        return DevImplementResult(
            status=result.status,
            task_id=task.id,
            project_id=project.id,
            base_commit=str(
                task.base_commit
            ),
            branch=(
                worktree.branch_name
            ),
            worktree=str(
                worktree.path
            ),
            changed_paths=changed,
            repairs_used=(
                repairs_used
            ),
            plan_summary=(
                plan_summary
            ),
            verifier_verdict=(
                verifier_verdict
            ),
            verifier_summary=(
                verifier_summary
            ),
            message=result.message,
            worker_stop_reason=(
                orchestration.stop_reason.value
                if orchestration is not None
                else None
            ),
            workers_used=(
                orchestration.workers_used
                if orchestration is not None
                else 0
            ),
            worker_steps=(
                orchestration.worker_steps
                if orchestration is not None
                else 0
            ),
            worker_tool_calls=(
                orchestration.tool_calls
                if orchestration is not None
                else 0
            ),
        )


def _result_payload(
    result: DevImplementResult,
) -> dict:
    return {
        "status": result.status,
        "task_id": result.task_id,
        "project_id": (
            result.project_id
        ),
        "base_commit": (
            result.base_commit
        ),
        "branch": result.branch,
        "worktree": result.worktree,
        "changed_paths": list(
            result.changed_paths
        ),
        "repairs_used": (
            result.repairs_used
        ),
        "plan_summary": (
            result.plan_summary
        ),
        "verifier_verdict": (
            result.verifier_verdict
        ),
        "verifier_summary": (
            result.verifier_summary
        ),
        "message": result.message,
        "worker_stop_reason": result.worker_stop_reason,
        "workers_used": result.workers_used,
        "worker_steps": result.worker_steps,
        "worker_tool_calls": result.worker_tool_calls,
        "auto_merged": False,
    }


def command_dev_implement(
    project_path: str | Path,
    request: str,
    *,
    acceptance: str | None = None,
    max_repairs: int = 2,
    json_output: bool = False,
) -> int:
    """CLI wrapper for autonomous development."""

    try:
        result = execute_dev_implement(
            project_path,
            request,
            acceptance=acceptance,
            max_repairs=max_repairs,
        )

    except KeyboardInterrupt:
        print(
            "Reverend development run interrupted.",
            file=sys.stderr,
        )
        return 130

    except Exception as exc:
        print(
            "Reverend development run failed: "
            f"{exc}",
            file=sys.stderr,
        )

        return 1

    payload = _result_payload(
        result
    )

    if json_output:
        print(
            json.dumps(
                payload,
                indent=2,
                ensure_ascii=False,
            )
        )

    else:
        print()
        print(
            "REVEREND DEVELOPMENT RESULT"
        )
        print("=" * 64)
        print(
            "status:",
            result.status.upper(),
        )
        print(
            "message:",
            result.message,
        )
        print(
            "task:",
            result.task_id,
        )
        print(
            "base:",
            result.base_commit,
        )
        print(
            "branch:",
            result.branch,
        )
        print(
            "worktree:",
            result.worktree,
        )
        print(
            "repairs used:",
            result.repairs_used,
        )

        if result.worker_stop_reason is not None:
            print(
                "worker orchestration:",
                result.worker_stop_reason,
                f"({result.workers_used} workers, "
                f"{result.worker_steps} steps, "
                f"{result.worker_tool_calls} worker tool calls)",
            )

        if result.plan_summary:
            print()
            print(
                "plan:",
                result.plan_summary,
            )

        print()
        print("changed files:")

        if result.changed_paths:
            for path in (
                result.changed_paths
            ):
                print(
                    " -",
                    path,
                )
        else:
            print(
                " (none)"
            )

        if (
            result.verifier_verdict
            is not None
        ):
            print()
            print(
                "fresh verifier:",
                result.verifier_verdict,
            )

            if (
                result.verifier_summary
            ):
                print(
                    "verifier summary:",
                    result.verifier_summary,
                )

        print()
        print(
            "No merge was performed."
        )
        print(
            "Inspect the task worktree and branch "
            "before integrating changes."
        )

    if result.status == "pass":
        return 0

    if result.status == "fail":
        return 1

    return 2
