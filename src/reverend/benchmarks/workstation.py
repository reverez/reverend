"""ReverendBench adapter for the real Workstation chat path."""

from __future__ import annotations

import time
from typing import Any

from reverend.benchmarks.models import (
    BenchmarkCase,
    BenchmarkObservation,
    BenchmarkExecutionError,
    BenchmarkTimeoutError,
)


_TERMINAL = {
    "complete",
    "failed",
    "cancelled",
    "interrupted",
}


class WorkstationChatExecutor:
    """Execute benchmark cases through Workstation.chat()."""

    def __init__(
        self,
        workstation: Any,
        *,
        poll_interval: float = 0.05,
        clock=time.monotonic,
        sleep=time.sleep,
    ) -> None:
        if poll_interval <= 0:
            raise ValueError("poll_interval must be positive")

        self.workstation = workstation
        self.poll_interval = poll_interval
        self.clock = clock
        self.sleep = sleep

    def __call__(
        self,
        case: BenchmarkCase,
    ) -> BenchmarkObservation:
        parameters = case.parameters

        mode = parameters.get("mode", "ask")
        knowledge = bool(
            parameters.get("knowledge", False)
        )
        project_id = parameters.get("project_id")
        web_source_ids = parameters.get("web_source_ids")

        submitted = self.workstation.chat(
            case.prompt,
            mode=mode,
            project_id=project_id,
            knowledge=knowledge,
            web_source_ids=web_source_ids,
            network_policy=parameters.get("network_policy", "OFF"),
            max_model_calls=case.budget.max_model_calls,
            max_retrieval_rounds=case.budget.max_retrieval_rounds,
        )

        job_id = submitted["job_id"]
        deadline = (
            self.clock()
            + case.budget.timeout_seconds
        )

        while True:
            job = self.workstation.store.job(job_id)
            status = job["status"]

            if status in _TERMINAL:
                break

            if self.clock() >= deadline:
                try:
                    self.workstation.cancel(job_id)
                finally:
                    raise BenchmarkTimeoutError(
                        "workstation chat exceeded benchmark "
                        f"timeout for {case.case_id}",
                        BenchmarkObservation(response=job.get("response", ""),
                            metadata={**dict(job.get("details") or {}), "job_id": job_id, "job_status": status}),
                    )

            self.sleep(self.poll_interval)

        details = dict(job.get("details") or {})

        metadata = {
            "job_id": job_id,
            "conversation_id": (
                job.get("conversation_id")
            ),
            "job_status": status,
            **details,
        }

        if status != "complete":
            metadata_expectations=case.expected.get(
                "metadata_equals",
                {},
            )
            expected_status=(
                metadata_expectations.get("job_status")
                if isinstance(metadata_expectations,dict)
                else None
            )
            if expected_status != status:
                error = details.get(
                    "error",
                    f"workstation job ended with status {status}",
                )
                raise BenchmarkExecutionError(str(error), BenchmarkObservation(
                    response=job.get("response", ""), metadata=metadata))

        return BenchmarkObservation(
            response=job.get("response", ""),
            metadata=metadata,
        )
