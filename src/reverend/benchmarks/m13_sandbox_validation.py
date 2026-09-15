"""Live OS-sandbox validation for M13 execution security."""

from __future__ import annotations

import argparse
import json
import resource
import subprocess
import tempfile
from pathlib import Path

from reverend.development.sandbox import (
    SandboxLimits,
    development_sandbox_argv,
)


PROBE_LIMITS = SandboxLimits(
    max_memory_bytes=1024 * 1024 * 1024,
    max_processes=32,
    max_open_files=128,
    max_cpu_seconds=30,
)


_PROBE = r"""
import json
import os
import resource
import socket
import sys
from pathlib import Path

host_home = Path(sys.argv[1])
workspace_probe = Path("/workspace/m13-sandbox-write.txt")
workspace_probe.write_text("sandbox-write-ok\n", encoding="utf-8")

system_write_blocked = False
try:
    Path("/usr/reverend-m13-write-probe").write_text(
        "unsafe",
        encoding="utf-8",
    )
except OSError:
    system_write_blocked = True

payload = {
    "cwd": os.getcwd(),
    "home": os.environ.get("HOME"),
    "tmpdir": os.environ.get("TMPDIR"),
    "sandbox_marker": os.environ.get("REVEREND_SANDBOX"),
    "host_home_visible": host_home.exists(),
    "interfaces": sorted(name for _, name in socket.if_nameindex()),
    "ssh_auth_sock": os.environ.get("SSH_AUTH_SOCK"),
    "aws_profile": os.environ.get("AWS_PROFILE"),
    "pythonpath": os.environ.get("PYTHONPATH"),
    "system_write_blocked": system_write_blocked,
    "workspace_write": workspace_probe.read_text(encoding="utf-8").strip(),
    "rlimit_as": list(resource.getrlimit(resource.RLIMIT_AS)),
    "rlimit_nproc": list(resource.getrlimit(resource.RLIMIT_NPROC)),
    "rlimit_nofile": list(resource.getrlimit(resource.RLIMIT_NOFILE)),
    "rlimit_core": list(resource.getrlimit(resource.RLIMIT_CORE)),
}
print(json.dumps(payload, sort_keys=True))
"""


def _evaluate(
    payload: dict,
    *,
    host_probe_exists: bool,
) -> dict:
    assertions = {
        "cwd_is_workspace": (
            payload.get("cwd")
            == "/workspace"
        ),
        "sandbox_home_is_private": (
            payload.get("home")
            == "/home/reverend"
        ),
        "tmp_is_private": (
            payload.get("tmpdir")
            == "/tmp"
        ),
        "sandbox_marker_present": (
            payload.get("sandbox_marker")
            == "untrusted"
        ),
        "host_home_hidden": (
            payload.get("host_home_visible")
            is False
        ),
        "network_namespace_isolated": (
            set(
                payload.get(
                    "interfaces",
                    [],
                )
            )
            <= {"lo"}
        ),
        "credential_handles_absent": all(
            payload.get(name)
            is None
            for name in (
                "ssh_auth_sock",
                "aws_profile",
                "pythonpath",
            )
        ),
        "system_runtime_read_only": (
            payload.get(
                "system_write_blocked"
            )
            is True
        ),
        "workspace_is_writable": (
            payload.get(
                "workspace_write"
            )
            == "sandbox-write-ok"
            and host_probe_exists
        ),
        "memory_limit_applied": (
            payload.get("rlimit_as", [None])[0]
            == PROBE_LIMITS.max_memory_bytes
        ),
        "process_limit_applied": (
            payload.get("rlimit_nproc", [None])[0]
            == PROBE_LIMITS.max_processes
        ),
        "fd_limit_applied": (
            payload.get("rlimit_nofile", [None])[0]
            == PROBE_LIMITS.max_open_files
        ),
        "core_dumps_disabled": (
            payload.get("rlimit_core", [None])[0]
            == 0
        ),
    }

    return {
        "assertions": assertions,
        "passed": all(
            assertions.values()
        ),
    }


def run_live_probe() -> dict:
    with tempfile.TemporaryDirectory(
        prefix="reverend-m13-sandbox-"
    ) as temporary:
        worktree = Path(
            temporary
        ) / "worktree"
        worktree.mkdir()

        argv = development_sandbox_argv(
            worktree,
            (
                "python3",
                "-c",
                _PROBE,
                str(Path.home()),
            ),
            timeout_seconds=20,
            limits=PROBE_LIMITS,
        )

        completed = subprocess.run(
            argv,
            cwd=str(worktree),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=25,
            check=False,
            env={},
        )

        result = {
            "returncode": (
                completed.returncode
            ),
            "stderr": (
                completed.stderr[-4000:]
            ),
            "sandbox_argv_head": list(
                argv[:12]
            ),
        }

        if completed.returncode != 0:
            result.update(
                passed=False,
                error=(
                    "Sandbox probe process failed."
                ),
            )
            return result

        try:
            payload = json.loads(
                completed.stdout.strip()
            )
        except json.JSONDecodeError:
            result.update(
                passed=False,
                error=(
                    "Sandbox probe did not return JSON."
                ),
                stdout=(
                    completed.stdout[-4000:]
                ),
            )
            return result

        evaluation = _evaluate(
            payload,
            host_probe_exists=(
                worktree
                .joinpath(
                    "m13-sandbox-write.txt"
                )
                .is_file()
            ),
        )

        result.update(
            payload=payload,
            **evaluation,
        )

        return result


def main(
    argv: list[str] | None = None,
) -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args(argv)

    try:
        result = run_live_probe()
    except Exception as exc:
        result = {
            "passed": False,
            "error": (
                f"{type(exc).__name__}: "
                f"{exc}"
            ),
        }

    print(
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
        )
    )

    return (
        0
        if result.get("passed")
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
