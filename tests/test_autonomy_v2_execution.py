from __future__ import annotations

import sys
from pathlib import Path

import pytest

from reverend.autonomy_v2.execution import (
    AgentInvocation,
    ModelProtocolError,
    OpenCodeRunner,
    parse_marker_json,
    validate_plan_payload,
    validate_review_payload,
)


class _CommandRunner(OpenCodeRunner):
    def __init__(self, command, *, stall_timeout=900):
        super().__init__(
            auto_approve=False,
            default_stall_timeout_seconds=stall_timeout,
        )
        self._command = tuple(command)

    def build_command(self, invocation):
        return self._command


def _invocation(tmp_path: Path, timeout: float = 2.0) -> AgentInvocation:
    return AgentInvocation(
        kind="test",
        agent="ignored",
        model="ignored",
        prompt="ignored",
        worktree=tmp_path,
        timeout_seconds=timeout,
        log_path=tmp_path / "agent.log",
    )


def test_runner_captures_output_without_shell(tmp_path):
    runner = _CommandRunner([sys.executable, "-c", "print('hello')"])
    result = runner.run(_invocation(tmp_path))
    assert result.succeeded is True
    assert result.timed_out is False
    assert result.stalled is False
    assert "hello" in result.output


def test_runner_terminates_timed_out_process_group(tmp_path):
    runner = _CommandRunner(
        [sys.executable, "-c", "import time; print('start', flush=True); time.sleep(10)"]
    )
    result = runner.run(_invocation(tmp_path, timeout=0.2))
    assert result.succeeded is False
    assert result.timed_out is True
    assert "start" in result.output


def test_runner_terminates_stalled_process_group(tmp_path):
    runner = _CommandRunner(
        [sys.executable, "-u", "-c", "import time; print('start', flush=True); time.sleep(10)"],
        stall_timeout=0.2,
    )
    result = runner.run(_invocation(tmp_path, timeout=5))
    assert result.succeeded is False
    assert result.timed_out is False
    assert result.stalled is True
    assert "start" in result.output


def test_activity_prevents_false_stall(tmp_path):
    runner = _CommandRunner(
        [
            sys.executable,
            "-u",
            "-c",
            "import time; [(print(i, flush=True), time.sleep(.08)) for i in range(5)]",
        ],
        stall_timeout=0.15,
    )
    result = runner.run(_invocation(tmp_path, timeout=3))
    assert result.succeeded is True
    assert result.stalled is False


def test_plan_protocol_is_strict():
    output = """
noise
AUTONOMY_PLAN_JSON_BEGIN
{"files_to_modify":["src/a.py"],"files_to_create":[],"tests_to_add_or_modify":["tests/test_a.py"],"acceptance_checks":["pytest"],"risks":[]}
AUTONOMY_PLAN_JSON_END
"""
    payload = parse_marker_json(
        output, "AUTONOMY_PLAN_JSON_BEGIN", "AUTONOMY_PLAN_JSON_END"
    )
    plan = validate_plan_payload(payload)
    assert plan["files_to_modify"] == ["src/a.py"]

    with pytest.raises(ModelProtocolError):
        validate_plan_payload({"files_to_modify": []})


def test_review_protocol_rejects_inconsistent_verdicts():
    verdict, defects = validate_review_payload({"verdict": "PASS", "defects": []})
    assert verdict == "PASS"
    assert defects == []

    with pytest.raises(ModelProtocolError):
        validate_review_payload({"verdict": "PASS", "defects": [{"message": "bug"}]})
    with pytest.raises(ModelProtocolError):
        validate_review_payload({"verdict": "FAIL", "defects": []})
