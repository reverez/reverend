#!/usr/bin/env python3
"""Deterministic checks for V3 local-model bakeoff results."""

from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path


def strip_fence(text: str) -> str:
    text = text.strip()

    match = re.fullmatch(
        r"```(?:python|json)?\s*(.*?)\s*```",
        text,
        re.DOTALL | re.IGNORECASE,
    )

    return match.group(1).strip() if match else text


def instruction_score(text: str) -> bool:
    cleaned = strip_fence(text)

    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        return False

    return value == {
        "status": "ok",
        "value": 42,
    }


def coding_score(text: str) -> bool:
    cleaned = strip_fence(text)

    lines = [
        line.expandtabs(4)
        for line in cleaned.splitlines()
    ]

    candidates = []

    # Some coding models return the entire requested function.
    if cleaned.lstrip().startswith(
        "def deduplicate_preserving_order"
    ):
        candidates.append(cleaned)

    # Some models interpret "function body only" as already-indented
    # body text, but omit indentation from the first line. Preserve
    # existing relative indentation and ensure every body line has at
    # least one function-level indent.
    normalized = []

    for line in lines:
        if not line.strip():
            normalized.append("")
            continue

        leading = len(line) - len(line.lstrip(" "))

        if leading < 4:
            line = (" " * (4 - leading)) + line

        normalized.append(line)

    candidates.append(
        "def deduplicate_preserving_order(items):\n"
        + "\n".join(normalized)
    )

    # Also support completely unindented body output.
    candidates.append(
        "def deduplicate_preserving_order(items):\n"
        + "\n".join(
            "    " + line
            for line in lines
        )
    )

    cases = [
        ([1, 2, 1, 3, 2], [1, 2, 3]),
        ([], []),
        (["a", "a", "b"], ["a", "b"]),
        ([0, 0, -1, 0, -1, 2], [0, -1, 2]),
    ]

    for source in dict.fromkeys(candidates):
        try:
            tree = ast.parse(source)
            code = compile(
                tree,
                "<model-output>",
                "exec",
            )

            namespace = {}
            exec(code, namespace)

            fn = namespace[
                "deduplicate_preserving_order"
            ]

            if all(
                fn(value) == expected
                for value, expected in cases
            ):
                return True

        except Exception:
            continue

    return False

def reasoning_score(text: str) -> bool:
    normalized = re.sub(
        r"[\s*_`$\\{}]",
        "",
        text.lower(),
    )

    return (
        "o(nlogn)" in normalized
        or "θ(nlogn)" in normalized
        or "nlogn" in normalized
    )


SCORERS = {
    "instruction": instruction_score,
    "coding": coding_score,
    "reasoning": reasoning_score,
}


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "report",
        type=Path,
    )

    args = parser.parse_args()

    data = json.loads(
        args.report.read_text(
            encoding="utf-8"
        )
    )

    evaluated = []

    for run in data["runs"]:
        case = run["case"]

        passed = (
            bool(run.get("success"))
            and SCORERS[case](
                run.get("response", "")
            )
        )

        evaluated.append(
            {
                "context": run["context"],
                "case": case,
                "passed": passed,
                "elapsed_seconds":
                    run.get("elapsed_seconds"),
                "generation_tokens_per_second":
                    run.get(
                        "generation_tokens_per_second"
                    ),
            }
        )

    print(
        json.dumps(
            evaluated,
            indent=2,
        )
    )

    passed = sum(
        result["passed"]
        for result in evaluated
    )

    total = len(evaluated)

    print(
        f"\nSCORE={passed}/{total}"
    )

    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
