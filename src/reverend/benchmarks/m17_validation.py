"""M17 fresh-web/frontier acceptance validation."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from reverend.benchmarks.catalog import m17_freshness_cases
from reverend.benchmarks.release import run_release_smoke
from reverend.intelligence.evidence import freshness_satisfies
from reverend.intelligence.understanding import freshness_window,understand
from reverend.research.search import (
    BRAVE_SEARCH_ENDPOINT,
    WebSearchConfig,
    configured_web_search,
)
from reverend.research.search_worker import validate_search_endpoint
from reverend.research.service import PublicResearch


def _pytest_summary(output: str) -> dict:
    import re
    passed=re.findall(r"(\d+) passed",output)
    failed=re.findall(r"(\d+) failed",output)
    return {
        "passed":int(passed[-1]) if passed else None,
        "failed":int(failed[-1]) if failed else 0,
    }


def _portable_contract() -> dict:
    brave=WebSearchConfig(
        provider="brave",
        endpoint=BRAVE_SEARCH_ENDPOINT,
        api_key="fixture-secret",
    )
    searx=WebSearchConfig(
        provider="searxng",
        endpoint="http://127.0.0.1:8888",
    )
    cases=m17_freshness_cases()
    assertions={
        "frontier_30_days_is_month":(
            freshness_window(
                "What was released in the last 30 days?"
            )=="month"
        ),
        "historical_absolute_date_is_stable":(
            freshness_window(
                "Which models were released in 2024?"
            )=="stable"
        ),
        "understanding_routes_frontier_current":(
            understand(
                "What important models were released in the last 30 days?"
            ).freshness=="current"
        ),
        "week_source_satisfies_month":freshness_satisfies(
            {"search_freshness":"week"},"month"
        ),
        "year_source_does_not_satisfy_day":not freshness_satisfies(
            {"search_freshness":"year"},"day"
        ),
        "unproven_external_not_fresh":not freshness_satisfies(
            {},"month"
        ),
        "brave_secret_hidden_from_repr":(
            "fixture-secret" not in repr(brave)
        ),
        "brave_safe_metadata_hides_secret":(
            "fixture-secret" not in json.dumps(brave.safe_metadata())
        ),
        "brave_endpoint_pinned":(
            validate_search_endpoint(
                "brave",
                BRAVE_SEARCH_ENDPOINT,
            ).hostname=="api.search.brave.com"
        ),
        "searx_loopback_http_allowed":(
            validate_search_endpoint(
                "searxng",
                searx.endpoint,
            ).hostname=="127.0.0.1"
        ),
        "m17_regression_catalog_complete":{
            case.case_id for case in cases
        }=={
            "m17-frontier-30-day-fresh",
            "m17-stale-external-fails-closed",
            "m17-ask-policy-never-searches",
            "m17-stable-local-first",
        },
    }
    return {
        "passed":all(assertions.values()),
        "assertions":assertions,
        "case_ids":sorted(case.case_id for case in cases),
        "provider_contracts":{
            "brave":brave.safe_metadata(),
            "searxng":searx.safe_metadata(),
        },
    }


def _run_live_search() -> dict:
    config=configured_web_search()
    if config is None:
        return {
            "configured":False,
            "passed":False,
            "error_code":"network_search_unavailable",
            "error":"No web-search provider is configured.",
        }

    with TemporaryDirectory(prefix="reverend-m17-search-") as temporary:
        research=PublicResearch(Path(temporary)/"public-sources.db")
        result=research.discover(
            "Python official documentation",
            allow_network=True,
            freshness="stable",
            limit=3,
            config=config,
        )
        sources=list(result.get("sources") or [])
        passed=bool(
            result.get("search_result_count",0)>0
            and sources
            and all(
                source.get("trust")=="UNTRUSTED_EXTERNAL"
                and str(source.get("url","")).startswith("https://")
                and source.get("content_hash")
                and source.get("search_provider")==config.provider
                and source.get("search_freshness")=="stable"
                for source in sources
            )
        )
        return {
            "configured":True,
            "passed":passed,
            "provider":config.provider,
            "configuration":config.safe_metadata(),
            "search_result_count":result.get("search_result_count"),
            "fetched_count":result.get("fetched_count"),
            "fetch_failure_count":result.get("fetch_failure_count"),
            "source_count":len(sources),
            "sources":[
                {
                    "url":source.get("url"),
                    "source_title":source.get("source_title"),
                    "content_hash":source.get("content_hash"),
                    "search_rank":source.get("search_rank"),
                    "search_freshness":source.get("search_freshness"),
                }
                for source in sources
            ],
        }


def run_validation(
    *,
    repository: Path,
    report_root: Path,
    skip_tests: bool=False,
    skip_live: bool=False,
    release_runner=None,
    live_search_runner=None,
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
        "milestone":"M17",
        "created_at":created_at.isoformat(),
        "code_revision":revision,
        "tests":{
            "skipped":skip_tests,
            "returncode":None,
            "passed":None,
            "failed":None,
        },
        "portable_contract":{},
        "release_smoke":{},
        "live_search":{"skipped":skip_live},
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
        summary["portable_contract"]=_portable_contract()
    except Exception as exc:
        summary["portable_contract"]={
            "passed":False,
            "error":f"{type(exc).__name__}: {exc}",
        }

    try:
        runner=run_release_smoke if release_runner is None else release_runner
        summary["release_smoke"]=runner(repository)
    except Exception as exc:
        summary["release_smoke"]={
            "passed":False,
            "error":f"{type(exc).__name__}: {exc}",
        }

    if not skip_live:
        try:
            runner=_run_live_search if live_search_runner is None else live_search_runner
            summary["live_search"]={"skipped":False,**runner()}
        except Exception as exc:
            error_code=getattr(exc,"code","web_search_failed")
            summary["live_search"]={
                "skipped":False,
                "configured":error_code!="network_search_unavailable",
                "passed":False,
                "error_code":error_code,
                "error":f"{type(exc).__name__}: {exc}",
            }

    tests_ok=bool(skip_tests or summary["tests"]["returncode"]==0)
    summary["portable_ok"]=bool(
        tests_ok
        and summary["portable_contract"].get("passed") is True
        and summary["release_smoke"].get("passed") is True
    )
    summary["live_ok"]=bool(
        not skip_live
        and summary["live_search"].get("configured") is True
        and summary["live_search"].get("passed") is True
    )
    summary["overall_ok"]=bool(
        summary["portable_ok"] and summary["live_ok"]
    )

    path=report_root/f"validation-{stamp}.json"
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
        default=Path("benchmarks/results/vnext/m17/live-validation"),
    )
    parser.add_argument("--skip-tests",action="store_true")
    parser.add_argument(
        "--skip-live",
        action="store_true",
        help=(
            "Run portable M17 gates only. This cannot certify a configured "
            "live web-search provider."
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
