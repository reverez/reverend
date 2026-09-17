from __future__ import annotations

import copy
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping

from .context import UnsafeRepositoryPath
from .execution import ModelProtocolError


DEFAULT_PROTECTED_PATHS = (
    ".git",
    ".autonomy",
    ".opencode",
    ".github",
    "AGENTS.md",
    "Documentation/Design",
    "scripts/autonomy-",
    "src/reverend/autonomy_v2",
    "config/autonomy-v2",
)

# Dependencies explicitly anticipated by the frozen C0-C9 Design programme.
# Existing requirements may not be removed or have their requirement strings
# rewritten unattended. New requirements outside this set require human review.
ALLOWED_DEPENDENCY_ADDITIONS = frozenset(
    {
        "fastapi",
        "pydantic",
        "uvicorn",
        "psycopg",
        "argon2-cffi",
        "httpx",
    }
)
_REQUIREMENT_NAME_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9_.-]*)")


class ChangePolicyError(RuntimeError):
    pass


@dataclass(frozen=True)
class ChangePolicy:
    repository_root: Path
    protected_prefixes: tuple[str, ...] = DEFAULT_PROTECTED_PATHS
    allow_protected: bool = False
    _planned_paths: frozenset[str] | None = None
    _baseline_dependencies: Mapping[str, tuple[str, ...]] | None = None
    _baseline_pyproject_static: Mapping[str, Any] | None = None

    def __init__(
        self,
        repository_root: str | Path,
        *,
        protected_prefixes: Iterable[str] = DEFAULT_PROTECTED_PATHS,
        allow_protected: bool = False,
    ) -> None:
        root = Path(repository_root).resolve()
        pyproject = _load_pyproject(root / "pyproject.toml")
        object.__setattr__(self, "repository_root", root)
        object.__setattr__(self, "protected_prefixes", tuple(protected_prefixes))
        object.__setattr__(self, "allow_protected", allow_protected)
        object.__setattr__(self, "_planned_paths", None)
        object.__setattr__(self, "_baseline_dependencies", _dependency_sections(pyproject))
        object.__setattr__(self, "_baseline_pyproject_static", _pyproject_static(pyproject))

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
        planned = self._planned_paths
        for raw_path in paths:
            path = self.normalize_relative(raw_path)
            if self.is_protected(path) and not self.allow_protected:
                raise ChangePolicyError(f"protected path modified: {path}")
            if planned is not None and path not in planned:
                raise ChangePolicyError(
                    f"implementation changed path outside validated plan: {path}"
                )
            normalized.append(path)

        result = tuple(dict.fromkeys(normalized))
        if "pyproject.toml" in result:
            self._validate_pyproject_changes()
        return result

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
            create.append(path)
        for raw_path in plan["tests_to_add_or_modify"]:
            path = self.normalize_relative(raw_path)
            if self.is_protected(path) and not self.allow_protected:
                raise ChangePolicyError(f"plan targets protected path: {path}")
            if not path.startswith("tests/"):
                raise ChangePolicyError(f"test path must be under tests/: {path}")
            tests.append(path)

        normalized_plan = {
            "files_to_modify": list(dict.fromkeys(modify)),
            "files_to_create": list(dict.fromkeys(create)),
            "tests_to_add_or_modify": list(dict.fromkeys(tests)),
            "acceptance_checks": list(plan["acceptance_checks"]),
            "risks": list(plan["risks"]),
        }
        object.__setattr__(
            self,
            "_planned_paths",
            frozenset(
                [
                    *normalized_plan["files_to_modify"],
                    *normalized_plan["files_to_create"],
                    *normalized_plan["tests_to_add_or_modify"],
                ]
            ),
        )
        return normalized_plan

    def prepare_plan_directories(self, plan: Mapping[str, list[str]]) -> None:
        """Create only parent directories explicitly implied by a validated plan."""
        if self._planned_paths is None:
            raise ChangePolicyError("plan must be validated before preparing directories")
        for raw_path in [
            *plan["files_to_create"],
            *plan["tests_to_add_or_modify"],
        ]:
            path = self.normalize_relative(raw_path)
            if path not in self._planned_paths:
                raise ChangePolicyError(f"unvalidated plan path: {path}")
            (self.repository_root / path).parent.mkdir(parents=True, exist_ok=True)

    def _validate_pyproject_changes(self) -> None:
        current_document = _load_pyproject(self.repository_root / "pyproject.toml")
        current_static = _pyproject_static(current_document)
        if current_static != dict(self._baseline_pyproject_static or {}):
            raise ChangePolicyError(
                "pyproject.toml changed outside project dependency declarations; "
                "build, scripts, test configuration, and package metadata require human review"
            )

        baseline = dict(self._baseline_dependencies or {})
        current = _dependency_sections(current_document)
        if not baseline and current:
            raise ChangePolicyError("creating dependency policy from scratch requires human review")

        section_names = set(baseline) | set(current)
        for section in sorted(section_names):
            before = _requirements_by_name(baseline.get(section, ()))
            after = _requirements_by_name(current.get(section, ()))

            for name, requirement in before.items():
                if name not in after:
                    raise ChangePolicyError(
                        f"existing dependency removed from {section}: {requirement}"
                    )
                if after[name] != requirement:
                    raise ChangePolicyError(
                        f"existing dependency requirement changed in {section}: "
                        f"{requirement!r} -> {after[name]!r}"
                    )

            for name, requirement in after.items():
                if name in before:
                    continue
                if name not in ALLOWED_DEPENDENCY_ADDITIONS:
                    raise ChangePolicyError(
                        f"dependency addition requires human review in {section}: {requirement}"
                    )
                if _is_direct_reference(requirement):
                    raise ChangePolicyError(
                        f"direct dependency reference requires human review in {section}: {requirement}"
                    )


def _load_pyproject(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        document = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ChangePolicyError(f"unable to parse pyproject.toml: {exc}") from exc
    if not isinstance(document, dict):
        raise ChangePolicyError("pyproject.toml root must be a table")
    return document


def _dependency_sections(document: Mapping[str, Any]) -> dict[str, tuple[str, ...]]:
    project = document.get("project")
    if project is None:
        return {}
    if not isinstance(project, dict):
        raise ChangePolicyError("project must be a table")

    result: dict[str, tuple[str, ...]] = {}
    dependencies = project.get("dependencies", [])
    if not isinstance(dependencies, list) or not all(
        isinstance(item, str) for item in dependencies
    ):
        raise ChangePolicyError("project.dependencies must be a list of strings")
    result["project.dependencies"] = tuple(dependencies)

    optional = project.get("optional-dependencies", {})
    if not isinstance(optional, dict):
        raise ChangePolicyError("project.optional-dependencies must be a table")
    for group, requirements in optional.items():
        if not isinstance(group, str) or not isinstance(requirements, list) or not all(
            isinstance(item, str) for item in requirements
        ):
            raise ChangePolicyError(
                "project.optional-dependencies entries must be string lists"
            )
        result[f"project.optional-dependencies.{group}"] = tuple(requirements)
    return result


def _pyproject_static(document: Mapping[str, Any]) -> dict[str, Any]:
    static = copy.deepcopy(dict(document))
    project = static.get("project")
    if isinstance(project, dict):
        project.pop("dependencies", None)
        project.pop("optional-dependencies", None)
    return static


def _requirements_by_name(requirements: Iterable[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for requirement in requirements:
        match = _REQUIREMENT_NAME_RE.match(requirement)
        if match is None:
            raise ChangePolicyError(f"unable to identify dependency name: {requirement!r}")
        name = match.group(1).lower().replace("_", "-").replace(".", "-")
        if name in result:
            raise ChangePolicyError(f"duplicate dependency requirement: {name}")
        result[name] = requirement
    return result


def _is_direct_reference(requirement: str) -> bool:
    lowered = requirement.lower()
    return " @ " in lowered or "://" in lowered or "file:" in lowered
