"""Correlated local trace recording without payload capture."""

from __future__ import annotations

import os
import threading
import time
import uuid
from collections.abc import Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterator


class ObservabilityLevel(str, Enum):
    MINIMAL = "minimal"
    NORMAL = "normal"
    DEBUG = "debug"

    @classmethod
    def parse(cls, value: str | "ObservabilityLevel" | None) -> "ObservabilityLevel":
        if isinstance(value, cls):
            return value
        raw = (
            str(value)
            if value is not None
            else os.environ.get("REVEREND_OBSERVABILITY_LEVEL", cls.NORMAL.value)
        )
        try:
            return cls(raw.strip().lower())
        except ValueError as exc:
            raise ValueError(
                "Observability level must be minimal, normal, or debug"
            ) from exc


class SpanKind(str, Enum):
    WORKFLOW = "workflow"
    TASK = "task"
    JOB = "job"
    MODEL = "model"
    TOOL = "tool"
    VERIFICATION = "verification"
    RESOURCE = "resource"
    ARTIFACT = "artifact"
    BENCHMARK = "benchmark"


class SpanStatus(str, Enum):
    RUNNING = "running"
    OK = "ok"
    ERROR = "error"
    CANCELLED = "cancelled"


def _identifier(value: Any, *, name: str, required: bool = False) -> str | None:
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        raise ValueError(f"{name} must be a non-empty bounded string")
    return value.strip()


def _context_value(context: object, name: str) -> Any:
    if isinstance(context, Mapping):
        return context.get(name)
    return getattr(context, name, None)


@dataclass(frozen=True)
class _TraceRef:
    """Internal correlation reference, not the authoritative vNext TraceContext."""

    trace_id: str
    workflow_id: str | None = None
    task_id: str | None = None
    job_id: str | None = None
    upstream_span_id: str | None = None
    recording: bool = True

    def __post_init__(self) -> None:
        _identifier(self.trace_id, name="trace_id", required=True)
        _identifier(self.workflow_id, name="workflow_id")
        _identifier(self.task_id, name="task_id")
        _identifier(self.job_id, name="job_id")
        _identifier(self.upstream_span_id, name="span_id")

    @classmethod
    def from_context(cls, context: object) -> "_TraceRef":
        """Consume the frozen TraceContext structurally when that contract is present."""

        return cls(
            trace_id=_identifier(
                _context_value(context, "trace_id"),
                name="trace_id",
                required=True,
            ),
            workflow_id=_identifier(
                _context_value(context, "workflow_id"),
                name="workflow_id",
            ),
            task_id=_identifier(
                _context_value(context, "task_id"),
                name="task_id",
            ),
            job_id=_identifier(
                _context_value(context, "job_id"),
                name="job_id",
            ),
            upstream_span_id=_identifier(
                _context_value(context, "span_id"),
                name="span_id",
                required=True,
            ),
        )


_CURRENT_TRACE: ContextVar[_TraceRef | None] = ContextVar(
    "reverend_current_trace",
    default=None,
)
_CURRENT_SPAN: ContextVar[str | None] = ContextVar(
    "reverend_current_span",
    default=None,
)


class SpanHandle:
    def __init__(
        self,
        recorder: "TraceRecorder",
        *,
        span_id: str,
        trace: _TraceRef,
        kind: SpanKind,
        name: str,
        started_at: str,
        started_monotonic: float,
        model: str | None,
        tool_name: str | None,
        attributes: Mapping[str, Any] | None,
    ):
        self.recorder = recorder
        self.span_id = span_id
        self.trace = trace
        self.kind = kind
        self.name = name
        self.started_at = started_at
        self.started_monotonic = started_monotonic
        self.model = model
        self.tool_name = tool_name
        self.attributes: dict[str, Any] = dict(attributes or {})
        self.artifact_ids: list[str] = []
        self._forced_status: SpanStatus | None = None
        self.error_type: str | None = None
        self.error_code: str | None = None
        self.finished = False
        self.persisted = trace.recording

    def set_attributes(self, **attributes: Any) -> None:
        self.attributes.update(attributes)

    def set_model(self, model: str | None) -> None:
        if model:
            self.model = str(model)[:256]

    def add_artifact(self, artifact_id: str) -> None:
        clean = _identifier(artifact_id, name="artifact_id", required=True)
        if clean not in self.artifact_ids:
            self.artifact_ids.append(clean)

    def fail(
        self,
        error: BaseException | None = None,
        *,
        code: str | None = None,
    ) -> None:
        self._forced_status = SpanStatus.ERROR
        if error is not None:
            self.error_type = type(error).__name__[:128]
            code = code or getattr(error, "code", None)
        if code:
            self.error_code = str(code)[:128]

    def cancel(self) -> None:
        self._forced_status = SpanStatus.CANCELLED

    @property
    def status(self) -> SpanStatus:
        return self._forced_status or SpanStatus.OK


class TraceRecorder:
    """Create/query correlated traces while never recording prompt/response payloads."""

    def __init__(
        self,
        store,
        *,
        level: ObservabilityLevel | str | None = None,
        monotonic=time.monotonic,
    ):
        self.store = store
        self.level = ObservabilityLevel.parse(level)
        self._monotonic = monotonic
        self._write_failures = 0
        self._failure_lock = threading.Lock()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def current_trace() -> _TraceRef | None:
        return _CURRENT_TRACE.get()

    @property
    def write_failures(self) -> int:
        with self._failure_lock:
            return self._write_failures

    def _record_write_failure(self) -> None:
        with self._failure_lock:
            self._write_failures += 1

    def create_trace(
        self,
        *,
        context: object | None = None,
        workflow_id: str | None = None,
        task_id: str | None = None,
        job_id: str | None = None,
        attributes: Mapping[str, Any] | None = None,
    ) -> _TraceRef:
        from .redaction import sanitize_attributes

        if context is not None:
            ref = _TraceRef.from_context(context)
        else:
            trace_id = str(uuid.uuid4())
            ref = _TraceRef(
                trace_id=trace_id,
                workflow_id=_identifier(workflow_id, name="workflow_id") or trace_id,
                task_id=_identifier(task_id, name="task_id"),
                job_id=_identifier(job_id, name="job_id"),
            )

        try:
            self.store.start_trace(
                trace_id=ref.trace_id,
                workflow_id=ref.workflow_id,
                task_id=ref.task_id,
                job_id=ref.job_id,
                level=self.level.value,
                started_at=self._now(),
                attributes=sanitize_attributes(attributes, level=self.level),
            )
        except Exception:
            self._record_write_failure()
            ref = replace(ref, recording=False)
        return ref

    def attach(
        self,
        *,
        workflow_id: str | None = None,
        task_id: str | None = None,
        job_id: str | None = None,
    ) -> _TraceRef | None:
        current = _CURRENT_TRACE.get()
        if current is None:
            return None

        updated = replace(
            current,
            workflow_id=(
                _identifier(workflow_id, name="workflow_id")
                if workflow_id is not None
                else current.workflow_id
            ),
            task_id=(
                _identifier(task_id, name="task_id")
                if task_id is not None
                else current.task_id
            ),
            job_id=(
                _identifier(job_id, name="job_id")
                if job_id is not None
                else current.job_id
            ),
        )
        _CURRENT_TRACE.set(updated)
        if updated.recording:
            try:
                self.store.link_trace(
                    updated.trace_id,
                    workflow_id=updated.workflow_id,
                    task_id=updated.task_id,
                    job_id=updated.job_id,
                )
            except Exception:
                self._record_write_failure()
                updated = replace(updated, recording=False)
                _CURRENT_TRACE.set(updated)
        return updated

    def _start_span(
        self,
        *,
        kind: SpanKind | str,
        name: str,
        trace: _TraceRef | None = None,
        parent_span_id: str | None = None,
        model: str | None = None,
        tool_name: str | None = None,
        attributes: Mapping[str, Any] | None = None,
    ) -> SpanHandle:
        from .redaction import sanitize_attributes

        active = trace or _CURRENT_TRACE.get()
        if active is None:
            raise RuntimeError("No active trace")
        span_kind = kind if isinstance(kind, SpanKind) else SpanKind(str(kind))
        if not isinstance(name, str) or not name.strip() or len(name) > 256:
            raise ValueError("Span name must be non-empty bounded text")

        span_id = str(uuid.uuid4())
        started_at = self._now()
        started_monotonic = self._monotonic()
        parent = (
            parent_span_id
            if parent_span_id is not None
            else (_CURRENT_SPAN.get() or active.upstream_span_id)
        )
        handle = SpanHandle(
            self,
            span_id=span_id,
            trace=active,
            kind=span_kind,
            name=name.strip(),
            started_at=started_at,
            started_monotonic=started_monotonic,
            model=model,
            tool_name=tool_name,
            attributes=attributes,
        )
        if active.recording:
            try:
                self.store.start_span(
                    span_id=span_id,
                    trace_id=active.trace_id,
                    parent_span_id=parent,
                    kind=span_kind.value,
                    name=handle.name,
                    started_at=started_at,
                    workflow_id=active.workflow_id,
                    task_id=active.task_id,
                    job_id=active.job_id,
                    model=(str(model)[:256] if model else None),
                    tool_name=(str(tool_name)[:256] if tool_name else None),
                    attributes=sanitize_attributes(attributes, level=self.level),
                )
            except Exception:
                self._record_write_failure()
                handle.persisted = False
        else:
            handle.persisted = False
        return handle

    def _finish_span(self, handle: SpanHandle) -> None:
        from .redaction import sanitize_attributes

        if handle.finished:
            return
        handle.finished = True
        duration = max(0.0, self._monotonic() - handle.started_monotonic)
        if not handle.persisted:
            return
        try:
            self.store.finish_span(
                handle.span_id,
                status=handle.status.value,
                completed_at=self._now(),
                duration_seconds=round(duration, 6),
                error_type=handle.error_type,
                error_code=handle.error_code,
                model=handle.model,
                tool_name=handle.tool_name,
                artifact_ids=tuple(handle.artifact_ids[:64]),
                attributes=sanitize_attributes(handle.attributes, level=self.level),
            )
        except Exception:
            self._record_write_failure()

    @contextmanager
    def activate(
        self,
        trace: _TraceRef,
        *,
        name: str,
        attributes: Mapping[str, Any] | None = None,
    ) -> Iterator[SpanHandle]:
        trace_token = _CURRENT_TRACE.set(trace)
        parent_token = _CURRENT_SPAN.set(None)
        try:
            root = self._start_span(
                kind=SpanKind.WORKFLOW,
                name=name,
                trace=trace,
                parent_span_id=None,
                attributes=attributes,
            )
            span_token = _CURRENT_SPAN.set(root.span_id)
            try:
                yield root
            except BaseException as exc:
                root.fail(exc)
                raise
            finally:
                _CURRENT_SPAN.reset(span_token)
                self._finish_span(root)
                if trace.recording:
                    try:
                        self.store.finish_trace(
                            trace.trace_id,
                            status=root.status.value,
                            completed_at=self._now(),
                            duration_seconds=round(
                                max(0.0, self._monotonic() - root.started_monotonic),
                                6,
                            ),
                        )
                    except Exception:
                        self._record_write_failure()
        finally:
            _CURRENT_SPAN.reset(parent_token)
            _CURRENT_TRACE.reset(trace_token)

    @contextmanager
    def span(
        self,
        kind: SpanKind | str,
        name: str,
        *,
        model: str | None = None,
        tool_name: str | None = None,
        attributes: Mapping[str, Any] | None = None,
    ) -> Iterator[SpanHandle | None]:
        if _CURRENT_TRACE.get() is None:
            yield None
            return

        handle = self._start_span(
            kind=kind,
            name=name,
            model=model,
            tool_name=tool_name,
            attributes=attributes,
        )
        token = _CURRENT_SPAN.set(handle.span_id)
        try:
            yield handle
        except BaseException as exc:
            handle.fail(exc)
            raise
        finally:
            _CURRENT_SPAN.reset(token)
            self._finish_span(handle)

    def trace(self, trace_id: str) -> dict[str, Any]:
        return self.store.trace(trace_id)

    def traces(self, *, limit: int = 50) -> list[dict[str, Any]]:
        return self.store.list_traces(limit=limit)

    def trace_for_job(self, job_id: str) -> dict[str, Any] | None:
        return self.store.trace_for_job(job_id)
