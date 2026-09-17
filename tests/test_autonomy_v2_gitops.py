from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from reverend.autonomy_v2.gitops import WorktreeManager


def _git(cwd: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=True,
    )
    return completed.stdout.strip()


def _repository(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init")
    (root / "README.md").write_text("# test\n", encoding="utf-8")
    _git(root, "add", "README.md")
    _git(
        root,
        "-c",
        "user.name=Reverend Test",
        "-c",
        "user.email=reverend@example.invalid",
        "commit",
        "-m",
        "initial",
    )
    return root


def test_worktree_isolated_from_primary_checkout(tmp_path):
    root = _repository(tmp_path)
    manager = WorktreeManager(root, runtime_root=tmp_path / "worktrees")
    manager.assert_clean()
    base = manager.head_commit("HEAD")

    worktree = manager.create_issue_worktree(
        issue_number=66,
        base_ref=base,
        branch_name="autonomy/v2-test-issue-66",
    )
    try:
        assert worktree.path.is_dir()
        assert _git(worktree.path, "rev-parse", "HEAD") == base
        assert manager.has_meaningful_diff(worktree.path, base) is False

        (worktree.path / "new.py").write_text("VALUE = 1\n", encoding="utf-8")
        assert manager.has_meaningful_diff(worktree.path, base) is True
        assert manager.changed_files(worktree.path, base) == ("new.py",)
        assert _git(root, "status", "--porcelain") == ""
    finally:
        manager.remove_worktree(worktree, force=True)


def test_worktree_manager_rejects_unsafe_refs(tmp_path):
    root = _repository(tmp_path)
    manager = WorktreeManager(root, runtime_root=tmp_path / "worktrees")

    with pytest.raises(ValueError):
        manager.create_issue_worktree(
            issue_number=66,
            base_ref="HEAD",
            branch_name="../../escape",
        )
