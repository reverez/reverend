from __future__ import annotations

import os
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence


@dataclass(frozen=True)
class VerificationStep:
    name: str
    argv: tuple[str, ...]
    timeout_seconds: float

    def __init__(self, name: str, argv: Sequence[str], timeout_seconds: float) -> None:
        if not name.strip():
            raise ValueError("verification step name must not be empty")
        if not argv:
            raise ValueError("verification argv must not be empty")
        if timeout_seconds <= 0:
            raise ValueError("verification timeout must be positive")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "argv", tuple(argv))
        object.__setattr__(self, "timeout_seconds", timeout_seconds)


@dataclass(frozen=True)
class VerificationResult:
    name: str
    argv: tuple[str, ...]
    returncode: int | None
    timed_out: bool
    log_path: Path

    @property
    def passed(self) -> bool:
        return not self.timed_out and self.returncode == 0


@dataclass(frozen=True)
class VerificationReport:
    results: tuple[VerificationResult, ...]

    @property
    def passed(self) -> bool:
        return bool(self.results) and all(result.passed for result in self.results)

    @property
    def failed_step(self) -> VerificationResult | None:
        return next((result for result in self.results if not result.passed), None)


class Verifier:
    """Run controller-owned verification against the isolated worktree."""

    def __init__(self, *, fail_fast: bool = True) -> None:
        self.fail_fast = fail_fast

    def run(
        self,
        *,
        worktree: str | Path,
        log_dir: str | Path,
        steps: Iterable[VerificationStep],
        heartbeat: Callable[[], None] | None = None,
        heartbeat_interval_seconds: float = 15,
    ) -> VerificationReport:
        worktree_path = Path(worktree).resolve()
        if not worktree_path.is_dir():
            raise ValueError(f"worktree does not exist: {worktree_path}")
        if heartbeat_interval_seconds <= 0:
            raise ValueError("heartbeat_interval_seconds must be positive")
        log_root = Path(log_dir).resolve()
        log_root.mkdir(parents=True, exist_ok=True)

        # A shared editable venv can point back at the controller checkout.
        # Force imports to resolve the isolated worktree first so verification
        # actually tests the code the agent changed.
        env = os.environ.copy()
        worktree_src = str((worktree_path / "src").resolve())
        existing_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            worktree_src
            if not existing_pythonpath
            else worktree_src + os.pathsep + existing_pythonpath
        )

        results: list[VerificationResult] = []
        for index, step in enumerate(steps, start=1):
            log_path = log_root / f"{index:02d}-{_slug(step.name)}.log"
            returncode: int | None = None
            timed_out = False
            stop = threading.Event()
            thread: threading.Thread | None = None
            if heartbeat is not None:
                try:
                    heartbeat()
                except Exception:
                    pass
                thread = threading.Thread(
                    target=_heartbeat_loop,
                    args=(stop, heartbeat, heartbeat_interval_seconds),
                    name=f"verification-heartbeat-{_slug(step.name)}",
                    daemon=True,
                )
                thread.start()
            try:
                with log_path.open("w", encoding="utf-8") as handle:
                    try:
                        completed = subprocess.run(
                            list(step.argv),
                            cwd=worktree_path,
                            env=env,
                            stdin=subprocess.DEVNULL,
                            stdout=handle,
                            stderr=subprocess.STDOUT,
                            text=True,
                            timeout=step.timeout_seconds,
                            check=False,
                        )
                        returncode = completed.returncode
                    except subprocess.TimeoutExpired:
                        timed_out = True
            finally:
                stop.set()
                if thread is not None:
                    thread.join(timeout=2)
                if heartbeat is not None:
                    try:
                        heartbeat()
                    except Exception:
                        pass
            result = VerificationResult(
                name=step.name,
                argv=step.argv,
                returncode=returncode,
                timed_out=timed_out,
                log_path=log_path,
            )
            results.append(result)
            if self.fail_fast and not result.passed:
                break
        return VerificationReport(tuple(results))


def default_verification_steps(
    *,
    targeted_tests: Iterable[str] = (),
    full_pytest_timeout_seconds: float = 1800,
) -> tuple[VerificationStep, ...]:
    python = sys.executable
    targets = tuple(targeted_tests)
    steps: list[VerificationStep] = [
        VerificationStep("git-diff-check", ("git", "diff", "--check"), 60),
        VerificationStep(
            "python-compile",
            (python, "-m", "compileall", "-q", "src"),
            180,
        ),
    ]
    if targets:
        steps.append(
            VerificationStep(
                "targeted-pytest",
                (python, "-m", "pytest", "-q", *targets),
                900,
            )
        )
    steps.append(
        VerificationStep(
            "full-pytest",
            (python, "-m", "pytest", "-q"),
            full_pytest_timeout_seconds,
        )
    )
    return tuple(steps)


def _heartbeat_loop(
    stop: threading.Event,
    heartbeat: Callable[[], None],
    interval_seconds: float,
) -> None:
    while not stop.wait(interval_seconds):
        try:
            heartbeat()
        except Exception:
            return


def _slug(value: str) -> str:
    output = "".join(
        character.lower() if character.isalnum() else "-" for character in value
    )
    return "-".join(part for part in output.split("-") if part) or "step"
