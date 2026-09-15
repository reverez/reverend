from __future__ import annotations

import subprocess

from reverend.runtime.hardware import measure_hardware


def test_measure_hardware_parses_nvidia_smi():
    def runner(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout=(
                "0, NVIDIA GeForce RTX 5070 Laptop GPU, "
                "8151, 6504, 1647, 12\n"
            ),
            stderr="",
        )

    snapshot = measure_hardware(
        clock=lambda: 123.0,
        gpu_runner=runner,
    )

    assert snapshot.captured_at == 123.0
    assert snapshot.cpu_logical_cores >= 1
    assert snapshot.ram_total_bytes >= snapshot.ram_available_bytes
    assert len(snapshot.gpus) == 1
    gpu = snapshot.gpus[0]
    assert gpu.name == "NVIDIA GeForce RTX 5070 Laptop GPU"
    assert gpu.memory_total_bytes == 8151 * 1024 * 1024
    assert gpu.memory_used_bytes == 6504 * 1024 * 1024
    assert gpu.memory_free_bytes == 1647 * 1024 * 1024
    assert gpu.utilization_percent == 12.0


def test_measure_hardware_treats_missing_nvidia_smi_as_cpu_only():
    def runner(*args, **kwargs):
        raise FileNotFoundError("nvidia-smi")

    snapshot = measure_hardware(gpu_runner=runner)

    assert snapshot.gpus == ()
