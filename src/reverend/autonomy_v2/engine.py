from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .controller import AutonomousController, PreparedIssue
from .execution import (
    AgentInvocation,
    AgentResult,
    ModelProtocolError,
    OpenCodeRunner,
    parse_marker_json,
    validate_plan_payload,
    validate_review_payload,
)
from .gitops import DiffTooLarge, GitCommandError
from .policy import ChangePolicy, ChangePolicyError
from .state import IssuePhase
from .verify import Verifier, default_verification_steps


@dataclass(frozen=True)
class EngineConfig:
    model: str
    planner_agent: str = "autonomy-v2-planner-bounded"
    implementer_agent: str = "autonomy-v2-implementer"
    reviewer_agent: str = "autonomy-v2-reviewer-bounded"
    planner_timeout_seconds: float = 600
    implement_timeout_seconds: float = 2700
    reviewer_timeout_seconds: float = 900
    max_planner_attempts: int = 2
    max_implement_attempts: int = 2
    max_review_attempts: int = 2
    max_repairs: int = 3
    heartbeat_interval_seconds: float = 15

    def __post_init__(self) -> None:
        if not self.model.strip():
            raise ValueError("model must not be empty")
        for name in (
            "max_planner_attempts",
            "max_implement_attempts",
            "max_review_attempts",
            "max_repairs",
        ):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be at least 1")
        if self.heartbeat_interval_seconds <= 0:
            raise ValueError("heartbeat_interval_seconds must be positive")


@dataclass(frozen=True)
class IssueOutcome:
    issue_number: int
    phase: IssuePhase
    commit: str | None = None
    reason: str | None = None

    @property
    def accepted(self) -> bool:
        return self.phase is IssuePhase.ACCEPTED


class IssueEngine:
    """Execute one prepared issue while deterministic code owns every gate."""

    def __init__(
        self,
        controller: AutonomousController,
        *,
        config: EngineConfig,
        runner: OpenCodeRunner | None = None,
        verifier: Verifier | None = None,
    ) -> None:
        self.controller = controller
        self.config = config
        self.runner = runner or OpenCodeRunner()
        self.verifier = verifier or Verifier(fail_fast=True)

    def run(self, prepared: PreparedIssue) -> IssueOutcome:
        run_id = prepared.run_id
        issue_number = prepared.issue.number
        worktree = prepared.worktree.path
        base_ref = prepared.worktree.base_ref
        logs = (
            self.controller.runtime_root
            / "logs"
            / run_id
            / f"issue-{issue_number}"
        )
        logs.mkdir(parents=True, exist_ok=True)
        policy = ChangePolicy(worktree)

        state = self.controller.store.get_issue(run_id, issue_number)
        if state.phase is not IssuePhase.CONTEXT_READY:
            raise RuntimeError(f"issue must start in CONTEXT_READY, got {state.phase}")

        self._event(prepared, "engine_started", {"worktree": str(worktree)})
        plan = self._plan(prepared, policy, logs)
        if plan is None:
            return self._terminal(
                run_id,
                issue_number,
                IssuePhase.BLOCKED,
                "planner failed to produce a valid bounded plan",
            )

        self.controller.store.transition_issue(
            run_id=run_id,
            issue_number=issue_number,
            target=IssuePhase.PLANNED,
            payload={"plan": plan},
        )
        policy.prepare_plan_directories(plan)
        self.controller.store.transition_issue(
            run_id=run_id,
            issue_number=issue_number,
            target=IssuePhase.IMPLEMENTING,
        )

        implementation_ok = self._implement(prepared, plan, policy, logs)
        if not implementation_ok:
            return self._terminal(
                run_id,
                issue_number,
                IssuePhase.QUARANTINED,
                "implementation attempts exhausted without a valid diff",
            )

        repair_number = 0
        while True:
            try:
                changed = self.controller.worktrees.changed_files(worktree, base_ref)
                policy.validate_changed_files(changed)
            except (ChangePolicyError, FileNotFoundError, ValueError) as exc:
                return self._terminal(
                    run_id,
                    issue_number,
                    IssuePhase.QUARANTINED,
                    f"change policy rejected implementation: {exc}",
                )

            current = self.controller.store.get_issue(run_id, issue_number)
            if current.phase in {IssuePhase.IMPLEMENTING, IssuePhase.REPAIRING}:
                self.controller.store.transition_issue(
                    run_id=run_id,
                    issue_number=issue_number,
                    target=IssuePhase.VERIFYING,
                )

            self.controller.heartbeat(run_id)
            self._event(
                prepared,
                "verification_started",
                {"repair_number": repair_number, "changed_files": list(changed)},
            )
            report = self.verifier.run(
                worktree=worktree,
                log_dir=logs / f"verify-{repair_number}",
                steps=default_verification_steps(
                    targeted_tests=self._targeted_tests(prepared, plan),
                ),
            )
            self.controller.heartbeat(run_id)
            if not report.passed:
                if repair_number >= self.config.max_repairs:
                    return self._terminal(
                        run_id,
                        issue_number,
                        IssuePhase.QUARANTINED,
                        f"verification still failing after {repair_number} repairs",
                    )
                failed = report.failed_step
                assert failed is not None
                self.controller.store.transition_issue(
                    run_id=run_id,
                    issue_number=issue_number,
                    target=IssuePhase.REPAIRING,
                    payload={"failed_step": failed.name},
                )
                repair_number += 1
                if not self._repair(
                    prepared,
                    plan,
                    policy,
                    logs,
                    repair_number,
                    reason=self._verification_failure_text(failed),
                ) and repair_number >= self.config.max_repairs:
                    return self._terminal(
                        run_id,
                        issue_number,
                        IssuePhase.QUARANTINED,
                        "repair attempts made no progress",
                    )
                continue

            self.controller.store.transition_issue(
                run_id=run_id,
                issue_number=issue_number,
                target=IssuePhase.REVIEWING,
            )

            review = self._review(prepared, plan, logs)
            if review is None:
                return self._terminal(
                    run_id,
                    issue_number,
                    IssuePhase.HUMAN_REVIEW_REQUIRED,
                    "reviewer failed to produce a valid verdict",
                )
            verdict, defects = review
            if verdict == "FAIL":
                if repair_number >= self.config.max_repairs:
                    return self._terminal(
                        run_id,
                        issue_number,
                        IssuePhase.HUMAN_REVIEW_REQUIRED,
                        "review defects remain after repair budget",
                    )
                self.controller.store.transition_issue(
                    run_id=run_id,
                    issue_number=issue_number,
                    target=IssuePhase.REPAIRING,
                    payload={"defects": defects},
                )
                repair_number += 1
                self._repair(
                    prepared,
                    plan,
                    policy,
                    logs,
                    repair_number,
                    reason=json.dumps(defects, indent=2, sort_keys=True),
                )
                continue

            try:
                commit = self.controller.worktrees.commit_changes(
                    worktree,
                    message=(
                        f"feat({prepared.issue.milestone.lower()}): "
                        f"{prepared.issue.title} (#{issue_number})"
                    ),
                )
            except GitCommandError as exc:
                return self._terminal(
                    run_id,
                    issue_number,
                    IssuePhase.HUMAN_REVIEW_REQUIRED,
                    f"controller commit failed: {exc}",
                )

            # ACCEPTED and accepted_commit are one SQLite transaction. A process
            # crash can no longer leave an ACCEPTED issue without its commit.
            self.controller.store.accept_issue(
                run_id=run_id,
                issue_number=issue_number,
                commit=commit,
            )
            self.controller.store.set_run_status(run_id, "COMPLETED")
            self._event(prepared, "issue_accepted", {"commit": commit})
            return IssueOutcome(issue_number, IssuePhase.ACCEPTED, commit=commit)

    def _plan(
        self,
        prepared: PreparedIssue,
        policy: ChangePolicy,
        logs: Path,
    ) -> dict[str, list[str]] | None:
        prompt = self._planner_prompt(prepared)
        for attempt_number in range(1, self.config.max_planner_attempts + 1):
            result = self._invoke(
                prepared,
                kind="plan",
                agent=self.config.planner_agent,
                prompt=prompt,
                timeout_seconds=self.config.planner_timeout_seconds,
                logs=logs,
            )
            if result is None:
                self._event(
                    prepared,
                    "planner_attempt_no_result",
                    {"attempt": attempt_number},
                )
                prompt = self._planner_prompt(prepared) + (
                    "\n\nRECOVERY ATTEMPT: the previous planner process timed out or failed. "
                    "Do not call any repository tools. All evidence is already embedded in "
                    "BOUNDED_CONTEXT. Immediately return the required plan protocol."
                )
                continue
            try:
                payload = parse_marker_json(
                    result.output,
                    "AUTONOMY_PLAN_JSON_BEGIN",
                    "AUTONOMY_PLAN_JSON_END",
                )
                plan = validate_plan_payload(payload)
                return policy.validate_plan(plan)
            except (
                ModelProtocolError,
                ChangePolicyError,
                FileNotFoundError,
                FileExistsError,
                ValueError,
            ) as exc:
                self._event(
                    prepared,
                    "planner_protocol_rejected",
                    {"error": str(exc), "attempt": attempt_number},
                )
                prompt = self._planner_prompt(prepared) + (
                    "\n\nThe deterministic controller rejected the previous plan: "
                    f"{exc}. Do not call tools. Correct the JSON plan using only the "
                    "controller-supplied paths and BOUNDED_CONTEXT."
                )
        return None

    def _implement(
        self,
        prepared: PreparedIssue,
        plan: dict[str, list[str]],
        policy: ChangePolicy,
        logs: Path,
    ) -> bool:
        prompt = self._implementer_prompt(prepared, plan)
        for attempt_number in range(1, self.config.max_implement_attempts + 1):
            before = self._diff_fingerprint(prepared)
            result = self._invoke(
                prepared,
                kind="implement",
                agent=self.config.implementer_agent,
                prompt=prompt,
                timeout_seconds=self.config.implement_timeout_seconds,
                logs=logs,
            )
            after = self._diff_fingerprint(prepared)
            if result is not None and after != before:
                try:
                    changed = self.controller.worktrees.changed_files(
                        prepared.worktree.path, prepared.worktree.base_ref
                    )
                    policy.validate_changed_files(changed)
                except (ChangePolicyError, ValueError) as exc:
                    self._event(
                        prepared,
                        "implementation_policy_rejected",
                        {"error": str(exc)},
                    )
                    return False
                return True
            prompt = self._implementer_prompt(prepared, plan) + (
                "\n\nRECOVERY ATTEMPT: the previous session produced no new repository diff. "
                "Do not restate the plan. Use the ACTUAL native OpenCode Read/Edit/Write tools; "
                "do not print XML, <function=...>, <tool_call>, JSON tool calls, or other "
                "pseudo-tool syntax. Inspect the planned files and make the required edits now."
            )
            self._event(
                prepared,
                "implementation_no_progress",
                {"attempt": attempt_number},
            )
        return False

    def _repair(
        self,
        prepared: PreparedIssue,
        plan: dict[str, list[str]],
        policy: ChangePolicy,
        logs: Path,
        repair_number: int,
        *,
        reason: str,
    ) -> bool:
        before = self._diff_fingerprint(prepared)
        prompt = self._implementer_prompt(prepared, plan) + (
            "\n\nThe deterministic controller rejected the current implementation. "
            "Repair the existing worktree; do not revert valid changes.\n\n"
            f"FAILURE EVIDENCE:\n{reason[-16000:]}"
        )
        result = self._invoke(
            prepared,
            kind=f"repair-{repair_number}",
            agent=self.config.implementer_agent,
            prompt=prompt,
            timeout_seconds=self.config.implement_timeout_seconds,
            logs=logs,
        )
        after = self._diff_fingerprint(prepared)
        if result is None or before == after:
            return False
        try:
            policy.validate_changed_files(
                self.controller.worktrees.changed_files(
                    prepared.worktree.path, prepared.worktree.base_ref
                )
            )
        except (ChangePolicyError, ValueError):
            return False
        return True

    def _review(
        self,
        prepared: PreparedIssue,
        plan: dict[str, list[str]],
        logs: Path,
    ) -> tuple[str, list[dict[str, object]]] | None:
        try:
            diff = self.controller.worktrees.diff_text(
                prepared.worktree.path, prepared.worktree.base_ref
            )
        except DiffTooLarge as exc:
            self._event(prepared, "review_diff_too_large", {"error": str(exc)})
            return None
        prompt = self._reviewer_prompt(prepared, plan, diff)
        for attempt_number in range(1, self.config.max_review_attempts + 1):
            result = self._invoke(
                prepared,
                kind="review",
                agent=self.config.reviewer_agent,
                prompt=prompt,
                timeout_seconds=self.config.reviewer_timeout_seconds,
                logs=logs,
            )
            if result is None:
                continue
            try:
                payload = parse_marker_json(
                    result.output,
                    "AUTONOMY_REVIEW_JSON_BEGIN",
                    "AUTONOMY_REVIEW_JSON_END",
                )
                return validate_review_payload(payload)
            except ModelProtocolError as exc:
                self._event(
                    prepared,
                    "review_protocol_rejected",
                    {"error": str(exc), "attempt": attempt_number},
                )
                prompt = self._reviewer_prompt(prepared, plan, diff) + (
                    "\n\nThe previous verdict violated the JSON protocol. Do not call tools. "
                    f"Controller error: {exc}. Return a corrected verdict immediately."
                )
        return None

    def _invoke(
        self,
        prepared: PreparedIssue,
        *,
        kind: str,
        agent: str,
        prompt: str,
        timeout_seconds: float,
        logs: Path,
    ) -> AgentResult | None:
        attempt = self.controller.store.start_attempt(
            run_id=prepared.run_id,
            issue_number=prepared.issue.number,
            kind=kind,
            model=self.config.model,
        )
        invocation = AgentInvocation(
            kind=kind,
            agent=agent,
            model=self.config.model,
            prompt=prompt,
            worktree=prepared.worktree.path,
            timeout_seconds=timeout_seconds,
            log_path=logs / f"{kind}-{attempt.ordinal}.log",
        )
        self.controller.heartbeat(prepared.run_id)
        stop = threading.Event()
        heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            args=(prepared.run_id, stop),
            name=f"autonomy-heartbeat-{kind}",
            daemon=True,
        )
        heartbeat_thread.start()
        try:
            result = self.runner.run(invocation)
        except Exception as exc:
            self.controller.store.finish_attempt(
                attempt.id,
                status="RUNTIME_ERROR",
                detail={"error": f"{type(exc).__name__}: {exc}"},
            )
            self._event(
                prepared,
                "agent_runtime_error",
                {"kind": kind, "error": f"{type(exc).__name__}: {exc}"},
            )
            return None
        finally:
            stop.set()
            heartbeat_thread.join(timeout=2)
            try:
                self.controller.heartbeat(prepared.run_id)
            except Exception:
                pass

        if result.timed_out:
            status = "TIMED_OUT"
        elif result.stalled:
            status = "STALLED"
        elif result.returncode != 0:
            status = "PROCESS_ERROR"
        else:
            status = "PROCESS_OK"
        self.controller.store.finish_attempt(
            attempt.id,
            status=status,
            detail={
                "returncode": result.returncode,
                "timed_out": result.timed_out,
                "stalled": result.stalled,
                "log_path": str(result.log_path),
            },
        )
        return result if result.succeeded else None

    def _heartbeat_loop(self, run_id: str, stop: threading.Event) -> None:
        while not stop.wait(self.config.heartbeat_interval_seconds):
            try:
                self.controller.heartbeat(run_id)
            except Exception:
                # Heartbeat telemetry must never terminate an otherwise healthy agent.
                return

    def _diff_fingerprint(self, prepared: PreparedIssue) -> str:
        try:
            diff = self.controller.worktrees.diff_text(
                prepared.worktree.path,
                prepared.worktree.base_ref,
                max_chars=2_000_000,
                max_untracked_file_bytes=1_000_000,
            )
        except DiffTooLarge:
            changed = self.controller.worktrees.changed_files(
                prepared.worktree.path, prepared.worktree.base_ref
            )
            diff = "\n".join(changed)
        return hashlib.sha256(diff.encode("utf-8", errors="replace")).hexdigest()

    @staticmethod
    def _targeted_tests(
        prepared: PreparedIssue, plan: dict[str, list[str]]
    ) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                [
                    *prepared.packet.candidate_tests,
                    *plan["tests_to_add_or_modify"],
                ]
            )
        )

    @staticmethod
    def _verification_failure_text(failed) -> str:
        try:
            log = failed.log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            log = "<verification log unavailable>"
        return (
            f"Verification step {failed.name!r} failed; "
            f"returncode={failed.returncode}, timed_out={failed.timed_out}.\n"
            f"LOG TAIL:\n{log[-16000:]}"
        )

    @staticmethod
    def _bounded_context(prepared: PreparedIssue) -> str:
        root = prepared.worktree.path.resolve()
        entries: list[tuple[str, str, int]] = []
        entries.extend(("DESIGN", path, 3200) for path in prepared.packet.design_sources)
        entries.extend(("SOURCE", path, 4500) for path in prepared.packet.candidate_source_files)
        entries.extend(("TEST", path, 2400) for path in prepared.packet.candidate_tests[:4])

        chunks: list[str] = []
        total_chars = 0
        max_total_chars = 36000
        for kind, relative, per_file_limit in entries:
            path = (root / relative).resolve()
            try:
                path.relative_to(root)
            except ValueError:
                continue
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if len(text) > per_file_limit:
                head = (per_file_limit * 2) // 3
                tail = per_file_limit - head
                text = (
                    text[:head]
                    + "\n...[controller excerpt truncated]...\n"
                    + text[-tail:]
                )
            remaining = max_total_chars - total_chars
            if remaining <= 0:
                break
            if len(text) > remaining:
                text = text[:remaining] + "\n...[context budget exhausted]..."
            chunks.append(f"--- {kind}: {relative} ---\n{text}")
            total_chars += len(text)
        return "\n\n".join(chunks)

    @staticmethod
    def _planner_prompt(prepared: PreparedIssue) -> str:
        return (
            "ZERO-TOOL PLANNING MODE. Plan exactly one bounded Reverend issue. The "
            "deterministic controller already performed repository discovery and validated "
            "the supplied paths. Do not call any tool or search for additional files.\n\n"
            "Use only ISSUE_PACKET and BOUNDED_CONTEXT. A genuinely new path may be proposed "
            "only under files_to_create. If a new test file is proposed, include it in both "
            "files_to_create and tests_to_add_or_modify. Determine the smallest complete "
            "implementation surface, then immediately return the exact required plan JSON.\n\n"
            "ISSUE_PACKET:\n"
            + json.dumps(prepared.packet.as_dict(), indent=2, sort_keys=True)
            + "\n\nBOUNDED_CONTEXT:\n"
            + IssueEngine._bounded_context(prepared)
        )

    @staticmethod
    def _implementer_prompt(
        prepared: PreparedIssue, plan: dict[str, list[str]]
    ) -> str:
        return (
            "Implement exactly one bounded Reverend issue now. Make repository edits; do not "
            "only describe them. The controller will run all tests and decide acceptance.\n\n"
            "ISSUE_PACKET:\n"
            + json.dumps(prepared.packet.as_dict(), indent=2, sort_keys=True)
            + "\n\nVALIDATED_PLAN:\n"
            + json.dumps(plan, indent=2, sort_keys=True)
        )

    @staticmethod
    def _reviewer_prompt(
        prepared: PreparedIssue,
        plan: dict[str, list[str]],
        diff: str,
    ) -> str:
        return (
            "ZERO-TOOL REVIEW MODE. Independently review the verified implementation for the "
            "active issue. Do not call repository tools. Deterministic verification already "
            "passed; use only the supplied requirements, bounded context, plan, and diff. "
            "Return the required review JSON protocol immediately.\n\n"
            "ISSUE_PACKET:\n"
            + json.dumps(prepared.packet.as_dict(), indent=2, sort_keys=True)
            + "\n\nBOUNDED_CONTEXT:\n"
            + IssueEngine._bounded_context(prepared)
            + "\n\nVALIDATED_PLAN:\n"
            + json.dumps(plan, indent=2, sort_keys=True)
            + "\n\nVERIFIED_DIFF:\n"
            + diff
        )

    def _event(
        self,
        prepared: PreparedIssue,
        kind: str,
        payload: dict[str, object],
    ) -> None:
        self.controller.store.record_event(
            run_id=prepared.run_id,
            issue_number=prepared.issue.number,
            kind=kind,
            payload=dict(payload),
        )

    def _terminal(
        self,
        run_id: str,
        issue_number: int,
        phase: IssuePhase,
        reason: str,
    ) -> IssueOutcome:
        current = self.controller.store.get_issue(run_id, issue_number)
        if current.phase is not phase:
            self.controller.store.transition_issue(
                run_id=run_id,
                issue_number=issue_number,
                target=phase,
                payload={"reason": reason},
            )
        self.controller.store.set_run_status(run_id, phase.value)
        return IssueOutcome(issue_number, phase, reason=reason)
