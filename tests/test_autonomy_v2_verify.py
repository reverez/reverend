from __future__ import annotations

import sys
from pathlib import Path

from reverend.autonomy_v2.verify import VerificationStep, Verifier


def test_verifier_stops_on_first_failure_and_persists_logs(tmp_path: Path):
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    verifier = Verifier(fail_fast=True)
    report = verifier.run(
        worktree=worktree,
        log_dir=tmp_path / "logs",
        steps=[
            VerificationStep(
                "pass",
                (sys.executable, "-c", "print('ok')"),
                5,
            ),
            VerificationStep(
                "fail",
                (sys.executable, "-c", "import sys; print('bad'); sys.exit(3)"),
                5,
            ),
            VerificationStep(
                "must-not-run",
                (sys.executable, "-c", "raise SystemExit(0)"),
                5,
            ),
        ],
    )

    assert report.passed is False
    assert [result.name for result in report.results] == ["pass", "fail"]
    assert report.failed_step is not None
    assert report.failed_step.returncode == 3
    assert "bad" in report.failed_step.log_path.read_text(encoding="utf-8")


def test_verifier_marks_timeout_as_failure(tmp_path: Path):
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    report = Verifier().run(
        worktree=worktree,
        log_dir=tmp_path / "logs",
        steps=[
            VerificationStep(
                "timeout",
                (sys.executable, "-c", "import time; time.sleep(10)"),
                0.1,
            )
        ],
    )
    assert report.passed is False
    assert report.failed_step is not None
    assert report.failed_step.timed_out is True
