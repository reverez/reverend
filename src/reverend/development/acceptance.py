"""Conservative acceptance-criteria compilation for development tasks."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class AcceptanceCriterion:
    criterion_id: str
    text: str
    category: str
    testability: str
    exact_literals: tuple[str, ...]
    regression_sensitive: bool


@dataclass(frozen=True)
class AcceptanceContract:
    original_text: str
    criteria: tuple[AcceptanceCriterion, ...]
    digest: str

    @property
    def criterion_ids(self) -> tuple[str, ...]:
        return tuple(item.criterion_id for item in self.criteria)


def _split_criteria(text: str) -> tuple[str, ...]:
    clean = text.strip()
    if not clean:
        return ()

    chunks: list[str] = []
    for line in clean.splitlines():
        stripped = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", line).strip()
        if not stripped:
            continue
        parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\`'\"])", stripped)
        chunks.extend(part.strip() for part in parts if part.strip())

    expanded: list[str] = []
    for chunk in chunks:
        parts = [part.strip() for part in chunk.split(";") if part.strip()]
        if len(parts) > 1 and all(len(part) >= 8 for part in parts):
            expanded.extend(parts)
        else:
            expanded.append(chunk)

    return tuple(dict.fromkeys(expanded))


def _quoted_literals(text: str) -> tuple[str, ...]:
    values: list[str] = []
    for pattern in (
        r"`([^`\n]+)`",
        r"'([^'\n]+)'",
        r'"([^"\n]+)"',
    ):
        for match in re.findall(pattern, text):
            value = match.strip()
            if value and value not in values:
                values.append(value)
    return tuple(values)


def _classify(text: str) -> tuple[str, str]:
    folded = text.casefold()
    if any(
        token in folded
        for token in (
            "test passes",
            "tests pass",
            "pytest",
            "ctest",
            "build passes",
            "typecheck",
            "lint",
        )
    ):
        return "deterministic_test", "deterministic"
    if any(
        token in folded
        for token in (
            "exactly",
            "raises ",
            "raise ",
            "returns ",
            "exit code",
            "error message",
            "default",
        )
    ):
        return "behavioral", "deterministic_candidate"
    if any(
        token in folded
        for token in (
            "do not modify",
            "must not modify",
            "unchanged",
            "untouched",
            "compatible",
            "public interface",
            "public api",
        )
    ):
        return "compatibility", "static_or_behavioral"
    return "behavioral", "verifier"


def compile_acceptance_criteria(text: str | None) -> AcceptanceContract:
    """Compile free text without inventing or rewriting user requirements."""

    original = (text or "").strip()
    criteria: list[AcceptanceCriterion] = []
    for index, item in enumerate(_split_criteria(original), start=1):
        category, testability = _classify(item)
        folded = item.casefold()
        regression_sensitive = any(
            token in folded
            for token in (
                "existing",
                "regression",
                "unchanged",
                "untouched",
                "compatible",
                "must not",
                "do not",
            )
        )
        criteria.append(
            AcceptanceCriterion(
                criterion_id=f"AC-{index:02d}",
                text=item,
                category=category,
                testability=testability,
                exact_literals=_quoted_literals(item),
                regression_sensitive=regression_sensitive,
            )
        )

    canonical = json.dumps(
        [asdict(item) for item in criteria],
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return AcceptanceContract(
        original_text=original,
        criteria=tuple(criteria),
        digest=digest,
    )


def render_acceptance_contract(contract: AcceptanceContract) -> str:
    """Render an immutable machine-readable contract for model prompts."""

    return json.dumps(
        {
            "digest": contract.digest,
            "criteria": [asdict(item) for item in contract.criteria],
        },
        indent=2,
        sort_keys=True,
    )
