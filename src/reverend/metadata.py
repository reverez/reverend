"""Bulk metadata for Windows-owned sources; callers retain membership authority."""
from __future__ import annotations

import base64
import re
import shutil
import subprocess
from pathlib import Path

WINDOWS_EPOCH_TICKS = 621355968000000000


def windows_path(root: Path) -> str | None:
    match = re.fullmatch(r"/mnt/([a-zA-Z])(?:/(.*))?", str(root))
    if not match:
        return None
    return match[1].upper() + ":\\" + (match[2] or "").replace("/", "\\")


def parse_manifest(output: bytes, root: Path) -> dict[str, tuple[int, int]]:
    prefix = windows_path(root).rstrip("\\") + "\\"
    result = {}
    for line in output.decode("utf-8-sig").splitlines():
        name, size, ticks = line.rsplit("\t", 2)
        # Preserve Unicode and case exactly. No case-folding or lossy encoding:
        # unmatched names take the safe stat fallback.
        name = name.replace("/", "\\")
        if not name.startswith(prefix):
            continue
        relative = name[len(prefix):].split("\\")
        if any(part in ("", ".", "..") for part in relative):
            continue
        result[str(root.joinpath(*relative))] = (
            int(size), (int(ticks) - WINDOWS_EPOCH_TICKS) * 100,
        )
    return result


def bulk_metadata(root: Path) -> tuple[dict, str, str | None]:
    winroot = windows_path(root)
    if winroot is None:
        return {}, "stat", None
    executable = shutil.which("powershell.exe")
    if executable is None:
        return {}, "stat", "PowerShell unavailable"
    literal = winroot.replace("'", "''")
    script = (
        "$ErrorActionPreference='Stop'; "
        "[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false); "
        f"Get-ChildItem -LiteralPath '{literal}' -Recurse -File -Force | "
        'ForEach-Object { [Console]::WriteLine(("{0}`t{1}`t{2}" '
        "-f $_.FullName,$_.Length,$_.LastWriteTimeUtc.Ticks)) }"
    )
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    try:
        process = subprocess.run(
            [executable, "-NoLogo", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
            capture_output=True, timeout=30, check=True,
        )
        return parse_manifest(process.stdout, root), "powershell", None
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        # Do not log the command or PowerShell stderr (may contain source names).
        return {}, "stat", f"PowerShell metadata failed: {type(exc).__name__}"
