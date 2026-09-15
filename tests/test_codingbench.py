from __future__ import annotations

import subprocess

from reverend.benchmarks.codingbench import (
    CASES,
    SELF_HOSTING_CASE,
    materialize_case,
    run_fixture_suite,
    score_case,
)


def test_required_fixture_catalog_is_complete():
    assert [case.case_id for case in CASES] == [
        "simple-bug",
        "multi-file-feature",
        "api-compatible-refactor",
        "test-failure-diagnosis",
        "config-schema-change",
        "wrong-file-trap",
        "architecture-constraint",
        "edge-case-repair",
        "test-weakening-trap",
        "bounded-repair",
        "ambiguous-repository-layout",
        "unrelated-file-penalty",
    ]
    assert SELF_HOSTING_CASE.case_id == "reverend-self-host-localization"


def test_fixture_materialization_is_a_real_git_repository(tmp_path):
    repo = materialize_case(CASES[0], tmp_path)
    result = subprocess.run(
        ("git", "-C", str(repo), "rev-parse", "--is-inside-work-tree"),
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    assert result.stdout.strip() == "true"
    assert (repo / "src/mathkit/calc.py").is_file()


def test_case_scoring_penalizes_missing_and_unrelated_paths():
    case = CASES[-1]
    result = score_case(
        case,
        (
            "src/worker/engine.py",
            "src/ui/retry_label.py",
        ),
    )
    assert not result.passed
    assert result.missing_required == ("tests/test_worker_engine.py",)
    assert result.forbidden_hits == ("src/ui/retry_label.py",)
    assert result.localization_recall == 0.5


def test_legacy_fixture_suite_is_deterministic_in_shape():
    result = run_fixture_suite("legacy")
    summary = result["summary"]
    assert summary["strategy"] == "legacy"
    assert summary["cases"] == 12
    assert 0 <= summary["passed"] <= 12
    assert 0.0 <= summary["success_rate"] <= 1.0
    assert 0.0 <= summary["localization_recall"] <= 1.0
    assert summary["unrelated_file_selections"] >= 0
    assert summary["average_selected_files"] > 0
    assert len(result["cases"]) == 12
