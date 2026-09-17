from __future__ import annotations

import fcntl
import json
import os
import re
import subprocess
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Iterable, Sequence

from .controller import AutonomousController, IssueSpec
from .engine import EngineConfig, IssueEngine, IssueOutcome
from .preflight import ModelPreflight
from .queue import GitHubIssueQueue, QueuedIssue
from .state import IssuePhase, TERMINAL_PHASES
from .verify import VerificationStep, Verifier, default_verification_steps


class ProductionRunError(RuntimeError):
    pass


class ProductionRunLocked(ProductionRunError):
    pass


@dataclass(frozen=True)
class ProductionConfig:
    repository: str
    model: str = "ollama/reverend-coder30"
    ollama_model: str = "reverend-coder30"
    base_ref: str = "HEAD"
    include_alex: bool = False
    max_repairs: int = 3
    max_issues: int | None = None
    run_preflight: bool = True
    milestone_gate_timeout_seconds: float = 3600

    def __post_init__(self) -> None:
        if not self.repository.strip() or "/" not in self.repository:
            raise ValueError("repository must be in owner/name form")
        if not self.model.strip():
            raise ValueError("model must not be empty")
        if not self.ollama_model.strip():
            raise ValueError("ollama_model must not be empty")
        if self.max_repairs < 1:
            raise ValueError("max_repairs must be at least 1")
        if self.max_issues is not None and self.max_issues < 1:
            raise ValueError("max_issues must be positive")
        if self.milestone_gate_timeout_seconds <= 0:
            raise ValueError("milestone gate timeout must be positive")


@dataclass(frozen=True)
class ResolvedIssueContext:
    requirements: tuple[str, ...]
    design_sources: tuple[str, ...]
    candidate_source_files: tuple[str, ...]
    candidate_tests: tuple[str, ...]
    acceptance: tuple[str, ...]


@dataclass(frozen=True)
class ProductionResult:
    session_id: str
    status: str
    completed_issues: int
    total_issues: int
    integration_branch: str
    integration_head: str | None
    stop_reason: str | None = None


class ProductionLock:
    """Single-host lock preventing two production controllers from sharing worktrees."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = None

    def __enter__(self) -> "ProductionLock":
        handle = self.path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            handle.close()
            raise ProductionRunLocked(
                f"another autonomy v2 production controller owns {self.path}"
            ) from exc
        handle.seek(0)
        handle.truncate()
        handle.write(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "acquired_at": datetime.now(UTC).isoformat(),
                },
                sort_keys=True,
            )
            + "\n"
        )
        handle.flush()
        os.fsync(handle.fileno())
        self._handle = handle
        return self

    def __exit__(self, *_args: object) -> None:
        if self._handle is None:
            return
        try:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        finally:
            self._handle.close()
            self._handle = None


class SessionStore:
    """Atomic durable session manifests around the issue-level SQLite state."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.sessions = self.root / "sessions"
        self.sessions.mkdir(parents=True, exist_ok=True)
        self.latest_path = self.root / "latest-session"

    def path(self, session_id: str) -> Path:
        _validate_session_id(session_id)
        return self.sessions / f"{session_id}.json"

    def create(self, payload: dict[str, object]) -> dict[str, object]:
        session_id = str(payload["session_id"])
        path = self.path(session_id)
        if path.exists():
            raise FileExistsError(path)
        now = datetime.now(UTC).isoformat()
        document = {**payload, "created_at": now, "updated_at": now}
        self.save(document)
        _atomic_write_text(self.latest_path, session_id + "\n")
        return document

    def save(self, payload: dict[str, object]) -> None:
        session_id = str(payload["session_id"])
        document = dict(payload)
        document["updated_at"] = datetime.now(UTC).isoformat()
        _atomic_write_json(self.path(session_id), document)

    def load(self, session_id: str) -> dict[str, object]:
        path = self.path(session_id)
        if not path.is_file():
            raise KeyError(f"unknown production session: {session_id}")
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ProductionRunError(f"invalid session manifest: {path}")
        return value

    def latest(self) -> str:
        if not self.latest_path.is_file():
            raise KeyError("no production session exists")
        value = self.latest_path.read_text(encoding="utf-8").strip()
        _validate_session_id(value)
        return value


class IssueContextResolver:
    """Deterministically narrow repository context before any model call."""

    _TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{2,}")
    _STOP = frozenset(
        {
            "the",
            "and",
            "for",
            "with",
            "from",
            "this",
            "that",
            "into",
            "issue",
            "development",
            "contract",
            "implement",
            "reverend",
            "canonical",
            "design",
            "documentation",
            "owner",
            "milestone",
            "area",
            "required",
            "workflow",
        }
    )

    def __init__(self, repository_root: str | Path, *, max_design_sources: int = 7) -> None:
        self.root = Path(repository_root).resolve()
        self.max_design_sources = max_design_sources
        if max_design_sources < 2:
            raise ValueError("max_design_sources must be at least 2")

    def resolve(self, issue: QueuedIssue) -> ResolvedIssueContext:
        tokens = self._tokens(" ".join((issue.title, issue.area, issue.body)))
        design_sources = self._design_sources(tokens)
        source_files = self._rank_tracked_paths(tokens, prefixes=("src/",), limit=8)
        test_files = self._rank_tracked_paths(tokens, prefixes=("tests/",), limit=8)
        requirements = self._requirements(issue)
        acceptance = (
            f"Implement GitHub issue #{issue.number}: {issue.title}",
            "Preserve accepted Reverend 0.4.0 behavior unless canonical Design explicitly supersedes it.",
            "All changed Python must compile and targeted plus full regression tests must pass.",
            "Do not fabricate live-provider, credential, browser, GPU, or external-service evidence.",
        )
        return ResolvedIssueContext(
            requirements=requirements,
            design_sources=design_sources,
            candidate_source_files=source_files,
            candidate_tests=test_files,
            acceptance=acceptance,
        )

    def _tokens(self, value: str) -> frozenset[str]:
        return frozenset(
            token.lower().replace("_", "-")
            for token in self._TOKEN_RE.findall(value)
            if token.lower() not in self._STOP
        )

    def _design_sources(self, tokens: frozenset[str]) -> tuple[str, ...]:
        root = self.root / "Documentation" / "Design"
        if not root.is_dir():
            raise ProductionRunError("Documentation/Design is missing")
        files = sorted(path for path in root.glob("*.md") if path.is_file())
        mandatory_names = (
            "00-design-index.md",
            "D9-development-programme-migration-and-acceptance.md",
            "D22-final-design-closure-and-implementation-readiness.md",
        )
        selected: list[Path] = []
        for name in mandatory_names:
            path = root / name
            if path.is_file():
                selected.append(path)

        scored: list[tuple[int, str, Path]] = []
        for path in files:
            if path in selected:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            filename_tokens = self._tokens(path.stem.replace("-", " "))
            heading_text = "\n".join(
                line for line in text.splitlines()[:400] if line.lstrip().startswith("#")
            )
            heading_tokens = self._tokens(heading_text)
            body_tokens = self._tokens(text[:40_000])
            score = (
                7 * len(tokens & filename_tokens)
                + 4 * len(tokens & heading_tokens)
                + len(tokens & body_tokens)
            )
            if score:
                scored.append((score, path.name, path))
        scored.sort(key=lambda item: (-item[0], item[1]))
        for _score, _name, path in scored:
            if path not in selected:
                selected.append(path)
            if len(selected) >= self.max_design_sources:
                break
        if not selected:
            raise ProductionRunError("no authoritative Design documents could be selected")
        return tuple(path.relative_to(self.root).as_posix() for path in selected)

    def _tracked_files(self) -> tuple[str, ...]:
        completed = subprocess.run(
            ["git", "-C", str(self.root), "ls-files", "-z"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if completed.returncode != 0:
            raise ProductionRunError(
                "git ls-files failed: " + completed.stderr.decode("utf-8", errors="replace")[-2000:]
            )
        return tuple(
            value.decode("utf-8", errors="strict")
            for value in completed.stdout.split(b"\0")
            if value
        )

    def _rank_tracked_paths(
        self,
        tokens: frozenset[str],
        *,
        prefixes: Sequence[str],
        limit: int,
    ) -> tuple[str, ...]:
        scored: list[tuple[int, str]] = []
        for path in self._tracked_files():
            if not any(path.startswith(prefix) for prefix in prefixes):
                continue
            path_tokens = self._tokens(path.replace("/", " ").replace(".", " "))
            score = len(tokens & path_tokens)
            if score:
                scored.append((score, path))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return tuple(path for _score, path in scored[:limit])

    @staticmethod
    def _requirements(issue: QueuedIssue) -> tuple[str, ...]:
        result = [f"{issue.title} (issue #{issue.number}, area {issue.area})"]
        for raw in issue.body.splitlines():
            line = raw.strip()
            if not line or line.startswith("```") or line.startswith("## Ownership"):
                continue
            if line.startswith("**Owner:") or line.startswith("**Milestone:") or line.startswith("**Area:"):
                continue
            if line.startswith(("- ", "* ")):
                line = line[2:].strip()
            if len(line) >= 12 and line not in result:
                result.append(line)
            if len(result) >= 20:
                break
        return tuple(result)


class ProductionRunner:
    """Project-level orchestrator around the deterministic issue engine.

    Each issue gets a one-issue durable controller run based on the current
    integration branch. This prevents later issues from accidentally starting
    from the original project baseline and gives every accepted issue a strict
    fast-forward path into the integration branch.
    """

    def __init__(
        self,
        repository_root: str | Path,
        *,
        config: ProductionConfig,
        queue_loader: Callable[[], tuple[QueuedIssue, ...]] | None = None,
        engine_factory: Callable[[AutonomousController, EngineConfig], IssueEngine] | None = None,
    ) -> None:
        self.root = Path(repository_root).resolve()
        if not (self.root / ".git").exists():
            raise ValueError(f"not a Git repository: {self.root}")
        self.config = config
        self.runtime = self.root / ".autonomy" / "v2-production"
        self.runtime.mkdir(parents=True, exist_ok=True)
        self.sessions = SessionStore(self.runtime)
        self.lock_path = self.runtime / "controller.lock"
        self.queue_loader = queue_loader or GitHubIssueQueue(
            config.repository,
            include_alex=config.include_alex,
        ).load
        self.engine_factory = engine_factory or (
            lambda controller, engine_config: IssueEngine(controller, config=engine_config)
        )

    def start(self) -> ProductionResult:
        with ProductionLock(self.lock_path):
            self._assert_root_clean()
            if self.config.run_preflight:
                report = ModelPreflight(
                    self.root,
                    opencode_model=self.config.model,
                    ollama_model=self.config.ollama_model,
                ).run(base_ref=self.config.base_ref)
                if not report.passed:
                    detail = "; ".join(report.errors) or "unknown preflight failure"
                    raise ProductionRunError(f"model preflight failed: {detail}")

            queue = self.queue_loader()
            if self.config.max_issues is not None:
                queue = queue[: self.config.max_issues]
            if not queue:
                raise ProductionRunError("development queue is empty")

            session_id = self._new_session_id()
            integration_branch = f"autonomy/v2-integration-{session_id}"
            integration_path = self._ensure_integration_worktree(
                session_id=session_id,
                branch=integration_branch,
                base_ref=self.config.base_ref,
                create=True,
            )
            manifest = self.sessions.create(
                {
                    "session_id": session_id,
                    "status": "RUNNING",
                    "repository": self.config.repository,
                    "model": self.config.model,
                    "ollama_model": self.config.ollama_model,
                    "base_ref": self.config.base_ref,
                    "include_alex": self.config.include_alex,
                    "max_repairs": self.config.max_repairs,
                    "integration_branch": integration_branch,
                    "integration_worktree": str(integration_path),
                    "queue": [asdict(issue) for issue in queue],
                    "next_index": 0,
                    "accepted": [],
                    "milestone_gates": {},
                    "current_issue": None,
                    "current_issue_run_id": None,
                    "issue_attempts": {},
                    "stop_reason": None,
                }
            )
            return self._drive(manifest)

    def resume(self, session_id: str | None = None, *, retry_failed: bool = False) -> ProductionResult:
        with ProductionLock(self.lock_path):
            resolved = session_id or self.sessions.latest()
            manifest = self.sessions.load(resolved)
            self._assert_manifest_compatible(manifest)
            self._ensure_integration_worktree(
                session_id=resolved,
                branch=str(manifest["integration_branch"]),
                base_ref=str(manifest["base_ref"]),
                create=False,
            )
            self._recover_interrupted_issue(manifest, retry_failed=retry_failed)
            if str(manifest["status"]) == "COMPLETED":
                return self._result(manifest)
            if str(manifest["status"]) in {"BLOCKED", "MILESTONE_FAILED"} and not retry_failed:
                return self._result(manifest)
            manifest["status"] = "RUNNING"
            manifest["stop_reason"] = None
            self.sessions.save(manifest)
            return self._drive(manifest)

    def status(self, session_id: str | None = None) -> dict[str, object]:
        resolved = session_id or self.sessions.latest()
        return self.sessions.load(resolved)

    def _drive(self, manifest: dict[str, object]) -> ProductionResult:
        queue = [QueuedIssue(**item) for item in manifest["queue"]]  # type: ignore[arg-type]
        index = int(manifest["next_index"])
        integration = Path(str(manifest["integration_worktree"]))
        previous_milestone: int | None = None
        if index:
            previous_milestone = queue[index - 1].milestone_number

        while index < len(queue):
            issue = queue[index]
            if previous_milestone is not None and issue.milestone_number != previous_milestone:
                if not self._run_milestone_gate(manifest, previous_milestone, integration):
                    return self._result(manifest)

            manifest["current_issue"] = issue.number
            self.sessions.save(manifest)
            outcome, issue_run_id, branch_name, worktree_path = self._run_issue(
                manifest,
                issue,
                integration,
            )
            manifest["current_issue_run_id"] = issue_run_id
            self.sessions.save(manifest)

            if not outcome.accepted or outcome.commit is None:
                manifest["status"] = "BLOCKED"
                manifest["stop_reason"] = outcome.reason or outcome.phase.value
                self.sessions.save(manifest)
                return self._result(manifest)

            self._fast_forward(integration, branch_name)
            merged_head = self._git(integration, "rev-parse", "HEAD")
            if merged_head != outcome.commit:
                raise ProductionRunError(
                    f"integration head {merged_head} does not equal accepted commit {outcome.commit}"
                )

            accepted = list(manifest["accepted"])  # type: ignore[arg-type]
            accepted.append(
                {
                    "issue": issue.number,
                    "milestone": issue.milestone,
                    "commit": outcome.commit,
                    "branch": branch_name,
                    "run_id": issue_run_id,
                }
            )
            manifest["accepted"] = accepted
            index += 1
            manifest["next_index"] = index
            manifest["current_issue"] = None
            manifest["current_issue_run_id"] = None
            manifest["stop_reason"] = None
            self.sessions.save(manifest)
            self._remove_worktree(worktree_path)
            previous_milestone = issue.milestone_number

        if previous_milestone is not None:
            if not self._run_milestone_gate(manifest, previous_milestone, integration):
                return self._result(manifest)
        manifest["status"] = "COMPLETED"
        manifest["current_issue"] = None
        manifest["current_issue_run_id"] = None
        manifest["stop_reason"] = None
        self.sessions.save(manifest)
        return self._result(manifest)

    def _run_issue(
        self,
        manifest: dict[str, object],
        issue: QueuedIssue,
        integration: Path,
    ) -> tuple[IssueOutcome, str, str, Path]:
        attempts = dict(manifest["issue_attempts"])  # type: ignore[arg-type]
        key = str(issue.number)
        ordinal = int(attempts.get(key, 0)) + 1
        attempts[key] = ordinal
        manifest["issue_attempts"] = attempts
        issue_run_id = f"{manifest['session_id']}-i{issue.number}-a{ordinal}"
        manifest["current_issue_run_id"] = issue_run_id
        self.sessions.save(manifest)

        controller = AutonomousController(self.root)
        spec = issue.as_issue_spec()
        controller.initialize_run(
            queue=[spec],
            base_ref=str(manifest["integration_branch"]),
            run_id=issue_run_id,
        )
        resolver = IssueContextResolver(integration)
        context = resolver.resolve(issue)
        prepared = controller.prepare_issue(
            run_id=issue_run_id,
            issue=spec,
            requirements=context.requirements,
            design_sources=context.design_sources,
            candidate_source_files=context.candidate_source_files,
            candidate_tests=context.candidate_tests,
            acceptance=context.acceptance,
        )
        engine = self.engine_factory(
            controller,
            EngineConfig(
                model=str(manifest["model"]),
                max_repairs=int(manifest["max_repairs"]),
            ),
        )
        outcome = engine.run(prepared)
        controller.store.set_run_status(
            issue_run_id,
            "COMPLETED" if outcome.accepted else outcome.phase.value,
        )
        state = controller.store.get_issue(issue_run_id, issue.number)
        if state.branch_name is None or state.worktree_path is None:
            raise ProductionRunError("issue runtime lost branch/worktree state")
        return outcome, issue_run_id, state.branch_name, Path(state.worktree_path)

    def _run_milestone_gate(
        self,
        manifest: dict[str, object],
        milestone_number: int,
        integration: Path,
    ) -> bool:
        key = f"C{milestone_number}"
        gates = dict(manifest["milestone_gates"])  # type: ignore[arg-type]
        if gates.get(key, {}).get("passed") is True:  # type: ignore[union-attr]
            return True
        log_dir = self.runtime / "logs" / str(manifest["session_id"]) / f"milestone-{key}"
        script = integration / "scripts" / "autonomy-gates.sh"
        if script.is_file():
            steps = (
                VerificationStep(
                    "autonomy-gates",
                    ("bash", "scripts/autonomy-gates.sh"),
                    self.config.milestone_gate_timeout_seconds,
                ),
            )
        else:
            steps = default_verification_steps(
                full_pytest_timeout_seconds=self.config.milestone_gate_timeout_seconds
            )
        report = Verifier(fail_fast=True).run(
            worktree=integration,
            log_dir=log_dir,
            steps=steps,
        )
        failed = report.failed_step
        gates[key] = {
            "passed": report.passed,
            "failed_step": failed.name if failed else None,
            "log": str(failed.log_path if failed else log_dir),
            "checked_at": datetime.now(UTC).isoformat(),
        }
        manifest["milestone_gates"] = gates
        if not report.passed:
            manifest["status"] = "MILESTONE_FAILED"
            manifest["stop_reason"] = f"{key} milestone verification failed"
        self.sessions.save(manifest)
        return report.passed

    def _recover_interrupted_issue(
        self,
        manifest: dict[str, object],
        *,
        retry_failed: bool,
    ) -> None:
        issue_number = manifest.get("current_issue")
        run_id = manifest.get("current_issue_run_id")
        if issue_number is None or not run_id:
            return
        controller = AutonomousController(self.root)
        try:
            state = controller.store.get_issue(str(run_id), int(issue_number))
        except KeyError:
            manifest["current_issue_run_id"] = None
            self.sessions.save(manifest)
            return

        if state.phase is IssuePhase.ACCEPTED and state.accepted_commit and state.branch_name:
            integration = Path(str(manifest["integration_worktree"]))
            self._fast_forward(integration, state.branch_name)
            accepted = list(manifest["accepted"])  # type: ignore[arg-type]
            if not any(int(item["issue"]) == int(issue_number) for item in accepted):  # type: ignore[index]
                accepted.append(
                    {
                        "issue": int(issue_number),
                        "milestone": state.milestone,
                        "commit": state.accepted_commit,
                        "branch": state.branch_name,
                        "run_id": str(run_id),
                    }
                )
                manifest["accepted"] = accepted
                manifest["next_index"] = int(manifest["next_index"]) + 1
            if state.worktree_path:
                self._remove_worktree(Path(state.worktree_path))
            manifest["current_issue"] = None
            manifest["current_issue_run_id"] = None
            self.sessions.save(manifest)
            return

        if state.phase in TERMINAL_PHASES and not retry_failed:
            manifest["status"] = "BLOCKED"
            manifest["stop_reason"] = f"issue #{issue_number} previously ended in {state.phase.value}"
            self.sessions.save(manifest)
            return

        # A process died while the issue was in flight, or the caller explicitly
        # requested a terminal retry. Preserve logs/SQLite evidence, discard only
        # the isolated unaccepted worktree, and restart the issue from current
        # integration HEAD with a fresh run id.
        if state.worktree_path:
            self._remove_worktree(Path(state.worktree_path))
        if state.branch_name:
            self._delete_branch(state.branch_name)
        controller.store.set_run_status(str(run_id), "INTERRUPTED_RETRY")
        manifest["current_issue_run_id"] = None
        manifest["status"] = "RUNNING"
        manifest["stop_reason"] = None
        self.sessions.save(manifest)

    def _ensure_integration_worktree(
        self,
        *,
        session_id: str,
        branch: str,
        base_ref: str,
        create: bool,
    ) -> Path:
        path = (self.root / ".worktrees" / "autonomy-v2-production" / session_id).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            current = self._git(path, "branch", "--show-current")
            if current != branch:
                raise ProductionRunError(
                    f"integration worktree is on {current!r}, expected {branch!r}"
                )
            return path
        branch_exists = self._git_result(self.root, "show-ref", "--verify", "--quiet", f"refs/heads/{branch}").returncode == 0
        if create and not branch_exists:
            self._git(self.root, "worktree", "add", "--no-track", "-b", branch, str(path), base_ref)
        elif branch_exists:
            self._git(self.root, "worktree", "add", str(path), branch)
        else:
            raise ProductionRunError(f"integration branch is missing: {branch}")
        return path

    def _fast_forward(self, integration: Path, branch: str) -> None:
        if self._git(integration, "status", "--porcelain"):
            raise ProductionRunError("integration worktree is dirty")
        self._git(integration, "merge", "--ff-only", branch)

    def _remove_worktree(self, path: Path) -> None:
        if not path.exists():
            return
        completed = self._git_result(self.root, "worktree", "remove", "--force", str(path))
        if completed.returncode != 0:
            raise ProductionRunError(
                "unable to remove issue worktree: " + completed.stderr.strip()[-2000:]
            )
        self._git_result(self.root, "worktree", "prune")

    def _delete_branch(self, branch: str) -> None:
        if not re.fullmatch(r"[A-Za-z0-9._/-]+", branch) or ".." in branch:
            raise ProductionRunError(f"unsafe branch name: {branch!r}")
        completed = self._git_result(self.root, "branch", "-D", branch)
        if completed.returncode not in {0, 1}:
            raise ProductionRunError(
                "unable to delete interrupted branch: " + completed.stderr.strip()[-2000:]
            )

    def _assert_root_clean(self) -> None:
        if self._git(self.root, "status", "--porcelain"):
            raise ProductionRunError("repository working tree must be clean before production run")

    def _assert_manifest_compatible(self, manifest: dict[str, object]) -> None:
        if str(manifest.get("repository")) != self.config.repository:
            raise ProductionRunError("session repository does not match configuration")
        if str(manifest.get("model")) != self.config.model:
            raise ProductionRunError("session model does not match configuration")

    def _result(self, manifest: dict[str, object]) -> ProductionResult:
        integration = Path(str(manifest["integration_worktree"]))
        head = self._git(integration, "rev-parse", "HEAD") if integration.exists() else None
        return ProductionResult(
            session_id=str(manifest["session_id"]),
            status=str(manifest["status"]),
            completed_issues=int(manifest["next_index"]),
            total_issues=len(manifest["queue"]),  # type: ignore[arg-type]
            integration_branch=str(manifest["integration_branch"]),
            integration_head=head,
            stop_reason=(str(manifest["stop_reason"]) if manifest.get("stop_reason") else None),
        )

    @staticmethod
    def _new_session_id() -> str:
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        return f"{stamp}-{uuid.uuid4().hex[:8]}"

    @staticmethod
    def _git_result(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120,
            check=False,
        )

    @classmethod
    def _git(cls, cwd: Path, *args: str) -> str:
        completed = cls._git_result(cwd, *args)
        if completed.returncode != 0:
            raise ProductionRunError(
                f"git {' '.join(args)} failed: {completed.stderr.strip()[-2000:]}"
            )
        return completed.stdout.strip()


def _validate_session_id(value: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9._-]+", value):
        raise ValueError(f"unsafe session id: {value!r}")


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    _atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _atomic_write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise
