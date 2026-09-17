from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

_GIB = 1024**3


@dataclass(frozen=True)
class ResourceSnapshot:
    total_memory_bytes: int
    available_memory_bytes: int
    total_swap_bytes: int
    free_swap_bytes: int
    disk_free_bytes: int
    commands: dict[str, str | None]

    @property
    def total_memory_gib(self) -> float:
        return self.total_memory_bytes / _GIB

    @property
    def available_memory_gib(self) -> float:
        return self.available_memory_bytes / _GIB

    @property
    def disk_free_gib(self) -> float:
        return self.disk_free_bytes / _GIB


@dataclass(frozen=True)
class ResourcePolicy:
    min_total_memory_gib: float = 20.0
    min_disk_free_gib: float = 30.0
    required_commands: tuple[str, ...] = ("git", "opencode", "ollama")


@dataclass(frozen=True)
class ResourceCheck:
    snapshot: ResourceSnapshot
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.errors


def snapshot_resources(repository_root: str | Path) -> ResourceSnapshot:
    root = Path(repository_root).resolve()
    memory = _read_meminfo()
    disk = shutil.disk_usage(root)
    commands = {
        name: shutil.which(name)
        for name in ("git", "opencode", "ollama", "nvidia-smi")
    }
    return ResourceSnapshot(
        total_memory_bytes=memory.get("MemTotal", 0),
        available_memory_bytes=memory.get("MemAvailable", memory.get("MemFree", 0)),
        total_swap_bytes=memory.get("SwapTotal", 0),
        free_swap_bytes=memory.get("SwapFree", 0),
        disk_free_bytes=disk.free,
        commands=commands,
    )


def check_resources(
    repository_root: str | Path,
    *,
    policy: ResourcePolicy | None = None,
) -> ResourceCheck:
    policy = policy or ResourcePolicy()
    snapshot = snapshot_resources(repository_root)
    errors: list[str] = []
    warnings: list[str] = []

    if snapshot.total_memory_gib < policy.min_total_memory_gib:
        errors.append(
            f"WSL exposes only {snapshot.total_memory_gib:.1f} GiB RAM; "
            f"need at least {policy.min_total_memory_gib:.1f} GiB for the configured 30B workflow"
        )
    if snapshot.disk_free_gib < policy.min_disk_free_gib:
        errors.append(
            f"only {snapshot.disk_free_gib:.1f} GiB disk free; "
            f"need at least {policy.min_disk_free_gib:.1f} GiB"
        )
    for command in policy.required_commands:
        if not snapshot.commands.get(command):
            errors.append(f"required command is not available on PATH: {command}")
    if not snapshot.commands.get("nvidia-smi"):
        warnings.append("nvidia-smi is unavailable; GPU availability cannot be independently checked")
    if snapshot.total_swap_bytes == 0:
        warnings.append("WSL swap is disabled; model/runtime OOM recovery margin is reduced")

    return ResourceCheck(snapshot, tuple(errors), tuple(warnings))


def _read_meminfo() -> dict[str, int]:
    path = Path("/proc/meminfo")
    if not path.exists():
        return {}
    values: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, separator, rest = line.partition(":")
        if not separator:
            continue
        fields = rest.strip().split()
        if not fields:
            continue
        try:
            value = int(fields[0])
        except ValueError:
            continue
        multiplier = 1024 if len(fields) > 1 and fields[1].lower() == "kb" else 1
        values[key] = value * multiplier
    return values
