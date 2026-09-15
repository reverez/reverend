"""Core state definitions for Reverend development tasks."""

from __future__ import annotations

from enum import Enum


class TrustMode(str, Enum):
    TRUSTED_REPO = "trusted_repo"
    UNTRUSTED_REPO = "untrusted_repo"


class TaskState(str, Enum):
    PENDING = "pending"
    PREPARING = "preparing"
    RUNNING = "running"
    VERIFYING = "verifying"
    COMPLETE = "complete"
    BLOCKED = "blocked"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    SKIPPED = "skipped"
