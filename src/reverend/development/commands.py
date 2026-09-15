"""Bounded subprocess execution inside Reverend task worktrees."""

from __future__ import annotations

import hashlib
import json
import os
import re
import signal
import sqlite3
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from reverend.config import DATA_ROOT

from .database import transaction
from .models import TrustMode
from .sandbox import (
    DevelopmentSandboxError,
    development_sandbox_argv,
)
from .projects import get_project
from .tasks import (
    TaskNotFoundError,
    get_task,
)


DEFAULT_ARTIFACT_ROOT = (
    DATA_ROOT / "artifacts"
)

DEFAULT_TIMEOUT_SECONDS = 300.0

DEFAULT_MAX_OUTPUT_BYTES = (
    10 * 1024 * 1024
)


class CommandRunnerError(RuntimeError):
    """Base command-runner error."""


class CommandPolicyError(CommandRunnerError):
    """Raised when execution violates Reverend policy."""


class CommandPathError(CommandPolicyError):
    """Raised when cwd escapes the task worktree."""


class UntrustedRepositoryError(
    CommandPolicyError
):
    """Raised when command execution is unsafe for an untrusted repo."""


class CommandExecutionError(
    CommandRunnerError
):
    """Raised when a process cannot be started."""


@dataclass(frozen=True)
class CommandArtifact:
    kind: str
    path: Path
    content_hash: str
    size_bytes: int


@dataclass(frozen=True)
class CommandResult:
    argv: tuple[str, ...]
    cwd: Path
    exit_code: int | None
    timed_out: bool
    output_limited: bool
    elapsed_seconds: float
    stdout: str
    stderr: str
    stdout_artifact: CommandArtifact
    stderr_artifact: CommandArtifact
    sandboxed: bool = False

    @property
    def succeeded(self) -> bool:
        return (
            self.exit_code == 0
            and not self.timed_out
            and not self.output_limited
        )


def _is_within(
    candidate: Path,
    root: Path,
) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False

    return True


_BLOCKED_ENV_FRAGMENTS = (
    "TOKEN",
    "SECRET",
    "PASSWORD",
    "PASSWD",
    "API_KEY",
    "APIKEY",
    "PRIVATE_KEY",
    "ACCESS_KEY",
)

_BLOCKED_ENV_NAMES = frozenset(
    {
        "BASH_ENV",
        "DBUS_SESSION_BUS_ADDRESS",
        "DOCKER_HOST",
        "GIT_ASKPASS",
        "GIT_CONFIG_GLOBAL",
        "GIT_CONFIG_SYSTEM",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "GPG_AGENT_INFO",
        "KRB5CCNAME",
        "KUBECONFIG",
        "LD_PRELOAD",
        "NETRC",
        "PYTHONBREAKPOINT",
        "PYTHONHOME",
        "PYTHONINSPECT",
        "PYTHONPATH",
        "PYTHONSTARTUP",
        "SSH_AGENT_PID",
        "SSH_ASKPASS",
        "SSH_AUTH_SOCK",
        "SUDO_ASKPASS",
        "XDG_RUNTIME_DIR",
    }
)

_BLOCKED_ENV_PREFIXES = (
    "AWS_",
    "AZURE_",
    "DOCKER_",
    "GCP_",
    "GH_",
    "GOOGLE_",
    "GPG_",
    "KUBE_",
    "OCI_",
    "SSH_",
    "VAULT_",
)


def _blocked_environment_name(key: str) -> bool:
    upper = key.upper()

    return (
        upper in _BLOCKED_ENV_NAMES
        or any(
            fragment in upper
            for fragment in _BLOCKED_ENV_FRAGMENTS
        )
        or any(
            upper.startswith(prefix)
            for prefix in _BLOCKED_ENV_PREFIXES
        )
    )


def _validate_environment_item(
    key: str,
    value: str,
) -> tuple[str, str]:
    if (
        not isinstance(key, str)
        or not re.fullmatch(
            r"[A-Za-z_][A-Za-z0-9_]*",
            key,
        )
    ):
        raise CommandPolicyError(
            "Environment variable name is invalid."
        )

    if not isinstance(value, str):
        raise CommandPolicyError(
            f"Environment variable {key} must be text."
        )

    if (
        "\x00" in value
        or len(value) > 16_384
    ):
        raise CommandPolicyError(
            f"Environment variable {key} is invalid or too large."
        )

    if _blocked_environment_name(key):
        raise CommandPolicyError(
            "Refusing credential/capability environment "
            f"variable: {key}"
        )

    return key, value


def _safe_environment(
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Remove host credential/capability handles from child processes."""

    result: dict[str, str] = {}

    for key, value in os.environ.items():
        if _blocked_environment_name(key):
            continue

        try:
            clean_key, clean_value = (
                _validate_environment_item(
                    key,
                    value,
                )
            )
        except CommandPolicyError:
            continue

        result[clean_key] = clean_value

    if extra:
        for key, value in extra.items():
            clean_key, clean_value = (
                _validate_environment_item(
                    key,
                    value,
                )
            )
            result[clean_key] = clean_value

    return result


def _terminate_process_group(
    process: subprocess.Popen[bytes],
) -> None:
    try:
        os.killpg(
            process.pid,
            signal.SIGTERM,
        )
    except ProcessLookupError:
        return

    try:
        process.wait(
            timeout=2.0
        )
        return
    except subprocess.TimeoutExpired:
        pass

    try:
        os.killpg(
            process.pid,
            signal.SIGKILL,
        )
    except ProcessLookupError:
        return

    try:
        process.wait(
            timeout=2.0
        )
    except subprocess.TimeoutExpired:
        pass


def _truncate(
    path: Path,
    maximum: int,
) -> None:
    if path.stat().st_size <= maximum:
        return

    with path.open("r+b") as handle:
        handle.truncate(
            maximum
        )


def _artifact(
    path: Path,
    kind: str,
) -> CommandArtifact:
    raw = path.read_bytes()

    return CommandArtifact(
        kind=kind,
        path=path,
        content_hash=hashlib.sha256(
            raw
        ).hexdigest(),
        size_bytes=len(raw),
    )


def _store_artifact(
    connection: sqlite3.Connection,
    *,
    task_id: str,
    run_id: str | None,
    step_id: str | None,
    artifact: CommandArtifact,
    command_id: str,
    argv: tuple[str, ...],
    sandboxed: bool,
) -> None:
    connection.execute(
        """
        INSERT INTO artifacts (
            id,
            task_id,
            run_id,
            step_id,
            kind,
            path,
            content_hash,
            metadata_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid.uuid4()),
            task_id,
            run_id,
            step_id,
            artifact.kind,
            str(artifact.path),
            artifact.content_hash,
            json.dumps(
                {
                    "command_id": command_id,
                    "argv": list(argv),
                    "sandboxed": sandboxed,
                    "size_bytes": (
                        artifact.size_bytes
                    ),
                },
                sort_keys=True,
            ),
        ),
    )


def run_command(
    connection: sqlite3.Connection,
    task_id: str,
    argv: Sequence[str],
    *,
    cwd: str | Path | None = None,
    timeout: float = (
        DEFAULT_TIMEOUT_SECONDS
    ),
    max_output_bytes: int = (
        DEFAULT_MAX_OUTPUT_BYTES
    ),
    environment: (
        Mapping[str, str] | None
    ) = None,
    run_id: str | None = None,
    step_id: str | None = None,
    artifact_root: (
        str | Path | None
    ) = None,
    sandbox: bool = False,
) -> CommandResult:
    """Run one bounded argv command under an explicit execution boundary."""

    task = get_task(
        connection,
        task_id,
    )

    if task is None:
        raise TaskNotFoundError(
            f"Unknown task: {task_id}"
        )

    project = get_project(
        connection,
        task.project_id,
    )

    if project is None:
        raise CommandRunnerError(
            "Task's registered project "
            "no longer exists."
        )

    if not isinstance(
        sandbox,
        bool,
    ):
        raise CommandPolicyError(
            "sandbox must be a boolean."
        )

    if (
        project.trust_mode
        != TrustMode.TRUSTED_REPO
        and not sandbox
    ):
        raise UntrustedRepositoryError(
            "Untrusted repository commands require "
            "the explicit OS sandbox."
        )

    if not task.worktree_path:
        raise CommandPolicyError(
            "Task has no isolated worktree."
        )

    worktree = Path(
        task.worktree_path
    ).resolve()

    if not worktree.is_dir():
        raise CommandPolicyError(
            "Task worktree does not exist: "
            f"{worktree}"
        )

    command = tuple(
        str(value)
        for value in argv
    )

    if not command:
        raise CommandPolicyError(
            "Command argv cannot be empty."
        )

    if any(
        value == ""
        for value in command
    ):
        raise CommandPolicyError(
            "Command argv cannot contain "
            "empty arguments."
        )

    if timeout <= 0:
        raise CommandPolicyError(
            "Command timeout must be positive."
        )

    if max_output_bytes < 1:
        raise CommandPolicyError(
            "max_output_bytes must be positive."
        )

    requested_cwd = (
        worktree
        if cwd is None
        else Path(cwd)
    )

    if not requested_cwd.is_absolute():
        requested_cwd = (
            worktree
            / requested_cwd
        )

    resolved_cwd = (
        requested_cwd.resolve()
    )

    if not _is_within(
        resolved_cwd,
        worktree,
    ):
        raise CommandPathError(
            "Command cwd escaped the "
            f"task worktree: {resolved_cwd}"
        )

    if not resolved_cwd.is_dir():
        raise CommandPathError(
            "Command cwd is not a directory: "
            f"{resolved_cwd}"
        )

    executed_command = command
    child_environment = _safe_environment(
        environment
    )

    if sandbox:
        if environment:
            raise CommandPolicyError(
                "Sandboxed execution uses a fixed minimal environment."
            )

        try:
            executed_command = development_sandbox_argv(
                worktree,
                command,
                timeout_seconds=timeout,
                cwd=resolved_cwd,
            )
        except DevelopmentSandboxError as exc:
            raise CommandPolicyError(
                str(exc)
            ) from exc

        child_environment = {}

    command_id = str(
        uuid.uuid4()
    )

    root = (
        Path(artifact_root)
        if artifact_root is not None
        else DEFAULT_ARTIFACT_ROOT
    )

    output_dir = (
        root
        / task.id
        / command_id
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=False,
    )
    try:
        os.chmod(
            output_dir,
            0o700,
        )
    except OSError:
        pass

    stdout_path = (
        output_dir
        / "stdout.txt"
    )

    stderr_path = (
        output_dir
        / "stderr.txt"
    )

    started = time.monotonic()
    deadline = (
        started
        + timeout
    )

    timed_out = False
    output_limited = False
    exit_code: int | None = None

    with (
        stdout_path.open(
            "wb"
        ) as stdout_handle,
        stderr_path.open(
            "wb"
        ) as stderr_handle,
    ):
        try:
            os.chmod(
                stdout_path,
                0o600,
            )
            os.chmod(
                stderr_path,
                0o600,
            )
        except OSError:
            pass
        try:
            process = subprocess.Popen(
                executed_command,
                cwd=str(
                    resolved_cwd
                ),
                env=child_environment,
                stdin=subprocess.DEVNULL,
                stdout=stdout_handle,
                stderr=stderr_handle,
                shell=False,
                start_new_session=True,
            )
        except OSError as exc:
            raise CommandExecutionError(
                "Unable to start command "
                f"{command[0]!r}: {exc}"
            ) from exc

        while True:
            exit_code = process.poll()

            if exit_code is not None:
                break

            now = time.monotonic()

            if now >= deadline:
                timed_out = True
                _terminate_process_group(
                    process
                )
                exit_code = (
                    process.returncode
                )
                break

            stdout_size = (
                stdout_path.stat()
                .st_size
            )

            stderr_size = (
                stderr_path.stat()
                .st_size
            )

            if (
                stdout_size
                > max_output_bytes
                or stderr_size
                > max_output_bytes
            ):
                output_limited = True

                _terminate_process_group(
                    process
                )

                exit_code = (
                    process.returncode
                )

                break

            time.sleep(
                0.05
            )

    _truncate(
        stdout_path,
        max_output_bytes,
    )

    _truncate(
        stderr_path,
        max_output_bytes,
    )

    elapsed = (
        time.monotonic()
        - started
    )

    stdout_artifact = _artifact(
        stdout_path,
        "command_stdout",
    )

    stderr_artifact = _artifact(
        stderr_path,
        "command_stderr",
    )

    stdout = stdout_path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    stderr = stderr_path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    with transaction(
        connection
    ):
        _store_artifact(
            connection,
            task_id=task.id,
            run_id=run_id,
            step_id=step_id,
            artifact=stdout_artifact,
            command_id=command_id,
            argv=command,
            sandboxed=sandbox,
        )

        _store_artifact(
            connection,
            task_id=task.id,
            run_id=run_id,
            step_id=step_id,
            artifact=stderr_artifact,
            command_id=command_id,
            argv=command,
            sandboxed=sandbox,
        )

    return CommandResult(
        argv=command,
        cwd=resolved_cwd,
        exit_code=exit_code,
        timed_out=timed_out,
        output_limited=(
            output_limited
        ),
        elapsed_seconds=round(
            elapsed,
            6,
        ),
        stdout=stdout,
        stderr=stderr,
        stdout_artifact=(
            stdout_artifact
        ),
        stderr_artifact=(
            stderr_artifact
        ),
        sandboxed=sandbox,
    )
