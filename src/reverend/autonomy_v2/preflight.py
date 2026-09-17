from __future__ import annotations

import json
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

from .execution import (
    AgentInvocation,
    ModelProtocolError,
    OpenCodeRunner,
    parse_marker_json,
    validate_plan_payload,
)
from .gitops import GitCommandError, WorktreeManager
from .resources import ResourceCheck, ResourcePolicy, check_resources


@dataclass(frozen=True)
class PreflightReport:
    passed: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    log_paths: tuple[Path, ...]
    resource_check: ResourceCheck


class ModelPreflight:
    """Prove the local model can actually read and edit through OpenCode.

    Capability metadata is not trusted. The preflight creates a disposable Git
    worktree, requires a planner read/tool pass, then requires the implementer to
    create one exact canary file and nothing else.
    """

    CANARY_NAME = "autonomy_v2_canary.txt"
    CANARY_CONTENT = "AUTONOMY_V2_CANARY\n"

    def __init__(
        self,
        repository_root: str | Path,
        *,
        opencode_model: str,
        ollama_model: str,
        runner: OpenCodeRunner | None = None,
        resource_policy: ResourcePolicy | None = None,
    ) -> None:
        self.repository_root = Path(repository_root).resolve()
        self.opencode_model = opencode_model
        self.ollama_model = ollama_model
        self.runner = runner or OpenCodeRunner()
        self.resource_policy = resource_policy or ResourcePolicy()
        self.runtime_root = self.repository_root / ".autonomy" / "preflight"
        self.worktrees = WorktreeManager(
            self.repository_root,
            runtime_root=self.repository_root / ".worktrees" / "autonomy-v2-preflight",
        )

    def _planner_prompt(self) -> str:
        return (
            "This is a READ-ONLY planner canary for Reverend autonomy v2. "
            "Use native repository READ tools to read README.md. Planning only: DO NOT create, "
            "edit, write, verify, search for, or otherwise act on the canary file. The canary "
            "file intentionally does not exist yet and will be created later by a separate "
            "implementer stage. After reading README.md, stop all repository exploration and "
            "immediately return the required plan JSON protocol. In that future plan, set "
            "files_to_create to exactly "
            f"[{self.CANARY_NAME!r}], set files_to_modify and tests_to_add_or_modify to empty "
            "lists, include exactly one acceptance check saying the canary content must match, "
            "and return no risks. Do not perform the plan."
        )

    def run(self, *, base_ref: str = "HEAD") -> PreflightReport:
        resource_check = check_resources(
            self.repository_root,
            policy=self.resource_policy,
        )
        errors = list(resource_check.errors)
        warnings = list(resource_check.warnings)
        logs: list[Path] = []
        if errors:
            return PreflightReport(False, tuple(errors), tuple(warnings), (), resource_check)

        ollama_error = self._check_ollama_model()
        if ollama_error:
            errors.append(ollama_error)
            return PreflightReport(False, tuple(errors), tuple(warnings), (), resource_check)

        token = uuid.uuid4().hex[:10]
        synthetic_issue = 900_000_000 + (int(token[:6], 16) % 90_000_000)
        branch = f"autonomy/v2-preflight-{token}"
        worktree = None
        try:
            worktree = self.worktrees.create_issue_worktree(
                issue_number=synthetic_issue,
                base_ref=base_ref,
                branch_name=branch,
            )

            plan = None
            planner_error = None
            planner_prompt = self._planner_prompt()

            for planner_attempt in range(1, 3):
                planner_log = (
                    self.runtime_root
                    / token
                    / f"planner-{planner_attempt}.log"
                )
                planner_result = self.runner.run(
                    AgentInvocation(
                        kind=f"preflight-plan-{planner_attempt}",
                        agent="autonomy-v2-planner",
                        model=self.opencode_model,
                        prompt=planner_prompt,
                        worktree=worktree.path,
                        timeout_seconds=600,
                        log_path=planner_log,
                    )
                )
                logs.append(planner_log)

                if not planner_result.succeeded:
                    planner_error = (
                        "OpenCode planner preflight failed "
                        f"(returncode={planner_result.returncode}, "
                        f"timeout={planner_result.timed_out})"
                    )
                    continue

                planner_changes = self.worktrees.changed_files(
                    worktree.path, worktree.base_ref
                )
                if planner_changes:
                    errors.append(
                        "read-only planner modified repository files during preflight: "
                        f"{planner_changes!r}"
                    )
                    return PreflightReport(
                        False, tuple(errors), tuple(warnings), tuple(logs), resource_check
                    )

                try:
                    payload = parse_marker_json(
                        planner_result.output,
                        "AUTONOMY_PLAN_JSON_BEGIN",
                        "AUTONOMY_PLAN_JSON_END",
                    )
                    plan = validate_plan_payload(payload)
                    break
                except ModelProtocolError as exc:
                    planner_error = f"planner tool/protocol canary failed: {exc}"
                    planner_prompt = self._planner_prompt() + (
                        "\n\nRECOVERY ATTEMPT: The previous response was rejected. "
                        "You emitted or described tool-call syntax instead of completing "
                        "the native OpenCode tool interaction and required protocol. "
                        "Do NOT print XML, <function=...>, <tool_call>, JSON tool calls, "
                        "or pseudo-tool syntax. Invoke the actual native Read tool exposed "
                        "by OpenCode. After the real tool result returns, immediately output "
                        "the exact AUTONOMY_PLAN_JSON_BEGIN / AUTONOMY_PLAN_JSON_END block."
                    )

            if plan is None:
                errors.append(planner_error or "planner preflight exhausted attempts")
                return PreflightReport(
                    False, tuple(errors), tuple(warnings), tuple(logs), resource_check
                )
            if plan["files_to_create"] != [self.CANARY_NAME]:
                errors.append(
                    "planner canary returned unexpected files_to_create: "
                    f"{plan['files_to_create']!r}"
                )
                return PreflightReport(
                    False, tuple(errors), tuple(warnings), tuple(logs), resource_check
                )

            implement_log = self.runtime_root / token / "implementer.log"
            implement_result = self.runner.run(
                AgentInvocation(
                    kind="preflight-implement",
                    agent="autonomy-v2-implementer",
                    model=self.opencode_model,
                    prompt=(
                        "This is a disposable autonomy preflight. Create exactly one repository "
                        f"file named {self.CANARY_NAME} with exact content:\n"
                        f"{self.CANARY_CONTENT}"
                        "Do not change any other file. Do not merely describe the edit."
                    ),
                    worktree=worktree.path,
                    timeout_seconds=600,
                    log_path=implement_log,
                )
            )
            logs.append(implement_log)
            if not implement_result.succeeded:
                errors.append(
                    "OpenCode implementer preflight failed "
                    f"(returncode={implement_result.returncode}, timeout={implement_result.timed_out})"
                )
                return PreflightReport(
                    False, tuple(errors), tuple(warnings), tuple(logs), resource_check
                )

            changed = self.worktrees.changed_files(worktree.path, worktree.base_ref)
            if changed != (self.CANARY_NAME,):
                errors.append(f"implementer canary changed unexpected files: {changed!r}")
                return PreflightReport(
                    False, tuple(errors), tuple(warnings), tuple(logs), resource_check
                )
            canary = worktree.path / self.CANARY_NAME
            if not canary.is_file():
                errors.append("implementer canary file was not created")
                return PreflightReport(
                    False, tuple(errors), tuple(warnings), tuple(logs), resource_check
                )

            canary_bytes = canary.read_bytes()
            expected = self.CANARY_CONTENT.encode("utf-8")
            accepted_contents = {
                expected,
                expected.rstrip(b"\n"),
            }
            if canary_bytes not in accepted_contents:
                errors.append(
                    "implementer canary content did not match sentinel "
                    f"(got={canary_bytes!r})"
                )
                return PreflightReport(
                    False, tuple(errors), tuple(warnings), tuple(logs), resource_check
                )
        except (GitCommandError, OSError, ValueError) as exc:
            errors.append(f"preflight infrastructure error: {type(exc).__name__}: {exc}")
        finally:
            if worktree is not None:
                try:
                    self.worktrees.remove_worktree(worktree, force=True)
                except Exception as exc:  # cleanup failure must be visible but not mask root cause
                    warnings.append(f"preflight worktree cleanup failed: {exc}")
                try:
                    self.worktrees.delete_branch(branch, force=True)
                except Exception as exc:
                    warnings.append(f"preflight branch cleanup failed: {exc}")

        return PreflightReport(
            not errors,
            tuple(errors),
            tuple(warnings),
            tuple(logs),
            resource_check,
        )

    def _check_ollama_model(self) -> str | None:
        try:
            completed = subprocess.run(
                ["ollama", "show", self.ollama_model],
                cwd=self.repository_root,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return f"unable to query Ollama model {self.ollama_model!r}: {exc}"
        if completed.returncode != 0:
            detail = completed.stderr.strip()[-1000:]
            return f"Ollama model {self.ollama_model!r} is unavailable: {detail}"
        return None
