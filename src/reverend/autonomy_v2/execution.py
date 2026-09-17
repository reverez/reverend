from __future__ import annotations

import json
import os
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


class ModelProtocolError(RuntimeError):
    pass


@dataclass(frozen=True)
class AgentInvocation:
    kind: str
    agent: str
    model: str
    prompt: str
    worktree: Path
    timeout_seconds: float
    log_path: Path


@dataclass(frozen=True)
class AgentResult:
    command: tuple[str, ...]
    returncode: int | None
    timed_out: bool
    output: str
    log_path: Path

    @property
    def succeeded(self) -> bool:
        return not self.timed_out and self.returncode == 0


class OpenCodeRunner:
    """Run one bounded OpenCode session without giving it controller authority."""

    def __init__(
        self,
        *,
        executable: str = "opencode",
        auto_approve: bool = True,
        extra_env: Mapping[str, str] | None = None,
    ) -> None:
        self.executable = executable
        self.auto_approve = auto_approve
        self.extra_env = dict(extra_env or {})

    def build_command(self, invocation: AgentInvocation) -> tuple[str, ...]:
        command: list[str] = [
            self.executable,
            "run",
            "--agent",
            invocation.agent,
            "--model",
            invocation.model,
        ]
        if self.auto_approve:
            command.append("--auto")
        command.append(invocation.prompt)
        return tuple(command)

    def run(self, invocation: AgentInvocation) -> AgentResult:
        if invocation.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        worktree = invocation.worktree.resolve()
        if not worktree.is_dir():
            raise ValueError(f"worktree does not exist: {worktree}")
        invocation.log_path.parent.mkdir(parents=True, exist_ok=True)
        command = self.build_command(invocation)
        env = os.environ.copy()
        env.update(self.extra_env)

        returncode: int | None = None
        timed_out = False
        with invocation.log_path.open("w", encoding="utf-8") as log_handle:
            process = subprocess.Popen(
                command,
                cwd=worktree,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                text=True,
                start_new_session=(os.name == "posix"),
            )
            try:
                returncode = process.wait(timeout=invocation.timeout_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                self._terminate_process(process)
                returncode = process.returncode

        output = invocation.log_path.read_text(encoding="utf-8", errors="replace")
        return AgentResult(
            command=command,
            returncode=returncode,
            timed_out=timed_out,
            output=output,
            log_path=invocation.log_path,
        )

    @staticmethod
    def _terminate_process(process: subprocess.Popen[str]) -> None:
        if process.poll() is not None:
            return
        try:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGTERM)
            else:
                process.terminate()
            process.wait(timeout=5)
            return
        except (ProcessLookupError, subprocess.TimeoutExpired):
            pass

        if process.poll() is None:
            try:
                if os.name == "posix":
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
            except ProcessLookupError:
                pass
            process.wait(timeout=5)


def parse_marker_json(output: str, begin_marker: str, end_marker: str) -> dict[str, object]:
    """Parse the last complete marker-delimited JSON object from model output."""
    begin = output.rfind(begin_marker)
    if begin < 0:
        raise ModelProtocolError(f"missing marker: {begin_marker}")
    payload_start = begin + len(begin_marker)
    end = output.find(end_marker, payload_start)
    if end < 0:
        raise ModelProtocolError(f"missing marker: {end_marker}")
    raw = output[payload_start:end].strip()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ModelProtocolError(f"invalid JSON between markers: {exc}") from exc
    if not isinstance(value, dict):
        raise ModelProtocolError("marker payload must be a JSON object")
    return value


def validate_plan_payload(payload: Mapping[str, object]) -> dict[str, list[str]]:
    required = (
        "files_to_modify",
        "files_to_create",
        "tests_to_add_or_modify",
        "acceptance_checks",
        "risks",
    )
    normalized: dict[str, list[str]] = {}
    for key in required:
        value = payload.get(key)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ModelProtocolError(f"plan field {key!r} must be a list of strings")
        normalized[key] = [item.strip() for item in value if item.strip()]
    return normalized


def validate_review_payload(payload: Mapping[str, object]) -> tuple[str, list[dict[str, object]]]:
    verdict = payload.get("verdict")
    defects = payload.get("defects")
    if verdict not in {"PASS", "FAIL"}:
        raise ModelProtocolError("review verdict must be PASS or FAIL")
    if not isinstance(defects, list) or not all(isinstance(item, dict) for item in defects):
        raise ModelProtocolError("review defects must be a list of objects")
    if verdict == "PASS" and defects:
        raise ModelProtocolError("PASS review must not include defects")
    if verdict == "FAIL" and not defects:
        raise ModelProtocolError("FAIL review must include at least one defect")
    return verdict, list(defects)
