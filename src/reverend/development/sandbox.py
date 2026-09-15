"""Fail-closed OS sandbox construction for untrusted development execution."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


class DevelopmentSandboxError(RuntimeError):
    """Raised when Reverend cannot establish the required OS sandbox."""


@dataclass(frozen=True)
class SandboxLimits:
    max_memory_bytes: int = 4 * 1024 * 1024 * 1024
    max_processes: int = 128
    max_open_files: int = 512
    max_cpu_seconds: int = 900

    def __post_init__(self) -> None:
        values = (
            self.max_memory_bytes,
            self.max_processes,
            self.max_open_files,
            self.max_cpu_seconds,
        )
        if any(
            not isinstance(value, int)
            or isinstance(value, bool)
            or value < 1
            for value in values
        ):
            raise ValueError(
                "Sandbox resource limits must be positive integers."
            )

        if self.max_memory_bytes > 16 * 1024 * 1024 * 1024:
            raise ValueError(
                "Sandbox memory limit exceeds the architectural maximum."
            )
        if self.max_processes > 512:
            raise ValueError(
                "Sandbox process limit exceeds the architectural maximum."
            )
        if self.max_open_files > 4096:
            raise ValueError(
                "Sandbox file-descriptor limit exceeds the architectural maximum."
            )
        if self.max_cpu_seconds > 3600:
            raise ValueError(
                "Sandbox CPU limit exceeds the architectural maximum."
            )


def _tool(
    name: str,
    explicit: str | None,
) -> Path:
    value = explicit or shutil.which(name)

    if not value:
        raise DevelopmentSandboxError(
            f"Untrusted execution requires {name}; no unsafe fallback is available."
        )

    path = Path(value).resolve()

    if not path.is_file():
        raise DevelopmentSandboxError(
            f"Required sandbox tool is unavailable: {path}"
        )

    allowed = (
        Path("/usr/bin"),
        Path("/bin"),
    )

    if not any(
        path.is_relative_to(root)
        for root in allowed
    ):
        raise DevelopmentSandboxError(
            f"Sandbox tool must be system-owned: {path}"
        )

    return path


def _mapped_executable(
    executable: str,
    worktree: Path,
) -> str:
    path = Path(executable)

    if not path.is_absolute():
        return executable

    resolved = path.resolve()

    if resolved.is_relative_to(worktree):
        relative = resolved.relative_to(worktree)
        return str(
            Path("/workspace")
            / relative
        )

    if (
        resolved.is_relative_to(Path("/usr"))
        or resolved.is_relative_to(Path("/bin"))
    ):
        return str(resolved)

    raise DevelopmentSandboxError(
        "Untrusted sandbox command cannot execute an absolute host path "
        f"outside the task worktree or system runtime: {resolved}"
    )


def development_sandbox_argv(
    worktree: str | Path,
    command: Sequence[str],
    *,
    timeout_seconds: float,
    cwd: str | Path | None = None,
    limits: SandboxLimits = SandboxLimits(),
    bwrap_path: str | None = None,
    prlimit_path: str | None = None,
) -> tuple[str, ...]:
    """Build one network-isolated bubblewrap command for a task worktree.

    This function only constructs the sandbox invocation. Callers remain
    responsible for task trust/state checks, output capture and wall-clock
    termination.
    """

    requested_root = Path(worktree)

    if requested_root.is_symlink():
        raise DevelopmentSandboxError(
            "Sandbox worktree root cannot be a symlink."
        )

    root = requested_root.resolve()

    if not root.is_dir():
        raise DevelopmentSandboxError(
            "Sandbox worktree must be an existing regular directory."
        )

    if (
        not isinstance(timeout_seconds, (int, float))
        or isinstance(timeout_seconds, bool)
        or timeout_seconds <= 0
    ):
        raise DevelopmentSandboxError(
            "Sandbox timeout must be positive."
        )

    argv = tuple(
        str(value)
        for value in command
    )

    if (
        not argv
        or any(
            not value
            or "\x00" in value
            for value in argv
        )
    ):
        raise DevelopmentSandboxError(
            "Sandbox command argv is invalid."
        )

    if cwd is None:
        sandbox_cwd = Path("/workspace")
    else:
        requested_cwd = Path(cwd)
        if not requested_cwd.is_absolute():
            requested_cwd = root / requested_cwd
        resolved_cwd = requested_cwd.resolve()
        if not resolved_cwd.is_relative_to(root):
            raise DevelopmentSandboxError(
                "Sandbox cwd escaped the task worktree."
            )
        if not resolved_cwd.is_dir():
            raise DevelopmentSandboxError(
                "Sandbox cwd must be an existing directory."
            )
        sandbox_cwd = (
            Path("/workspace")
            / resolved_cwd.relative_to(root)
        )

    bwrap = _tool(
        "bwrap",
        bwrap_path,
    )
    prlimit = _tool(
        "prlimit",
        prlimit_path,
    )

    cpu_seconds = max(
        1,
        min(
            limits.max_cpu_seconds,
            int(timeout_seconds) + 5,
        ),
    )

    sandbox = [
        str(bwrap),
        "--unshare-all",
        "--die-with-parent",
        "--new-session",
        "--clearenv",
        "--ro-bind",
        "/usr",
        "/usr",
    ]

    for source in (
        Path("/lib"),
        Path("/lib64"),
    ):
        if source.exists():
            sandbox.extend(
                [
                    "--ro-bind",
                    str(source),
                    str(source),
                ]
            )

    # A private filesystem view: no host /home, credentials, runtime sockets,
    # or network namespace are shared. Only the task worktree is writable.
    sandbox.extend(
        [
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--tmpfs",
            "/tmp",
            "--dir",
            "/home",
            "--dir",
            "/home/reverend",
            "--setenv",
            "HOME",
            "/home/reverend",
            "--setenv",
            "TMPDIR",
            "/tmp",
            "--setenv",
            "PATH",
            "/usr/bin:/bin",
            "--setenv",
            "LANG",
            "C.UTF-8",
            "--setenv",
            "REVEREND_SANDBOX",
            "untrusted",
            "--bind",
            str(root),
            "/workspace",
            "--chdir",
            str(sandbox_cwd),
            str(prlimit),
            f"--as={limits.max_memory_bytes}",
            f"--cpu={cpu_seconds}",
            f"--nproc={limits.max_processes}",
            f"--nofile={limits.max_open_files}",
            "--core=0",
            "--",
            _mapped_executable(
                argv[0],
                root,
            ),
            *argv[1:],
        ]
    )

    return tuple(sandbox)
