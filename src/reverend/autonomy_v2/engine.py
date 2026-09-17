from __future__ import annotations

import hashlib
import json
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
    planner_agent: str = "autonomy-v2-planner"
    implementer_agent: str = "autonomy-v2-implementer"
    reviewer_agent: str = "autonomy-v2-reviewer"
    planner_timeout_seconds: float = 600
    implement_timeout_seconds: float = 2700
    reviewer_timeout_seconds: float = 900
    max_planner_attempts: int = 2
    max_implement_attempts: int = 2
    max_review_attempts: int = 2
    max_repairs: int = 3

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
            if current.phase is IssuePhase.IMPLEMENTING or current.phase is IssuePhase.REPAIRING:
                self.controller.store.transition_issue(
                    run_id=run_id,
                    issue_number=issue_number,
                    target=IssuePhase.VERIFYING,
                )

            report = self.verifier.run(
                worktree=worktree,
                log_dir=logs / f"verify-{repair_number}",
                steps=default_verification_steps(
                    targeted_tests=self._targeted_tests(prepared, plan),
                ),
            )
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
                ):
                    if repair_number >= self.config.max_repairs:
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

            self.controller.store.transition_issue(
                run_id=run_id,
                issue_number=issue_number,
                target=IssuePhase.ACCEPTED,
                payload={"commit": commit},
            )
            self.controller.store.mark_accepted_commit(
                run_id=run_id,
                issue_number=issue_number,
                commit=commit,
            )
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
                self.controller.store.record_event(
                    run_id=prepared.run_id,
                    issue_number=prepared.issue.number,
                    kind="planner_attempt_no_result",
                    payload={"attempt": attempt_number},
                )
                prompt = self._planner_prompt(prepared) + (
                    "\n\nRECOVERY ATTEMPT: the previous planner process timed out or failed "
                    "before producing a valid plan. Be substantially more constrained now. "
                    "Do NOT repeat broad discovery. Do NOT use repository-wide Glob or Grep. "
                    "Use only paths already present in ISSUE_PACKET unless a single missing "
                    "fact makes planning impossible. Read at most two Design sources and two "
                    "candidate implementation/test files, then immediately return the required "
                    "AUTONOMY_PLAN_JSON_BEGIN / AUTONOMY_PLAN_JSON_END block."
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
            except (ModelProtocolError, ChangePolicyError, FileNotFoundError, FileExistsError, ValueError) as exc:
                self.controller.store.record_event(
                    run_id=prepared.run_id,
                    issue_number=prepared.issue.number,
                    kind="planner_protocol_rejected",
                    payload={"error": str(exc)},
                )
                prompt = self._planner_prompt(prepared) + (
                    "\n\nYour previous plan was rejected by the deterministic controller: "
                    f"{exc}. Return a corrected plan only after verifying every path."
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
        for attempt in range(1, self.config.max_implement_attempts + 1):
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
                    self.controller.store.record_event(
                        run_id=prepared.run_id,
                        issue_number=prepared.issue.number,
                        kind="implementation_policy_rejected",
                        payload={"error": str(exc)},
                    )
                    return False
                return True
            prompt = self._implementer_prompt(prepared, plan) + (
                "\n\nRECOVERY ATTEMPT: the previous session produced no new repository diff. "
                "Do not restate the plan. Use the ACTUAL native OpenCode Read/Edit/Write tools; "
                "do not print XML, <function=...>, <tool_call>, JSON tool calls, or other "
                "pseudo-tool syntax. Inspect the current files and make the required edits now."
            )
            self.controller.store.record_event(
                run_id=prepared.run_id,
                issue_number=prepared.issue.number,
                kind="implementation_no_progress",
                payload={"attempt": attempt},
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
            self.controller.store.record_event(
                run_id=prepared.run_id,
                issue_number=prepared.issue.number,
                kind="review_diff_too_large",
                payload={"error": str(exc)},
            )
            return None
        prompt = self._reviewer_prompt(prepared, plan, diff)
        for _ in range(self.config.max_review_attempts):
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
                self.controller.store.record_event(
                    run_id=prepared.run_id,
                    issue_number=prepared.issue.number,
                    kind="review_protocol_rejected",
                    payload={"error": str(exc)},
                )
                prompt = self._reviewer_prompt(prepared, plan, diff) + (
                    "\n\nYour previous verdict did not satisfy the required JSON protocol. "
                    f"Controller error: {exc}"
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
        try:
            result = self.runner.run(invocation)
        except Exception as exc:
            self.controller.store.finish_attempt(
                attempt.id,
                status="RUNTIME_ERROR",
                detail={"error": f"{type(exc).__name__}: {exc}"},
            )
            return None

        if result.timed_out:
            status = "TIMED_OUT"
        elif result.returncode != 0:
            status = "PROCESS_ERROR"
        else:
            status = "PROCESS_OK"
        self.controller.store.finish_attempt(
            attempt.id,
            status=status,
            detail={"returncode": result.returncode, "log_path": str(result.log_path)},
        )
        return result if result.succeeded else None

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
    def _planner_prompt(prepared: PreparedIssue) -> str:
        return (
            "Plan exactly one bounded Reverend issue. The deterministic controller has already "
            "resolved and validated every path supplied in ISSUE_PACKET.design_sources, "
            "candidate_source_files, and candidate_tests. Trust those paths. Do NOT glob or "
            "search merely to rediscover or verify them.\n\n"
            "STRICT PLANNING BUDGET:\n"
            "- Treat ISSUE_PACKET as the bounded planning surface.\n"
            "- Do not run repository-wide globs such as **/*.py.\n"
            "- Do not grep the whole repository for generic classes or symbols.\n"
            "- Select the most issue-relevant Design documents from design_sources; read no "
            "more than four unless a concrete conflict requires one additional document.\n"
            "- Inspect candidate source files directly instead of rediscovering them.\n"
            "- Use at most eight repository read/search operations.\n"
            "- Once the required implementation files and tests are known, STOP exploring.\n"
            "- Immediately return the exact AUTONOMY_PLAN_JSON_BEGIN / "
            "AUTONOMY_PLAN_JSON_END protocol required by the planner agent.\n"
            "- Do not implement anything during planning.\n\n"
            "ISSUE_PACKET:\n"
            + json.dumps(prepared.packet.as_dict(), indent=2, sort_keys=True)
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
            "Independently review the implementation for the active issue. Deterministic "
            "verification has already passed. Return the required review JSON protocol.\n\n"
            "ISSUE_PACKET:\n"
            + json.dumps(prepared.packet.as_dict(), indent=2, sort_keys=True)
            + "\n\nVALIDATED_PLAN:\n"
            + json.dumps(plan, indent=2, sort_keys=True)
            + "\n\nVERIFIED_DIFF:\n"
            + diff
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
        return IssueOutcome(issue_number, phase, reason=reason)
