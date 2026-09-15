#!/usr/bin/env python3
"""Benchmark local Ollama models for the V3 development engine."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from reverend.config import ollama_host


DEFAULT_CONTEXTS = [8192, 16384, 32768]

PROMPTS = {
    "instruction": (
        "Return exactly this JSON object and no markdown: "
        '{"status":"ok","value":42}'
    ),
    "coding": """
Write only the body of this Python function.

def deduplicate_preserving_order(items):
    \"\"\"Return items with duplicates removed while preserving first occurrence.\"\"\"

Requirements:
- O(n) expected time.
- Do not sort.
- Do not import anything.
- Return a list.
""".strip(),
    "reasoning": """
A program processes n records. For each record it performs an O(log n)
balanced-tree lookup and then, once after all records, sorts n results.

State the final asymptotic time complexity and explain it in at most
three sentences.
""".strip(),
}


def api(
    base: str,
    path: str,
    payload: dict | None = None,
    *,
    timeout: int = 1800,
) -> dict:
    body = (
        None
        if payload is None
        else json.dumps(payload).encode("utf-8")
    )

    request = urllib.request.Request(
        base.rstrip("/") + path,
        data=body,
        headers={"Content-Type": "application/json"},
    )

    with urllib.request.urlopen(
        request,
        timeout=timeout,
    ) as response:
        return json.load(response)


def windows_memory() -> dict[str, Any]:
    script = r"""
$os = Get-CimInstance Win32_OperatingSystem
[pscustomobject]@{
    total_kib = [int64]$os.TotalVisibleMemorySize
    free_kib = [int64]$os.FreePhysicalMemory
} | ConvertTo-Json -Compress
"""

    try:
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                script,
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )

        data = json.loads(result.stdout.strip())

        return {
            "total_ram_gib": round(
                data["total_kib"] / 1024 / 1024,
                2,
            ),
            "free_ram_gib": round(
                data["free_kib"] / 1024 / 1024,
                2,
            ),
        }

    except Exception as exc:
        return {"error": str(exc)}


def gpu_memory() -> dict[str, Any]:
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu="
                "name,memory.total,memory.used,memory.free,"
                "utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )

        fields = [
            item.strip()
            for item in result.stdout.strip().split(",")
        ]

        return {
            "gpu": fields[0],
            "vram_total_mib": int(fields[1]),
            "vram_used_mib": int(fields[2]),
            "vram_free_mib": int(fields[3]),
            "gpu_util_percent": int(fields[4]),
        }

    except Exception as exc:
        return {"error": str(exc)}


def loaded_model(
    base: str,
    model: str,
) -> dict[str, Any]:
    try:
        response = api(base, "/api/ps")

        for item in response.get("models", []):
            names = {
                item.get("name"),
                item.get("model"),
            }

            if model in names:
                return {
                    "size_bytes": item.get("size"),
                    "size_vram_bytes": item.get(
                        "size_vram"
                    ),
                    "context_length": item.get(
                        "context_length"
                    ),
                    "expires_at": item.get(
                        "expires_at"
                    ),
                }

        return {}

    except Exception as exc:
        return {"error": str(exc)}


def throughput(
    count: int | None,
    duration_ns: int | None,
) -> float | None:
    if not count or not duration_ns:
        return None

    return round(
        count / (duration_ns / 1_000_000_000),
        2,
    )


def run_case(
    base: str,
    *,
    model: str,
    context: int,
    name: str,
    prompt: str,
    keep_alive: str,
) -> dict[str, Any]:
    before_ram = windows_memory()
    before_gpu = gpu_memory()

    started = time.monotonic()

    response = api(
        base,
        "/api/generate",
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": keep_alive,
            "think": False,
            "options": {
                "num_ctx": context,
                "num_predict": 384,
                "temperature": 0,
            },
        },
    )

    elapsed = time.monotonic() - started

    after_ram = windows_memory()
    after_gpu = gpu_memory()
    loaded = loaded_model(base, model)

    return {
        "case": name,
        "context": context,
        "success": True,
        "elapsed_seconds": round(elapsed, 3),
        "load_seconds": round(
            response.get("load_duration", 0)
            / 1_000_000_000,
            3,
        ),
        "prompt_tokens": response.get(
            "prompt_eval_count"
        ),
        "prompt_tokens_per_second": throughput(
            response.get("prompt_eval_count"),
            response.get("prompt_eval_duration"),
        ),
        "generated_tokens": response.get(
            "eval_count"
        ),
        "generation_tokens_per_second": throughput(
            response.get("eval_count"),
            response.get("eval_duration"),
        ),
        "done_reason": response.get("done_reason"),
        "response": response.get(
            "response",
            "",
        ).strip(),
        "thinking": response.get(
            "thinking",
            "",
        ).strip(),
        "loaded_model": loaded,
        "ram_before": before_ram,
        "ram_after": after_ram,
        "gpu_before": before_gpu,
        "gpu_after": after_gpu,
    }


def unload(base: str, model: str) -> None:
    try:
        api(
            base,
            "/api/generate",
            {
                "model": model,
                "prompt": "",
                "keep_alive": 0,
            },
            timeout=120,
        )
    except Exception:
        pass


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument("model")

    parser.add_argument(
        "--contexts",
        nargs="+",
        type=int,
        default=DEFAULT_CONTEXTS,
    )

    parser.add_argument(
        "--output",
        type=Path,
    )

    parser.add_argument(
        "--keep-alive",
        default="10m",
    )

    parser.add_argument(
        "--cold-each-context",
        action="store_true",
    )

    args = parser.parse_args()

    base = ollama_host()

    report = {
        "model": args.model,
        "ollama_host": base,
        "created_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "contexts": args.contexts,
        "system": {
            "ram": windows_memory(),
            "gpu": gpu_memory(),
        },
        "runs": [],
    }

    print(
        f"MODEL={args.model}",
        flush=True,
    )

    print(
        f"OLLAMA={base}",
        flush=True,
    )

    for context in args.contexts:
        if args.cold_each_context:
            unload(base, args.model)

        for name, prompt in PROMPTS.items():
            print(
                f"\n[{args.model}] "
                f"context={context} "
                f"case={name}",
                flush=True,
            )

            try:
                result = run_case(
                    base,
                    model=args.model,
                    context=context,
                    name=name,
                    prompt=prompt,
                    keep_alive=args.keep_alive,
                )

            except Exception as exc:
                result = {
                    "case": name,
                    "context": context,
                    "success": False,
                    "error": repr(exc),
                }

            report["runs"].append(result)

            summary = {
                key: result.get(key)
                for key in (
                    "case",
                    "context",
                    "success",
                    "elapsed_seconds",
                    "load_seconds",
                    "prompt_tokens_per_second",
                    "generation_tokens_per_second",
                    "generated_tokens",
                    "error",
                )
                if key in result
            }

            print(
                json.dumps(
                    summary,
                    indent=2,
                ),
                flush=True,
            )

            if not result["success"]:
                break

        if (
            report["runs"]
            and not report["runs"][-1]["success"]
        ):
            break

    if args.output:
        args.output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        args.output.write_text(
            json.dumps(
                report,
                indent=2,
            ),
            encoding="utf-8",
        )

        print(
            f"\nRESULT={args.output}",
            flush=True,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
