"""Typed data model for ReverendBench."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class BenchmarkCategory(str, Enum):
    OPEN_DOMAIN = "open_domain"
    PERSONAL_KNOWLEDGE = "personal_knowledge"
    RESEARCH = "research"
    ROUTING = "routing"
    RENDERING = "rendering"
    DEVELOPMENT = "development"
    SECURITY = "security"


class BenchmarkStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class BenchmarkBudget:
    timeout_seconds: float = 30.0
    max_model_calls: int = 1
    max_retrieval_rounds: int = 1

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.max_model_calls < 0:
            raise ValueError("max_model_calls must be non-negative")
        if self.max_retrieval_rounds < 0:
            raise ValueError("max_retrieval_rounds must be non-negative")


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    name: str
    category: BenchmarkCategory
    prompt: str
    parameters: dict[str, Any] = field(default_factory=dict)
    expected: dict[str, Any] = field(default_factory=dict)
    tags: tuple[str, ...] = ()
    budget: BenchmarkBudget = field(default_factory=BenchmarkBudget)

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise ValueError("case_id must not be empty")
        if not self.name.strip():
            raise ValueError("name must not be empty")
        if not self.prompt.strip():
            raise ValueError("prompt must not be empty")
        if any(not tag.strip() for tag in self.tags):
            raise ValueError("tags must not contain empty values")


@dataclass(frozen=True)
class BenchmarkObservation:
    response: str
    metadata: dict[str, Any] = field(default_factory=dict)


class BenchmarkExecutionError(RuntimeError):
    """A failed execution retaining the last observed response and diagnostics."""
    def __init__(self, message: str, observation: BenchmarkObservation):
        super().__init__(message)
        self.observation = observation


class BenchmarkTimeoutError(BenchmarkExecutionError, TimeoutError):
    pass


@dataclass(frozen=True)
class BenchmarkAssertion:
    name: str
    passed: bool
    detail: str = ""

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("assertion name must not be empty")


@dataclass(frozen=True)
class BenchmarkResult:
    case_id: str
    status: BenchmarkStatus
    duration_seconds: float
    response: str = ""
    assertions: tuple[BenchmarkAssertion, ...] = ()
    metrics: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise ValueError("case_id must not be empty")
        if self.duration_seconds < 0:
            raise ValueError("duration_seconds must be non-negative")

    @property
    def passed(self) -> bool:
        return self.status is BenchmarkStatus.PASS

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
