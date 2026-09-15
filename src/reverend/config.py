"""Environment-first runtime configuration for the local AI platform."""
from __future__ import annotations

import atexit
import json
import os
import socket
import struct
from functools import lru_cache
from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient


def _runtime_config_path() -> Path:
    explicit = (
        os.environ.get("REVEREND_RUNTIME_CONFIG")
        or os.environ.get("AI_RUNTIME_CONFIG")
    )

    if explicit:
        return Path(explicit)

    canonical = (
        Path.home()
        / ".config"
        / "reverend"
        / "runtime.json"
    )

    legacy = (
        Path.home()
        / ".config"
        / "local-ai"
        / "runtime.json"
    )

    if canonical.exists() or not legacy.exists():
        return canonical

    return legacy


RUNTIME_CONFIG = _runtime_config_path()


def read_runtime_config(
    path: Path | None = None,
) -> dict[str, Any]:
    config_path = path or RUNTIME_CONFIG

    if not config_path.exists():
        return {}

    try:
        value = json.loads(
            config_path.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Invalid runtime configuration: {config_path}"
        ) from exc

    if not isinstance(value, dict):
        raise RuntimeError(
            f"Runtime configuration must be a JSON object: "
            f"{config_path}"
        )

    return value


_RUNTIME = read_runtime_config()


def runtime_value(
    env_name: str,
    config_key: str,
    default: Any = None,
    *,
    config: dict[str, Any] | None = None,
) -> Any:
    explicit = os.environ.get(env_name)

    if explicit not in (None, ""):
        return explicit

    values = _RUNTIME if config is None else config
    return values.get(config_key, default)


def _data_root_has_state(root: Path) -> bool:
    """Return whether a candidate root contains authoritative Reverend state."""

    file_markers = (
        root / "platform.db",
        root / "workstation.db",
        root / "development.db",
        root / "engineering-memory.db",
        root / "public-sources.db",
        root / "ingestion" / "state.json",
    )

    return any(path.is_file() for path in file_markers)


def _default_data_root() -> Path:
    """Prefer the root that owns the authoritative knowledge registry."""

    canonical = (
        Path.home()
        / ".local"
        / "share"
        / "reverend"
    )
    legacy = (
        Path.home()
        / "reverend-data"
        / "dev"
        / "ai-data"
    )

    canonical_registry = (
        canonical / "platform.db"
    ).is_file()
    legacy_registry = (
        legacy / "platform.db"
    ).is_file()

    # platform.db is the authoritative registry. Auxiliary state such as
    # validation reports, workstation history, or public-source caches may
    # legitimately exist in the canonical directory before a migration is
    # complete and must not steal precedence from a healthy legacy registry.
    if canonical_registry:
        return canonical

    if legacy_registry:
        return legacy

    canonical_state = _data_root_has_state(
        canonical
    )
    legacy_state = _data_root_has_state(
        legacy
    )

    if canonical_state and not legacy_state:
        return canonical

    if legacy_state or legacy.exists():
        return legacy

    return canonical


DATA_ROOT = Path(
    runtime_value(
        "AI_DATA_ROOT",
        "data_root",
        str(_default_data_root()),
    )
)

QDRANT_PATH = Path(
    runtime_value(
        "QDRANT_PATH",
        "qdrant_path",
        str(DATA_ROOT / "qdrant"),
    )
)

QDRANT_URL = runtime_value(
    "QDRANT_URL",
    "qdrant_url",
)

COLLECTION = runtime_value(
    "QDRANT_COLLECTION",
    "qdrant_collection",
    "local_knowledge_v2",
)


def ollama_host() -> str:
    explicit = runtime_value(
        "OLLAMA_HOST",
        "ollama_host",
    )

    if explicit:
        return str(explicit).rstrip("/")

    # Discover WSL's Windows gateway locally.
    # This performs no external network probing.
    try:
        if "microsoft" in Path(
            "/proc/sys/kernel/osrelease"
        ).read_text().lower():
            for line in Path(
                "/proc/net/route"
            ).read_text().splitlines()[1:]:
                fields = line.split()

                if (
                    fields[1] == "00000000"
                    and int(fields[3], 16) & 2
                ):
                    gateway = socket.inet_ntoa(
                        struct.pack(
                            "<I",
                            int(fields[2], 16),
                        )
                    )

                    return f"http://{gateway}:11434"

            # WSL2 normally exposes the Windows host as the default route.
            # If that discovery fails, try the local resolver before falling
            # back to localhost. No machine-specific gateway is embedded.
            try:
                for line in Path("/etc/resolv.conf").read_text().splitlines():
                    if line.startswith("nameserver "):
                        candidate = line.split()[1]
                        socket.inet_aton(candidate)
                        return f"http://{candidate}:11434"
            except (OSError, ValueError, IndexError):
                pass

    except (
        OSError,
        ValueError,
        IndexError,
    ):
        pass

    return "http://localhost:11434"


@lru_cache(maxsize=1)
def qdrant_client() -> QdrantClient:
    if QDRANT_URL:
        return QdrantClient(
            url=str(QDRANT_URL),
            api_key=os.environ.get(
                "QDRANT_API_KEY"
            ),
            timeout=60,
        )

    return QdrantClient(
        path=str(QDRANT_PATH)
    )


def close_qdrant() -> None:
    if qdrant_client.cache_info().currsize:
        qdrant_client().close()
        qdrant_client.cache_clear()


atexit.register(close_qdrant)
