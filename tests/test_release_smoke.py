from __future__ import annotations

import subprocess
from pathlib import Path

from reverend.benchmarks.release import (
    _clean_head_archive,
)


def _git(
    cwd: Path,
    *args: str,
) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout


def test_release_archive_uses_committed_head_and_reports_local_edits(
    tmp_path,
):
    repository = (
        tmp_path
        / "repo"
    )
    repository.mkdir()

    _git(
        repository,
        "init",
        "-b",
        "main",
    )
    _git(
        repository,
        "config",
        "user.name",
        "Reverend Test",
    )
    _git(
        repository,
        "config",
        "user.email",
        "reverend@example.invalid",
    )

    tracked = (
        repository
        / "tracked.txt"
    )
    tracked.write_text(
        "committed\n",
        encoding="utf-8",
    )
    _git(
        repository,
        "add",
        "tracked.txt",
    )
    _git(
        repository,
        "commit",
        "-m",
        "fixture",
    )

    tracked.write_text(
        "local edit\n",
        encoding="utf-8",
    )
    (
        repository
        / "untracked.txt"
    ).write_text(
        "not part of release\n",
        encoding="utf-8",
    )

    destination = (
        tmp_path
        / "archive"
    )
    (
        revision,
        changes,
    ) = _clean_head_archive(
        repository,
        destination,
    )

    assert revision == _git(
        repository,
        "rev-parse",
        "HEAD",
    ).strip()
    assert (
        destination
        / "tracked.txt"
    ).read_text(
        encoding="utf-8"
    ) == "committed\n"
    assert not (
        destination
        / "untracked.txt"
    ).exists()
    assert any(
        "tracked.txt"
        in line
        for line
        in changes
    )
