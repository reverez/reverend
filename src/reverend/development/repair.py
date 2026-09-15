"""Bounded repair orchestration for Reverend development tasks."""

from __future__ import annotations

import json
import re
import sqlite3
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from .acceptance import compile_acceptance_criteria
from .edits import (
    EditBatchResult,
    EditProposal,
    apply_edits,
)
from .tasks import (
    TaskNotFoundError,
    get_task,
)
from .verification import (
    VerificationCheck,
    VerificationEvidence,
    VerificationReport,
    run_verification_plan,
)


DEFAULT_MAX_REPAIRS = 2
DEFAULT_MAX_DIAGNOSTIC_CHARS = 12_000


class RepairError(RuntimeError):
    """Base error for Reverend repair orchestration."""


class RepairBudgetError(RepairError):
    """Raised when an invalid repair budget is configured."""


class RepairStrategyError(RepairError):
    """Raised when a repair strategy returns unusable output."""


@dataclass(frozen=True)
class RepairDiagnostics:
    attempt: int
    text: str
    failed_checks: tuple[str, ...]
    failure_kind: str = "unknown"
    failing_tests: tuple[str, ...] = ()
    changed_paths: tuple[str, ...] = ()
    acceptance_criteria: tuple[str, ...] = ()


@dataclass(frozen=True)
class RepairRequest:
    task_id: str
    attempt: int
    diagnostics: RepairDiagnostics


@dataclass(frozen=True)
class RepairAttempt:
    attempt: int
    diagnostics: RepairDiagnostics
    proposals: tuple[EditProposal, ...]
    edit_result: EditBatchResult
    verification: VerificationReport


@dataclass(frozen=True)
class RepairLoopResult:
    passed: bool
    initial_verification: VerificationReport
    attempts: tuple[RepairAttempt, ...]
    final_verification: VerificationReport

    @property
    def repairs_used(self) -> int:
        return len(self.attempts)


RepairStrategy = Callable[
    [RepairRequest],
    Sequence[EditProposal],
]


def _artifact_text(
    path: str | None,
    *,
    maximum: int,
) -> tuple[str, bool]:
    """Read bounded artifact text and report whether it was clipped."""

    if not path:
        return "", False

    artifact = Path(path)

    try:
        raw = artifact.read_bytes()
    except OSError:
        return "", False

    clipped = (
        len(raw) > maximum
    )

    if clipped:
        marker = (
            b"\n...[artifact output clipped]\n"
        )

        payload_limit = max(
            0,
            maximum - len(marker),
        )

        raw = (
            raw[:payload_limit]
            + marker
        )

    return (
        raw.decode(
            "utf-8",
            errors="replace",
        ),
        clipped,
    )


def _verification_details(
    connection: sqlite3.Connection,
    evidence: VerificationEvidence,
) -> dict:
    row = connection.execute(
        """
        SELECT details_json
        FROM verifications
        WHERE id = ?
        """,
        (evidence.id,),
    ).fetchone()

    if row is None:
        return {}

    try:
        value = json.loads(
            row["details_json"]
        )
    except (
        json.JSONDecodeError,
        TypeError,
    ):
        return {}

    if not isinstance(
        value,
        dict,
    ):
        return {}

    return value




def _classify_failure(
    failures: tuple[VerificationEvidence, ...],
    text: str,
) -> str:
    folded = text.casefold()
    if any(item.timed_out or item.status == "error" for item in failures):
        return "environment"
    if any(item.kind == "source_integrity" for item in failures):
        return "source_integrity"
    if any(item.kind == "build" for item in failures):
        return "build"
    if "syntaxerror" in folded or "compile error" in folded:
        return "syntax_or_build"
    if any(item.kind == "test" for item in failures):
        if "assertionerror" in folded or re.search(r"\bfailed\s+\S+::", folded):
            return "test_assertion"
        return "test_failure"
    return "verification_failure"


def _failing_test_names(text: str) -> tuple[str, ...]:
    values: list[str] = []
    for match in re.findall(
        r"(?m)^(?:FAILED|ERROR)\s+([^\s]+(?:::[^\s]+)+)",
        text,
    ):
        clean = match.rstrip(":-")
        if clean not in values:
            values.append(clean)
    return tuple(values[:20])


def _changed_paths(root: str | Path) -> tuple[str, ...]:
    root = Path(root).resolve()
    paths: set[str] = set()
    commands = (
        ("git", "-C", str(root), "diff", "--name-only", "-z", "HEAD", "--"),
        ("git", "-C", str(root), "ls-files", "--others", "--exclude-standard", "-z"),
    )
    for argv in commands:
        try:
            result = subprocess.run(
                argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=20.0,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode != 0:
            continue
        for raw in result.stdout.split(b"\0"):
            if not raw:
                continue
            try:
                path = raw.decode("utf-8")
            except UnicodeDecodeError:
                continue
            if path.startswith(".reverend-build/"):
                continue
            paths.add(path)
    return tuple(sorted(paths))

def collect_failure_diagnostics(
    connection: sqlite3.Connection,
    report: VerificationReport,
    *,
    attempt: int,
    max_chars: int = DEFAULT_MAX_DIAGNOSTIC_CHARS,
    task_id: str | None = None,
) -> RepairDiagnostics:
    """Reduce failed verification evidence into bounded repair context."""

    if max_chars < 256:
        raise RepairError(
            "max_chars must be at least 256."
        )

    failures = tuple(
        check
        for check in report.checks
        if check.required
        and not check.passed
    )

    if not failures:
        return RepairDiagnostics(
            attempt=attempt,
            text="No required verification failures.",
            failed_checks=(),
        )

    chunks: list[str] = []
    artifact_clipped = False

    for check in failures:
        details = _verification_details(
            connection,
            check,
        )

        chunks.append(
            "\n".join(
                [
                    f"CHECK: {check.name}",
                    f"KIND: {check.kind}",
                    f"STATUS: {check.status}",
                    f"EXIT_CODE: {check.exit_code}",
                    f"TIMED_OUT: {check.timed_out}",
                    f"OUTPUT_LIMITED: {check.output_limited}",
                    f"SUMMARY: {check.summary}",
                ]
            )
        )

        stdout_info = details.get(
            "stdout_artifact"
        )

        stderr_info = details.get(
            "stderr_artifact"
        )

        if isinstance(
            stdout_info,
            dict,
        ):
            (
                stdout,
                stdout_clipped,
            ) = _artifact_text(
                stdout_info.get("path"),
                maximum=max_chars // 2,
            )

            artifact_clipped = (
                artifact_clipped
                or stdout_clipped
            )

            if stdout.strip():
                chunks.append(
                    "STDOUT:\n"
                    + stdout
                )

        if isinstance(
            stderr_info,
            dict,
        ):
            (
                stderr,
                stderr_clipped,
            ) = _artifact_text(
                stderr_info.get("path"),
                maximum=max_chars // 2,
            )

            artifact_clipped = (
                artifact_clipped
                or stderr_clipped
            )

            if stderr.strip():
                chunks.append(
                    "STDERR:\n"
                    + stderr
                )

    text = "\n\n".join(
        chunks
    )

    failing_tests = _failing_test_names(text)
    failure_kind = _classify_failure(failures, text)
    changed_paths: tuple[str, ...] = ()
    acceptance_criteria: tuple[str, ...] = ()

    if task_id is not None:
        task = get_task(connection, task_id)
        if task is not None:
            if task.worktree_path:
                changed_paths = _changed_paths(task.worktree_path)
            contract = compile_acceptance_criteria(task.acceptance_criteria)
            acceptance_criteria = tuple(
                f"{item.criterion_id}: {item.text}"
                for item in contract.criteria
            )

    structured = [
        f"FAILURE_KIND: {failure_kind}",
        "FAILING_TESTS: "
        + (", ".join(failing_tests) if failing_tests else "(none extracted)"),
        "CHANGED_PATHS: "
        + (", ".join(changed_paths) if changed_paths else "(none)"),
        "AUTHORITATIVE_ACCEPTANCE:",
    ]
    structured.extend(
        f"- {item}" for item in acceptance_criteria
    )
    if not acceptance_criteria:
        structured.append("- (none explicitly supplied)")

    text = "\n".join(structured) + "\n\n" + text

    truncated = artifact_clipped

    if len(text) > max_chars:
        text = text[
            : max_chars - 40
        ]

        text += (
            "\n\n...[repair diagnostics clipped]"
        )

        truncated = True

    if truncated:
        text = (
            "Diagnostics are bounded and were truncated.\n\n"
            + text
        )

    return RepairDiagnostics(
        attempt=attempt,
        text=text,
        failed_checks=tuple(
            check.name
            for check in failures
        ),
        failure_kind=failure_kind,
        failing_tests=failing_tests,
        changed_paths=changed_paths,
        acceptance_criteria=acceptance_criteria,
    )


def _record_repair_attempt(
    connection: sqlite3.Connection,
    *,
    task_id: str,
    run_id: str | None,
    attempt: int,
    diagnostics: RepairDiagnostics,
    proposals: Sequence[EditProposal],
    edit_result: EditBatchResult,
    verification: VerificationReport,
) -> None:
    connection.execute(
        """
        INSERT INTO experiments (
            id,
            task_id,
            run_id,
            name,
            hypothesis,
            outcome,
            status,
            metadata_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid.uuid4()),
            task_id,
            run_id,
            f"repair-attempt-{attempt}",
            (
                "A bounded structured repair "
                "can resolve current verification failures."
            ),
            (
                "verification passed"
                if verification.passed
                else "verification still failing"
            ),
            "complete",
            json.dumps(
                {
                    "attempt": attempt,
                    "failed_checks": list(
                        diagnostics.failed_checks
                    ),
                    "failure_kind": diagnostics.failure_kind,
                    "failing_tests": list(diagnostics.failing_tests),
                    "changed_paths_before_repair": list(diagnostics.changed_paths),
                    "acceptance_criteria": list(diagnostics.acceptance_criteria),
                    "proposal_count": len(
                        proposals
                    ),
                    "changed_paths": list(
                        edit_result.changed_paths
                    ),
                    "verification_passed": (
                        verification.passed
                    ),
                },
                sort_keys=True,
            ),
        ),
    )


def run_repair_loop(
    connection: sqlite3.Connection,
    task_id: str,
    checks: Sequence[VerificationCheck],
    repair_strategy: RepairStrategy,
    *,
    run_id: str | None = None,
    step_id: str | None = None,
    max_repairs: int = DEFAULT_MAX_REPAIRS,
    diagnostic_chars: int = DEFAULT_MAX_DIAGNOSTIC_CHARS,
) -> RepairLoopResult:
    """Verify, repair and re-verify under a hard retry budget."""

    if max_repairs < 0:
        raise RepairBudgetError(
            "max_repairs cannot be negative."
        )

    if max_repairs > 10:
        raise RepairBudgetError(
            "max_repairs above 10 is forbidden."
        )

    task = get_task(
        connection,
        task_id,
    )

    if task is None:
        raise TaskNotFoundError(
            f"Unknown task: {task_id}"
        )

    initial = run_verification_plan(
        connection,
        task_id,
        checks,
        run_id=run_id,
        step_id=step_id,
        fail_fast=True,
    )

    if initial.passed:
        return RepairLoopResult(
            passed=True,
            initial_verification=initial,
            attempts=(),
            final_verification=initial,
        )

    attempts: list[
        RepairAttempt
    ] = []

    current = initial

    for attempt_number in range(
        1,
        max_repairs + 1,
    ):
        diagnostics = (
            collect_failure_diagnostics(
                connection,
                current,
                attempt=attempt_number,
                max_chars=diagnostic_chars,
                task_id=task_id,
            )
        )

        request = RepairRequest(
            task_id=task_id,
            attempt=attempt_number,
            diagnostics=diagnostics,
        )

        proposed = repair_strategy(
            request
        )

        proposals = tuple(
            proposed
        )

        if not proposals:
            raise RepairStrategyError(
                "Repair strategy returned "
                f"no edits for attempt {attempt_number}."
            )

        if not all(
            isinstance(
                proposal,
                EditProposal,
            )
            for proposal in proposals
        ):
            raise RepairStrategyError(
                "Repair strategy must return "
                "EditProposal instances only."
            )

        edit_result = apply_edits(
            connection,
            task_id,
            proposals,
        )

        verification = (
            run_verification_plan(
                connection,
                task_id,
                checks,
                run_id=run_id,
                step_id=step_id,
                fail_fast=True,
            )
        )

        _record_repair_attempt(
            connection,
            task_id=task_id,
            run_id=run_id,
            attempt=attempt_number,
            diagnostics=diagnostics,
            proposals=proposals,
            edit_result=edit_result,
            verification=verification,
        )

        item = RepairAttempt(
            attempt=attempt_number,
            diagnostics=diagnostics,
            proposals=proposals,
            edit_result=edit_result,
            verification=verification,
        )

        attempts.append(
            item
        )

        current = verification

        if verification.passed:
            return RepairLoopResult(
                passed=True,
                initial_verification=initial,
                attempts=tuple(
                    attempts
                ),
                final_verification=verification,
            )

    return RepairLoopResult(
        passed=False,
        initial_verification=initial,
        attempts=tuple(
            attempts
        ),
        final_verification=current,
    )
