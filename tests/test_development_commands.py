from __future__ import annotations

import json
import stat
import subprocess
import sys
import time

import pytest

from reverend.development import (
    CommandPathError,
    CommandPolicyError,
    TaskState,
    TrustMode,
    UntrustedRepositoryError,
    create_task,
    create_task_worktree,
    database,
    register_project,
    run_command,
    transition_task,
)


def git(repo, *args):
    return subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            *args,
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )


def make_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    subprocess.run(
        [
            "git",
            "init",
            "-b",
            "main",
            str(repo),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    (repo / "README.md").write_text(
        "# Repository\n",
        encoding="utf-8",
    )

    git(repo, "add", "README.md")

    git(
        repo,
        "-c",
        "user.name=Reverend Test",
        "-c",
        "user.email=reverend@example.invalid",
        "commit",
        "-m",
        "Initial commit",
    )

    return repo


def setup_task(
    tmp_path,
    *,
    trust_mode=TrustMode.TRUSTED_REPO,
):
    repo = make_repo(tmp_path)

    context = database(
        tmp_path / "development.db"
    )

    connection = context.__enter__()

    project = register_project(
        connection,
        repo,
        trust_mode=trust_mode,
    )

    task = create_task(
        connection,
        project.id,
        title="Command test",
        request="Test command runner",
    )

    task = transition_task(
        connection,
        task.id,
        TaskState.PREPARING,
    )

    worktree = create_task_worktree(
        connection,
        task.id,
        root=tmp_path / "worktrees",
    )

    return (
        context,
        connection,
        task,
        worktree,
    )


def test_command_runs_inside_worktree(
    tmp_path,
):
    (
        context,
        connection,
        task,
        worktree,
    ) = setup_task(tmp_path)

    try:
        result = run_command(
            connection,
            task.id,
            [
                sys.executable,
                "-c",
                (
                    "from pathlib import Path; "
                    "print(Path.cwd())"
                ),
            ],
            artifact_root=(
                tmp_path / "artifacts"
            ),
        )

        assert result.succeeded
        assert (
            result.stdout.strip()
            == str(worktree.path)
        )
    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_command_never_uses_shell(
    tmp_path,
):
    (
        context,
        connection,
        task,
        _,
    ) = setup_task(tmp_path)

    try:
        result = run_command(
            connection,
            task.id,
            [
                sys.executable,
                "-c",
                "import sys; print(sys.argv[1])",
                "$(echo unsafe)",
            ],
            artifact_root=(
                tmp_path / "artifacts"
            ),
        )

        assert result.stdout.strip() == (
            "$(echo unsafe)"
        )
    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_cwd_cannot_escape_worktree(
    tmp_path,
):
    (
        context,
        connection,
        task,
        _,
    ) = setup_task(tmp_path)

    try:
        with pytest.raises(
            CommandPathError
        ):
            run_command(
                connection,
                task.id,
                [
                    sys.executable,
                    "-c",
                    "print('unsafe')",
                ],
                cwd=tmp_path,
                artifact_root=(
                    tmp_path / "artifacts"
                ),
            )
    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_timeout_terminates_process(
    tmp_path,
):
    (
        context,
        connection,
        task,
        _,
    ) = setup_task(tmp_path)

    try:
        started = time.monotonic()

        result = run_command(
            connection,
            task.id,
            [
                sys.executable,
                "-c",
                "import time; time.sleep(20)",
            ],
            timeout=0.15,
            artifact_root=(
                tmp_path / "artifacts"
            ),
        )

        elapsed = (
            time.monotonic()
            - started
        )

        assert result.timed_out
        assert not result.succeeded
        assert elapsed < 3.0
    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_output_is_bounded(
    tmp_path,
):
    (
        context,
        connection,
        task,
        _,
    ) = setup_task(tmp_path)

    try:
        result = run_command(
            connection,
            task.id,
            [
                sys.executable,
                "-c",
                (
                    "import sys; "
                    "sys.stdout.write('x' * 1000000); "
                    "sys.stdout.flush(); "
                    "import time; time.sleep(10)"
                ),
            ],
            timeout=5.0,
            max_output_bytes=4096,
            artifact_root=(
                tmp_path / "artifacts"
            ),
        )

        assert result.output_limited
        assert not result.succeeded
        assert len(
            result.stdout.encode()
        ) <= 4096
    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_stdout_and_stderr_are_persisted(
    tmp_path,
):
    (
        context,
        connection,
        task,
        _,
    ) = setup_task(tmp_path)

    try:
        result = run_command(
            connection,
            task.id,
            [
                sys.executable,
                "-c",
                (
                    "import sys; "
                    "print('out'); "
                    "print('err', file=sys.stderr)"
                ),
            ],
            artifact_root=(
                tmp_path / "artifacts"
            ),
        )

        assert result.stdout == "out\n"
        assert result.stderr == "err\n"

        count = connection.execute(
            """
            SELECT COUNT(*)
            FROM artifacts
            WHERE task_id = ?
            """,
            (
                task.id,
            ),
        ).fetchone()[0]

        assert count == 2

        assert (
            result.stdout_artifact
            .content_hash
        )

        assert (
            result.stderr_artifact
            .content_hash
        )
    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_nonzero_exit_is_recorded(
    tmp_path,
):
    (
        context,
        connection,
        task,
        _,
    ) = setup_task(tmp_path)

    try:
        result = run_command(
            connection,
            task.id,
            [
                sys.executable,
                "-c",
                "raise SystemExit(7)",
            ],
            artifact_root=(
                tmp_path / "artifacts"
            ),
        )

        assert result.exit_code == 7
        assert not result.succeeded
        assert not result.timed_out
    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_secret_like_environment_is_rejected(
    tmp_path,
):
    (
        context,
        connection,
        task,
        _,
    ) = setup_task(tmp_path)

    try:
        with pytest.raises(
            CommandPolicyError
        ):
            run_command(
                connection,
                task.id,
                [
                    sys.executable,
                    "-c",
                    "print('never')",
                ],
                environment={
                    "MY_API_KEY": "secret"
                },
                artifact_root=(
                    tmp_path / "artifacts"
                ),
            )
    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_untrusted_repo_is_blocked(
    tmp_path,
):
    (
        context,
        connection,
        task,
        _,
    ) = setup_task(
        tmp_path,
        trust_mode=(
            TrustMode.UNTRUSTED_REPO
        ),
    )

    try:
        with pytest.raises(
            UntrustedRepositoryError
        ):
            run_command(
                connection,
                task.id,
                [
                    sys.executable,
                    "-c",
                    "print('blocked')",
                ],
                artifact_root=(
                    tmp_path / "artifacts"
                ),
            )
    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_host_credential_capability_environment_is_removed(
    tmp_path,
    monkeypatch,
):
    (
        context,
        connection,
        task,
        _,
    ) = setup_task(tmp_path)

    blocked = {
        "SSH_AUTH_SOCK": "/tmp/agent.sock",
        "AWS_PROFILE": "personal",
        "KUBECONFIG": "/home/user/.kube/config",
        "PYTHONPATH": "/sensitive/python/path",
        "GIT_ASKPASS": "/tmp/askpass",
        "LD_PRELOAD": "/tmp/inject.so",
    }

    for key, value in blocked.items():
        monkeypatch.setenv(key, value)

    try:
        result = run_command(
            connection,
            task.id,
            [
                sys.executable,
                "-c",
                (
                    "import json, os; "
                    "keys="
                    + repr(tuple(blocked))
                    + "; "
                    "print(json.dumps({k: os.environ.get(k) for k in keys}))"
                ),
            ],
            artifact_root=(
                tmp_path / "artifacts"
            ),
        )

        assert result.succeeded
        observed = json.loads(
            result.stdout
        )
        assert observed == {
            key: None
            for key in blocked
        }
    finally:
        context.__exit__(
            None,
            None,
            None,
        )


@pytest.mark.parametrize(
    "name",
    [
        "SSH_AUTH_SOCK",
        "AWS_PROFILE",
        "PYTHONPATH",
        "GIT_ASKPASS",
    ],
)
def test_explicit_capability_environment_is_rejected(
    tmp_path,
    name,
):
    (
        context,
        connection,
        task,
        _,
    ) = setup_task(tmp_path)

    try:
        with pytest.raises(
            CommandPolicyError,
            match="credential/capability",
        ):
            run_command(
                connection,
                task.id,
                [
                    sys.executable,
                    "-c",
                    "print('never')",
                ],
                environment={
                    name: "unsafe"
                },
                artifact_root=(
                    tmp_path / "artifacts"
                ),
            )
    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_explicit_safe_environment_is_allowed(
    tmp_path,
):
    (
        context,
        connection,
        task,
        _,
    ) = setup_task(tmp_path)

    try:
        result = run_command(
            connection,
            task.id,
            [
                sys.executable,
                "-c",
                (
                    "import os; "
                    "print(os.environ['REVEREND_SAFE_MARKER'])"
                ),
            ],
            environment={
                "REVEREND_SAFE_MARKER": "allowed"
            },
            artifact_root=(
                tmp_path / "artifacts"
            ),
        )

        assert result.succeeded
        assert result.stdout.strip() == "allowed"
    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_command_artifacts_are_owner_only(
    tmp_path,
):
    (
        context,
        connection,
        task,
        _,
    ) = setup_task(tmp_path)

    try:
        result = run_command(
            connection,
            task.id,
            [
                sys.executable,
                "-c",
                "print('private output')",
            ],
            artifact_root=(
                tmp_path / "artifacts"
            ),
        )

        assert stat.S_IMODE(
            result.stdout_artifact.path.parent.stat().st_mode
        ) == 0o700
        assert stat.S_IMODE(
            result.stdout_artifact.path.stat().st_mode
        ) == 0o600
        assert stat.S_IMODE(
            result.stderr_artifact.path.stat().st_mode
        ) == 0o600
    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_untrusted_command_requires_explicit_sandbox(
    tmp_path,
):
    (
        context,
        connection,
        task,
        _,
    ) = setup_task(
        tmp_path,
        trust_mode=(
            TrustMode.UNTRUSTED_REPO
        ),
    )

    try:
        with pytest.raises(
            UntrustedRepositoryError,
            match="explicit OS sandbox",
        ):
            run_command(
                connection,
                task.id,
                [
                    sys.executable,
                    "-c",
                    "print('blocked')",
                ],
                artifact_root=(
                    tmp_path / "artifacts"
                ),
            )
    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_explicit_sandbox_is_the_only_untrusted_execution_path(
    tmp_path,
    monkeypatch,
):
    (
        context,
        connection,
        task,
        worktree,
    ) = setup_task(
        tmp_path,
        trust_mode=(
            TrustMode.UNTRUSTED_REPO
        ),
    )
    observed = {}

    def sandbox_argv(
        root,
        command,
        *,
        timeout_seconds,
        cwd,
    ):
        observed.update(
            root=root,
            command=tuple(command),
            timeout=timeout_seconds,
            cwd=cwd,
        )
        return (
            sys.executable,
            "-c",
            "print('sandbox fixture')",
        )

    monkeypatch.setattr(
        "reverend.development.commands."
        "development_sandbox_argv",
        sandbox_argv,
    )

    try:
        result = run_command(
            connection,
            task.id,
            [
                "python3",
                "-c",
                "print('untrusted')",
            ],
            sandbox=True,
            timeout=12,
            artifact_root=(
                tmp_path / "artifacts"
            ),
        )

        assert result.succeeded
        assert result.sandboxed is True
        assert result.stdout.strip() == (
            "sandbox fixture"
        )
        assert observed == {
            "root": worktree.path.resolve(),
            "command": (
                "python3",
                "-c",
                "print('untrusted')",
            ),
            "timeout": 12,
            "cwd": worktree.path.resolve(),
        }

        rows = connection.execute(
            """
            SELECT metadata_json
            FROM artifacts
            WHERE task_id=?
            """,
            (task.id,),
        ).fetchall()

        assert len(rows) == 2
        assert all(
            json.loads(row["metadata_json"])[
                "sandboxed"
            ]
            is True
            for row in rows
        )
    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_sandbox_refuses_custom_environment(
    tmp_path,
    monkeypatch,
):
    (
        context,
        connection,
        task,
        _,
    ) = setup_task(
        tmp_path,
        trust_mode=(
            TrustMode.UNTRUSTED_REPO
        ),
    )

    monkeypatch.setattr(
        "reverend.development.commands."
        "development_sandbox_argv",
        lambda *args, **kwargs: (
            sys.executable,
            "-c",
            "print('never')",
        ),
    )

    try:
        with pytest.raises(
            CommandPolicyError,
            match="fixed minimal environment",
        ):
            run_command(
                connection,
                task.id,
                ["python3", "-V"],
                sandbox=True,
                environment={
                    "SAFE_MARKER": "value"
                },
                artifact_root=(
                    tmp_path / "artifacts"
                ),
            )
    finally:
        context.__exit__(
            None,
            None,
            None,
        )
