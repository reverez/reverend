"""Payload-safe observability metadata filtering."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from .core import ObservabilityLevel


_SECRET_KEY = re.compile(
    r"(?:^|_)(?:secret|password|passwd|authorization|cookie|"
    r"api_key|access_token|refresh_token|bearer|credential|"
    r"private_key)(?:$|_)",
    re.I,
)
_PAYLOAD_KEY = re.compile(
    r"(?:^|_)(?:prompt|response|content|body|text|input|output|"
    r"diff|raw_response|chain_of_thought|thinking)(?:$|_)",
    re.I,
)
_SAFE_NUMERIC_METRIC = re.compile(
    r"(?:^|_)(?:count|calls|tokens|seconds|bytes|chars|limit|budget)$",
    re.I,
)
_NORMAL_SAFE = re.compile(
    r"(?:"
    r"(?:^|_)(?:id|ids|status|state|kind|role|model|digest|context|"
    r"provider|phase|reason|outcome|version|method|runtime|tool|"
    r"error_code)(?:$|_)|"
    r"(?:count|calls|tokens|seconds|bytes|chars|limit|budget)$"
    r")",
    re.I,
)


def _safe_scalar(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:512]
    return None


def _debug_value(value: Any, *, depth: int = 0) -> Any:
    if depth >= 3:
        return None

    scalar = _safe_scalar(value)
    if scalar is not None or value is None:
        return scalar

    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= 32:
                break
            clean_key = str(key)[:128]
            if _SECRET_KEY.search(clean_key) or _PAYLOAD_KEY.search(clean_key):
                continue
            clean = _debug_value(item, depth=depth + 1)
            if clean is not None:
                result[clean_key] = clean
        return result

    if isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        result = []
        for item in list(value)[:32]:
            clean = _debug_value(item, depth=depth + 1)
            if clean is not None:
                result.append(clean)
        return result

    return None


def sanitize_attributes(
    attributes: Mapping[str, Any] | None,
    *,
    level: ObservabilityLevel,
) -> dict[str, Any]:
    """Return bounded operational metadata without request/response payloads."""

    if not attributes or level is ObservabilityLevel.MINIMAL:
        return {}

    result: dict[str, Any] = {}

    for index, (key, value) in enumerate(attributes.items()):
        if index >= 64:
            break

        clean_key = str(key)[:128]
        if _SECRET_KEY.search(clean_key):
            continue

        # Payload-derived counters such as prompt_tokens are safe operational
        # metadata only when they are numeric. The similarly named raw payload
        # fields (prompt/response/content/etc.) remain forbidden.
        if _SAFE_NUMERIC_METRIC.search(clean_key) and isinstance(
            value, (int, float)
        ) and not isinstance(value, bool):
            result[clean_key] = value
            continue

        if _PAYLOAD_KEY.search(clean_key):
            continue

        if level is ObservabilityLevel.NORMAL:
            if not _NORMAL_SAFE.search(clean_key):
                continue
            clean = _safe_scalar(value)
        else:
            clean = _debug_value(value)

        if clean is not None:
            result[clean_key] = clean

    return result
