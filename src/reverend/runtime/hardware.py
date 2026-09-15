"""Portable local hardware measurements for the vNext compute runtime."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import time
from collections.abc import Callable


@dataclass(frozen=True)
class GpuSnapshot:
    """One locally visible GPU at a point in time."""

    index: int
    name: str
    memory_total_bytes: int
    memory_used_bytes: int
    memory_free_bytes: int
    utilization_percent: float | None = None


@dataclass(frozen=True)
class HardwareSnapshot:
    """Measured local capacity without claiming ownership of it."""

    captured_at: float
    cpu_logical_cores: int
    ram_total_bytes: int
    ram_available_bytes: int
    gpus: tuple[GpuSnapshot, ...] = ()


_MIB = 1024 * 1024


def _linux_meminfo(path: Path = Path("/proc/meminfo")) -> tuple[int, int] | None:
    try:
        values: dict[str, int] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if ":" not in line:
                continue
            key, raw = line.split(":", 1)
            fields = raw.strip().split()
            if not fields:
                continue
            value = int(fields[0])
            unit = fields[1].lower() if len(fields) > 1 else ""
            if unit == "kb":
                value *= 1024
            values[key] = value

        total = values.get("MemTotal")
        available = values.get("MemAvailable", values.get("MemFree"))
        if total is None or available is None:
            return None
        return total, available
    except (OSError, ValueError):
        return None


def _portable_ram() -> tuple[int, int]:
    measured = _linux_meminfo()
    if measured is not None:
        return measured

    try:
        page_size = int(os.sysconf("SC_PAGE_SIZE"))
        total_pages = int(os.sysconf("SC_PHYS_PAGES"))
        available_pages = int(os.sysconf("SC_AVPHYS_PAGES"))
        return (
            page_size * total_pages,
            page_size * available_pages,
        )
    except (AttributeError, OSError, ValueError):
        return (0, 0)


def _nvidia_gpus(
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[GpuSnapshot, ...]:
    """Measure NVIDIA GPU memory when nvidia-smi is locally available."""

    command = [
        "nvidia-smi",
        "--query-gpu=index,name,memory.total,memory.used,memory.free,utilization.gpu",
        "--format=csv,noheader,nounits",
    ]

    try:
        completed = runner(
            command,
            text=True,
            capture_output=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ()

    if completed.returncode != 0:
        return ()

    result: list[GpuSnapshot] = []
    for line in completed.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 6:
            continue
        try:
            index = int(parts[0])
            total = int(float(parts[2])) * _MIB
            used = int(float(parts[3])) * _MIB
            free = int(float(parts[4])) * _MIB
            utilization = float(parts[5])
        except ValueError:
            continue

        result.append(
            GpuSnapshot(
                index=index,
                name=parts[1],
                memory_total_bytes=total,
                memory_used_bytes=used,
                memory_free_bytes=free,
                utilization_percent=utilization,
            )
        )

    return tuple(result)


def measure_hardware(
    *,
    clock: Callable[[], float] = time.time,
    gpu_runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> HardwareSnapshot:
    """Return a best-effort measured local hardware snapshot.

    Missing nvidia-smi is not an error: CPU-only environments simply expose no GPU.
    """

    ram_total, ram_available = _portable_ram()
    return HardwareSnapshot(
        captured_at=clock(),
        cpu_logical_cores=max(1, int(os.cpu_count() or 1)),
        ram_total_bytes=max(0, ram_total),
        ram_available_bytes=max(0, ram_available),
        gpus=_nvidia_gpus(runner=gpu_runner),
    )
