"""Hard runtime policies for local-only AI inference."""

from __future__ import annotations

import socket
import struct
from dataclasses import dataclass
from enum import Enum
from ipaddress import ip_address
from pathlib import Path
from urllib.parse import urlparse


class PolicyViolation(RuntimeError):
    """Raised when a runtime action violates platform policy."""


class InferenceMode(str, Enum):
    LOCAL_ONLY = "local_only"


def discover_wsl_windows_gateway() -> str | None:
    """Return the Windows-host gateway visible from WSL.

    This deliberately ignores configured Ollama endpoints so a remote
    configuration cannot whitelist itself.
    """

    try:
        if "microsoft" not in Path(
            "/proc/sys/kernel/osrelease"
        ).read_text(encoding="utf-8").lower():
            return None

        lines = Path("/proc/net/route").read_text(
            encoding="utf-8"
        ).splitlines()[1:]

        for line in lines:
            fields = line.split()

            if len(fields) < 4:
                continue

            destination = fields[1]
            gateway_hex = fields[2]
            flags = int(fields[3], 16)

            if destination == "00000000" and flags & 2:
                return socket.inet_ntoa(
                    struct.pack(
                        "<I",
                        int(gateway_hex, 16),
                    )
                )

    except (
        OSError,
        ValueError,
        IndexError,
    ):
        return None

    return None


def _is_loopback(host: str) -> bool:
    if host.lower() == "localhost":
        return True

    try:
        return ip_address(host).is_loopback
    except ValueError:
        return False


@dataclass(frozen=True)
class InferencePolicy:
    """Security boundary governing model inference."""

    mode: InferenceMode = InferenceMode.LOCAL_ONLY
    allow_public_web: bool = True

    def validate_inference_endpoint(
        self,
        endpoint: str,
        *,
        extra_local_hosts: tuple[str, ...] = (),
    ) -> str:
        parsed = urlparse(endpoint)

        if parsed.scheme not in {"http", "https"}:
            raise PolicyViolation(
                "Inference endpoint must use HTTP or HTTPS."
            )

        if parsed.username or parsed.password:
            raise PolicyViolation(
                "Credentials embedded in inference URLs are forbidden."
            )

        host = parsed.hostname

        if not host:
            raise PolicyViolation(
                f"Invalid inference endpoint: {endpoint!r}"
            )

        allowed_hosts = {
            item.lower()
            for item in extra_local_hosts
            if item
        }

        gateway = discover_wsl_windows_gateway()

        if gateway:
            allowed_hosts.add(gateway.lower())

        if (
            _is_loopback(host)
            or host.lower() in allowed_hosts
        ):
            return endpoint.rstrip("/")

        raise PolicyViolation(
            "LOCAL_ONLY inference policy rejected "
            f"non-local endpoint: {endpoint}"
        )
