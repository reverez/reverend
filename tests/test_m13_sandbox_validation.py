from __future__ import annotations

from reverend.benchmarks.m13_sandbox_validation import (
    PROBE_LIMITS,
    _evaluate,
)


def good_payload():
    return {
        "cwd": "/workspace",
        "home": "/home/reverend",
        "tmpdir": "/tmp",
        "sandbox_marker": "untrusted",
        "host_home_visible": False,
        "interfaces": ["lo"],
        "ssh_auth_sock": None,
        "aws_profile": None,
        "pythonpath": None,
        "system_write_blocked": True,
        "workspace_write": "sandbox-write-ok",
        "rlimit_as": [
            PROBE_LIMITS.max_memory_bytes,
            PROBE_LIMITS.max_memory_bytes,
        ],
        "rlimit_nproc": [
            PROBE_LIMITS.max_processes,
            PROBE_LIMITS.max_processes,
        ],
        "rlimit_nofile": [
            PROBE_LIMITS.max_open_files,
            PROBE_LIMITS.max_open_files,
        ],
        "rlimit_core": [0, 0],
    }


def test_m13_live_sandbox_evaluator_accepts_required_boundary():
    result = _evaluate(
        good_payload(),
        host_probe_exists=True,
    )

    assert result["passed"] is True
    assert all(
        result["assertions"].values()
    )


def test_m13_live_sandbox_evaluator_rejects_network_or_home_escape():
    payload = good_payload()
    payload["interfaces"] = [
        "eth0",
        "lo",
    ]
    payload[
        "host_home_visible"
    ] = True

    result = _evaluate(
        payload,
        host_probe_exists=True,
    )

    assert result["passed"] is False
    assert (
        result["assertions"][
            "network_namespace_isolated"
        ]
        is False
    )
    assert (
        result["assertions"][
            "host_home_hidden"
        ]
        is False
    )


def test_m13_live_sandbox_evaluator_rejects_missing_resource_limits():
    payload = good_payload()
    payload["rlimit_as"] = [
        -1,
        -1,
    ]

    result = _evaluate(
        payload,
        host_probe_exists=True,
    )

    assert result["passed"] is False
    assert (
        result["assertions"][
            "memory_limit_applied"
        ]
        is False
    )
