"""Deterministic ReverendBench coverage for M11 worker orchestration."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from reverend.benchmarks.models import (
    BenchmarkBudget,
    BenchmarkCase,
    BenchmarkCategory,
    BenchmarkObservation,
)
from reverend.workers import (
    WorkerBudget,
    WorkerExecution,
    WorkerOrchestrator,
    WorkerRole,
    WorkerStatus,
    WorkerTask,
)


def worker_cases() -> tuple[BenchmarkCase, ...]:
    return (
        BenchmarkCase(
            case_id="m11-worker-bounded-success",
            name="Bounded worker plan completes",
            category=BenchmarkCategory.DEVELOPMENT,
            prompt="Run a bounded localizer and reasoner plan.",
            parameters={
                "workers": [
                    {"task_id": "localize", "role": "code_localizer"},
                    {"task_id": "reason", "role": "reasoner"},
                ],
                "max_workers": 2,
                "max_worker_steps": 2,
                "max_tool_calls": 0,
            },
            expected={
                "metadata_equals": {
                    "stop_reason": "complete",
                    "workers_used": 2,
                    "worker_steps": 2,
                    "tool_calls": 0,
                },
            },
            tags=("m11", "workers", "budget"),
            budget=BenchmarkBudget(timeout_seconds=5.0, max_model_calls=0),
        ),
        BenchmarkCase(
            case_id="m11-worker-budget-stop",
            name="Worker count budget stops delegation",
            category=BenchmarkCategory.SECURITY,
            prompt="Reject a worker plan beyond its worker budget.",
            parameters={
                "workers": [
                    {"task_id": "one", "role": "reasoner"},
                    {"task_id": "two", "role": "reasoner"},
                ],
                "max_workers": 1,
                "max_worker_steps": 4,
                "max_tool_calls": 0,
            },
            expected={
                "metadata_equals": {
                    "stop_reason": "worker_budget_exhausted",
                    "workers_used": 1,
                },
            },
            tags=("m11", "workers", "budget", "fail-closed"),
            budget=BenchmarkBudget(timeout_seconds=5.0, max_model_calls=0),
        ),
        BenchmarkCase(
            case_id="m11-development-engine-workers",
            name="Development engine uses typed worker orchestration",
            category=BenchmarkCategory.DEVELOPMENT,
            prompt="Change value() so it returns 2.",
            parameters={
                "integration": "development_engine",
            },
            expected={
                "metadata_equals": {
                    "status": "pass",
                    "stop_reason": "complete",
                    "workers_used": 3,
                    "worker_steps": 3,
                    "tool_calls": 0,
                    "model_calls": 3,
                    "primary_checkout_unchanged": True,
                    "worktree_changed": True,
                    "coder_verified_by": "coder:verify",
                },
            },
            tags=("m11", "workers", "development", "isolation", "verifier"),
            budget=BenchmarkBudget(
                timeout_seconds=20.0,
                max_model_calls=3,
                max_retrieval_rounds=0,
            ),
        ),
        BenchmarkCase(
            case_id="m11-verifier-rejection",
            name="Independent verifier rejection stops plan",
            category=BenchmarkCategory.DEVELOPMENT,
            prompt="Reject a candidate result through the verifier seam.",
            parameters={
                "workers": [
                    {
                        "task_id": "coder",
                        "role": "coder",
                        "requires_verification": True,
                    },
                    {"task_id": "later", "role": "reasoner"},
                ],
                "max_workers": 3,
                "max_worker_steps": 3,
                "max_tool_calls": 0,
                "verifier_verdict": "fail",
            },
            expected={
                "metadata_equals": {
                    "stop_reason": "verifier_rejected",
                    "workers_used": 2,
                },
            },
            tags=("m11", "workers", "verifier", "fail-closed"),
            budget=BenchmarkBudget(timeout_seconds=5.0, max_model_calls=0),
        ),
    )


class _DeterministicDevelopmentScheduler:
    """Fixture-controlled local-model seam for the real development engine."""

    def __init__(self):
        self.calls = []

    def generate(self, role, prompt, **kwargs):
        self.calls.append((role, prompt, kwargs))

        if "local coding planner" in prompt:
            response = {
                "summary": "Change value() to return 2.",
                "files": [
                    {
                        "path": "value.py",
                        "action": "modify",
                        "reason": "The requested behavior is implemented here.",
                    }
                ],
                "implementation_steps": [
                    "Replace the return value with 2."
                ],
                "verification": [
                    "Run the deterministic value check."
                ],
                "risks": [],
                "needs_more_context": False,
            }
        elif "local implementation model" in prompt:
            match = re.search(
                r"FILE: value\.py\nEXISTS: true\nSHA256: ([0-9a-f]{64})",
                prompt,
            )
            if match is None:
                raise RuntimeError(
                    "Integration benchmark could not recover the approved file hash."
                )
            response = {
                "summary": "Return two from value().",
                "edits": [
                    {
                        "path": "value.py",
                        "action": "replace",
                        "expected_sha256": match.group(1),
                        "content": "def value():\n    return 2\n",
                    }
                ],
                "needs_more_context": False,
            }
        elif "FRESH INDEPENDENT code verifier" in prompt:
            response = {
                "verdict": "pass",
                "summary": "The isolated change is present and the deterministic check passed.",
                "findings": [
                    {
                        "criterion": "AC-01: value() returns 2 and deterministic verification passes.",
                        "status": "met",
                        "evidence": "The tracked diff changes the return value and value-check passed.",
                    }
                ],
                "risks": [],
            }
        else:
            raise RuntimeError(
                "Unexpected model prompt in development worker benchmark."
            )

        payload = json.dumps(response)
        return SimpleNamespace(
            role=role,
            model="m11-deterministic-fixture",
            digest="m11-deterministic-fixture-v1",
            context=int(kwargs.get("context", 16384)),
            think=bool(kwargs.get("think", False)),
            exclusive_memory=bool(kwargs.get("exclusive_memory", True)),
            elapsed_seconds=0.001,
            response={
                "response": payload,
                "prompt_eval_count": max(1, len(prompt) // 4),
                "eval_count": max(1, len(payload) // 4),
            },
        )


class DevelopmentWorkerExecutor:
    """Exercise M11 through the real M5 isolated development engine."""

    def __init__(self, scheduler_factory=None):
        self.scheduler_factory = (
            scheduler_factory
            or _DeterministicDevelopmentScheduler
        )

    def __call__(self, case: BenchmarkCase) -> BenchmarkObservation:
        from reverend.development import (
            TaskState,
            create_task,
            create_task_worktree,
            database,
            register_project,
            transition_task,
        )
        from reverend.development.engine import run_development_task
        from reverend.development.verification import VerificationCheck

        with TemporaryDirectory(prefix="reverend-m11-development-") as temporary:
            root = Path(temporary)
            repository = root / "repo"
            repository.mkdir()

            subprocess.run(
                ["git", "init", "-b", "main", str(repository)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            (repository / "value.py").write_text(
                "def value():\n    return 1\n",
                encoding="utf-8",
            )
            subprocess.run(
                ["git", "-C", str(repository), "add", "."],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repository),
                    "-c",
                    "user.name=Reverend Bench",
                    "-c",
                    "user.email=reverend@example.invalid",
                    "commit",
                    "-m",
                    "Initial benchmark fixture",
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            scheduler = self.scheduler_factory()

            with database(root / "development.db") as connection:
                project = register_project(connection, repository)
                task = create_task(
                    connection,
                    project.id,
                    title="Return two",
                    request=case.prompt,
                    acceptance_criteria="value() returns 2 and deterministic verification passes.",
                )
                transition_task(
                    connection,
                    task.id,
                    TaskState.PREPARING,
                )
                worktree = create_task_worktree(
                    connection,
                    task.id,
                    root=root / "worktrees",
                )
                transition_task(
                    connection,
                    task.id,
                    TaskState.RUNNING,
                )

                check = VerificationCheck(
                    name="value-check",
                    kind="test",
                    argv=(
                        sys.executable,
                        "-c",
                        (
                            "from pathlib import Path; "
                            "ns={}; "
                            "exec(Path('value.py').read_text(), ns); "
                            "raise SystemExit(0 if ns['value']() == 2 else 1)"
                        ),
                    ),
                )

                result = run_development_task(
                    connection,
                    task.id,
                    scheduler,
                    checks=(check,),
                    max_repairs=0,
                    python_executable=sys.executable,
                )

                worktree_value = (
                    Path(worktree.path)
                    / "value.py"
                ).read_text(encoding="utf-8")
                model_calls = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM model_runs WHERE task_id = ?",
                        (task.id,),
                    ).fetchone()[0]
                )

            primary_value = (
                repository
                / "value.py"
            ).read_text(encoding="utf-8")

            orchestration = result.orchestration
            if orchestration is None:
                raise RuntimeError(
                    "Development integration produced no worker orchestration result."
                )

            coder = next(
                (
                    record
                    for record in orchestration.records
                    if record.role is WorkerRole.CODER
                ),
                None,
            )

            metadata = {
                "status": result.status,
                "stop_reason": orchestration.stop_reason.value,
                "workers_used": orchestration.workers_used,
                "worker_steps": orchestration.worker_steps,
                "tool_calls": orchestration.tool_calls,
                "model_calls": model_calls,
                "retrieval_rounds": 0,
                "primary_checkout_unchanged": (
                    primary_value
                    == "def value():\n    return 1\n"
                ),
                "worktree_changed": (
                    worktree_value
                    == "def value():\n    return 2\n"
                ),
                "coder_verified_by": (
                    coder.verified_by
                    if coder is not None
                    else None
                ),
                "roles": [
                    record.role.value
                    for record in orchestration.records
                ],
            }

            return BenchmarkObservation(
                response=result.message,
                metadata=metadata,
            )


class WorkerOrchestrationExecutor:
    """Run deterministic worker-plan cases through the real orchestrator."""

    def __call__(self, case: BenchmarkCase) -> BenchmarkObservation:
        if case.parameters.get("integration") == "development_engine":
            return DevelopmentWorkerExecutor()(case)

        p = case.parameters
        tasks = tuple(
            WorkerTask(
                task_id=str(item["task_id"]),
                role=WorkerRole(str(item["role"])),
                objective=f"Benchmark worker {item['task_id']}",
                input_state={"case_id": case.case_id},
                requires_verification=bool(
                    item.get("requires_verification", False)
                ),
            )
            for item in p.get("workers", [])
        )
        budget = WorkerBudget(
            max_workers=int(p.get("max_workers", 4)),
            max_worker_steps=int(p.get("max_worker_steps", 8)),
            max_tool_calls=int(p.get("max_tool_calls", 8)),
        )

        def execute(task, policy):
            return WorkerExecution(
                status=WorkerStatus.COMPLETE,
                output_state={
                    "task_id": task.task_id,
                    "role": task.role.value,
                },
                steps_used=1,
                tool_calls=0,
            )

        verifier_verdict = str(p.get("verifier_verdict", "pass"))

        def verify(task, policy):
            return WorkerExecution(
                status=WorkerStatus.COMPLETE,
                output_state={"verdict": verifier_verdict},
                steps_used=1,
                tool_calls=0,
            )

        result = WorkerOrchestrator(budget).run(
            tasks,
            execute,
            verifier=verify,
        )
        metadata = {
            "stop_reason": result.stop_reason.value,
            "workers_used": result.workers_used,
            "worker_steps": result.worker_steps,
            "tool_calls": result.tool_calls,
            "records": [
                {
                    "task_id": record.task_id,
                    "role": record.role.value,
                    "status": record.status.value,
                    "stop_reason": record.stop_reason.value,
                    "verified_by": record.verified_by,
                }
                for record in result.records
            ],
        }
        return BenchmarkObservation(
            response=(
                "Worker orchestration completed."
                if result.completed
                else f"Worker orchestration stopped: {result.stop_reason.value}."
            ),
            metadata=metadata,
        )
