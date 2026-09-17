from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from .notifications import IncidentReporter
from .preflight import ModelPreflight
from .production import (
    ProductionConfig,
    ProductionResult,
    ProductionRunError,
    ProductionRunLocked,
    ProductionRunner,
    SessionStore,
    build_health_snapshot,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reverend-autonomy-v2",
        description="Crash-resilient unattended Reverend development controller.",
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Git repository root (default: current directory)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="start a new unattended C0-C9 production session")
    run.add_argument("--repository", help="GitHub owner/name; auto-detected when omitted")
    run.add_argument(
        "--model",
        default=os.environ.get("REVEREND_AUTONOMY_MODEL", "ollama/reverend-coder30"),
    )
    run.add_argument(
        "--ollama-model",
        default=os.environ.get("REVEREND_OLLAMA_MODEL", "reverend-coder30"),
    )
    run.add_argument("--base-ref", default="HEAD")
    run.add_argument("--include-alex", action="store_true")
    run.add_argument("--max-repairs", type=int, default=3)
    run.add_argument("--max-issues", type=int)
    run.add_argument("--max-issue-attempts", type=int, default=3)
    run.add_argument("--max-deferred-passes", type=int, default=2)
    run.add_argument("--max-milestone-gate-attempts", type=int, default=2)
    run.add_argument("--skip-preflight", action="store_true")
    run.add_argument("--no-push-progress", action="store_true")

    resume = sub.add_parser("resume", help="resume the latest or named session")
    resume.add_argument("--session")
    resume.add_argument("--retry-failed", action="store_true")

    status = sub.add_parser("status", help="show raw durable session manifest")
    status.add_argument("--session")

    health = sub.add_parser("health", help="show concise live autonomy health")
    health.add_argument("--session")

    watch = sub.add_parser("watch", help="continuously display live autonomy health")
    watch.add_argument("--session")
    watch.add_argument("--interval", type=float, default=5.0)
    watch.add_argument("--once", action="store_true")

    incidents = sub.add_parser("incidents", help="show recent autonomy incidents")
    incidents.add_argument("--limit", type=int, default=20)

    preflight = sub.add_parser("preflight", help="prove model read/edit capability")
    preflight.add_argument(
        "--model",
        default=os.environ.get("REVEREND_AUTONOMY_MODEL", "ollama/reverend-coder30"),
    )
    preflight.add_argument(
        "--ollama-model",
        default=os.environ.get("REVEREND_OLLAMA_MODEL", "reverend-coder30"),
    )
    preflight.add_argument("--base-ref", default="HEAD")

    return parser


def _runtime(root: Path) -> Path:
    return root / ".autonomy" / "v2-production"


def _detect_repository(root: Path) -> str:
    completed = subprocess.run(
        ["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"],
        cwd=root,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
        check=False,
    )
    if completed.returncode == 0 and completed.stdout.strip():
        value = completed.stdout.strip()
        if "/" in value:
            return value
    raise ProductionRunError(
        "unable to auto-detect GitHub repository; pass --repository owner/name"
    )


def _config_from_manifest(manifest: dict[str, object]) -> ProductionConfig:
    return ProductionConfig(
        repository=str(manifest["repository"]),
        model=str(manifest["model"]),
        ollama_model=str(manifest["ollama_model"]),
        base_ref=str(manifest["base_ref"]),
        include_alex=bool(manifest.get("include_alex", False)),
        max_repairs=int(manifest.get("max_repairs", 3)),
        max_issue_attempts=int(manifest.get("max_issue_attempts", 3)),
        max_deferred_passes=int(manifest.get("max_deferred_passes", 2)),
        max_milestone_gate_attempts=int(
            manifest.get("max_milestone_gate_attempts", 2)
        ),
        push_progress=bool(manifest.get("push_progress", True)),
        run_preflight=False,
    )


def _print_result(result: ProductionResult) -> None:
    print(
        json.dumps(
            {
                "session_id": result.session_id,
                "status": result.status,
                "completed_issues": result.completed_issues,
                "total_issues": result.total_issues,
                "integration_branch": result.integration_branch,
                "integration_head": result.integration_head,
                "stop_reason": result.stop_reason,
            },
            indent=2,
            sort_keys=True,
        )
    )


def _exit_for_status(status: str) -> int:
    if status in {"COMPLETED", "RUNNING"}:
        return 0
    if status == "MILESTONE_FAILED":
        return 30
    return 20


def _health(root: Path, session: str | None) -> dict[str, object]:
    store = SessionStore(_runtime(root))
    resolved = session or store.latest()
    manifest = store.load(resolved)
    return build_health_snapshot(root, manifest)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = Path(args.root).resolve()
    if not (root / ".git").exists():
        print(f"error: not a Git repository: {root}", file=sys.stderr)
        return 2

    try:
        if args.command == "status":
            store = SessionStore(_runtime(root))
            session = args.session or store.latest()
            print(json.dumps(store.load(session), indent=2, sort_keys=True))
            return 0

        if args.command == "health":
            print(json.dumps(_health(root, args.session), indent=2, sort_keys=True))
            return 0

        if args.command == "watch":
            if args.interval <= 0:
                raise ValueError("watch interval must be positive")
            while True:
                snapshot = _health(root, args.session)
                if not args.once:
                    print("\033[2J\033[H", end="")
                print(json.dumps(snapshot, indent=2, sort_keys=True), flush=True)
                if args.once or snapshot.get("status") in {
                    "COMPLETED", "BLOCKED", "MILESTONE_FAILED"
                }:
                    return _exit_for_status(str(snapshot.get("status")))
                time.sleep(args.interval)

        if args.command == "incidents":
            reporter = IncidentReporter(root)
            print(json.dumps(reporter.latest(args.limit), indent=2, sort_keys=True))
            return 0

        if args.command == "preflight":
            report = ModelPreflight(
                root,
                opencode_model=args.model,
                ollama_model=args.ollama_model,
            ).run(base_ref=args.base_ref)
            print(
                json.dumps(
                    {
                        "passed": report.passed,
                        "errors": list(report.errors),
                        "warnings": list(report.warnings),
                        "logs": [str(path) for path in report.log_paths],
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0 if report.passed else 20

        if args.command == "run":
            repository = args.repository or _detect_repository(root)
            config = ProductionConfig(
                repository=repository,
                model=args.model,
                ollama_model=args.ollama_model,
                base_ref=args.base_ref,
                include_alex=args.include_alex,
                max_repairs=args.max_repairs,
                max_issues=args.max_issues,
                max_issue_attempts=args.max_issue_attempts,
                max_deferred_passes=args.max_deferred_passes,
                max_milestone_gate_attempts=args.max_milestone_gate_attempts,
                push_progress=not args.no_push_progress,
                run_preflight=not args.skip_preflight,
            )
            result = ProductionRunner(root, config=config).start()
            _print_result(result)
            return _exit_for_status(result.status)

        if args.command == "resume":
            store = SessionStore(_runtime(root))
            session = args.session or store.latest()
            manifest = store.load(session)
            config = _config_from_manifest(manifest)
            result = ProductionRunner(root, config=config).resume(
                session,
                retry_failed=args.retry_failed,
            )
            _print_result(result)
            return _exit_for_status(result.status)

        raise AssertionError(args.command)

    except ProductionRunLocked as exc:
        print(f"temporary: {exc}", file=sys.stderr)
        return 75
    except (ProductionRunError, KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 20
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"controller crash: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 70


if __name__ == "__main__":
    raise SystemExit(main())
