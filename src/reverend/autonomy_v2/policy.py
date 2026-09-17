from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable, Mapping

from .context import UnsafeRepositoryPath
from .execution import ModelProtocolError


DEFAULT_PROTECTED_PATHS = (
    ".git",
    ".autonomy",
    ".opencode",
    "AGENTS.md",
    "scripts/autonomy-",
    "src/reverend/autonomy_v2",
    "config/autonomy-v2",
)


class ChangePolicyError(RuntimeError):
    pass


@dataclass(frozen=True)
class ChangePolicy:
    repository_root: Path
    protected_prefixes: tuple[str, ...] = DEFAULT_PROTECTED_PATHS
    allow_protected: bool = False

    def __init__(
        self,
        repository_root: str | Path,
        *,
        protected_prefixes: Iterable[str] = DEFAULT_PROTECTED_PATHS,
        allow_protected: bool = False,
    ) -> None:
        object.__setattr__(self, "repository_root", Path(repository_root).resolve())
        object.__setattr__(self, "protected_prefixes", tuple(protected_prefixes))
        object.__setattr__(self, "allow_protected", allow_protected)

    def normalize_relative(self, raw_path: str, *, must_exist: bool | None = None) -> str:
        pure = PurePosixPath(raw_path)
        if not raw_path or pure.is_absolute() or ".." in pure.parts:
            raise UnsafeRepositoryPath(raw_path)
        resolved = (self.repository_root / Path(*pure.parts)).resolve()
        try:
            relative = resolved.relative_to(self.repository_root).as_posix()
        except ValueError as exc:
            raise UnsafeRepositoryPath(raw_path) from exc
        if must_exist is True and not resolved.exists():
            raise FileNotFoundError(relative)
        if must_exist is False and resolved.exists():
            raise FileExistsError(relative)
        return relative

    def is_protected(self, relative_path: str) -> bool:
        normalized = relative_path.rstrip("/")
        for prefix in self.protected_prefixes:
            prefix = prefix.rstrip("/")
            if normalized == prefix or normalized.startswith(prefix + "/"):
                return True
            if prefix.endswith("-") and normalized.startswith(prefix):
                return True
        return False

    def validate_changed_files(self, paths: Iterable[str]) -> tuple[str, ...]:
        normalized: list[str] = []
        for raw_path in paths:
            path = self.normalize_relative(raw_path)
            if self.is_protected(path) and not self.allow_protected:
                raise ChangePolicyError(f"protected path modified: {path}")
            normalized.append(path)
        return tuple(dict.fromkeys(normalized))

    def validate_plan(self, plan: Mapping[str, list[str]]) -> dict[str, list[str]]:
        required = {
            "files_to_modify",
            "files_to_create",
            "tests_to_add_or_modify",
            "acceptance_checks",
            "risks",
        }
        if set(plan) != required:
            raise ModelProtocolError("plan fields do not match required schema")

        modify: list[str] = []
        create: list[str] = []
        tests: list[str] = []
        for raw_path in plan["files_to_modify"]:
            path = self.normalize_relative(raw_path, must_exist=True)
            if self.is_protected(path) and not self.allow_protected:
                raise ChangePolicyError(f"plan targets protected path: {path}")
            modify.append(path)
        for raw_path in plan["files_to_create"]:
            path = self.normalize_relative(raw_path, must_exist=False)
            if self.is_protected(path) and not self.allow_protected:
                raise ChangePolicyError(f"plan targets protected path: {path}")
            parent = (self.repository_root / path).parent
            if not parent.exists():
                raise FileNotFoundError(f"parent directory does not exist: {parent}")
            create.append(path)
        for raw_path in plan["tests_to_add_or_modify"]:
            path = self.normalize_relative(raw_path)
            if self.is_protected(path) and not self.allow_protected:
                raise ChangePolicyError(f"plan targets protected path: {path}")
            if not path.startswith("tests/"):
                raise ChangePolicyError(f"test path must be under tests/: {path}")
            tests.append(path)

        return {
            "files_to_modify": list(dict.fromkeys(modify)),
            "files_to_create": list(dict.fromkeys(create)),
            "tests_to_add_or_modify": list(dict.fromkeys(tests)),
            "acceptance_checks": list(plan["acceptance_checks"]),
            "risks": list(plan["risks"]),
        }
