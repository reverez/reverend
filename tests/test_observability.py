from __future__ import annotations

import json

import pytest

from reverend.observability import (
    ObservabilityLevel,
    SpanKind,
    SQLiteTraceStore,
    TraceRecorder,
)


def recorder(tmp_path, *, level=ObservabilityLevel.NORMAL):
    return TraceRecorder(
        SQLiteTraceStore(tmp_path / "observability.db"),
        level=level,
    )


def test_correlated_trace_persists_workflow_job_task_model_and_tool(tmp_path):
    observed = recorder(tmp_path)
    trace = observed.create_trace(
        workflow_id="workflow-1",
        job_id="job-1",
        attributes={"kind": "chat"},
    )

    with observed.activate(trace, name="chat") as workflow:
        observed.attach(task_id="task-1")

        with observed.span(SpanKind.JOB, "chat.job") as job:
            assert job is not None
            with observed.span(
                SpanKind.MODEL,
                "model.generate",
                model="qwen3-coder:30b",
                attributes={
                    "role": "strong_code",
                    "prompt_tokens": 120,
                    "generated_tokens": 44,
                    "prompt": "must never persist",
                },
            ):
                pass

            with pytest.raises(RuntimeError):
                with observed.span(
                    SpanKind.TOOL,
                    "tool.search",
                    tool_name="local_search",
                    attributes={
                        "tool_name": "local_search",
                        "content": "private source body",
                    },
                ):
                    raise RuntimeError("a sensitive failure message")

        assert workflow.status.value == "ok"

    payload = observed.trace(trace.trace_id)
    assert payload["trace"]["workflow_id"] == "workflow-1"
    assert payload["trace"]["job_id"] == "job-1"
    assert payload["trace"]["task_id"] == "task-1"

    spans = payload["spans"]
    kinds = {span["kind"] for span in spans}
    assert {"workflow", "job", "model", "tool"} <= kinds

    model = next(span for span in spans if span["kind"] == "model")
    assert model["model"] == "qwen3-coder:30b"
    assert model["attributes"]["prompt_tokens"] == 120
    assert "prompt" not in model["attributes"]

    tool = next(span for span in spans if span["kind"] == "tool")
    assert tool["status"] == "error"
    assert tool["error_type"] == "RuntimeError"
    assert "content" not in tool["attributes"]

    serialized = json.dumps(payload)
    assert "must never persist" not in serialized
    assert "sensitive failure message" not in serialized


def test_root_failure_marks_trace_and_span_error(tmp_path):
    observed = recorder(tmp_path)
    trace = observed.create_trace(workflow_id="workflow-failure")

    with pytest.raises(ValueError):
        with observed.activate(trace, name="failing-workflow"):
            raise ValueError("payload should not be written")

    payload = observed.trace(trace.trace_id)
    assert payload["trace"]["status"] == "error"
    assert payload["spans"][0]["status"] == "error"
    assert payload["spans"][0]["error_type"] == "ValueError"
    assert "payload should not be written" not in json.dumps(payload)


def test_trace_context_is_consumed_structurally_without_redefinition(tmp_path):
    class FrozenContext:
        trace_id = "trace-authoritative"
        span_id = "upstream-span"
        parent_span_id = "upstream-parent"
        workflow_id = "workflow-authoritative"
        task_id = "task-authoritative"
        job_id = "job-authoritative"

    observed = recorder(tmp_path)
    trace = observed.create_trace(context=FrozenContext())

    with observed.activate(trace, name="authoritative"):
        pass

    payload = observed.trace("trace-authoritative")
    assert payload["trace"]["workflow_id"] == "workflow-authoritative"
    assert payload["trace"]["task_id"] == "task-authoritative"
    assert payload["trace"]["job_id"] == "job-authoritative"
    assert payload["spans"][0]["parent_span_id"] == "upstream-span"


def test_observability_levels_bound_metadata_and_never_keep_payloads(tmp_path):
    minimal = recorder(tmp_path / "minimal", level="minimal")
    trace = minimal.create_trace(
        workflow_id="wf-min",
        attributes={"model": "qwen", "prompt_tokens": 99},
    )
    with minimal.activate(trace, name="minimal"):
        pass
    assert minimal.trace(trace.trace_id)["trace"]["attributes"] == {}

    debug = recorder(tmp_path / "debug", level="debug")
    trace = debug.create_trace(
        workflow_id="wf-debug",
        attributes={
            "note": "safe operational note",
            "password": "never",
            "content": "never",
        },
    )
    with debug.activate(trace, name="debug"):
        pass
    attributes = debug.trace(trace.trace_id)["trace"]["attributes"]
    assert attributes["note"] == "safe operational note"
    assert "password" not in attributes
    assert "content" not in attributes


def test_trace_api_can_find_job_correlation(tmp_path):
    observed = recorder(tmp_path)
    trace = observed.create_trace(workflow_id="wf", job_id="job-find")
    with observed.activate(trace, name="findable"):
        pass

    payload = observed.trace_for_job("job-find")
    assert payload is not None
    assert payload["trace"]["trace_id"] == trace.trace_id


def test_trace_persistence_survives_store_reopen(tmp_path):
    path=tmp_path/"observability.db"
    first=TraceRecorder(SQLiteTraceStore(path),level="normal")
    trace=first.create_trace(workflow_id="persistent-workflow",job_id="persistent-job")
    with first.activate(trace,name="persistent"):
        with first.span(SpanKind.VERIFICATION,"verify",attributes={"status":"pass"}) as span:
            assert span is not None
            span.add_artifact("artifact-1")

    reopened=TraceRecorder(SQLiteTraceStore(path),level="normal")
    payload=reopened.trace(trace.trace_id)

    assert payload["trace"]["status"]=="ok"
    verification=next(row for row in payload["spans"] if row["kind"]=="verification")
    assert verification["artifact_ids"]==["artifact-1"]
    assert verification["attributes"]["status"]=="pass"


def test_trace_context_requires_authoritative_span_identity(tmp_path):
    class InvalidContext:
        trace_id="trace"
        workflow_id="workflow"

    observed=recorder(tmp_path)

    with pytest.raises(ValueError,match="span_id"):
        observed.create_trace(context=InvalidContext())


def test_parent_child_span_relationships_are_deterministic(tmp_path):
    observed=recorder(tmp_path)
    trace=observed.create_trace(workflow_id="workflow",job_id="job")

    with observed.activate(trace,name="workflow") as root:
        with observed.span(SpanKind.JOB,"job") as job:
            assert job is not None
            with observed.span(SpanKind.MODEL,"model",model="fixture"):
                pass
            with observed.span(
                SpanKind.RESOURCE,
                "resource",
                attributes={"status":"leased"},
            ):
                pass
            with observed.span(
                SpanKind.ARTIFACT,
                "artifact",
                attributes={"status":"created"},
            ) as artifact:
                assert artifact is not None
                artifact.add_artifact("artifact-1")

    payload=observed.trace(trace.trace_id)
    by_name={row["name"]:row for row in payload["spans"]}
    assert by_name["job"]["parent_span_id"]==root.span_id
    assert by_name["model"]["parent_span_id"]==job.span_id
    assert by_name["resource"]["parent_span_id"]==job.span_id
    assert by_name["artifact"]["parent_span_id"]==job.span_id
    assert by_name["artifact"]["artifact_ids"]==["artifact-1"]


def test_observability_write_failure_is_non_authoritative():
    class BrokenStore:
        def start_trace(self,**_kwargs):
            raise OSError("disk unavailable")

    observed=TraceRecorder(BrokenStore())
    trace=observed.create_trace(workflow_id="workflow",job_id="job")

    assert trace.recording is False
    assert observed.write_failures>=1

    with observed.activate(trace,name="workflow"):
        with observed.span(
            SpanKind.TOOL,
            "tool",
            tool_name="fixture",
        ):
            pass

    assert observed.write_failures>=1
