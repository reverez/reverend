from reverend.benchmarks.research_quality import run_research_bench


def test_adversarial_research_bench_passes_all_fixture_categories():
    result = run_research_bench()
    assert result["total"] == 14
    assert result["passed"] == 14
    assert result["all_passed"] is True
    assert all(result["metrics"].values())
