"""M18 workstation visual/artifact acceptance validation."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from reverend.benchmarks.release import run_release_smoke
from reverend.intelligence.evidence import EvidenceClass,select_evidence
from reverend.research.image_worker import ALLOWED_MEDIA_TYPES,MAX_IMAGE_BYTES
from reverend.research.search import configured_web_search
from reverend.research.service import PublicResearch


def _pytest_summary(output: str) -> dict:
    import re
    passed=re.findall(r"(\d+) passed",output)
    failed=re.findall(r"(\d+) failed",output)
    return {
        "passed":int(passed[-1]) if passed else None,
        "failed":int(failed[-1]) if failed else 0,
    }


def _portable_contract(repository: Path) -> dict:
    root=Path(repository)
    ui=root/"src"/"reverend"/"ui"
    app=(ui/"app.js").read_text(encoding="utf-8")
    sources=(ui/"sources.js").read_text(encoding="utf-8")
    diagrams=(ui/"diagrams.js").read_text(encoding="utf-8")
    html=(ui/"index.html").read_text(encoding="utf-8")
    css=(ui/"app.css").read_text(encoding="utf-8")
    server=(root/"src"/"reverend"/"workstation"/"server.py").read_text(encoding="utf-8")
    workstation=(root/"src"/"reverend"/"workstation"/"service.py").read_text(encoding="utf-8")

    assertions={
        "local_ui_scripts_only":(
            '<script defer src="http://' not in html
            and '<script defer src="https://' not in html
        ),
        "markdown_remote_images_disabled":(
            ".disable('image')" in app
        ),
        "images_use_authenticated_local_proxy":(
            "/api/research/images/" in app
            and "X-Reverend-Token" in app
            and "URL.createObjectURL" in app
            and "URL.revokeObjectURL" in app
        ),
        "browser_never_uses_source_url_as_img_src":(
            "img.src=source.url" not in app+sources
            and "img.src=source.source" not in app+sources
        ),
        "csp_allows_blob_not_remote_images":(
            "img-src 'self' data: blob:;" in server
            and "img-src 'self' data: https:" not in server
        ),
        "html_preview_is_sandboxed":(
            "frame.setAttribute('sandbox','')" in app
            and "allow-scripts" not in app
            and "DOMPurify.sanitize(preview.source" in app
        ),
        "diagram_renderer_is_local_and_bounded":(
            "MAX_NODES=40" in diagrams
            and "MAX_EDGES=80" in diagrams
            and "createElementNS" in diagrams
            and "innerHTML" not in diagrams
        ),
        "searched_images_follow_evidence_gate":(
            workstation.index("sources=list(evidence_result.accepted)")
            < workstation.index("self.research.fetch_image(")
            and "source.get('evidence_class')=='FRESH'" in workstation
            and "image_candidates[:2]" in workstation
        ),
        "visual_evidence_gallery_shipped":(
            "source-gallery" in sources
            and ".source-gallery" in css
        ),
        "artifact_expand_mode_shipped":(
            "setInspectorWide" in app
            and ".inspector-open.inspector-wide" in css
        ),
        "source_navigation_shipped":(
            "sourceSet:[]" in app
            and "selectInspectorSource" in app
            and "← Previous" in app
            and "Next →" in app
        ),
        "research_activity_states_shipped":(
            "Searching the web…" in app
            and "Reading web sources…" in app
            and "Searching local knowledge…" in app
        ),
    }
    return {
        "passed":all(assertions.values()),
        "assertions":assertions,
    }


_LIVE_VISUAL_QUERIES=(
    "NVIDIA GeForce RTX 5070 Laptop GPU recent",
    "NVIDIA GeForce RTX 5070 Laptop GPU review recent",
    "NVIDIA GeForce RTX 5070 Laptop GPU specifications recent",
)


def _run_live_visual(
    *,
    config=None,
    research_factory=PublicResearch,
    queries=None,
) -> dict:
    config=configured_web_search() if config is None else config
    if config is None:
        return {
            "configured":False,
            "passed":False,
            "error_code":"network_search_unavailable",
            "error":"No web-search provider is configured.",
        }

    probe_queries=tuple(queries or _LIVE_VISUAL_QUERIES)
    if not probe_queries or len(probe_queries)>3:
        raise ValueError("M18 live visual probe must use one to three bounded queries")

    with TemporaryDirectory(prefix="reverend-m18-visual-") as temporary:
        research=research_factory(Path(temporary)/"public-sources.db")
        attempts=[]
        total_search_results=0
        total_fetched=0
        total_accepted=0
        saw_image_candidate=False

        for query_index,query in enumerate(probe_queries,1):
            discovered=research.discover(
                query,
                allow_network=True,
                freshness="month",
                limit=3,
                config=config,
            )
            candidates=[]
            for index,source in enumerate(discovered.get("sources") or [],1):
                candidates.append({
                    "chunk_id":"public:"+source["id"],
                    "source":source["url"],
                    "source_title":source.get("source_title") or source["url"],
                    "corpus":"public",
                    "trust_class":"UNTRUSTED_EXTERNAL",
                    "content":source.get("content","")[:2000],
                    "id":source["id"],
                    "citation_label":f"W{query_index}-{index}",
                    "search_provider":source.get("search_provider"),
                    "search_rank":source.get("search_rank"),
                    "search_freshness":source.get("search_freshness"),
                    "_image_candidate_url":source.get("_image_candidate_url"),
                })

            gated=select_evidence(
                query,
                candidates,
                (EvidenceClass.FRESH,),
                limit=3,
            )
            visuals=[
                row for row in gated.accepted
                if row.get("_image_candidate_url")
            ]

            search_result_count=int(discovered.get("search_result_count") or 0)
            fetched_count=int(discovered.get("fetched_count") or 0)
            accepted_count=len(gated.accepted)
            total_search_results+=search_result_count
            total_fetched+=fetched_count
            total_accepted+=accepted_count

            attempt={
                "query_index":query_index,
                "search_result_count":search_result_count,
                "fetched_count":fetched_count,
                "accepted_count":accepted_count,
                "image_candidate_count":len(visuals),
                "image_attempts":0,
                "image_failures":0,
                "outcome":"no_image_candidate" if not visuals else "candidate_found",
            }

            if not visuals:
                attempts.append(attempt)
                continue

            saw_image_candidate=True
            for visual in visuals[:2]:
                attempt["image_attempts"]+=1
                try:
                    metadata=research.fetch_image(
                        visual["_image_candidate_url"],
                        allow_network=True,
                        source_id=visual["id"],
                    )
                    image=research.image(metadata["id"])
                    source=research.get(visual["id"])
                except Exception:
                    attempt["image_failures"]+=1
                    continue

                passed=bool(
                    metadata.get("media_type") in ALLOWED_MEDIA_TYPES
                    and 0<metadata.get("byte_count",0)<=MAX_IMAGE_BYTES
                    and source.get("image_id")==metadata.get("id")
                    and image.get("media_type")==metadata.get("media_type")
                    and len(image.get("content",b""))==metadata.get("byte_count")
                )
                if not passed:
                    attempt["image_failures"]+=1
                    continue

                attempt["outcome"]="passed"
                attempts.append(attempt)
                return {
                    "configured":True,
                    "passed":True,
                    "provider":config.provider,
                    "configuration":config.safe_metadata(),
                    "search_result_count":search_result_count,
                    "fetched_count":fetched_count,
                    "accepted_count":accepted_count,
                    "probe_attempt_count":len(attempts),
                    "attempts":attempts,
                    "image":{
                        "id":metadata.get("id"),
                        "media_type":metadata.get("media_type"),
                        "byte_count":metadata.get("byte_count"),
                        "content_hash":metadata.get("content_hash"),
                    },
                }

            attempt["outcome"]="image_acquisition_failed"
            attempts.append(attempt)

        return {
            "configured":True,
            "passed":False,
            "provider":config.provider,
            "configuration":config.safe_metadata(),
            "error_code":(
                "live_image_acquisition_failed"
                if saw_image_candidate
                else "live_image_candidate_unavailable"
            ),
            "search_result_count":total_search_results,
            "fetched_count":total_fetched,
            "accepted_count":total_accepted,
            "probe_attempt_count":len(attempts),
            "attempts":attempts,
        }

def run_validation(
    *,
    repository: Path,
    report_root: Path,
    skip_tests: bool=False,
    skip_live: bool=False,
    release_runner=None,
    live_visual_runner=None,
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
        "milestone":"M18",
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
        "live_visual":{"skipped":skip_live},
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
        summary["portable_contract"]=_portable_contract(repository)
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
            runner=_run_live_visual if live_visual_runner is None else live_visual_runner
            summary["live_visual"]={"skipped":False,**runner()}
        except Exception as exc:
            error_code=getattr(exc,"code","live_visual_failed")
            summary["live_visual"]={
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
        and summary["live_visual"].get("configured") is True
        and summary["live_visual"].get("passed") is True
    )
    summary["overall_ok"]=bool(summary["portable_ok"] and summary["live_ok"])

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
        default=Path("benchmarks/results/vnext/m18/live-validation"),
    )
    parser.add_argument("--skip-tests",action="store_true")
    parser.add_argument(
        "--skip-live",
        action="store_true",
        help=(
            "Run portable M18 gates only. This cannot certify the live "
            "searched-image path through the configured provider."
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
