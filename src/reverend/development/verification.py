"""Deterministic build and test verification for Reverend."""

from __future__ import annotations

import json
import sqlite3
import sys
import time
import uuid
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Sequence

from reverend.codeintel import (
    scan_repository,
)

from .commands import (
    CommandRunnerError,
    run_command,
)
from .models import TaskState
from .tasks import (
    TaskNotFoundError,
    get_task,
)


class VerificationError(RuntimeError):
    """Base Reverend verification error."""


class VerificationStateError(
    VerificationError
):
    """Raised when task state cannot be verified."""


@dataclass(frozen=True)
class VerificationCheck:
    name: str
    kind: str
    argv: tuple[str, ...]
    timeout: float = 300.0
    required: bool = True
    cwd: str | None = None
    environment: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class VerificationEvidence:
    id: str
    name: str
    kind: str
    required: bool
    passed: bool
    status: str
    argv: tuple[str, ...]
    exit_code: int | None
    timed_out: bool
    output_limited: bool
    elapsed_seconds: float
    summary: str


@dataclass(frozen=True)
class VerificationReport:
    checks: tuple[
        VerificationEvidence,
        ...
    ]

    @property
    def passed(self) -> bool:
        return all(
            check.passed
            or not check.required
            for check in self.checks
        )

    @property
    def failed_required(
        self,
    ) -> tuple[
        VerificationEvidence,
        ...
    ]:
        return tuple(
            check
            for check in self.checks
            if (
                check.required
                and not check.passed
            )
        )


def _node_test_check(root: Path) -> VerificationCheck | None:
    """Return a bounded explicit Node test check without installing packages."""

    package = root / "package.json"

    if (
        not package.is_file()
        or package.is_symlink()
    ):
        return None

    try:
        raw = package.read_bytes()
    except OSError:
        return None

    if (
        not raw
        or len(raw) > 128 * 1024
        or b"\\x00" in raw
    ):
        return None

    try:
        value = json.loads(
            raw.decode("utf-8")
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ):
        return None

    if not isinstance(value, dict):
        return None

    scripts = value.get("scripts")

    if not isinstance(scripts, dict):
        return None

    test = scripts.get("test")

    if (
        not isinstance(test, str)
        or not test.strip()
    ):
        return None

    normalized = " ".join(
        test.strip().split()
    )

    placeholder = (
        "no test specified"
        in normalized.casefold()
        or normalized.casefold()
        in {
            "exit 0",
            "true",
        }
    )

    if placeholder:
        return None

    return VerificationCheck(
        name="npm-test",
        kind="test",
        argv=(
            "npm",
            "--silent",
            "test",
        ),
        timeout=300.0,
        environment=(
            ("CI", "1"),
            ("NODE_ENV", "test"),
        ),
    )


def discover_verification_plan(
    path: str | Path,
    *,
    python_executable: str | None = None,
    affected_tests: Sequence[str] = (),
) -> tuple[
    VerificationCheck,
    ...
]:
    """Conservatively discover deterministic repository checks."""

    root = Path(path).resolve()

    profile = scan_repository(
        root,
        history_limit=0,
    )

    checks: list[
        VerificationCheck
    ] = [
        VerificationCheck(
            name="git-diff-check",
            kind="source_integrity",
            argv=(
                "git",
                "diff",
                "--check",
            ),
            timeout=30.0,
        )
    ]

    if (
        "python"
        in profile.build_systems
        and profile.test_count > 0
    ):
        test_paths = set(profile.test_files)
        targeted = tuple(
            dict.fromkeys(
                path
                for path in affected_tests
                if path in test_paths
            )
        )[:8]
        if targeted:
            checks.append(
                VerificationCheck(
                    name="pytest-targeted",
                    kind="test",
                    argv=(
                        python_executable
                        or sys.executable,
                        "-m",
                        "pytest",
                        "-q",
                        *targeted,
                    ),
                    timeout=180.0,
                )
            )
        checks.append(
            VerificationCheck(
                name="pytest",
                kind="test",
                argv=(
                    python_executable
                    or sys.executable,
                    "-m",
                    "pytest",
                    "-q",
                ),
                timeout=300.0,
            )
        )

    if (
        "node" in profile.build_systems
        and profile.test_count > 0
    ):
        node_test = _node_test_check(
            root
        )

        if node_test is not None:
            checks.append(
                node_test
            )

    if "cmake" in profile.build_systems:
        from .cmake import discover_cmake_checks
        checks.extend(discover_cmake_checks(root))

    return tuple(
        checks
    )


def _terminal_output_excerpt(stdout: str, stderr: str) -> str:
    """Return a bounded deterministic command-result excerpt."""
    lines=[
        line.strip()
        for line in (stdout+"\n"+stderr).splitlines()
        if line.strip()
    ]
    if not lines:
        return ""
    return lines[-1][:300]


def _persist_evidence(
    connection: sqlite3.Connection,
    *,
    verification_id: str,
    task_id: str,
    run_id: str | None,
    check: VerificationCheck,
    status: str,
    exit_code: int | None,
    summary: str,
    details: dict,
) -> None:
    connection.execute(
        """
        INSERT INTO verifications (
            id,
            task_id,
            run_id,
            kind,
            status,
            command,
            exit_code,
            summary,
            details_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            verification_id,
            task_id,
            run_id,
            check.kind,
            status,
            json.dumps(
                list(
                    check.argv
                )
            ),
            exit_code,
            summary,
            json.dumps(
                details,
                sort_keys=True,
            ),
        ),
    )


def run_verification_plan(
    connection: sqlite3.Connection,
    task_id: str,
    checks: Sequence[
        VerificationCheck
    ],
    *,
    run_id: str | None = None,
    step_id: str | None = None,
    fail_fast: bool = True,
) -> VerificationReport:
    """Execute and persist deterministic verification evidence."""

    task = get_task(
        connection,
        task_id,
    )

    if task is None:
        raise TaskNotFoundError(
            f"Unknown task: {task_id}"
        )

    if task.state not in {
        TaskState.RUNNING,
        TaskState.VERIFYING,
    }:
        raise VerificationStateError(
            "Task must be RUNNING or VERIFYING "
            "before verification."
        )

    if not task.worktree_path:
        raise VerificationStateError(
            "Task has no isolated worktree."
        )

    if not checks:
        raise VerificationError(
            "Verification plan cannot be empty."
        )

    evidence: list[
        VerificationEvidence
    ] = []

    for check in checks:
        if not check.name.strip():
            raise VerificationError(
                "Verification check name "
                "cannot be empty."
            )

        if not check.kind.strip():
            raise VerificationError(
                "Verification check kind "
                "cannot be empty."
            )

        if not check.argv:
            raise VerificationError(
                f"Verification {check.name!r} "
                "has empty argv."
            )

        verification_id = str(
            uuid.uuid4()
        )

        started = time.monotonic()

        try:
            no_tests = False
            if check.name == 'ctest':
                listing_argv = ('ctest', '--test-dir', '.reverend-build', '--show-only=json-v1')
                listing = run_command(connection, task.id, listing_argv, timeout=30,
                                      run_id=run_id, step_id=step_id)
                if not listing.succeeded:
                    raise CommandRunnerError('CTest discovery failed; inspect command artifacts')
                try:
                    no_tests = len(json.loads(listing.stdout)['tests']) == 0
                except (ValueError, KeyError, TypeError) as exc:
                    raise CommandRunnerError('Invalid CTest discovery output') from exc
                if no_tests:
                    check = replace(check, argv=listing_argv, required=False)
            result = listing if no_tests else run_command(
                connection,
                task.id,
                check.argv,
                cwd=check.cwd,
                timeout=(
                    check.timeout
                ),
                environment=(
                    dict(check.environment)
                    if check.environment
                    else None
                ),
                run_id=run_id,
                step_id=step_id,
            )

            passed = (
                result.succeeded
            )

            if no_tests:
                check = replace(check, required=False)
            status = (
                "skipped" if no_tests else
                "passed"
                if passed
                else "failed"
            )

            if no_tests:
                summary = 'ctest: no tests registered; build evidence only'
            elif result.timed_out:
                summary = (
                    f"{check.name}: timed out"
                )
            elif result.output_limited:
                summary = (
                    f"{check.name}: "
                    "output limit exceeded"
                )
            elif result.exit_code != 0:
                summary = (
                    f"{check.name}: "
                    f"exit code {result.exit_code}"
                )
            else:
                excerpt=_terminal_output_excerpt(
                    result.stdout,
                    result.stderr,
                )
                summary = (
                    f"{check.name}: passed"
                    + (
                        f" | {excerpt}"
                        if excerpt
                        else ""
                    )
                )

            details = {
                "name": check.name,
                "required": (
                    check.required
                ),
                "argv": list(
                    check.argv
                ),
                "cwd": str(
                    result.cwd
                ),
                "environment": {
                    key: value
                    for key, value in check.environment
                },
                "timed_out": (
                    result.timed_out
                ),
                "output_limited": (
                    result.output_limited
                ),
                "elapsed_seconds": (
                    result.elapsed_seconds
                ),
                "stdout_artifact": {
                    "path": str(
                        result.stdout_artifact.path
                    ),
                    "sha256": (
                        result.stdout_artifact
                        .content_hash
                    ),
                },
                "stderr_artifact": {
                    "path": str(
                        result.stderr_artifact.path
                    ),
                    "sha256": (
                        result.stderr_artifact
                        .content_hash
                    ),
                },
            }

            _persist_evidence(
                connection,
                verification_id=(
                    verification_id
                ),
                task_id=task.id,
                run_id=run_id,
                check=check,
                status=status,
                exit_code=(
                    result.exit_code
                ),
                summary=summary,
                details=details,
            )

            item = VerificationEvidence(
                id=verification_id,
                name=check.name,
                kind=check.kind,
                required=(
                    check.required
                ),
                passed=passed,
                status=status,
                argv=check.argv,
                exit_code=(
                    result.exit_code
                ),
                timed_out=(
                    result.timed_out
                ),
                output_limited=(
                    result.output_limited
                ),
                elapsed_seconds=(
                    result.elapsed_seconds
                ),
                summary=summary,
            )

        except CommandRunnerError as exc:
            elapsed = (
                time.monotonic()
                - started
            )

            summary = (
                f"{check.name}: "
                f"command error: {exc}"
            )

            details = {
                "name": check.name,
                "required": (
                    check.required
                ),
                "argv": list(
                    check.argv
                ),
                "error": str(exc),
                "elapsed_seconds": (
                    elapsed
                ),
            }

            _persist_evidence(
                connection,
                verification_id=(
                    verification_id
                ),
                task_id=task.id,
                run_id=run_id,
                check=check,
                status="error",
                exit_code=None,
                summary=summary,
                details=details,
            )

            item = VerificationEvidence(
                id=verification_id,
                name=check.name,
                kind=check.kind,
                required=(
                    check.required
                ),
                passed=False,
                status="error",
                argv=check.argv,
                exit_code=None,
                timed_out=False,
                output_limited=False,
                elapsed_seconds=round(
                    elapsed,
                    6,
                ),
                summary=summary,
            )

        evidence.append(
            item
        )

        if (
            fail_fast
            and item.required
            and not item.passed
        ):
            break

    return VerificationReport(
        checks=tuple(
            evidence
        )
    )


def verify_task(
    connection: sqlite3.Connection,
    task_id: str,
    *,
    run_id: str | None = None,
    step_id: str | None = None,
    python_executable: str | None = None,
    fail_fast: bool = True,
) -> VerificationReport:
    """Discover and execute Reverend's conservative verification plan."""

    task = get_task(
        connection,
        task_id,
    )

    if task is None:
        raise TaskNotFoundError(
            f"Unknown task: {task_id}"
        )

    if not task.worktree_path:
        raise VerificationStateError(
            "Task has no isolated worktree."
        )

    checks = (
        discover_verification_plan(
            task.worktree_path,
            python_executable=(
                python_executable
            ),
        )
    )

    return run_verification_plan(
        connection,
        task_id,
        checks,
        run_id=run_id,
        step_id=step_id,
        fail_fast=fail_fast,
    )
