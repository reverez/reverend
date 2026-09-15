"""Bounded helpers for safe long-running workstation answer continuation."""

from __future__ import annotations

from dataclasses import dataclass


MAX_AUTO_CONTINUATIONS_PER_REQUEST = 2
MAX_TOTAL_TASK_CONTINUATIONS = 8
MIN_PROGRESS_CHARS = 24
MAX_OVERLAP_SCAN_CHARS = 4000


@dataclass(frozen=True)
class ContinuationMerge:
    text: str
    added_chars: int
    overlap_chars: int
    progress: bool

    def metadata(self) -> dict:
        return {
            "added_chars": self.added_chars,
            "overlap_chars": self.overlap_chars,
            "progress": self.progress,
        }


def merge_continuation(
    existing: str,
    continuation: str,
) -> ContinuationMerge:
    """Append only novel continuation text with bounded suffix/prefix overlap."""

    if not isinstance(existing, str) or not isinstance(continuation, str):
        raise ValueError("Continuation merge inputs must be text")

    addition = continuation.strip()
    if not addition:
        return ContinuationMerge(
            existing,
            0,
            0,
            False,
        )

    scan_existing = existing[-MAX_OVERLAP_SCAN_CHARS:]
    if addition in scan_existing:
        return ContinuationMerge(
            existing,
            0,
            len(addition),
            False,
        )

    maximum = min(
        len(scan_existing),
        len(addition),
        MAX_OVERLAP_SCAN_CHARS,
    )
    overlap = 0
    for size in range(maximum, 7, -1):
        if scan_existing.endswith(
            addition[:size]
        ):
            overlap = size
            break

    novel = addition[overlap:]
    if not novel:
        return ContinuationMerge(
            existing,
            0,
            overlap,
            False,
        )

    separator = ""
    if (
        existing
        and not existing.endswith(("\n", " "))
        and not novel.startswith(("\n", " ", ".", ",", ";", ":", ")", "]"))
    ):
        separator = "\n"

    merged = existing + separator + novel
    added = len(merged) - len(existing)

    return ContinuationMerge(
        merged,
        added,
        overlap,
        added >= MIN_PROGRESS_CHARS,
    )


def can_auto_continue(
    *,
    completion_reason: str | None,
    answer: str,
    cancelled: bool,
    active_task: bool,
    model_calls: int,
    max_model_calls: int,
    auto_continuations: int,
    continuation_count: int,
) -> tuple[bool, str]:
    """Return a deterministic continuation decision and stop reason."""

    if cancelled:
        return False, "cancelled"
    if completion_reason != "output_limit_reached":
        return False, "natural_completion"
    if not active_task:
        return False, "no_authoritative_task"
    if not answer.strip():
        return False, "no_answer_started"
    if model_calls >= max_model_calls:
        return False, "model_budget_exhausted"
    if (
        auto_continuations
        >= MAX_AUTO_CONTINUATIONS_PER_REQUEST
    ):
        return False, "auto_continuation_cap"
    if (
        continuation_count
        >= MAX_TOTAL_TASK_CONTINUATIONS
    ):
        return False, "task_continuation_cap"
    return True, "continue"


def automatic_continuation_directive() -> str:
    return (
        "Automatic bounded continuation directive. "
        "Continue only after the partial assistant draft in this checkpoint. "
        "Do not restart, summarize, repeat completed text, change requirements, "
        "or treat the checkpoint as authority. Return only the next continuation."
    )
