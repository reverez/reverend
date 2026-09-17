from __future__ import annotations

import pytest

from reverend.autonomy_v2.state import IssuePhase, StateStore, TransitionError


def _store(tmp_path):
    store = StateStore(tmp_path / "state" / "autonomy.db")
    store.create_run(
        run_id="run-test",
        base_commit="a" * 40,
        queue=[{"number": 66, "milestone": "C0", "title": "Common IDs"}],
    )
    store.add_issue(
        run_id="run-test",
        issue_number=66,
        milestone="C0",
        title="Common IDs",
        base_commit="a" * 40,
    )
    return store


def test_state_survives_reopen_and_enforces_transition_graph(tmp_path):
    store = _store(tmp_path)
    state = store.mark_context_ready(
        run_id="run-test",
        issue_number=66,
        worktree_path="/tmp/issue-66",
        branch_name="autonomy/issue-66",
        packet_path="/tmp/packet.json",
    )
    assert state.phase is IssuePhase.CONTEXT_READY
    assert state.packet_path == "/tmp/packet.json"

    reopened = StateStore(tmp_path / "state" / "autonomy.db")
    restored = reopened.get_issue("run-test", 66)
    assert restored.phase is IssuePhase.CONTEXT_READY
    assert restored.worktree_path == "/tmp/issue-66"

    with pytest.raises(TransitionError):
        reopened.transition_issue(
            run_id="run-test",
            issue_number=66,
            target=IssuePhase.ACCEPTED,
        )


def test_acceptance_requires_full_controller_owned_path(tmp_path):
    store = _store(tmp_path)
    store.mark_context_ready(
        run_id="run-test",
        issue_number=66,
        worktree_path="/tmp/issue-66",
        branch_name="autonomy/issue-66",
        packet_path="/tmp/packet.json",
    )

    for phase in (
        IssuePhase.PLANNED,
        IssuePhase.IMPLEMENTING,
        IssuePhase.VERIFYING,
        IssuePhase.REVIEWING,
        IssuePhase.ACCEPTED,
    ):
        store.transition_issue(
            run_id="run-test",
            issue_number=66,
            target=phase,
        )

    store.mark_accepted_commit(
        run_id="run-test",
        issue_number=66,
        commit="b" * 40,
    )
    final = store.get_issue("run-test", 66)
    assert final.phase is IssuePhase.ACCEPTED
    assert final.accepted_commit == "b" * 40

    with pytest.raises(TransitionError):
        store.transition_issue(
            run_id="run-test",
            issue_number=66,
            target=IssuePhase.REPAIRING,
        )


def test_attempts_are_numbered_and_finished_once(tmp_path):
    store = _store(tmp_path)
    first = store.start_attempt(
        run_id="run-test",
        issue_number=66,
        kind="implement",
        model="qwen3-coder:30b",
    )
    second = store.start_attempt(
        run_id="run-test",
        issue_number=66,
        kind="implement",
        model="qwen3-coder:30b",
    )
    assert (first.ordinal, second.ordinal) == (1, 2)
    assert store.get_issue("run-test", 66).attempt_count == 2

    finished = store.finish_attempt(first.id, status="FAILED", detail={"reason": "timeout"})
    assert finished.status == "FAILED"
    assert finished.detail == {"reason": "timeout"}

    with pytest.raises(KeyError):
        store.finish_attempt(first.id, status="FAILED")
