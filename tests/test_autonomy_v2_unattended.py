from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

from reverend.autonomy_v2.engine import IssueOutcome
from reverend.autonomy_v2.notifications import IncidentReporter
from reverend.autonomy_v2.production import (
    ProductionConfig,
    ProductionRunner,
    build_health_snapshot,
)
from reverend.autonomy_v2.queue import QueuedIssue
from reverend.autonomy_v2.state import IssuePhase, StateStore


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
        "# Design index\nC0 contracts.\n", encoding="utf-8"
    )
    (root / "Documentation" / "Design" / "D0-system-contracts.md").write_text(
        "# Contracts\nIdentifiers schema enums.\n", encoding="utf-8"
    )
    (root / "Documentation" / "Design" / "D9-development-programme-migration-and-acceptance.md").write_text(
        "# Development\nC0 before C1.\n", encoding="utf-8"
    )
    (root / "Documentation" / "Design" / "D22-pre-development-architecture-closure.md").write_text(
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


def _issue(number: int) -> QueuedIssue:
    return QueuedIssue(
        number=number,
        title=f"Common contracts {number}",
        body=(
            "## Ownership\n\n"
            "**Owner:** arnav\n"
            "**Milestone:** C0 — Test milestone\n"
            "**Area:** contracts\n\n"
            "## Development contract\n"
            "- preserve accepted behavior\n"
        ),
        owner="arnav",
        milestone_number=0,
        milestone_name="Test milestone",
        area="contracts",
    )


def test_accept_issue_persists_phase_and_commit_atomically(tmp_path):
    store = StateStore(tmp_path / "state.db")
    store.create_run(run_id="run-1", base_commit="a" * 40, queue=[])
    store.add_issue(
        run_id="run-1",
        issue_number=66,
        milestone="C0",
        title="contracts",
        base_commit="a" * 40,
    )
    store.mark_context_ready(
        run_id="run-1",
        issue_number=66,
        worktree_path="/tmp/worktree",
        branch_name="autonomy/test",
        packet_path="/tmp/packet.json",
    )
    for phase in (
        IssuePhase.PLANNED,
        IssuePhase.IMPLEMENTING,
        IssuePhase.VERIFYING,
        IssuePhase.REVIEWING,
    ):
        store.transition_issue(run_id="run-1", issue_number=66, target=phase)

    state = store.accept_issue(
        run_id="run-1",
        issue_number=66,
        commit="b" * 40,
    )

    assert state.phase is IssuePhase.ACCEPTED
    assert state.accepted_commit == "b" * 40


def test_incident_reporter_is_durable(tmp_path, monkeypatch):
    monkeypatch.delenv("REVEREND_ALERT_COMMAND", raising=False)
    monkeypatch.delenv("REVEREND_ALERT_WEBHOOK_URL", raising=False)
    reporter = IncidentReporter(tmp_path)
    reporter.emit(
        severity="critical",
        kind="blocked",
        message="planner exhausted recovery",
        session_id="session-1",
        issue_number=66,
    )
    latest = reporter.latest(1)
    assert latest[0]["severity"] == "CRITICAL"
    assert latest[0]["kind"] == "blocked"
    assert latest[0]["issue_number"] == 66


def test_health_snapshot_exposes_phase_heartbeat_and_attempt(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    store = StateStore(root / ".autonomy" / "state" / "autonomy.db")
    store.create_run(run_id="run-health", base_commit="a" * 40, queue=[])
    store.add_issue(
        run_id="run-health",
        issue_number=66,
        milestone="C0",
        title="contracts",
        base_commit="a" * 40,
    )
    store.mark_context_ready(
        run_id="run-health",
        issue_number=66,
        worktree_path="/tmp/worktree",
        branch_name="autonomy/test",
        packet_path="/tmp/packet.json",
    )
    attempt = store.start_attempt(
        run_id="run-health",
        issue_number=66,
        kind="plan",
        model="fake/model",
    )
    manifest = {
        "session_id": "session-health",
        "status": "RUNNING",
        "queue": [{"number": 66}],
        "accepted": [],
        "deferred": [],
        "current_issue": 66,
        "current_issue_run_id": "run-health",
        "updated_at": "now",
        "stop_reason": None,
    }

    health = build_health_snapshot(root, manifest)

    assert health["issue_phase"] == "CONTEXT_READY"
    assert health["healthy"] is True
    assert health["latest_attempt"]["kind"] == "plan"
    store.finish_attempt(attempt.id, status="PROCESS_OK")


class _FlakyEngine:
    def __init__(self, controller, counts: dict[int, int]) -> None:
        self.controller = controller
        self.counts = counts

    def run(self, prepared):
        number = prepared.issue.number
        self.counts[number] = self.counts.get(number, 0) + 1
        if number == 66 and self.counts[number] <= 2:
            self.controller.store.transition_issue(
                run_id=prepared.run_id,
                issue_number=number,
                target=IssuePhase.BLOCKED,
                payload={"reason": "synthetic transient failure"},
            )
            return IssueOutcome(
                number,
                IssuePhase.BLOCKED,
                reason="synthetic transient failure",
            )

        target = prepared.worktree.path / f"issue-{number}.txt"
        target.write_text(f"issue {number}\n", encoding="utf-8")
        for phase in (
            IssuePhase.PLANNED,
            IssuePhase.IMPLEMENTING,
            IssuePhase.VERIFYING,
            IssuePhase.REVIEWING,
        ):
            self.controller.store.transition_issue(
                run_id=prepared.run_id,
                issue_number=number,
                target=phase,
            )
        commit = self.controller.worktrees.commit_changes(
            prepared.worktree.path,
            message=f"test issue {number}",
        )
        self.controller.store.accept_issue(
            run_id=prepared.run_id,
            issue_number=number,
            commit=commit,
        )
        return IssueOutcome(number, IssuePhase.ACCEPTED, commit=commit)


def test_flaky_issue_is_deferred_then_recovered_without_human_input(
    tmp_path, monkeypatch
):
    root = _repo(tmp_path)
    counts: dict[int, int] = {}
    monkeypatch.setattr(
        "reverend.autonomy_v2.production.check_resources",
        lambda _root: SimpleNamespace(errors=(), warnings=()),
    )

    def factory(controller, _config):
        return _FlakyEngine(controller, counts)

    runner = ProductionRunner(
        root,
        config=ProductionConfig(
            repository="owner/repo",
            model="fake/model",
            ollama_model="fake-model",
            run_preflight=False,
            push_progress=False,
            max_issue_attempts=2,
            max_deferred_passes=1,
        ),
        queue_loader=lambda: (_issue(66), _issue(67)),
        engine_factory=factory,
    )

    result = runner.start()

    assert result.status == "COMPLETED"
    assert result.completed_issues == 2
    assert counts[66] == 3
    assert counts[67] == 1
    manifest = runner.status(result.session_id)
    assert manifest["deferred"] == []
    assert {item["issue"] for item in manifest["accepted"]} == {66, 67}
