"""M16 runtime reliability and agent-state acceptance validation."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from reverend.benchmarks.catalog import m16_reliability_cases
from reverend.benchmarks.release import run_release_smoke
from reverend.intelligence.contracts import RequestBudget
from reverend.runtime.completion import CompletionReason
from reverend.runtime.models import DEFAULT_MODELS, ModelRole
from reverend.workstation.agent_loop import (
    MAX_AUTO_CONTINUATIONS_PER_REQUEST,
    MAX_TOTAL_TASK_CONTINUATIONS,
)
from reverend.workstation.context import compile_chat_prompt_v2
from reverend.workstation.presentation import response_details
from reverend.workstation.task_state import extract_authoritative_requirements
from reverend.workstation.verification import VerificationCheck


def _pytest_summary(output: str) -> dict:
    import re
    passed=re.findall(r"(\d+) passed",output)
    failed=re.findall(r"(\d+) failed",output)
    return {
        "passed":int(passed[-1]) if passed else None,
        "failed":int(failed[-1]) if failed else 0,
    }


def _portable_contract() -> dict:
    cases=m16_reliability_cases()
    case_ids={case.case_id for case in cases}
    completion_values={item.value for item in CompletionReason}

    prompt,context=compile_chat_prompt_v2(
        instruction="SYSTEM",
        current_request="Continue Exercise 99",
        authoritative_task=(
            "AUTHORITATIVE TASK — TRUSTED USER STATE\n"
            "Exercise 99 must remain unchanged."
        ),
        recent_messages=[],
        retrieved_messages=[],
        evidence_sources=[],
        context_window=8192,
        output_reserve_tokens=1536,
    )
    extracted=extract_authoritative_requirements(
        "Requirements:\n"
        "- MUST preserve ALPHA.\n"
        "- DO NOT emit BETA.\n"
        "Acceptance criteria:\n"
        "- Exactly 2 output items."
    )
    safe=response_details({
        "role":"deep_reason",
        "completion_reason":"complete",
        "hidden_reasoning_present":True,
        "thinking_activity_count":3,
        "prompt":"SECRET_PROMPT",
        "raw_response":"SECRET_RAW",
        "chain_of_thought":"SECRET_REASONING",
        "sources":[{"content":"SECRET_SOURCE"}],
    })
    safe_serialized=json.dumps(safe,sort_keys=True)

    assertions={
        "request_budget_ceiling_4096":RequestBudget().output_tokens==4096,
        "strong_code_model_preserved":DEFAULT_MODELS[ModelRole.STRONG_CODE].model=="qwen3-coder:30b",
        "strong_code_context_16k":DEFAULT_MODELS[ModelRole.STRONG_CODE].context==16384,
        "strong_code_exclusive":DEFAULT_MODELS[ModelRole.STRONG_CODE].exclusive_memory is True,
        "deep_reason_exclusive":DEFAULT_MODELS[ModelRole.DEEP_REASON].exclusive_memory is True,
        "fast_general_shared":DEFAULT_MODELS[ModelRole.FAST_GENERAL].exclusive_memory is False,
        "completion_output_limit_typed":"output_limit_reached" in completion_values,
        "completion_reasoning_exhaustion_typed":(
            "reasoning_budget_exhausted_before_answer" in completion_values
        ),
        "context_compiler_v2":context.get("context_compiler")=="v2",
        "authority_precedes_current_request":(
            prompt.index("AUTHORITATIVE TASK — TRUSTED USER STATE")
            < prompt.index("CURRENT USER REQUEST — TRUSTED USER INSTRUCTION")
        ),
        "requirements_extracted":len(extracted.immutable_requirements)==2,
        "acceptance_extracted":len(extracted.acceptance_criteria)==1,
        "high_assurance_detected":extracted.high_assurance is True,
        "agent_loop_per_request_bound":MAX_AUTO_CONTINUATIONS_PER_REQUEST==2,
        "agent_loop_lineage_bound":MAX_TOTAL_TASK_CONTINUATIONS==8,
        "m16_regression_catalog_complete":case_ids=={
            "m16-reasoning-budget-exhausted",
            "m16-output-limit-checkpoint",
            "m16-high-assurance-verification",
            "m16-verification-fails-closed",
        },
        "response_details_hides_prompt":"SECRET_PROMPT" not in safe_serialized,
        "response_details_hides_raw_response":"SECRET_RAW" not in safe_serialized,
        "response_details_hides_reasoning":"SECRET_REASONING" not in safe_serialized,
        "response_details_hides_source_body":"SECRET_SOURCE" not in safe_serialized,
        "verification_status_contract":VerificationCheck(
            "semantic requirement","unchecked","semantic_only"
        ).status=="unchecked",
    }
    return {
        "passed":all(assertions.values()),
        "assertions":assertions,
        "m16_case_ids":sorted(case_ids),
        "model_profile":{
            role.value:{
                "model":spec.model,
                "context":spec.context,
                "exclusive_memory":spec.exclusive_memory,
            }
            for role,spec in DEFAULT_MODELS.items()
        },
    }


def _wait_job(workstation,identity: str,*,timeout: float=240.0) -> dict:
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        job=workstation.store.job(identity)
        if job["status"] not in {"queued","running","stopping"}:
            return job
        time.sleep(0.05)
    try:
        workstation.cancel(identity)
    except Exception:
        pass
    raise TimeoutError("M16 live Workstation inference timed out.")


def _raw_reasoning_keys(value) -> list[str]:
    forbidden={"thinking","chain_of_thought","raw_response"}
    found=[]
    def visit(item,path=""):
        if isinstance(item,dict):
            for key,child in item.items():
                child_path=f"{path}.{key}" if path else str(key)
                if key in forbidden:
                    found.append(child_path)
                visit(child,child_path)
        elif isinstance(item,list):
            for index,child in enumerate(item):
                visit(child,f"{path}[{index}]")
    visit(value)
    return found


def _run_live_workstation() -> dict:
    from reverend.development.coder import create_local_scheduler
    from reverend.workstation.service import Workstation

    with TemporaryDirectory(prefix="reverend-m16-live-") as temporary:
        workstation=Workstation(
            Path(temporary),
            scheduler_factory=create_local_scheduler,
        )
        try:
            probes=[]
            for name,prompt,mode in (
                (
                    "fast_general",
                    "Reply with one short sentence confirming local inference is running.",
                    "ask",
                ),
                (
                    "deep_reason",
                    "Reason privately, then reply with exactly the single word READY.",
                    "reason",
                ),
            ):
                started=time.monotonic()
                submitted=workstation.chat(
                    prompt,
                    mode=mode,
                    max_model_calls=1,
                    privacy_mode="ephemeral",
                )
                job=_wait_job(workstation,submitted["job_id"])
                details=dict(job.get("details") or {})
                response=str(job.get("response") or "").strip()
                raw_keys=_raw_reasoning_keys(details)
                expected_role=name
                passed=bool(
                    job.get("status")=="complete"
                    and response
                    and details.get("model_calls")==1
                    and details.get("generation_calls")==1
                    and details.get("completion_reason")=="complete"
                    and details.get("role")==expected_role
                    and not raw_keys
                )
                probes.append({
                    "name":name,
                    "passed":passed,
                    "wall_seconds":round(time.monotonic()-started,6),
                    "status":job.get("status"),
                    "role":details.get("role"),
                    "model":details.get("model"),
                    "completion_reason":details.get("completion_reason"),
                    "prompt_tokens":details.get("prompt_tokens"),
                    "generated_tokens":details.get("generated_tokens"),
                    "hidden_reasoning_present":details.get("hidden_reasoning_present"),
                    "thinking_activity_count":details.get("thinking_activity_count"),
                    "raw_reasoning_keys":raw_keys,
                    "response":response,
                })

            return {
                "passed":all(row["passed"] for row in probes),
                "probes":probes,
            }
        finally:
            workstation.close()


def _run_live_strong_code() -> dict:
    from reverend.development.coder import create_local_scheduler

    scheduler=create_local_scheduler()
    started=time.monotonic()
    chunks=list(
        scheduler.stream(
            ModelRole.STRONG_CODE,
            "Return exactly the single word READY.",
            predict=64,
        )
    )
    response="".join(
        str(chunk.get("response") or "")
        for chunk in chunks
    ).strip()
    final=chunks[-1] if chunks else {}
    passed=bool(
        response
        and final.get("done") is True
        and final.get("completion_reason")=="complete"
        and final.get("role")=="strong_code"
        and final.get("model")=="qwen3-coder:30b"
        and final.get("context")==16384
        and final.get("exclusive_memory") is True
        and final.get("residency_policy")=="exclusive"
        and "thinking" not in final
        and "chain_of_thought" not in final
    )
    return {
        "passed":passed,
        "wall_seconds":round(time.monotonic()-started,6),
        "response":response,
        "model":final.get("model"),
        "role":final.get("role"),
        "context":final.get("context"),
        "completion_reason":final.get("completion_reason"),
        "exclusive_memory":final.get("exclusive_memory"),
        "residency_policy":final.get("residency_policy"),
        "residency_unload_count":final.get("residency_unload_count"),
        "residency_unloaded_models":final.get("residency_unloaded_models"),
        "generated_tokens":final.get("generated_tokens"),
    }


def run_validation(
    *,
    repository: Path,
    report_root: Path,
    skip_tests: bool=False,
    skip_live: bool=False,
    release_runner=None,
    live_workstation_runner=None,
    strong_code_runner=None,
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
        "milestone":"M16",
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
        "live_workstation":{"skipped":skip_live},
        "live_strong_code":{"skipped":skip_live},
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
            runner=(
                _run_live_workstation
                if live_workstation_runner is None
                else live_workstation_runner
            )
            summary["live_workstation"]={"skipped":False,**runner()}
        except Exception as exc:
            summary["live_workstation"]={
                "skipped":False,
                "passed":False,
                "error":f"{type(exc).__name__}: {exc}",
            }

        try:
            runner=(
                _run_live_strong_code
                if strong_code_runner is None
                else strong_code_runner
            )
            summary["live_strong_code"]={"skipped":False,**runner()}
        except Exception as exc:
            summary["live_strong_code"]={
                "skipped":False,
                "passed":False,
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
        and summary["live_workstation"].get("passed") is True
        and summary["live_strong_code"].get("passed") is True
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
        default=Path("benchmarks/results/vnext/m16/live-validation"),
    )
    parser.add_argument("--skip-tests",action="store_true")
    parser.add_argument(
        "--skip-live",
        action="store_true",
        help=(
            "Run portable M16 gates only. This cannot mark M16 accepted."
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
