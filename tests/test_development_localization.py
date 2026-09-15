from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from reverend.development import localization as localization_module

from reverend.benchmarks.codingbench import (
    CASES,
    CodingBenchCase,
    SELF_HOSTING_CASE,
    materialize_case,
    run_fixture_suite,
)
from reverend.development.localization import (
    LocalizationError,
    localize_repository,
)


def _fixture(tmp_path, case_id):
    case = next(item for item in CASES if item.case_id == case_id)
    return case, materialize_case(case, tmp_path)


def test_negative_constraint_excludes_wrong_file_trap(tmp_path):
    case, repo = _fixture(tmp_path, "wrong-file-trap")
    result = localize_repository(repo, case.query)
    paths = tuple(item.path for item in result.candidates)

    assert "src/users/v2/serializer.py" in paths
    assert "tests/test_user_service.py" in paths
    assert "src/users/legacy/serializer.py" not in paths
    assert "src/users/legacy/serializer.py" in result.excluded_paths


def test_architecture_constraint_prefers_port_over_bypass(tmp_path):
    case, repo = _fixture(tmp_path, "architecture-constraint")
    result = localize_repository(repo, case.query)
    paths = tuple(item.path for item in result.candidates)

    assert "src/audit/ports.py" in paths
    assert "src/audit/service.py" in paths
    assert "tests/test_audit_service.py" in paths
    assert "src/audit/sqlite.py" not in paths


def test_untouched_constraint_removes_unrelated_ui_and_docs(tmp_path):
    case, repo = _fixture(tmp_path, "unrelated-file-penalty")
    result = localize_repository(repo, case.query)
    paths = tuple(item.path for item in result.candidates)

    assert set(paths[:2]) == {
        "tests/test_worker_engine.py",
        "src/worker/engine.py",
    }
    assert "src/ui/retry_label.py" not in paths
    assert "docs/retries.md" not in paths


def test_localization_exposes_tests_dependencies_and_repository_map(tmp_path):
    case, repo = _fixture(tmp_path, "multi-file-feature")
    result = localize_repository(repo, case.query)

    assert "tests/test_widget_service.py" in result.affected_tests
    assert "src/app/service.py" in result.likely_implementation_paths
    assert result.repository.file_count == 4
    assert result.repository.test_count == 1
    assert result.repository.recent_commits
    assert any(
        item.source_path == "src/app/service.py"
        and item.target_path == "src/app/models.py"
        for item in result.dependencies
    )


def test_optimized_fixture_suite_passes_all_localization_traps():
    result = run_fixture_suite("optimized")
    assert result["summary"]["passed"] == 12
    assert result["summary"]["success_rate"] == 1.0
    assert result["summary"]["localization_recall"] == 1.0
    assert result["summary"]["unrelated_file_selections"] == 0


def test_self_host_localization_finds_verifier_and_its_test():
    root = Path(__file__).resolve().parents[1]
    result = localize_repository(root, SELF_HOSTING_CASE.query)
    paths = tuple(item.path for item in result.candidates)

    assert "src/reverend/development/verifier.py" in paths
    assert "tests/test_development_verifier.py" in paths


def test_empty_localization_query_is_rejected(tmp_path):
    _, repo = _fixture(tmp_path, "simple-bug")
    with pytest.raises(LocalizationError):
        localize_repository(repo, "  ")



def test_negative_constraint_preserves_dotted_paths(tmp_path):
    case, repo = _fixture(tmp_path, "ambiguous-repository-layout")
    result = localize_repository(repo, case.query)
    paths = tuple(item.path for item in result.candidates)

    assert "src/shop/service.py" in paths
    assert "tests/test_shop_service.py" in paths
    assert "examples/shop/service.py" not in paths
    assert "examples/shop/service.py" in result.excluded_paths

def test_forbidden_exact_path_is_global_not_search_hit_dependent(
    tmp_path,
    monkeypatch,
):
    case, repo = _fixture(tmp_path, "ambiguous-repository-layout")
    original_search = localization_module.search_code

    def without_forbidden(*args, **kwargs):
        result = original_search(*args, **kwargs)
        return SimpleNamespace(
            hits=tuple(
                hit
                for hit in result.hits
                if hit.path != "examples/shop/service.py"
            )
        )

    monkeypatch.setattr(
        localization_module,
        "search_code",
        without_forbidden,
    )

    result = localize_repository(repo, case.query)
    paths = tuple(item.path for item in result.candidates)

    assert "examples/shop/service.py" not in paths
    assert "examples/shop/service.py" in result.excluded_paths


def test_graph_added_implementation_can_surface_conventional_test(
    tmp_path,
    monkeypatch,
):
    case = CodingBenchCase(
        case_id="graph-affinity-regression",
        title="Update router behavior",
        request="Update the router implementation and its affected service behavior.",
        acceptance="The service regression test remains covered.",
        files=(
            (
                "src/pkg/router.py",
                "from .service import handle\n\ndef route(value):\n    return handle(value)\n",
            ),
            (
                "src/pkg/service.py",
                "def handle(value):\n    return value\n",
            ),
            (
                "tests/test_service.py",
                "def test_service_contract():\n    assert True\n",
            ),
        ),
        required_paths=(
            "src/pkg/router.py",
            "src/pkg/service.py",
            "tests/test_service.py",
        ),
        forbidden_paths=(),
    )
    repo = materialize_case(case, tmp_path)
    original_search = localization_module.search_code

    def router_only(*args, **kwargs):
        result = original_search(*args, **kwargs)
        router_hits = tuple(
            hit
            for hit in result.hits
            if hit.path == "src/pkg/router.py"
        )
        assert router_hits
        return SimpleNamespace(hits=router_hits)

    monkeypatch.setattr(
        localization_module,
        "search_code",
        router_only,
    )

    result = localize_repository(repo, case.query)
    paths = tuple(item.path for item in result.candidates)

    assert "src/pkg/service.py" in paths
    assert "tests/test_service.py" in paths
    service_test = next(
        item
        for item in result.candidates
        if item.path == "tests/test_service.py"
    )
    assert any(
        reason == "localizer:test-affinity:src/pkg/service.py"
        for reason in service_test.reasons
    )


def test_exact_production_path_is_deterministic_high_confidence_evidence(
    tmp_path,
):
    case, repo = _fixture(tmp_path, "ambiguous-repository-layout")
    result = localize_repository(repo, case.query)

    production = next(
        item
        for item in result.candidates
        if item.path == "src/shop/service.py"
    )
    assert "localizer:explicit-path" in production.reasons
    assert production.confidence == "high"
    assert "examples/shop/service.py" not in {
        item.path for item in result.candidates
    }
