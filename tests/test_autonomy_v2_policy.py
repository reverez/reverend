from __future__ import annotations

from pathlib import Path

import pytest

from reverend.autonomy_v2.context import UnsafeRepositoryPath
from reverend.autonomy_v2.policy import ChangePolicy, ChangePolicyError


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "src" / "reverend").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / ".opencode").mkdir()
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / "Documentation" / "Design").mkdir(parents=True)
    (root / "src" / "reverend" / "feature.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "src" / "reverend" / "other.py").write_text("OTHER = 1\n", encoding="utf-8")
    (root / "tests" / "test_feature.py").write_text("def test_x(): assert True\n", encoding="utf-8")
    (root / ".opencode" / "agent.md").write_text("protected\n", encoding="utf-8")
    (root / ".github" / "workflows" / "ci.yml").write_text("name: CI\n", encoding="utf-8")
    (root / "Documentation" / "Design" / "D0.md").write_text("# Frozen design\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        "[project]\n"
        "name = \"example\"\n"
        "dependencies = [\"qdrant-client\", \"pydantic==2.0\"]\n\n"
        "[project.optional-dependencies]\n"
        "dev = [\"pytest>=8\"]\n\n"
        "[tool.pytest.ini_options]\n"
        "testpaths = [\"tests\"]\n",
        encoding="utf-8",
    )
    return root


def _plan(**overrides):
    value = {
        "files_to_modify": ["src/reverend/feature.py"],
        "files_to_create": ["src/reverend/new_feature.py"],
        "tests_to_add_or_modify": ["tests/test_feature.py"],
        "acceptance_checks": ["pytest"],
        "risks": [],
    }
    value.update(overrides)
    return value


def test_change_policy_rejects_protected_and_escape_paths(tmp_path):
    root = _repo(tmp_path)
    policy = ChangePolicy(root)

    assert policy.validate_changed_files(["src/reverend/feature.py"]) == (
        "src/reverend/feature.py",
    )

    for protected in (
        ".opencode/agent.md",
        ".github/workflows/ci.yml",
        "Documentation/Design/D0.md",
        "src/reverend/autonomy_v2/state.py",
    ):
        with pytest.raises(ChangePolicyError):
            policy.validate_changed_files([protected])
    with pytest.raises(UnsafeRepositoryPath):
        policy.validate_changed_files(["../escape.py"])


def test_plan_paths_are_checked_before_model_can_implement(tmp_path):
    root = _repo(tmp_path)
    policy = ChangePolicy(root)
    plan = policy.validate_plan(_plan())
    assert plan["files_to_create"] == ["src/reverend/new_feature.py"]

    with pytest.raises(FileNotFoundError):
        ChangePolicy(root).validate_plan(
            _plan(
                files_to_modify=["src/reverend/missing.py"],
                files_to_create=[],
                tests_to_add_or_modify=[],
            )
        )


def test_changed_files_must_remain_inside_validated_plan(tmp_path):
    root = _repo(tmp_path)
    policy = ChangePolicy(root)
    policy.validate_plan(_plan())

    assert policy.validate_changed_files(
        ["src/reverend/feature.py", "tests/test_feature.py"]
    ) == ("src/reverend/feature.py", "tests/test_feature.py")

    with pytest.raises(ChangePolicyError, match="outside validated plan"):
        policy.validate_changed_files(["src/reverend/other.py"])


def test_new_nested_file_plan_does_not_require_parent_to_preexist(tmp_path):
    root = _repo(tmp_path)
    policy = ChangePolicy(root)
    plan = policy.validate_plan(
        _plan(
            files_to_modify=[],
            files_to_create=["src/reverend/contracts/models.py"],
            tests_to_add_or_modify=[],
        )
    )
    policy.prepare_plan_directories(plan)
    assert (root / "src" / "reverend" / "contracts").is_dir()


def test_dependency_guard_allows_only_frozen_design_additions(tmp_path):
    root = _repo(tmp_path)
    policy = ChangePolicy(root)
    policy.validate_plan(
        _plan(
            files_to_modify=["pyproject.toml"],
            files_to_create=[],
            tests_to_add_or_modify=[],
        )
    )

    (root / "pyproject.toml").write_text(
        "[project]\n"
        "name = \"example\"\n"
        "dependencies = [\"qdrant-client\", \"pydantic==2.0\", \"fastapi>=0.100\"]\n\n"
        "[project.optional-dependencies]\n"
        "dev = [\"pytest>=8\"]\n\n"
        "[tool.pytest.ini_options]\n"
        "testpaths = [\"tests\"]\n",
        encoding="utf-8",
    )
    assert policy.validate_changed_files(["pyproject.toml"]) == ("pyproject.toml",)


def test_dependency_guard_rejects_unapproved_addition_and_existing_rewrite(tmp_path):
    root = _repo(tmp_path)
    policy = ChangePolicy(root)
    policy.validate_plan(
        _plan(
            files_to_modify=["pyproject.toml"],
            files_to_create=[],
            tests_to_add_or_modify=[],
        )
    )

    (root / "pyproject.toml").write_text(
        "[project]\n"
        "name = \"example\"\n"
        "dependencies = [\"qdrant-client\", \"pydantic==2.0\", \"requests\"]\n\n"
        "[project.optional-dependencies]\n"
        "dev = [\"pytest>=8\"]\n\n"
        "[tool.pytest.ini_options]\n"
        "testpaths = [\"tests\"]\n",
        encoding="utf-8",
    )
    with pytest.raises(ChangePolicyError, match="requires human review"):
        policy.validate_changed_files(["pyproject.toml"])

    (root / "pyproject.toml").write_text(
        "[project]\n"
        "name = \"example\"\n"
        "dependencies = [\"qdrant-client>=1\", \"pydantic==2.0\"]\n\n"
        "[project.optional-dependencies]\n"
        "dev = [\"pytest>=8\"]\n\n"
        "[tool.pytest.ini_options]\n"
        "testpaths = [\"tests\"]\n",
        encoding="utf-8",
    )
    with pytest.raises(ChangePolicyError, match="requirement changed"):
        policy.validate_changed_files(["pyproject.toml"])


def test_pyproject_non_dependency_configuration_is_immutable_unattended(tmp_path):
    root = _repo(tmp_path)
    policy = ChangePolicy(root)
    policy.validate_plan(
        _plan(
            files_to_modify=["pyproject.toml"],
            files_to_create=[],
            tests_to_add_or_modify=[],
        )
    )
    (root / "pyproject.toml").write_text(
        "[project]\n"
        "name = \"example\"\n"
        "dependencies = [\"qdrant-client\", \"pydantic==2.0\"]\n\n"
        "[project.optional-dependencies]\n"
        "dev = [\"pytest>=8\"]\n\n"
        "[tool.pytest.ini_options]\n"
        "testpaths = []\n",
        encoding="utf-8",
    )
    with pytest.raises(ChangePolicyError, match="changed outside"):
        policy.validate_changed_files(["pyproject.toml"])


def test_direct_dependency_references_require_human_review(tmp_path):
    root = _repo(tmp_path)
    policy = ChangePolicy(root)
    policy.validate_plan(
        _plan(
            files_to_modify=["pyproject.toml"],
            files_to_create=[],
            tests_to_add_or_modify=[],
        )
    )
    (root / "pyproject.toml").write_text(
        "[project]\n"
        "name = \"example\"\n"
        "dependencies = [\"qdrant-client\", \"pydantic==2.0\", \"fastapi @ https://example.invalid/pkg.whl\"]\n\n"
        "[project.optional-dependencies]\n"
        "dev = [\"pytest>=8\"]\n\n"
        "[tool.pytest.ini_options]\n"
        "testpaths = [\"tests\"]\n",
        encoding="utf-8",
    )
    with pytest.raises(ChangePolicyError, match="direct dependency reference"):
        policy.validate_changed_files(["pyproject.toml"])
