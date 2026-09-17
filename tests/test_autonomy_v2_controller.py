from __future__ import annotations

import subprocess
from pathlib import Path

from reverend.autonomy_v2.controller import AutonomousController, IssueSpec
from reverend.autonomy_v2.state import IssuePhase


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
    (root / "Documentation" / "Design").mkdir(parents=True)
    (root / "src").mkdir()
    (root / "tests").mkdir()
    (root / ".gitignore").write_text(".autonomy/\n.worktrees/\n", encoding="utf-8")
    (root / "Documentation" / "Design" / "D0.md").write_text(
        "# Contracts\nIDs are opaque UUID4 values.\n",
        encoding="utf-8",
    )
    (root / "src" / "existing.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "tests" / "test_existing.py").write_text(
        "def test_existing(): assert True\n",
        encoding="utf-8",
    )
    _git(root, "init")
    _git(root, "add", ".")
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


def test_controller_prepares_issue_without_polluting_implementation_diff(tmp_path):
    root = _repository(tmp_path)
    controller = AutonomousController(root)
    issue = IssueSpec(number=66, milestone="C0", title="Common IDs")
    run_id = controller.initialize_run(queue=[issue], run_id="run-controller-test")

    prepared = controller.prepare_issue(
        run_id=run_id,
        issue=issue,
        requirements=["opaque UUID4 identifiers", "schema_version = 1"],
        design_sources=["Documentation/Design/D0.md"],
        candidate_source_files=["src/existing.py"],
        candidate_tests=["tests/test_existing.py"],
        acceptance=["targeted tests pass", "full regression passes"],
    )
    try:
        state = controller.store.get_issue(run_id, 66)
        assert state.phase is IssuePhase.CONTEXT_READY
        assert Path(state.packet_path or "").is_file()
        assert Path(state.packet_path or "").is_relative_to(root / ".autonomy")
        assert prepared.packet_path.is_relative_to(root / ".autonomy")
        assert prepared.packet_path.is_relative_to(prepared.worktree.path) is False
        assert controller.worktrees.has_meaningful_diff(
            prepared.worktree.path, state.base_commit
        ) is False
    finally:
        controller.worktrees.remove_worktree(prepared.worktree, force=True)
