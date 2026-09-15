from __future__ import annotations

from pathlib import Path

import pytest

from reverend.development.sandbox import (
    DevelopmentSandboxError,
    SandboxLimits,
    development_sandbox_argv,
)


SYSTEM_TOOL = "/usr/bin/true"


def test_sandbox_is_network_and_home_isolated(
    tmp_path,
):
    worktree = tmp_path / "worktree"
    worktree.mkdir()

    argv = development_sandbox_argv(
        worktree,
        ("python3", "-c", "print('ok')"),
        timeout_seconds=30,
        bwrap_path=SYSTEM_TOOL,
        prlimit_path=SYSTEM_TOOL,
    )

    assert "--unshare-all" in argv
    assert "--share-net" not in argv
    assert "--clearenv" in argv
    assert "--tmpfs" in argv
    assert "/tmp" in argv
    assert "--bind" in argv
    bind_index = argv.index("--bind")
    assert argv[bind_index + 1] == str(
        worktree.resolve()
    )
    assert argv[bind_index + 2] == "/workspace"

    # /home is created inside the sandbox; the host home is never bind-mounted.
    pairs = tuple(
        zip(
            argv,
            argv[1:],
        )
    )
    assert (
        "--ro-bind",
        str(Path.home()),
    ) not in pairs
    assert str(Path.home()) not in argv

    assert "--setenv" in argv
    assert "REVEREND_SANDBOX" in argv
    assert "untrusted" in argv


def test_sandbox_applies_resource_limits(
    tmp_path,
):
    worktree = tmp_path / "worktree"
    worktree.mkdir()

    limits = SandboxLimits(
        max_memory_bytes=512 * 1024 * 1024,
        max_processes=16,
        max_open_files=64,
        max_cpu_seconds=20,
    )

    argv = development_sandbox_argv(
        worktree,
        ("python3", "-c", "print('ok')"),
        timeout_seconds=7,
        limits=limits,
        bwrap_path=SYSTEM_TOOL,
        prlimit_path=SYSTEM_TOOL,
    )

    assert "--as=536870912" in argv
    assert "--cpu=12" in argv
    assert "--nproc=16" in argv
    assert "--nofile=64" in argv
    assert "--core=0" in argv


def test_absolute_worktree_executable_is_mapped_inside_sandbox(
    tmp_path,
):
    worktree = tmp_path / "worktree"
    executable = worktree / "tools" / "check"
    executable.parent.mkdir(
        parents=True,
    )
    executable.write_text(
        "#!/bin/sh\nexit 0\n",
        encoding="utf-8",
    )

    argv = development_sandbox_argv(
        worktree,
        (str(executable), "--verify"),
        timeout_seconds=30,
        bwrap_path=SYSTEM_TOOL,
        prlimit_path=SYSTEM_TOOL,
    )

    assert "/workspace/tools/check" in argv
    assert str(executable.resolve()) not in argv[
        argv.index("--") + 1:
    ]


def test_absolute_host_executable_outside_runtime_is_rejected(
    tmp_path,
):
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    host_tool = tmp_path / "host-tool"
    host_tool.write_text(
        "unsafe",
        encoding="utf-8",
    )

    with pytest.raises(
        DevelopmentSandboxError,
        match="absolute host path",
    ):
        development_sandbox_argv(
            worktree,
            (str(host_tool),),
            timeout_seconds=30,
            bwrap_path=SYSTEM_TOOL,
            prlimit_path=SYSTEM_TOOL,
        )


def test_symlink_worktree_root_is_rejected(
    tmp_path,
):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(
        real,
        target_is_directory=True,
    )

    with pytest.raises(
        DevelopmentSandboxError,
        match="symlink",
    ):
        development_sandbox_argv(
            link,
            ("python3",),
            timeout_seconds=30,
            bwrap_path=SYSTEM_TOOL,
            prlimit_path=SYSTEM_TOOL,
        )


@pytest.mark.parametrize(
    "limits",
    [
        {
            "max_memory_bytes": 17
            * 1024
            * 1024
            * 1024,
        },
        {
            "max_processes": 513,
        },
        {
            "max_open_files": 4097,
        },
        {
            "max_cpu_seconds": 3601,
        },
    ],
)
def test_sandbox_architectural_limits_are_bounded(
    limits,
):
    with pytest.raises(ValueError):
        SandboxLimits(
            **limits
        )
