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
    (root / "src" / "reverend" / "feature.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "tests" / "test_feature.py").write_text("def test_x(): assert True\n", encoding="utf-8")
    (root / ".opencode" / "agent.md").write_text("protected\n", encoding="utf-8")
    return root


def test_change_policy_rejects_protected_and_escape_paths(tmp_path):
    root = _repo(tmp_path)
    policy = ChangePolicy(root)

    assert policy.validate_changed_files(["src/reverend/feature.py"]) == (
        "src/reverend/feature.py",
    )

    with pytest.raises(ChangePolicyError):
        policy.validate_changed_files([".opencode/agent.md"])
    with pytest.raises(ChangePolicyError):
        policy.validate_changed_files(["src/reverend/autonomy_v2/state.py"])
    with pytest.raises(UnsafeRepositoryPath):
        policy.validate_changed_files(["../escape.py"])


def test_plan_paths_are_checked_before_model_can_implement(tmp_path):
    root = _repo(tmp_path)
    policy = ChangePolicy(root)
    plan = policy.validate_plan(
        {
            "files_to_modify": ["src/reverend/feature.py"],
            "files_to_create": ["src/reverend/new_feature.py"],
            "tests_to_add_or_modify": ["tests/test_feature.py"],
            "acceptance_checks": ["pytest"],
            "risks": [],
        }
    )
    assert plan["files_to_create"] == ["src/reverend/new_feature.py"]

    with pytest.raises(FileNotFoundError):
        policy.validate_plan(
            {
                "files_to_modify": ["src/reverend/missing.py"],
                "files_to_create": [],
                "tests_to_add_or_modify": [],
                "acceptance_checks": [],
                "risks": [],
            }
        )
