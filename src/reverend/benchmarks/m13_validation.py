"""Single-command M13 Privacy & Execution Security v2 validation.

Portable validation checks the deterministic privacy, encryption, trust and capability
contracts. Live validation executes the real bubblewrap/prlimit sandbox on the current
workstation. No model call participates in M13 acceptance.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from reverend.benchmarks.m13_sandbox_validation import (
    run_live_probe,
)
from reverend.development import (
    ProjectRegistryError,
    TrustMode,
    database,
    register_project,
)
from reverend.development.commands import (
    CommandPolicyError,
    _safe_environment,
)
from reverend.development.sandbox import (
    development_sandbox_argv,
)
from reverend.workstation.crypto import (
    ENCRYPTED_PREFIX,
)
from reverend.workstation.store import (
    PrivacyMode,
    WorkspaceStore,
)


def _pytest_summary(
    output: str,
) -> dict:
    passed = re.findall(
        r"(\d+) passed",
        output,
    )
    failed = re.findall(
        r"(\d+) failed",
        output,
    )

    return {
        "passed": (
            int(
                passed[-1]
            )
            if passed
            else None
        ),
        "failed": (
            int(
                failed[-1]
            )
            if failed
            else 0
        ),
    }


def _git(
    *argv: str,
) -> None:
    subprocess.run(
        list(argv),
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _write_repository(
    root: Path,
) -> Path:
    repository = (
        root
        / "repo"
    )
    repository.mkdir()

    _git(
        "git",
        "init",
        "-b",
        "main",
        str(repository),
    )

    (
        repository
        / "README.md"
    ).write_text(
        "# M13 fixture\n",
        encoding="utf-8",
    )

    _git(
        "git",
        "-C",
        str(repository),
        "add",
        ".",
    )
    _git(
        "git",
        "-C",
        str(repository),
        "-c",
        "user.name=Reverend Validation",
        "-c",
        "user.email=reverend@example.invalid",
        "commit",
        "-m",
        "M13 validation fixture",
    )

    return repository


def _portable_security() -> dict:
    assertions: dict[
        str,
        bool,
    ] = {}
    metadata: dict = {}

    with TemporaryDirectory(
        prefix="reverend-m13-portable-"
    ) as temporary:
        root = Path(
            temporary
        )

        # Privacy and encrypted persistence.
        store = WorkspaceStore(
            root
            / "workstation.db",
            key_path=(
                root
                / "state.key"
            ),
        )

        normal = (
            store.create_conversation(
                title="M13 normal secret",
                privacy_mode="normal",
            )
        )
        private = (
            store.create_conversation(
                title="M13 private secret",
                privacy_mode="private",
            )
        )
        ephemeral = (
            store.create_conversation(
                title="M13 ephemeral secret",
                privacy_mode="ephemeral",
            )
        )

        store.add_message(
            normal,
            "user",
            "M13 normal message",
            {
                "kind": "normal"
            },
        )
        store.add_message(
            private,
            "user",
            "M13 private message",
            {
                "kind": "private"
            },
        )
        store.add_message(
            ephemeral,
            "user",
            "M13 ephemeral message",
            {
                "kind": "ephemeral"
            },
        )

        normal_job = store.new_job(
            "chat",
            normal,
        )
        store.update_job(
            normal_job,
            response="M13 normal response",
            details={
                "secure": True
            },
        )

        ephemeral_job = (
            store.new_job(
                "chat",
                ephemeral,
            )
        )
        store.update_job(
            ephemeral_job,
            response="M13 ephemeral response",
            details={
                "temporary": True
            },
        )

        assertions[
            "privacy_modes_explicit"
        ] = bool(
            store.privacy_mode(
                normal
            )
            is PrivacyMode.NORMAL
            and store.privacy_mode(
                private
            )
            is PrivacyMode.PRIVATE
            and store.privacy_mode(
                ephemeral
            )
            is PrivacyMode.EPHEMERAL
        )

        with sqlite3.connect(
            store.path
        ) as raw:
            persisted_conversations = (
                raw.execute(
                    "SELECT id,title "
                    "FROM conversations "
                    "ORDER BY id"
                ).fetchall()
            )
            persisted_messages = (
                raw.execute(
                    "SELECT conversation_id,"
                    "content,metadata "
                    "FROM messages "
                    "ORDER BY conversation_id"
                ).fetchall()
            )
            persisted_jobs = (
                raw.execute(
                    "SELECT id,response,details "
                    "FROM jobs"
                ).fetchall()
            )

        protected = [
            row[1]
            for row
            in persisted_conversations
        ]
        protected += [
            value
            for row
            in persisted_messages
            for value
            in row[1:]
        ]
        protected += [
            value
            for row
            in persisted_jobs
            for value
            in row[1:]
        ]

        assertions[
            "persistent_payloads_encrypted"
        ] = bool(
            protected
            and all(
                isinstance(
                    value,
                    str,
                )
                and value.startswith(
                    ENCRYPTED_PREFIX
                )
                for value
                in protected
            )
        )

        raw_blob = (
            "\n".join(
                protected
            )
        )

        assertions[
            "persistent_plaintext_absent"
        ] = all(
            secret
            not in raw_blob
            for secret in (
                "M13 normal secret",
                "M13 private secret",
                "M13 normal message",
                "M13 private message",
                "M13 normal response",
            )
        )

        persisted_ids = {
            row[0]
            for row
            in persisted_conversations
        }
        persisted_message_ids = {
            row[0]
            for row
            in persisted_messages
        }
        persisted_job_ids = {
            row[0]
            for row
            in persisted_jobs
        }

        assertions[
            "ephemeral_never_persisted"
        ] = bool(
            ephemeral
            not in persisted_ids
            and ephemeral
            not in persisted_message_ids
            and ephemeral_job
            not in persisted_job_ids
        )

        assertions[
            "durable_round_trip"
        ] = bool(
            store.messages(
                normal
            )[0]["content"]
            == "M13 normal message"
            and store.messages(
                private
            )[0]["content"]
            == "M13 private message"
            and store.job(
                normal_job
            )["response"]
            == "M13 normal response"
        )

        key_mode = (
            store.key_path
            .stat()
            .st_mode
            & 0o777
        )
        database_mode = (
            store.path
            .stat()
            .st_mode
            & 0o777
        )
        assertions[
            "state_files_owner_only"
        ] = bool(
            key_mode
            == 0o600
            and database_mode
            == 0o600
        )

        # Trust cannot be silently escalated.
        repository = (
            _write_repository(
                root
            )
        )
        development_db = (
            root
            / "development.db"
        )

        with database(
            development_db
        ) as connection:
            project = register_project(
                connection,
                repository,
                trust_mode=(
                    TrustMode.UNTRUSTED_REPO
                ),
            )
            trust_blocked = False

            try:
                register_project(
                    connection,
                    repository,
                    trust_mode=(
                        TrustMode.TRUSTED_REPO
                    ),
                )
            except ProjectRegistryError:
                trust_blocked = True

            current = (
                connection.execute(
                    "SELECT trust_mode "
                    "FROM projects "
                    "WHERE id=?",
                    (
                        project.id,
                    ),
                ).fetchone()[0]
            )

        assertions[
            "trust_escalation_blocked"
        ] = bool(
            trust_blocked
            and current
            == TrustMode.UNTRUSTED_REPO.value
        )

        # Host credential/capability handles are filtered and cannot be
        # explicitly reintroduced.
        previous = os.environ.get(
            "SSH_AUTH_SOCK"
        )
        os.environ[
            "SSH_AUTH_SOCK"
        ] = "/tmp/m13-agent.sock"

        try:
            filtered = (
                _safe_environment()
            )
        finally:
            if previous is None:
                os.environ.pop(
                    "SSH_AUTH_SOCK",
                    None,
                )
            else:
                os.environ[
                    "SSH_AUTH_SOCK"
                ] = previous

        explicit_blocked = False

        try:
            _safe_environment(
                {
                    "SSH_AUTH_SOCK":
                    "/tmp/m13-agent.sock"
                }
            )
        except CommandPolicyError:
            explicit_blocked = True

        assertions[
            "credential_capabilities_filtered"
        ] = bool(
            "SSH_AUTH_SOCK"
            not in filtered
            and explicit_blocked
        )

        # Static sandbox construction is also portable: use known system
        # binaries as stand-ins so the command is never executed.
        sandbox_argv = (
            development_sandbox_argv(
                root,
                (
                    "python3",
                    "-c",
                    "print('m13')",
                ),
                timeout_seconds=10,
                bwrap_path="/usr/bin/true",
                prlimit_path="/usr/bin/true",
            )
        )

        assertions[
            "sandbox_contract_fail_closed"
        ] = bool(
            "--unshare-all"
            in sandbox_argv
            and "--share-net"
            not in sandbox_argv
            and "--clearenv"
            in sandbox_argv
            and str(
                Path.home()
            )
            not in sandbox_argv
            and "--bind"
            in sandbox_argv
            and "/workspace"
            in sandbox_argv
        )

        metadata = {
            "persistent_conversations": (
                len(
                    persisted_conversations
                )
            ),
            "persistent_messages": (
                len(
                    persisted_messages
                )
            ),
            "persistent_jobs": (
                len(
                    persisted_jobs
                )
            ),
            "key_mode": oct(
                key_mode
            ),
            "database_mode": oct(
                database_mode
            ),
            "project_trust": (
                current
            ),
            "sandbox_argv_head": list(
                sandbox_argv[:12]
            ),
            "model_calls": 0,
        }

    return {
        "passed": all(
            assertions.values()
        ),
        "assertions": (
            assertions
        ),
        "metadata": metadata,
    }


def run_validation(
    *,
    report_root: Path,
    skip_tests: bool = False,
    skip_live_sandbox: bool = False,
    live_probe=None,
) -> tuple[int, dict]:
    report_root = Path(
        report_root
    )
    report_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    created_at = datetime.now(
        timezone.utc
    )
    stamp = (
        created_at.strftime(
            "%Y%m%dT%H%M%SZ"
        )
    )

    try:
        revision = (
            subprocess.check_output(
                [
                    "git",
                    "rev-parse",
                    "HEAD",
                ],
                text=True,
            ).strip()
        )
    except (
        OSError,
        subprocess.CalledProcessError,
    ):
        revision = None

    summary = {
        "schema_version": 1,
        "created_at": (
            created_at.isoformat()
        ),
        "code_revision": revision,
        "tests": {
            "skipped": (
                skip_tests
            ),
            "returncode": None,
            "passed": None,
            "failed": None,
        },
        "portable_security": {},
        "live_sandbox": {
            "skipped": (
                skip_live_sandbox
            ),
        },
        "portable_ok": False,
        "overall_ok": False,
    }

    if not skip_tests:
        completed = subprocess.run(
            [
                str(
                    Path(
                        sys.executable
                    )
                ),
                "-m",
                "pytest",
                "-q",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        output = (
            (
                completed.stdout
                or ""
            )
            + (
                completed.stderr
                or ""
            )
        )
        counts = (
            _pytest_summary(
                output
            )
        )
        summary[
            "tests"
        ].update(
            returncode=(
                completed.returncode
            ),
            passed=(
                counts["passed"]
            ),
            failed=(
                counts["failed"]
            ),
        )

        if (
            completed.returncode
        ):
            summary[
                "tests"
            ]["tail"] = (
                output[-4000:]
            )

    try:
        summary[
            "portable_security"
        ] = (
            _portable_security()
        )
    except Exception as exc:
        summary[
            "portable_security"
        ] = {
            "passed": False,
            "error": (
                f"{type(exc).__name__}: "
                f"{exc}"
            ),
        }

    if not skip_live_sandbox:
        try:
            probe = (
                run_live_probe
                if live_probe
                is None
                else live_probe
            )
            live = probe()
            summary[
                "live_sandbox"
            ] = {
                "skipped": False,
                **live,
            }
        except Exception as exc:
            summary[
                "live_sandbox"
            ] = {
                "skipped": False,
                "passed": False,
                "error": (
                    f"{type(exc).__name__}: "
                    f"{exc}"
                ),
            }

    tests_ok = bool(
        skip_tests
        or summary[
            "tests"
        ][
            "returncode"
        ]
        == 0
    )
    portable_security_ok = bool(
        summary[
            "portable_security"
        ].get(
            "passed"
        )
        is True
    )

    summary[
        "portable_ok"
    ] = bool(
        tests_ok
        and portable_security_ok
    )

    live_ok = bool(
        not skip_live_sandbox
        and summary[
            "live_sandbox"
        ].get(
            "passed"
        )
        is True
    )

    summary[
        "overall_ok"
    ] = bool(
        summary[
            "portable_ok"
        ]
        and live_ok
    )

    summary_path = (
        report_root
        / (
            "validation-"
            f"{stamp}.json"
        )
    )
    summary[
        "summary_path"
    ] = str(
        summary_path
    )
    summary_path.write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    if summary[
        "overall_ok"
    ]:
        return 0, summary

    if (
        skip_live_sandbox
        and summary[
            "portable_ok"
        ]
    ):
        return 2, summary

    return 1, summary


def main(
    argv: list[str] | None = None,
) -> int:
    parser = (
        argparse.ArgumentParser()
    )
    parser.add_argument(
        "--report-root",
        type=Path,
        default=Path(
            "benchmarks/results/"
            "vnext/m13/live-validation"
        ),
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help=(
            "Skip pytest when a green "
            "full suite has already been "
            "recorded."
        ),
    )
    parser.add_argument(
        "--skip-live-sandbox",
        action="store_true",
        help=(
            "Run portable gates only. "
            "This cannot mark M13 accepted."
        ),
    )

    args = parser.parse_args(
        argv
    )

    code, summary = (
        run_validation(
            report_root=(
                args.report_root
            ),
            skip_tests=(
                args.skip_tests
            ),
            skip_live_sandbox=(
                args.skip_live_sandbox
            ),
        )
    )

    print(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
    )

    return code


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
