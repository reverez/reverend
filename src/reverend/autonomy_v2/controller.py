from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from .context import ContextBuilder, IssuePacket
from .gitops import WorktreeInfo, WorktreeManager
from .state import IssuePhase, StateStore


@dataclass(frozen=True)
class IssueSpec:
    number: int
    milestone: str
    title: str


@dataclass(frozen=True)
class PreparedIssue:
    run_id: str
    issue: IssueSpec
    worktree: WorktreeInfo
    packet: IssuePacket
    packet_path: Path


class AutonomousController:
    """Durable outer controller for autonomous development.

    The model never owns run state, Git integration, or acceptance. This
    controller establishes crash-recoverable state, isolated per-run issue
    worktrees, and deterministic verified context packets before model work.
    """

    def __init__(self, repository_root: str | Path) -> None:
        self.repository_root = Path(repository_root).resolve()
        self.runtime_root = self.repository_root / ".autonomy"
        self.store = StateStore(self.runtime_root / "state" / "autonomy.db")
        self.worktrees = WorktreeManager(
            self.repository_root,
            runtime_root=self.repository_root / ".worktrees" / "autonomy-v2",
        )

    def initialize_run(
        self,
        *,
        queue: Iterable[IssueSpec],
        base_ref: str = "HEAD",
        run_id: str | None = None,
    ) -> str:
        issues = tuple(queue)
        if not issues:
            raise ValueError("queue must contain at least one issue")
        numbers = [issue.number for issue in issues]
        if len(numbers) != len(set(numbers)):
            raise ValueError("queue contains duplicate issue numbers")

        self.worktrees.assert_clean()
        base_commit = self.worktrees.head_commit(base_ref)
        resolved_run_id = run_id or f"run-{uuid.uuid4()}"
        self.store.create_run(
            run_id=resolved_run_id,
            base_commit=base_commit,
            queue=[asdict(issue) for issue in issues],
        )
        for issue in issues:
            self.store.add_issue(
                run_id=resolved_run_id,
                issue_number=issue.number,
                milestone=issue.milestone,
                title=issue.title,
                base_commit=base_commit,
            )
        self.store.record_event(
            run_id=resolved_run_id,
            kind="run_initialized",
            payload={"base_commit": base_commit, "issue_count": len(issues)},
        )
        return resolved_run_id

    def prepare_issue(
        self,
        *,
        run_id: str,
        issue: IssueSpec,
        requirements: Iterable[str],
        design_sources: Iterable[str],
        candidate_source_files: Iterable[str] = (),
        candidate_tests: Iterable[str] = (),
        acceptance: Iterable[str] = (),
    ) -> PreparedIssue:
        state = self.store.get_issue(run_id, issue.number)
        if state.phase is not IssuePhase.PENDING:
            raise RuntimeError(
                f"issue {issue.number} cannot be prepared from phase {state.phase}"
            )
        if state.title != issue.title or state.milestone != issue.milestone:
            raise ValueError("issue specification does not match persisted queue")

        short_run = _safe_run_key(run_id)
        branch_name = f"autonomy/v2-{short_run}-issue-{issue.number}"
        # The original v2 prototype keyed worktree paths only by issue number.
        # That made a crashed/stale run capable of blocking a later run of the
        # same issue. Namespace worktrees by durable run id while keeping Git
        # operations controlled by the shared manager.
        run_worktrees = WorktreeManager(
            self.repository_root,
            runtime_root=self.worktrees.runtime_root / short_run,
        )
        worktree = run_worktrees.create_issue_worktree(
            issue_number=issue.number,
            base_ref=state.base_commit,
            branch_name=branch_name,
        )
        try:
            builder = ContextBuilder(worktree.path)
            packet = builder.build(
                issue_number=issue.number,
                title=issue.title,
                milestone=issue.milestone,
                base_commit=state.base_commit,
                requirements=requirements,
                design_sources=design_sources,
                candidate_source_files=candidate_source_files,
                candidate_tests=candidate_tests,
                acceptance=acceptance,
            )
            packet_path = builder.write_atomic(
                packet,
                self.runtime_root / "packets" / run_id / f"issue-{issue.number}.json",
                destination_root=self.runtime_root,
            )
            self.store.mark_context_ready(
                run_id=run_id,
                issue_number=issue.number,
                worktree_path=str(worktree.path),
                branch_name=branch_name,
                packet_path=str(packet_path),
            )
        except Exception:
            try:
                run_worktrees.remove_worktree(worktree, force=True)
            finally:
                raise

        return PreparedIssue(
            run_id=run_id,
            issue=issue,
            worktree=worktree,
            packet=packet,
            packet_path=packet_path,
        )

    def heartbeat(self, run_id: str) -> None:
        self.store.heartbeat(run_id)


def _safe_run_key(run_id: str) -> str:
    """Produce a branch/path-safe stable short key without trusting run text."""
    import hashlib

    return hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:12]
