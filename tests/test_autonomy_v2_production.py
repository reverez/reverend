from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from reverend.autonomy_v2.engine import IssueOutcome
from reverend.autonomy_v2.production import (
    IssueContextResolver,
    ProductionConfig,
    ProductionLock,
    ProductionRunLocked,
    ProductionRunner,
    SessionStore,
)
from reverend.autonomy_v2.queue import QueuedIssue
from reverend.autonomy_v2.state import IssuePhase


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    )
    return completed.stdout.strip()


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "Documentation" / "Design").mkdir(parents=True)
    (root / "src" / "reverend").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / ".gitignore").write_text(
        ".autonomy/\n.worktrees/\n__pycache__/\n.pytest_cache/\n",
        encoding="utf-8",
    )
    (root / "Documentation" / "Design" / "00-design-index.md").write_text(
        "# Design index\nC0 contracts. C1 persistence.\n", encoding="utf-8"
    )
    (root / "Documentation" / "Design" / "D0-system-contracts.md").write_text(
        "# Contracts\nIdentifiers schema enums.\n", encoding="utf-8"
    )
    (root / "Documentation" / "Design" / "D9-development-programme-migration-and-acceptance.md").write_text(
        "# Development\nC0 before C1.\n", encoding="utf-8"
    )
    (root / "Documentation" / "Design" / "D22-final-design-closure-and-implementation-readiness.md").write_text(
        "# Closure\nImplementation ready.\n", encoding="utf-8"
    )
    (root / "src" / "reverend" / "contracts.py").write_text(
        "SCHEMA_VERSION = 1\n", encoding="utf-8"
    )
    (root / "tests" / "test_smoke.py").write_text(
        "def test_smoke():\n    assert True\n", encoding="utf-8"
    )
    _git(root, "init")
    _git(root, "config", "user.name", "Reverend Test")
    _git(root, "config", "user.email", "reverend@example.invalid")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "baseline")
    return root


def _issue(number: int, milestone: int, title: str) -> QueuedIssue:
    return QueuedIssue(
        number=number,
        title=title,
        body=(
            "## Ownership\n\n"
            "**Owner:** arnav\n"
            f"**Milestone:** C{milestone} — Test milestone\n"
            "**Area:** contracts\n\n"
            "## Development contract\n"
            "- preserve accepted behavior\n"
            "- add deterministic tests\n"
        ),
        owner="arnav",
        milestone_number=milestone,
        milestone_name="Test milestone",
        area="contracts",
    )


class _FakeEngine:
    def __init__(self, controller, observed_bases: list[str]) -> None:
        self.controller = controller
        self.observed_bases = observed_bases

    def run(self, prepared):
        self.observed_bases.append(prepared.packet.base_commit)
        target = prepared.worktree.path / f"issue-{prepared.issue.number}.txt"
        target.write_text(f"issue {prepared.issue.number}\n", encoding="utf-8")
        for phase in (
            IssuePhase.PLANNED,
            IssuePhase.IMPLEMENTING,
            IssuePhase.VERIFYING,
            IssuePhase.REVIEWING,
        ):
            self.controller.store.transition_issue(
                run_id=prepared.run_id,
                issue_number=prepared.issue.number,
                target=phase,
            )
        commit = self.controller.worktrees.commit_changes(
            prepared.worktree.path,
            message=f"test issue {prepared.issue.number}",
        )
        self.controller.store.transition_issue(
            run_id=prepared.run_id,
            issue_number=prepared.issue.number,
            target=IssuePhase.ACCEPTED,
            payload={"commit": commit},
        )
        self.controller.store.mark_accepted_commit(
            run_id=prepared.run_id,
            issue_number=prepared.issue.number,
            commit=commit,
        )
        return IssueOutcome(
            prepared.issue.number,
            IssuePhase.ACCEPTED,
            commit=commit,
        )


def test_session_store_round_trip(tmp_path):
    store = SessionStore(tmp_path / "runtime")
    payload = store.create({"session_id": "session-1", "status": "RUNNING"})
    assert payload["status"] == "RUNNING"
    assert store.latest() == "session-1"
    loaded = store.load("session-1")
    assert loaded["session_id"] == "session-1"
    assert loaded["created_at"]
    assert loaded["updated_at"]


def test_production_lock_is_exclusive(tmp_path):
    path = tmp_path / "controller.lock"
    with ProductionLock(path):
        with pytest.raises(ProductionRunLocked):
            with ProductionLock(path):
                pass


def test_context_resolver_returns_existing_bounded_paths(tmp_path):
    root = _repo(tmp_path)
    context = IssueContextResolver(root).resolve(
        _issue(66, 0, "Common identifiers schema enums")
    )
    assert "Documentation/Design/00-design-index.md" in context.design_sources
    assert any("D0-system-contracts" in path for path in context.design_sources)
    assert "src/reverend/contracts.py" in context.candidate_source_files
    for relative in (*context.design_sources, *context.candidate_source_files, *context.candidate_tests):
        assert (root / relative).exists()


def test_two_issues_chain_from_current_integration_head(tmp_path):
    root = _repo(tmp_path)
    issues = (
        _issue(66, 0, "Common identifiers schema enums"),
        _issue(67, 0, "Contract schema extension"),
    )
    observed_bases: list[str] = []

    def factory(controller, _config):
        return _FakeEngine(controller, observed_bases)

    runner = ProductionRunner(
        root,
        config=ProductionConfig(
            repository="owner/repo",
            model="fake/model",
            ollama_model="fake-model",
            run_preflight=False,
        ),
        queue_loader=lambda: issues,
        engine_factory=factory,
    )
    result = runner.start()
    assert result.status == "COMPLETED"
    assert result.completed_issues == 2
    assert len(observed_bases) == 2
    assert observed_bases[0] != observed_bases[1]
    integration = Path(runner.status(result.session_id)["integration_worktree"])
    assert (integration / "issue-66.txt").is_file()
    assert (integration / "issue-67.txt").is_file()
    assert _git(integration, "rev-parse", "HEAD") == result.integration_head


def test_max_issues_limits_queue_before_execution(tmp_path):
    root = _repo(tmp_path)
    observed_bases: list[str] = []

    def factory(controller, _config):
        return _FakeEngine(controller, observed_bases)

    runner = ProductionRunner(
        root,
        config=ProductionConfig(
            repository="owner/repo",
            model="fake/model",
            ollama_model="fake-model",
            max_issues=1,
            run_preflight=False,
        ),
        queue_loader=lambda: (
            _issue(66, 0, "Common identifiers schema enums"),
            _issue(67, 0, "Contract schema extension"),
        ),
        engine_factory=factory,
    )
    result = runner.start()
    assert result.status == "COMPLETED"
    assert result.completed_issues == 1
    assert result.total_issues == 1
