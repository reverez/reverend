from __future__ import annotations

import json

import pytest

from reverend.benchmarks.models import (
    BenchmarkAssertion,
    BenchmarkResult,
    BenchmarkStatus,
)
from reverend.benchmarks.reporting import (
    BenchmarkRun,
    report_path,
    save_run,
)


def sample_run() -> BenchmarkRun:
    return BenchmarkRun(
        run_id="run-001",
        started_at="2026-09-13T20:00:00Z",
        completed_at="2026-09-13T20:00:05Z",
        results=(
            BenchmarkResult(
                case_id="pass-case",
                status=BenchmarkStatus.PASS,
                duration_seconds=1.25,
                assertions=(
                    BenchmarkAssertion(
                        name="answer-present",
                        passed=True,
                    ),
                ),
                metrics={"model_calls": 1},
            ),
            BenchmarkResult(
                case_id="fail-case",
                status=BenchmarkStatus.FAIL,
                duration_seconds=2.5,
                assertions=(
                    BenchmarkAssertion(
                        name="expected-answer",
                        passed=False,
                        detail="wrong entity",
                    ),
                ),
            ),
        ),
        metadata={
            "git_commit": "abc123",
            "branch": "architecture/m6-vnext-foundation",
        },
    )


def test_run_serialization_contains_summary():
    payload = sample_run().to_dict()

    assert payload["schema_version"] == 1
    assert payload["summary"]["total"] == 2
    assert payload["summary"]["passed"] == 1
    assert payload["summary"]["failed"] == 1
    assert payload["results"][0]["status"] == "pass"
    assert payload["results"][1]["status"] == "fail"


def test_save_run_writes_stable_json(tmp_path):
    run = sample_run()

    destination = save_run(
        run,
        root=tmp_path,
    )

    assert destination == (
        tmp_path
        / "benchmarks"
        / "runs"
        / "run-001.json"
    )

    payload = json.loads(
        destination.read_text(encoding="utf-8")
    )

    assert payload["run_id"] == "run-001"
    assert payload["metadata"]["git_commit"] == "abc123"
    assert payload["summary"]["total"] == 2


def test_run_reports_are_immutable(tmp_path):
    run = sample_run()

    save_run(
        run,
        root=tmp_path,
    )

    with pytest.raises(
        FileExistsError,
        match="already exists",
    ):
        save_run(
            run,
            root=tmp_path,
        )


def test_unsafe_run_id_is_rejected(tmp_path):
    with pytest.raises(
        ValueError,
        match="run_id",
    ):
        BenchmarkRun(
            run_id="../escape",
            started_at="start",
            completed_at="end",
            results=(),
        )

    with pytest.raises(
        ValueError,
        match="unsafe",
    ):
        report_path(
            tmp_path,
            "../../escape",
        )


def test_report_serializes_result_response():
    run = sample_run()

    payload = run.to_dict()

    assert "response" in payload["results"][0]


def test_competing_report_writer_cannot_replace_result(tmp_path,monkeypatch):
    import os
    original_link=os.link
    def competing_writer(source,destination):
        destination.write_text('winner')
        original_link(source,destination)
    monkeypatch.setattr(os,'link',competing_writer)
    with pytest.raises(FileExistsError):save_run(sample_run(),root=tmp_path)
    assert report_path(tmp_path,'run-001').read_text()=='winner'
    assert not list((tmp_path/'benchmarks'/'runs').glob('.benchmark-*'))
