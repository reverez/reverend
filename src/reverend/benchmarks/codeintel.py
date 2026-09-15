"""Deterministic ReverendBench coverage for M12 code localization."""

from __future__ import annotations

import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from reverend.benchmarks.models import (
    BenchmarkBudget,
    BenchmarkCase,
    BenchmarkCategory,
    BenchmarkObservation,
)
from reverend.codeintel import search_code


def codeintel_cases() -> tuple[BenchmarkCase, ...]:
    return (
        BenchmarkCase(
            case_id="m12-structural-localization",
            name="Structural localization expands implementation to dependency and test",
            category=BenchmarkCategory.DEVELOPMENT,
            prompt="Change the task transition behavior.",
            parameters={
                "query": "transition task",
            },
            expected={
                "metadata_equals": {
                    "direct_top_path": "src/example/tasks.py",
                    "dependency_related": True,
                    "test_related": True,
                    "dependency_symbol_focused": True,
                    "test_symbol_focused": True,
                    "model_calls": 0,
                    "retrieval_rounds": 1,
                },
            },
            tags=(
                "m12",
                "code-intelligence",
                "localization",
                "dependency-graph",
                "deterministic",
            ),
            budget=BenchmarkBudget(
                timeout_seconds=5.0,
                max_model_calls=0,
                max_retrieval_rounds=1,
            ),
        ),
    )


class CodeIntelligenceExecutor:
    """Run deterministic localization against a real temporary Git repository."""

    def __call__(
        self,
        case: BenchmarkCase,
    ) -> BenchmarkObservation:
        with TemporaryDirectory(
            prefix="reverend-m12-codeintel-"
        ) as temporary:
            repository = (
                Path(temporary)
                / "repo"
            )
            repository.mkdir()

            subprocess.run(
                [
                    "git",
                    "init",
                    "-b",
                    "main",
                    str(repository),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            files = {
                "src/example/__init__.py": "",
                "src/example/models.py": (
                    "class TaskState:\n"
                    "    PENDING = 'pending'\n"
                ),
                "src/example/guard.py": (
                    "def enforce(value):\n"
                    "    return value\n"
                ),
                "src/example/tasks.py": (
                    "from .models import TaskState\n"
                    "from .guard import enforce\n\n"
                    "def transition_task(task):\n"
                    "    return enforce(TaskState.PENDING)\n"
                ),
                "tests/test_tasks.py": (
                    "from src.example.tasks import transition_task\n\n"
                    "def test_transition():\n"
                    "    assert transition_task(object()) == 'pending'\n"
                ),
                "README.md": (
                    "# Example\n\n"
                    "A small unrelated repository fixture.\n"
                ),
            }

            for relative, content in files.items():
                target = (
                    repository
                    / relative
                )
                target.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )
                target.write_text(
                    content,
                    encoding="utf-8",
                )

            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repository),
                    "add",
                    ".",
                ],
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

            result = search_code(
                repository,
                str(
                    case.parameters.get(
                        "query",
                        case.prompt,
                    )
                ),
                limit=10,
            )

            paths = list(
                result.paths
            )

            dependency = next(
                (
                    hit
                    for hit in result.hits
                    if hit.path
                    == "src/example/guard.py"
                ),
                None,
            )
            test = next(
                (
                    hit
                    for hit in result.hits
                    if hit.path
                    == "tests/test_tasks.py"
                ),
                None,
            )

            dependency_related = bool(
                dependency
                and any(
                    reason.startswith(
                        "graph:imports:"
                        "src/example/tasks.py"
                    )
                    for reason
                    in dependency.reasons
                )
            )
            test_related = bool(
                test
                and any(
                    reason.startswith(
                        "graph:imported_by:"
                        "src/example/tasks.py"
                    )
                    for reason
                    in test.reasons
                )
            )

            dependency_symbol_focused = bool(
                dependency
                and "enforce"
                in dependency.symbols
                and (
                    "call:transition_task->enforce"
                    in dependency.reasons
                )
            )
            test_symbol_focused = bool(
                test
                and "test_transition"
                in test.symbols
                and (
                    "call:test_transition->transition_task"
                    in test.reasons
                )
            )

            metadata = {
                "direct_top_path": (
                    paths[0]
                    if paths
                    else None
                ),
                "dependency_related": (
                    dependency_related
                ),
                "test_related": (
                    test_related
                ),
                "dependency_symbol_focused": (
                    dependency_symbol_focused
                ),
                "test_symbol_focused": (
                    test_symbol_focused
                ),
                "paths": paths,
                "model_calls": 0,
                "retrieval_rounds": 1,
            }

            return BenchmarkObservation(
                response=(
                    "Localized "
                    + ", ".join(paths)
                ),
                metadata=metadata,
            )
