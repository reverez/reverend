from __future__ import annotations

import pytest

from reverend.benchmarks.models import (
    BenchmarkAssertion,
    BenchmarkCase,
    BenchmarkCategory,
    BenchmarkObservation,
)
from reverend.benchmarks.runner import BenchmarkRunner
from reverend.benchmarks.suites import (
    BenchmarkSuiteName,
    BenchmarkSuiteRegistry,
)


def sample_case(case_id="case"):
    return BenchmarkCase(
        case_id=case_id,
        name=case_id,
        category=BenchmarkCategory.RESEARCH,
        prompt="test",
    )


def test_named_future_suites_register_existing_benchmarks():
    registry = BenchmarkSuiteRegistry()
    suite = registry.register(
        BenchmarkSuiteName.RESEARCH,
        (sample_case(),),
        description="Existing Reverend research regression cases.",
    )

    assert suite.name == "ResearchBench"
    assert registry.names() == ("ResearchBench",)
    assert registry.get("ResearchBench").cases[0].case_id == "case"


def test_suite_registry_reuses_existing_runner():
    registry = BenchmarkSuiteRegistry()
    registry.register(BenchmarkSuiteName.VERIFY, (sample_case("verify"),))
    runner = BenchmarkRunner(
        executor=lambda case: BenchmarkObservation(response=case.case_id),
        evaluator=lambda *_: (BenchmarkAssertion(name="ok", passed=True),),
    )

    results = registry.run(BenchmarkSuiteName.VERIFY, runner)

    assert len(results) == 1
    assert results[0].passed is True


def test_suite_registry_rejects_accidental_redefinition():
    registry = BenchmarkSuiteRegistry()
    registry.register(BenchmarkSuiteName.CODING, (sample_case(),))

    with pytest.raises(ValueError, match="already registered"):
        registry.register(BenchmarkSuiteName.CODING, (sample_case("other"),))


def test_registry_accepts_existing_reverend_catalogue_cases():
    from reverend.benchmarks.catalog import m17_freshness_cases

    registry = BenchmarkSuiteRegistry()
    suite = registry.register(
        BenchmarkSuiteName.RESEARCH,
        m17_freshness_cases(),
        description="Existing M17 research regressions.",
    )

    assert suite.cases
    assert all("m17-regression" in case.tags for case in suite.cases)


def test_reverendbench_umbrella_names_cover_wave2_quality_domains():
    expected={
        "ResearchBench","RetrievalBench","CodingBench","ArchitectBench",
        "VerifyBench","IntegrationBench","SecurityBench","StakeholderBench",
        "AssetBench","PerformanceBench","WholeSystemBench",
    }
    assert {item.value for item in BenchmarkSuiteName} == expected
