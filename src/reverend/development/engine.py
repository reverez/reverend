"""End-to-end autonomous local development engine for Reverend."""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from dataclasses import asdict, dataclass

from reverend.runtime import ModelScheduler
from reverend.workers import (
    OrchestrationResult,
    WorkerBudget,
    WorkerExecution,
    WorkerOrchestrator,
    WorkerRole,
    WorkerStatus,
    WorkerStopReason,
    WorkerTask,
)

from .coder import (
    CodingPlanRun,
    generate_coding_plan,
)
from .edits import (
    EditApplyError,
    EditBatchResult,
    apply_edits,
)
from .implementation_model import (
    ImplementationProposalRun,
    ImplementationResponseError,
    generate_implementation_proposals,
)
from .repair import (
    DEFAULT_MAX_REPAIRS,
    RepairLoopResult,
    run_repair_loop,
)
from .repair_model import (
    make_local_repair_strategy,
)
from .tasks import (
    TaskNotFoundError,
    get_task,
)
from .verification import (
    VerificationCheck,
    discover_verification_plan,
)
from .verifier import (
    FreshVerificationResult,
    run_fresh_verifier,
)


class DevelopmentEngineError(RuntimeError):
    """Base autonomous development engine error."""


_DEVELOPMENT_WORKER_BUDGET = WorkerBudget(
    max_workers=3,
    max_worker_steps=3,
    max_tool_calls=0,
)

# One semantic correction cycle fits inside the current hard eight-model-call
# request ceiling while preserving independent verification.
MAX_SEMANTIC_REPAIR_CYCLES = 1


@dataclass(frozen=True)
class DevelopmentRunResult:
    status: str
    plan: CodingPlanRun
    implementation: ImplementationProposalRun | None
    initial_edits: EditBatchResult | None
    repair: RepairLoopResult | None
    verifier: FreshVerificationResult | None
    message: str
    orchestration: OrchestrationResult | None = None
    semantic_repairs_used: int = 0
    total_repairs_used: int = 0

    @property
    def passed(self) -> bool:
        return self.status == "pass"


def _result_status(
    verifier: FreshVerificationResult,
) -> str:
    if verifier.verdict == "pass":
        return "pass"

    if verifier.verdict == "fail":
        return "fail"

    return "unverified"


def _orchestration_event(
    result: OrchestrationResult,
) -> dict:
    return {
        "stop_reason": result.stop_reason.value,
        "workers_used": result.workers_used,
        "worker_steps": result.worker_steps,
        "tool_calls": result.tool_calls,
        "records": [
            {
                "task_id": record.task_id,
                "role": record.role.value,
                "status": record.status.value,
                "stop_reason": record.stop_reason.value,
                "verified_by": record.verified_by,
            }
            for record in result.records
        ],
    }


def _verifier_feedback(verifier: FreshVerificationResult) -> str:
    parts=[
        "Fresh independent verifier rejected the current implementation.",
        f"VERDICT: {getattr(verifier,'verdict','unknown')}",
        f"SUMMARY: {str(getattr(verifier,'summary',''))[:3000]}",
    ]
    findings=getattr(verifier,'findings',()) or ()
    for item in findings[:12]:
        parts.append(
            "FINDING: "
            + f"{getattr(item,'criterion','criterion')} | "
            + f"{getattr(item,'status','unknown')} | "
            + str(getattr(item,'evidence',''))[:1200]
        )
    risks=getattr(verifier,'risks',()) or ()
    for risk in risks[:8]:
        parts.append("RISK: "+str(risk)[:1200])
    return "\n".join(parts)[:6000]


def _remaining_model_calls(scheduler) -> int | None:
    budget=getattr(scheduler,"budget",None)
    runs=getattr(scheduler,"runs",None)
    maximum=getattr(budget,"max_model_calls",None)
    if isinstance(maximum,int) and isinstance(runs,list):
        return max(0,maximum-len(runs))
    return None


def _merge_orchestration(
    results: list[OrchestrationResult],
) -> OrchestrationResult:
    if not results:
        raise DevelopmentEngineError("No orchestration results to merge.")
    return OrchestrationResult(
        records=tuple(
            record
            for result in results
            for record in result.records
        ),
        stop_reason=results[-1].stop_reason,
        workers_used=sum(result.workers_used for result in results),
        worker_steps=sum(result.worker_steps for result in results),
        tool_calls=sum(result.tool_calls for result in results),
    )


def run_development_task(
    connection: sqlite3.Connection,
    task_id: str,
    scheduler: ModelScheduler,
    *,
    checks: tuple[VerificationCheck, ...] | None = None,
    run_id: str | None = None,
    step_id: str | None = None,
    max_repairs: int = DEFAULT_MAX_REPAIRS,
    python_executable: str | None = None,
    on_event=None,
) -> DevelopmentRunResult:
    """Execute one complete Reverend development task.

    M11 owns the logical worker sequence. The mature M5 execution plane remains
    authoritative: workers never receive direct filesystem or shell authority,
    repository mutation still flows only through apply_edits(), deterministic
    checks still run through the verification subsystem, and the fresh verifier
    remains a separate callback from the coder worker.
    """

    task = get_task(
        connection,
        task_id,
    )

    if task is None:
        raise TaskNotFoundError(
            f"Unknown task: {task_id}"
        )

    if not task.worktree_path:
        raise DevelopmentEngineError(
            "Task has no isolated worktree."
        )

    state: dict[str, object] = {}

    def execute_worker(
        worker_task: WorkerTask,
        policy,
    ) -> WorkerExecution:
        if worker_task.role is WorkerRole.CODE_LOCALIZER:
            if not policy.repository_read or policy.propose_edits:
                raise DevelopmentEngineError(
                    "Code Localizer policy violates development isolation."
                )

            if on_event:
                on_event(
                    "plan",
                    {"stage_status": "running"},
                )

            plan_run = generate_coding_plan(
                connection,
                task_id,
                scheduler,
                run_id=run_id,
                step_id=step_id,
                corrective_feedback=(
                    state.get("corrective_feedback")
                    if isinstance(state.get("corrective_feedback"),str)
                    else None
                ),
            )
            state["plan"] = plan_run

            if on_event:
                localization = getattr(plan_run, "localization", None)
                acceptance = getattr(plan_run, "acceptance_contract", None)
                on_event(
                    "localization",
                    {
                        "candidate_files": [
                            {
                                "path": item.path,
                                "confidence": item.confidence,
                                "is_test": item.is_test,
                            }
                            for item in getattr(localization, "candidates", ())
                        ],
                        "affected_tests": list(
                            getattr(localization, "affected_tests", ())
                        ),
                        "excluded_paths": list(
                            getattr(localization, "excluded_paths", ())
                        ),
                    },
                )
                on_event(
                    "acceptance",
                    {
                        "digest": getattr(acceptance, "digest", None),
                        "criteria": [
                            {
                                "id": item.criterion_id,
                                "text": item.text,
                                "category": item.category,
                                "testability": item.testability,
                            }
                            for item in getattr(acceptance, "criteria", ())
                        ],
                    },
                )
                plan_payload = (
                    asdict(plan_run.plan)
                    if hasattr(plan_run.plan, "__dataclass_fields__")
                    else {
                        "summary": str(getattr(plan_run.plan, "summary", "")),
                        "planned_paths": [
                            getattr(item, "path", "")
                            for item in getattr(plan_run.plan, "files", ())
                        ],
                    }
                )
                plan_payload["stage_status"] = "complete"
                on_event(
                    "plan",
                    plan_payload,
                )

            if plan_run.plan.needs_more_context:
                return WorkerExecution(
                    status=WorkerStatus.BLOCKED,
                    output_state={
                        "reason": "needs_more_context",
                        "plan_summary": str(getattr(plan_run.plan, "summary", ""))[:4000],
                    },
                )

            return WorkerExecution(
                status=WorkerStatus.COMPLETE,
                output_state={
                    "plan_summary": str(getattr(plan_run.plan, "summary", ""))[:4000],
                    "planned_paths": [
                        planned.path
                        for planned in getattr(plan_run.plan, "files", ())
                    ],
                },
            )

        if worker_task.role is WorkerRole.CODER:
            if not policy.propose_edits or policy.execute_tools:
                raise DevelopmentEngineError(
                    "Coder policy violates development isolation."
                )

            plan_run = state.get("plan")

            if plan_run is None:
                raise DevelopmentEngineError(
                    "Coder worker started without a typed localizer result."
                )

            dependencies = worker_task.input_state.get("dependencies")
            localized = (
                dependencies.get("localize")
                if isinstance(dependencies, Mapping)
                else None
            )
            if not isinstance(localized, Mapping):
                raise DevelopmentEngineError(
                    "Coder worker received no typed localizer dependency state."
                )

            expected_summary = str(
                getattr(plan_run.plan, "summary", "")
            )[:4000]
            expected_paths = [
                planned.path
                for planned in getattr(plan_run.plan, "files", ())
            ]
            if (
                localized.get("plan_summary") != expected_summary
                or list(localized.get("planned_paths", ())) != expected_paths
            ):
                raise DevelopmentEngineError(
                    "Coder dependency state does not match the host-localized plan."
                )

            if on_event:
                on_event(
                    "implementation",
                    {"stage_status": "running"},
                )

            edit_validation_repairs = 0
            edit_validation_feedback: str | None = None
            cycle_repair_budget = int(
                state.get("cycle_repair_budget", max_repairs)
            )

            while True:
                try:
                    implementation = generate_implementation_proposals(
                        connection,
                        task_id,
                        scheduler,
                        plan_run.plan,
                        run_id=run_id,
                        step_id=step_id,
                        corrective_feedback=edit_validation_feedback,
                    )
                except ImplementationResponseError as exc:
                    detail = str(exc)
                    recoverable = (
                        detail == "Repair response contains no edits."
                    )
                    if (
                        not recoverable
                        or edit_validation_repairs >= cycle_repair_budget
                    ):
                        raise

                    edit_validation_repairs += 1
                    state["initial_edit_repairs_used"] = (
                        int(state.get("initial_edit_repairs_used", 0))
                        + 1
                    )
                    edit_validation_feedback = (
                        "The previous structured implementation response contained "
                        "no usable edits even though the approved coding plan has "
                        "actionable files. Return the complete corrected JSON object "
                        "for the same approved plan with every required edit. "
                        "Do not return edits=[] unless needs_more_context=true. "
                        "Host diagnostic:\n"
                        + detail[:3500]
                    )
                    if on_event:
                        on_event(
                            "repair",
                            {
                                "stage_status": "retrying",
                                "failure_kind": "implementation_empty_edits",
                                "attempt": edit_validation_repairs,
                                "diagnostic": detail[:3500],
                            },
                        )
                    continue

                state["implementation"] = implementation

                if implementation.needs_more_context:
                    return WorkerExecution(
                        status=WorkerStatus.BLOCKED,
                        output_state={
                            "reason": "needs_more_context",
                            "summary": str(getattr(implementation, "summary", ""))[:4000],
                        },
                    )

                try:
                    initial_edits = apply_edits(
                        connection,
                        task_id,
                        implementation.proposals,
                    )
                    break
                except EditApplyError as exc:
                    detail = str(exc)
                    recoverable = detail.startswith(
                        "Applied edits failed Git whitespace validation:"
                    )
                    if (
                        not recoverable
                        or edit_validation_repairs >= cycle_repair_budget
                    ):
                        raise

                    edit_validation_repairs += 1
                    state["initial_edit_repairs_used"] = (
                        int(state.get("initial_edit_repairs_used", 0))
                        + 1
                    )
                    edit_validation_feedback = (
                        "The previous structured edit proposal was safely rolled "
                        "back by the host because Git whitespace validation failed. "
                        "Return a corrected proposal for the same approved plan. "
                        "Remove the reported trailing-whitespace/whitespace errors "
                        "without changing unrelated content. Host diagnostic:\n"
                        + detail[:3500]
                    )
                    if on_event:
                        on_event(
                            "repair",
                            {
                                "stage_status": "retrying",
                                "failure_kind": "edit_whitespace_validation",
                                "attempt": edit_validation_repairs,
                                "diagnostic": detail[:3500],
                            },
                        )

            state["initial_edits"] = initial_edits

            if on_event:
                on_event(
                    "edits",
                    {
                        "stage_status": "complete",
                        "changed_paths": list(initial_edits.changed_paths),
                        "diff": getattr(initial_edits, "diff", "")[:64000],
                    },
                )

            if checks is None:
                localization = getattr(plan_run, "localization", None)
                discovered = discover_verification_plan(
                    task.worktree_path,
                    python_executable=python_executable,
                    affected_tests=tuple(
                        getattr(localization, "affected_tests", ())
                    ),
                )
            else:
                discovered = tuple(checks)

            if not discovered:
                state["no_checks"] = True
                return WorkerExecution(
                    status=WorkerStatus.BLOCKED,
                    output_state={
                        "reason": "no_deterministic_checks",
                        "changed_paths": list(initial_edits.changed_paths),
                    },
                )

            repair_strategy = make_local_repair_strategy(
                connection,
                task_id,
                scheduler,
                run_id=run_id,
                step_id=step_id,
            )

            if on_event:
                on_event(
                    "verification",
                    {
                        "stage_status": "running",
                        "checks": [
                            {
                                "name": getattr(check, "name", ""),
                                "kind": getattr(check, "kind", ""),
                                "argv": list(getattr(check, "argv", ())),
                            }
                            for check in discovered
                        ],
                    },
                )

            repair = run_repair_loop(
                connection,
                task_id,
                discovered,
                repair_strategy,
                run_id=run_id,
                step_id=step_id,
                max_repairs=max(
                    0,
                    int(state.get("cycle_repair_budget", max_repairs))
                    - edit_validation_repairs,
                ),
            )
            state["repair"] = repair

            if on_event:
                on_event(
                    "verification",
                    {
                        "stage_status": (
                            "complete"
                            if repair.passed
                            else "failed"
                        ),
                        "repairs_used": (
                            edit_validation_repairs + repair.repairs_used
                        ),
                    },
                )
                on_event(
                    "repair",
                    {
                        "passed": bool(repair.passed),
                        "repairs_used": int(
                            edit_validation_repairs + repair.repairs_used
                        ),
                        "attempts": [
                            {
                                "attempt": getattr(item, "attempt", None),
                                "failure_kind": getattr(
                                    getattr(item, "diagnostics", None),
                                    "failure_kind",
                                    "unknown",
                                ),
                                "changed_paths": list(
                                    getattr(
                                        getattr(item, "edit_result", None),
                                        "changed_paths",
                                        (),
                                    )
                                ),
                            }
                            for item in getattr(repair, "attempts", ())
                        ],
                    },
                )

            return WorkerExecution(
                status=WorkerStatus.COMPLETE,
                output_state={
                    "changed_paths": list(initial_edits.changed_paths),
                    "repairs_used": (
                        edit_validation_repairs + repair.repairs_used
                    ),
                    "deterministic_passed": bool(repair.passed),
                },
            )

        raise DevelopmentEngineError(
            f"Unsupported development worker role: {worker_task.role.value}"
        )

    def verify_worker(
        worker_task: WorkerTask,
        policy,
    ) -> WorkerExecution:
        if (
            worker_task.role is not WorkerRole.CRITIC_VERIFIER
            or not policy.verify
            or policy.propose_edits
            or policy.execute_tools
        ):
            raise DevelopmentEngineError(
                "Critic / Verifier policy violates verifier separation."
            )

        if (
            worker_task.input_state.get("subject_task_id") != "coder"
            or worker_task.input_state.get("subject_role")
            != WorkerRole.CODER.value
        ):
            raise DevelopmentEngineError(
                "Critic / Verifier received an invalid verification subject."
            )

        subject_output = worker_task.input_state.get("subject_output")
        if not isinstance(subject_output, Mapping):
            raise DevelopmentEngineError(
                "Critic / Verifier received no typed coder output."
            )

        initial_edits = state.get("initial_edits")
        expected_changed = list(
            getattr(initial_edits, "changed_paths", ())
        )
        if list(subject_output.get("changed_paths", ())) != expected_changed:
            raise DevelopmentEngineError(
                "Critic / Verifier candidate state does not match applied edits."
            )

        if on_event:
            on_event(
                "fresh_verifier",
                {"stage_status": "running"},
            )

        plan_run = state.get("plan")
        planned_files = (
            getattr(getattr(plan_run, "plan", None), "files", ())
            if plan_run is not None
            else ()
        )
        expected_paths = tuple(
            item.path
            for item in planned_files
            if getattr(item, "action", "none") != "none"
        )
        localization = getattr(plan_run, "localization", None)
        acceptance_contract = getattr(plan_run, "acceptance_contract", None)

        verifier = run_fresh_verifier(
            connection,
            task_id,
            scheduler,
            run_id=run_id,
            step_id=step_id,
            expected_paths=(expected_paths or None),
            excluded_paths=tuple(
                getattr(localization, "excluded_paths", ())
            ),
            acceptance_contract=acceptance_contract,
        )
        state["verifier"] = verifier

        if on_event:
            repair = state.get("repair")
            on_event(
                "fresh_verifier",
                {
                    "stage_status": (
                        "complete"
                        if verifier.verdict == "pass"
                        else (
                            "failed"
                            if verifier.verdict == "fail"
                            else "blocked"
                        )
                    ),
                    "verdict": verifier.verdict,
                    "findings": [
                        {
                            "criterion": getattr(item, "criterion", ""),
                            "status": getattr(item, "status", ""),
                            "evidence": str(getattr(item, "evidence", ""))[:1200],
                        }
                        for item in getattr(verifier, "findings", ())
                    ],
                    "repairs_used": (
                        (
                            getattr(repair, "repairs_used", 0)
                            if repair is not None
                            else 0
                        )
                        + int(state.get("semantic_repairs_used",0))
                        + int(state.get("initial_edit_repairs_used",0))
                    ),
                },
            )

        return WorkerExecution(
            status=WorkerStatus.COMPLETE,
            output_state={
                "verdict": verifier.verdict,
                "summary": str(getattr(verifier, "summary", ""))[:4000],
            },
        )

    def run_cycle() -> OrchestrationResult:
        return WorkerOrchestrator(
            _DEVELOPMENT_WORKER_BUDGET
        ).run(
            (
                WorkerTask(
                    task_id="localize",
                    role=WorkerRole.CODE_LOCALIZER,
                    objective=(
                        "Localize the requested development change and produce "
                        "the existing bounded coding plan."
                    ),
                ),
                WorkerTask(
                    task_id="coder",
                    role=WorkerRole.CODER,
                    objective=(
                        "Produce and apply the existing structured edit proposal, "
                        "then run deterministic verification."
                    ),
                    depends_on=("localize",),
                    requires_verification=True,
                ),
            ),
            execute_worker,
            verifier=verify_worker,
        )

    state["cycle_repair_budget"]=max_repairs
    state["semantic_repairs_used"]=0
    orchestration_runs=[run_cycle()]

    verifier=state.get("verifier")
    repair=state.get("repair")
    deterministic_repairs=(
        int(getattr(repair,"repairs_used",0))
        if repair is not None
        else 0
    )
    initial_edit_repairs=int(
        state.get("initial_edit_repairs_used",0)
    )
    spent_repairs=initial_edit_repairs+deterministic_repairs
    state["total_repairs_used"]=spent_repairs

    if (
        verifier is not None
        and getattr(verifier,"verdict",None)=="fail"
        and max_repairs>spent_repairs
    ):
        remaining_calls=_remaining_model_calls(scheduler)
        can_afford=(
            remaining_calls is None
            or remaining_calls>=3
        )
        if can_afford and MAX_SEMANTIC_REPAIR_CYCLES>0:
            feedback=_verifier_feedback(verifier)
            state["semantic_repairs_used"]=1
            state["corrective_feedback"]=feedback
            state["cycle_repair_budget"]=max(
                0,
                max_repairs-spent_repairs-1,
            )
            for key in (
                "plan",
                "implementation",
                "initial_edits",
                "repair",
                "verifier",
                "no_checks",
            ):
                state.pop(key,None)
            if on_event:
                on_event(
                    "semantic_repair",
                    {
                        "attempt":1,
                        "reason":"fresh_verifier_rejected",
                    },
                )
            orchestration_runs.append(run_cycle())
            final_repair=state.get("repair")
            state["total_repairs_used"]=(
                int(state.get("initial_edit_repairs_used",0))
                + deterministic_repairs
                + 1
                + (
                    int(getattr(final_repair,"repairs_used",0))
                    if final_repair is not None
                    else 0
                )
            )

    orchestration=_merge_orchestration(orchestration_runs)

    if on_event:
        on_event(
            "workers",
            _orchestration_event(orchestration),
        )

    plan_run = state.get("plan")

    if plan_run is None:
        raise DevelopmentEngineError(
            "Development orchestration ended before localization."
        )

    implementation = state.get("implementation")
    initial_edits = state.get("initial_edits")
    repair = state.get("repair")
    verifier = state.get("verifier")

    if plan_run.plan.needs_more_context:
        return DevelopmentRunResult(
            status="blocked",
            plan=plan_run,
            implementation=None,
            initial_edits=None,
            repair=None,
            verifier=None,
            message=(
                "Planning model requested additional context."
            ),
            orchestration=orchestration,
        )

    if (
        implementation is not None
        and implementation.needs_more_context
    ):
        return DevelopmentRunResult(
            status="blocked",
            plan=plan_run,
            implementation=implementation,
            initial_edits=None,
            repair=None,
            verifier=None,
            message=(
                "Implementation model requested additional context."
            ),
            orchestration=orchestration,
        )

    if state.get("no_checks"):
        return DevelopmentRunResult(
            status="unverified",
            plan=plan_run,
            implementation=implementation,
            initial_edits=initial_edits,
            repair=None,
            verifier=None,
            message=(
                "No deterministic verification checks "
                "could be established."
            ),
            orchestration=orchestration,
        )

    if verifier is not None:
        status = _result_status(
            verifier
        )

        if status == "pass":
            message = (
                "Implementation passed deterministic verification "
                "and fresh independent verification."
            )

        elif status == "fail":
            message = (
                "Implementation failed final verification."
            )

        else:
            message = (
                "Implementation could not be fully verified."
            )

        return DevelopmentRunResult(
            status=status,
            plan=plan_run,
            implementation=implementation,
            initial_edits=initial_edits,
            repair=repair,
            verifier=verifier,
            message=message,
            orchestration=orchestration,
            semantic_repairs_used=int(
                state.get("semantic_repairs_used",0)
            ),
            total_repairs_used=int(
                state.get("total_repairs_used",0)
            ),
        )

    return DevelopmentRunResult(
        status="blocked",
        plan=plan_run,
        implementation=(
            implementation
            if isinstance(implementation, ImplementationProposalRun)
            else None
        ),
        initial_edits=(
            initial_edits
            if isinstance(initial_edits, EditBatchResult)
            else initial_edits
        ),
        repair=(
            repair
            if isinstance(repair, RepairLoopResult)
            else repair
        ),
        verifier=None,
        message=(
            "Development worker orchestration stopped before independent "
            f"verification: {orchestration.stop_reason.value}."
        ),
        orchestration=orchestration,
    )
