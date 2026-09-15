"""Canonical Reverend final acceptance across M16-M18."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from reverend.benchmarks import m16_validation,m17_validation,m18_validation
from reverend.benchmarks.release import run_release_smoke


def _pytest_summary(output: str) -> dict:
    import re
    passed=re.findall(r"(\d+) passed",output)
    failed=re.findall(r"(\d+) failed",output)
    return {
        "passed":int(passed[-1]) if passed else None,
        "failed":int(failed[-1]) if failed else 0,
    }


def _delegated_release(_repository: Path) -> dict:
    return {
        "passed":True,
        "delegated":True,
        "authority":"final_validation.release_smoke",
    }


def _run_m16(repository: Path,report_root: Path,skip_live: bool) -> dict:
    _,summary=m16_validation.run_validation(
        repository=repository,
        report_root=report_root/"m16",
        skip_tests=True,
        skip_live=skip_live,
        release_runner=_delegated_release,
    )
    return summary


def _run_m17(repository: Path,report_root: Path,skip_live: bool) -> dict:
    _,summary=m17_validation.run_validation(
        repository=repository,
        report_root=report_root/"m17",
        skip_tests=True,
        skip_live=skip_live,
        release_runner=_delegated_release,
    )
    return summary


def _run_m18(repository: Path,report_root: Path,skip_live: bool) -> dict:
    _,summary=m18_validation.run_validation(
        repository=repository,
        report_root=report_root/"m18",
        skip_tests=True,
        skip_live=skip_live,
        release_runner=_delegated_release,
    )
    return summary


def run_validation(
    *,
    repository: Path,
    report_root: Path,
    skip_tests: bool=False,
    skip_live: bool=False,
    release_runner=None,
    m16_runner=None,
    m17_runner=None,
    m18_runner=None,
) -> tuple[int,dict]:
    repository=Path(repository).resolve()
    report_root=Path(report_root)
    report_root.mkdir(parents=True,exist_ok=True)
    created_at=datetime.now(timezone.utc)
    stamp=created_at.strftime("%Y%m%dT%H%M%SZ")
    try:
        revision=subprocess.check_output(
            ["git","-C",str(repository),"rev-parse","HEAD"],
            text=True,
        ).strip()
    except (OSError,subprocess.CalledProcessError):
        revision=None

    summary={
        "schema_version":1,
        "programme":"Reverend post-vNext final acceptance",
        "created_at":created_at.isoformat(),
        "code_revision":revision,
        "tests":{
            "skipped":skip_tests,
            "returncode":None,
            "passed":None,
            "failed":None,
        },
        "release_smoke":{},
        "milestones":{},
        "portable_ok":False,
        "live_ok":False,
        "overall_ok":False,
    }

    if not skip_tests:
        completed=subprocess.run(
            [str(Path(sys.executable)),"-m","pytest","-q"],
            cwd=repository,
            text=True,
            capture_output=True,
            check=False,
        )
        output=(completed.stdout or "")+(completed.stderr or "")
        counts=_pytest_summary(output)
        summary["tests"].update(
            returncode=completed.returncode,
            passed=counts["passed"],
            failed=counts["failed"],
        )
        if completed.returncode:
            summary["tests"]["tail"]=output[-4000:]

    try:
        runner=run_release_smoke if release_runner is None else release_runner
        summary["release_smoke"]=runner(repository)
    except Exception as exc:
        summary["release_smoke"]={
            "passed":False,
            "error":f"{type(exc).__name__}: {exc}",
        }

    runners={
        "M16":_run_m16 if m16_runner is None else m16_runner,
        "M17":_run_m17 if m17_runner is None else m17_runner,
        "M18":_run_m18 if m18_runner is None else m18_runner,
    }
    for name,runner in runners.items():
        try:
            milestone=runner(repository,report_root,skip_live)
        except Exception as exc:
            milestone={
                "portable_ok":False,
                "live_ok":False,
                "overall_ok":False,
                "error":f"{type(exc).__name__}: {exc}",
            }
        summary["milestones"][name]=milestone

    tests_ok=bool(skip_tests or summary["tests"]["returncode"]==0)
    milestones=list(summary["milestones"].values())
    summary["portable_ok"]=bool(
        tests_ok
        and summary["release_smoke"].get("passed") is True
        and len(milestones)==3
        and all(item.get("portable_ok") is True for item in milestones)
    )
    summary["live_ok"]=bool(
        not skip_live
        and len(milestones)==3
        and all(item.get("live_ok") is True for item in milestones)
    )
    summary["overall_ok"]=bool(summary["portable_ok"] and summary["live_ok"])

    summary["remaining_gates"]=(
        []
        if summary["overall_ok"]
        else (
            [
                "M16 live Ollama/workstation/strong-code acceptance",
                "M17 live configured search-provider acceptance",
                "M18 live searched-image/sandbox acceptance",
            ]
            if skip_live
            else [
                name
                for name,item in summary["milestones"].items()
                if item.get("overall_ok") is not True
            ]
        )
    )

    path=report_root/f"final-validation-{stamp}.json"
    summary["summary_path"]=str(path)
    path.write_text(
        json.dumps(summary,indent=2,sort_keys=True)+"\n",
        encoding="utf-8",
    )

    if summary["overall_ok"]:
        return 0,summary
    if skip_live and summary["portable_ok"]:
        return 2,summary
    return 1,summary


def main(argv: list[str] | None=None) -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--repository",type=Path,default=Path("."))
    parser.add_argument(
        "--report-root",
        type=Path,
        default=Path("benchmarks/results/vnext/final-validation"),
    )
    parser.add_argument("--skip-tests",action="store_true")
    parser.add_argument(
        "--skip-live",
        action="store_true",
        help=(
            "Run the complete portable programme only. This cannot certify "
            "the real WSL/Ollama/search/image paths."
        ),
    )
    args=parser.parse_args(argv)
    code,summary=run_validation(
        repository=args.repository,
        report_root=args.report_root,
        skip_tests=args.skip_tests,
        skip_live=args.skip_live,
    )
    print(json.dumps(summary,indent=2,sort_keys=True))
    return code


if __name__=="__main__":
    raise SystemExit(main())
