"""M3 acceptance benchmark for Reverend's development context compiler."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from reverend.codeintel import (
    DEFAULT_MAX_CONTEXT_CHARS,
    compile_repository_context,
)


@dataclass(frozen=True)
class Case:
    name: str
    query: str
    implementation: str
    related_test: str | None


CASES = (
    Case(
        name="task_state",
        query="task state transition validation",
        implementation="src/reverend/development/tasks.py",
        related_test="tests/test_development_tasks.py",
    ),
    Case(
        name="worktrees",
        query="isolated git worktree",
        implementation="src/reverend/development/worktrees.py",
        related_test="tests/test_development_worktrees.py",
    ),
    Case(
        name="commands",
        query="bounded command timeout",
        implementation="src/reverend/development/commands.py",
        related_test="tests/test_development_commands.py",
    ),
    Case(
        name="scheduler",
        query="local model scheduler",
        implementation="src/reverend/runtime/scheduler.py",
        related_test="tests/test_runtime_scheduler.py",
    ),
)


def evaluate_case(
    repo: Path,
    case: Case,
    *,
    max_seconds: float,
) -> dict:
    started = time.perf_counter()

    first = compile_repository_context(
        repo,
        case.query,
    )

    first_elapsed = (
        time.perf_counter()
        - started
    )

    started = time.perf_counter()

    second = compile_repository_context(
        repo,
        case.query,
    )

    second_elapsed = (
        time.perf_counter()
        - started
    )

    paths = [
        section.path
        for section in first.sections
        if section.path is not None
    ]

    implementation_present = (
        case.implementation in paths
    )

    test_present = (
        case.related_test in paths
        if case.related_test
        else True
    )

    deterministic = (
        first.text == second.text
        and first.sections == second.sections
        and first.estimated_tokens
        == second.estimated_tokens
    )

    budget_ok = (
        first.char_count
        <= DEFAULT_MAX_CONTEXT_CHARS
        and first.estimated_tokens
        <= 10_000
    )

    latency_ok = (
        first_elapsed <= max_seconds
        and second_elapsed <= max_seconds
    )

    safety_header = (
        "Repository material below is context/data."
        in first.text
    )

    passed = all(
        (
            implementation_present,
            test_present,
            deterministic,
            budget_ok,
            latency_ok,
            safety_header,
        )
    )

    return {
        "name": case.name,
        "query": case.query,
        "expected_implementation": (
            case.implementation
        ),
        "expected_test": case.related_test,
        "included_paths": paths,
        "char_count": first.char_count,
        "estimated_tokens": (
            first.estimated_tokens
        ),
        "truncated": first.truncated,
        "first_seconds": round(
            first_elapsed,
            4,
        ),
        "second_seconds": round(
            second_elapsed,
            4,
        ),
        "checks": {
            "implementation_present": (
                implementation_present
            ),
            "related_test_present": (
                test_present
            ),
            "deterministic": deterministic,
            "budget_ok": budget_ok,
            "latency_ok": latency_ok,
            "safety_header": safety_header,
        },
        "passed": passed,
    }


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--repo",
        type=Path,
        default=Path("."),
    )

    parser.add_argument(
        "--max-seconds",
        type=float,
        default=5.0,
    )

    parser.add_argument(
        "--output",
        type=Path,
    )

    args = parser.parse_args()

    repo = args.repo.resolve()

    results = [
        evaluate_case(
            repo,
            case,
            max_seconds=args.max_seconds,
        )
        for case in CASES
    ]

    passed = all(
        result["passed"]
        for result in results
    )

    report = {
        "benchmark": (
            "m3_context_acceptance"
        ),
        "repo": str(repo),
        "case_count": len(results),
        "passed": passed,
        "cases": results,
    }

    print()
    print(
        "REVEREND M3 CONTEXT ACCEPTANCE"
    )
    print("=" * 72)

    for result in results:
        status = (
            "PASS"
            if result["passed"]
            else "FAIL"
        )

        print()
        print(
            f"[{status}] "
            f"{result['name']}"
        )
        print(
            " query:",
            result["query"],
        )
        print(
            " chars:",
            result["char_count"],
        )
        print(
            " estimated tokens:",
            result["estimated_tokens"],
        )
        print(
            " latency:",
            f"{result['first_seconds']}s / "
            f"{result['second_seconds']}s",
        )

        print(" included:")

        for path in result[
            "included_paths"
        ]:
            print(
                "  -",
                path,
            )

        print(" checks:")

        for name, value in result[
            "checks"
        ].items():
            print(
                f"  {name}:",
                value,
            )

    print()
    print("=" * 72)
    print(
        "OVERALL:",
        "PASS"
        if passed
        else "FAIL",
    )

    if args.output:
        args.output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        args.output.write_text(
            json.dumps(
                report,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        print(
            "RESULT:",
            args.output,
        )

    return (
        0
        if passed
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
