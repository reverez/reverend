from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


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
    """Run controller-owned verification commands with no shell interpolation."""

    def __init__(self, *, fail_fast: bool = True) -> None:
        self.fail_fast = fail_fast

    def run(
        self,
        *,
        worktree: str | Path,
        log_dir: str | Path,
        steps: Iterable[VerificationStep],
    ) -> VerificationReport:
        worktree_path = Path(worktree).resolve()
        if not worktree_path.is_dir():
            raise ValueError(f"worktree does not exist: {worktree_path}")
        log_root = Path(log_dir).resolve()
        log_root.mkdir(parents=True, exist_ok=True)

        results: list[VerificationResult] = []
        for index, step in enumerate(steps, start=1):
            log_path = log_root / f"{index:02d}-{_slug(step.name)}.log"
            returncode: int | None = None
            timed_out = False
            with log_path.open("w", encoding="utf-8") as handle:
                try:
                    completed = subprocess.run(
                        list(step.argv),
                        cwd=worktree_path,
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


def _slug(value: str) -> str:
    output = "".join(character.lower() if character.isalnum() else "-" for character in value)
    return "-".join(part for part in output.split("-") if part) or "step"
