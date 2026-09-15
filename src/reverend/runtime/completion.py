"""Safe generation-completion metadata for local model execution."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class CompletionReason(str, Enum):
    """Provider-neutral completion states safe to persist and render."""

    COMPLETE = "complete"
    OUTPUT_LIMIT_REACHED = "output_limit_reached"
    REASONING_BUDGET_EXHAUSTED_BEFORE_ANSWER = (
        "reasoning_budget_exhausted_before_answer"
    )
    EMPTY_FINAL_RESPONSE = "empty_final_response"
    INFERENCE_CANCELLED = "inference_cancelled"


def classify_completion(
    *,
    done: bool,
    done_reason: str | None,
    answer_started: bool,
    hidden_reasoning_present: bool,
    cancelled: bool,
) -> str | None:
    """Map provider completion metadata without observing private reasoning text."""

    if cancelled:
        return CompletionReason.INFERENCE_CANCELLED.value

    if not done:
        return None

    provider_reason = str(
        done_reason or ""
    ).strip().lower()

    if provider_reason in {
        "length",
        "max_tokens",
        "token_limit",
    }:
        if (
            hidden_reasoning_present
            and not answer_started
        ):
            return (
                CompletionReason
                .REASONING_BUDGET_EXHAUSTED_BEFORE_ANSWER
                .value
            )
        return (
            CompletionReason
            .OUTPUT_LIMIT_REACHED
            .value
        )

    if not answer_started:
        return (
            CompletionReason
            .EMPTY_FINAL_RESPONSE
            .value
        )

    return CompletionReason.COMPLETE.value


@dataclass(frozen=True)
class CompletionSnapshot:
    """Safe aggregate state for one streamed completion checkpoint."""

    done: bool
    done_reason: str | None
    completion_reason: str | None
    prompt_tokens: int | None
    generated_tokens: int | None
    response_chars: int
    answer_started: bool
    hidden_reasoning_present: bool
    thinking_activity_count: int
    cancelled: bool
    output_budget: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
