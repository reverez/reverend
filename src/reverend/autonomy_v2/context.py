from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable


class UnsafeRepositoryPath(ValueError):
    pass


@dataclass(frozen=True)
class IssuePacket:
    issue_number: int
    title: str
    milestone: str
    base_commit: str
    requirements: tuple[str, ...]
    design_sources: tuple[str, ...]
    candidate_source_files: tuple[str, ...]
    candidate_tests: tuple[str, ...]
    acceptance: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        return payload


class ContextBuilder:
    """Build small, path-validated context packets before invoking an LLM."""

    def __init__(self, repository_root: str | Path) -> None:
        self.repository_root = Path(repository_root).resolve()
        if not self.repository_root.is_dir():
            raise ValueError(f"repository root does not exist: {repository_root}")

    def _relative_existing(self, raw_path: str) -> str:
        pure = PurePosixPath(raw_path)
        if pure.is_absolute() or ".." in pure.parts:
            raise UnsafeRepositoryPath(raw_path)
        resolved = (self.repository_root / Path(*pure.parts)).resolve()
        try:
            relative = resolved.relative_to(self.repository_root)
        except ValueError as exc:
            raise UnsafeRepositoryPath(raw_path) from exc
        if not resolved.exists():
            raise FileNotFoundError(raw_path)
        return relative.as_posix()

    def _validated_paths(self, paths: Iterable[str]) -> tuple[str, ...]:
        result: list[str] = []
        seen: set[str] = set()
        for raw_path in paths:
            validated = self._relative_existing(raw_path)
            if validated not in seen:
                result.append(validated)
                seen.add(validated)
        return tuple(result)

    def build(
        self,
        *,
        issue_number: int,
        title: str,
        milestone: str,
        base_commit: str,
        requirements: Iterable[str],
        design_sources: Iterable[str],
        candidate_source_files: Iterable[str] = (),
        candidate_tests: Iterable[str] = (),
        acceptance: Iterable[str] = (),
    ) -> IssuePacket:
        if issue_number <= 0:
            raise ValueError("issue_number must be positive")
        if not title.strip():
            raise ValueError("title must not be empty")
        if not milestone.strip():
            raise ValueError("milestone must not be empty")
        if not base_commit.strip():
            raise ValueError("base_commit must not be empty")

        normalized_requirements = tuple(item.strip() for item in requirements if item.strip())
        normalized_acceptance = tuple(item.strip() for item in acceptance if item.strip())
        validated_design_sources = self._validated_paths(design_sources)
        if not validated_design_sources:
            raise ValueError("at least one existing design source is required")

        return IssuePacket(
            issue_number=issue_number,
            title=title.strip(),
            milestone=milestone.strip(),
            base_commit=base_commit.strip(),
            requirements=normalized_requirements,
            design_sources=validated_design_sources,
            candidate_source_files=self._validated_paths(candidate_source_files),
            candidate_tests=self._validated_paths(candidate_tests),
            acceptance=normalized_acceptance,
        )

    def write_atomic(self, packet: IssuePacket, destination: str | Path) -> Path:
        destination_path = Path(destination)
        if not destination_path.is_absolute():
            destination_path = self.repository_root / destination_path
        destination_path = destination_path.resolve()
        try:
            destination_path.relative_to(self.repository_root)
        except ValueError as exc:
            raise UnsafeRepositoryPath(str(destination)) from exc

        destination_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(packet.as_dict(), indent=2, sort_keys=True) + "\n"
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination_path.name}.",
            suffix=".tmp",
            dir=destination_path.parent,
            text=True,
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, destination_path)
        except Exception:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise
        return destination_path
