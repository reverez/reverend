"""Named ReverendBench suite registration for vNext evaluation growth."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .models import BenchmarkCase


class BenchmarkSuiteName(str, Enum):
    RESEARCH = "ResearchBench"
    RETRIEVAL = "RetrievalBench"
    CODING = "CodingBench"
    ARCHITECT = "ArchitectBench"
    VERIFY = "VerifyBench"
    INTEGRATION = "IntegrationBench"
    SECURITY = "SecurityBench"
    STAKEHOLDER = "StakeholderBench"
    ASSET = "AssetBench"
    PERFORMANCE = "PerformanceBench"
    WHOLE_SYSTEM = "WholeSystemBench"


@dataclass(frozen=True)
class BenchmarkSuite:
    name: str
    cases: tuple[BenchmarkCase, ...]
    description: str = ""

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Benchmark suite name must not be empty")
        identifiers = [case.case_id for case in self.cases]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Benchmark suite contains duplicate case ids")


class BenchmarkSuiteRegistry:
    """Small registry that reuses BenchmarkRunner rather than replacing it."""

    def __init__(self):
        self._suites: dict[str, BenchmarkSuite] = {}

    @staticmethod
    def _name(value: BenchmarkSuiteName | str) -> str:
        if isinstance(value, BenchmarkSuiteName):
            return value.value
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Benchmark suite name must not be empty")
        return value.strip()

    def register(
        self,
        name: BenchmarkSuiteName | str,
        cases: Iterable[BenchmarkCase],
        *,
        description: str = "",
        replace: bool = False,
    ) -> BenchmarkSuite:
        key = self._name(name)
        if key in self._suites and not replace:
            raise ValueError(f"Benchmark suite already registered: {key}")
        suite = BenchmarkSuite(
            name=key,
            cases=tuple(cases),
            description=description.strip(),
        )
        self._suites[key] = suite
        return suite

    def get(self, name: BenchmarkSuiteName | str) -> BenchmarkSuite:
        key = self._name(name)
        try:
            return self._suites[key]
        except KeyError as exc:
            raise KeyError(f"Unknown benchmark suite: {key}") from exc

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._suites))

    def run(self, name: BenchmarkSuiteName | str, runner):
        return runner.run(self.get(name).cases)
