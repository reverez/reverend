"""Frozen-contract data types for Reverend's generic control plane."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Any

class WorkflowStatus(str, Enum):
    PENDING="pending"; ACTIVE="active"; COMPLETE="complete"; FAILED="failed"; CANCELLED="cancelled"
class TaskStatus(str, Enum):
    PENDING="pending"; READY="ready"; RUNNING="running"; BLOCKED="blocked"; COMPLETE="complete"; FAILED="failed"; CANCELLED="cancelled"
class JobStatus(str, Enum):
    QUEUED="queued"; ACQUIRING_RESOURCES="acquiring_resources"; RUNNING="running"; VERIFYING="verifying"; SUCCEEDED="succeeded"; FAILED="failed"; CANCELLED="cancelled"; TIMED_OUT="timed_out"
class ValidationState(str, Enum):
    UNVALIDATED="unvalidated"; VALIDATED="validated"; REJECTED="rejected"
class PromotionState(str, Enum):
    UNPROMOTED="unpromoted"; PROMOTED="promoted"; RETAINED="retained"

@dataclass(frozen=True)
class Workflow:
    id:str; objective:str; status:WorkflowStatus; trace_id:str; created_at:str; updated_at:str
@dataclass(frozen=True)
class Task:
    id:str; workflow_id:str; kind:str; objective:str; status:TaskStatus; dependencies:tuple[str,...]; acceptance_criteria:tuple[str,...]; created_at:str; updated_at:str
@dataclass(frozen=True)
class Job:
    id:str; task_id:str; attempt_number:int; status:JobStatus; executor:str|None; trace_context:dict[str,Any]; started_at:str|None; finished_at:str|None; error_code:str|None; result_ref:str|None
@dataclass(frozen=True)
class Event:
    id:str; event_type:str; occurred_at:str; trace_context:dict[str,Any]; actor:str; subject_ids:tuple[str,...]; schema_version:int; payload:dict[str,Any]
@dataclass(frozen=True)
class Artifact:
    id:str; artifact_type:str; schema_version:int; content_ref:str|None; inline_content:str|None; content_hash:str; producer_job_id:str|None; parent_ids:tuple[str,...]; provenance:dict[str,Any]; validation_state:ValidationState; promotion_state:PromotionState; created_at:str
