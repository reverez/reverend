"""Durable authoritative Workflow/Task/Job/Event/Artifact state."""
from __future__ import annotations
import hashlib,json,sqlite3,uuid
from contextlib import contextmanager
from datetime import datetime,timezone
from pathlib import Path
from typing import Any,Iterator
from reverend.config import DATA_ROOT
from .models import Artifact,Event,Job,JobStatus,PromotionState,Task,TaskStatus,ValidationState,Workflow,WorkflowStatus
SCHEMA_VERSION=1
MAX_INLINE_ARTIFACT_BYTES=64*1024
MAX_EVENT_PAYLOAD_BYTES=32*1024
class ControlPlaneError(RuntimeError):pass
class StateTransitionError(ControlPlaneError):pass
class DependencyCycleError(ControlPlaneError):pass
class NotFoundError(ControlPlaneError):pass
class ArtifactStateError(ControlPlaneError):pass
WORKFLOW_TRANSITIONS={WorkflowStatus.PENDING:{WorkflowStatus.ACTIVE,WorkflowStatus.CANCELLED},WorkflowStatus.ACTIVE:{WorkflowStatus.COMPLETE,WorkflowStatus.FAILED,WorkflowStatus.CANCELLED},WorkflowStatus.COMPLETE:set(),WorkflowStatus.FAILED:set(),WorkflowStatus.CANCELLED:set()}
TASK_TRANSITIONS={TaskStatus.PENDING:{TaskStatus.READY,TaskStatus.CANCELLED},TaskStatus.READY:{TaskStatus.RUNNING,TaskStatus.BLOCKED,TaskStatus.CANCELLED},TaskStatus.RUNNING:{TaskStatus.BLOCKED,TaskStatus.COMPLETE,TaskStatus.FAILED,TaskStatus.CANCELLED},TaskStatus.BLOCKED:{TaskStatus.READY,TaskStatus.FAILED,TaskStatus.CANCELLED},TaskStatus.COMPLETE:set(),TaskStatus.FAILED:set(),TaskStatus.CANCELLED:set()}
JOB_TRANSITIONS={JobStatus.QUEUED:{JobStatus.ACQUIRING_RESOURCES,JobStatus.RUNNING,JobStatus.CANCELLED,JobStatus.TIMED_OUT},JobStatus.ACQUIRING_RESOURCES:{JobStatus.RUNNING,JobStatus.FAILED,JobStatus.CANCELLED,JobStatus.TIMED_OUT},JobStatus.RUNNING:{JobStatus.VERIFYING,JobStatus.SUCCEEDED,JobStatus.FAILED,JobStatus.CANCELLED,JobStatus.TIMED_OUT},JobStatus.VERIFYING:{JobStatus.SUCCEEDED,JobStatus.FAILED,JobStatus.CANCELLED,JobStatus.TIMED_OUT},JobStatus.SUCCEEDED:set(),JobStatus.FAILED:set(),JobStatus.CANCELLED:set(),JobStatus.TIMED_OUT:set()}
SCHEMA_SQL="""
CREATE TABLE IF NOT EXISTS control_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS workflows(id TEXT PRIMARY KEY,objective TEXT NOT NULL,status TEXT NOT NULL,trace_id TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,workflow_id TEXT NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,kind TEXT NOT NULL,objective TEXT NOT NULL,status TEXT NOT NULL,acceptance_criteria_json TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS task_dependencies(task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,depends_on_task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,PRIMARY KEY(task_id,depends_on_task_id),CHECK(task_id<>depends_on_task_id));
CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,attempt_number INTEGER NOT NULL,status TEXT NOT NULL,executor TEXT,trace_json TEXT NOT NULL,started_at TEXT,finished_at TEXT,error_code TEXT,result_ref TEXT,UNIQUE(task_id,attempt_number));
CREATE TABLE IF NOT EXISTS events(sequence INTEGER PRIMARY KEY AUTOINCREMENT,id TEXT NOT NULL UNIQUE,event_type TEXT NOT NULL,occurred_at TEXT NOT NULL,trace_json TEXT NOT NULL,actor TEXT NOT NULL,subject_json TEXT NOT NULL,schema_version INTEGER NOT NULL,payload_json TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT,'events are immutable');END;
CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT,'events are immutable');END;
CREATE TABLE IF NOT EXISTS artifacts(id TEXT PRIMARY KEY,artifact_type TEXT NOT NULL,schema_version INTEGER NOT NULL,content_ref TEXT,inline_content TEXT,content_hash TEXT NOT NULL,producer_job_id TEXT REFERENCES jobs(id),provenance_json TEXT NOT NULL,validation_state TEXT NOT NULL,promotion_state TEXT NOT NULL,created_at TEXT NOT NULL,CHECK(content_ref IS NOT NULL OR inline_content IS NOT NULL));
CREATE TABLE IF NOT EXISTS artifact_parents(artifact_id TEXT NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,parent_id TEXT NOT NULL REFERENCES artifacts(id),PRIMARY KEY(artifact_id,parent_id),CHECK(artifact_id<>parent_id));
CREATE INDEX IF NOT EXISTS tasks_workflow_idx ON tasks(workflow_id);
CREATE INDEX IF NOT EXISTS jobs_task_idx ON jobs(task_id,attempt_number);
CREATE INDEX IF NOT EXISTS events_type_idx ON events(event_type,sequence);
CREATE INDEX IF NOT EXISTS artifacts_job_idx ON artifacts(producer_job_id);
"""
def default_control_plane_path(data_root:Path|None=None)->Path:return Path(data_root or DATA_ROOT)/"control-plane.db"
def _now()->str:return datetime.now(timezone.utc).isoformat()
def _clean_text(value:str,field:str,*,limit:int=20_000)->str:
    if not isinstance(value,str) or not value.strip():raise ValueError(f"{field} must be non-empty text")
    clean=value.strip()
    if len(clean)>limit:raise ValueError(f"{field} exceeds {limit} characters")
    return clean
def _json(value:Any,*,field:str,limit:int)->str:
    try:encoded=json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False)
    except (TypeError,ValueError) as exc:raise ValueError(f"{field} must be JSON serializable") from exc
    if len(encoded.encode("utf-8"))>limit:raise ValueError(f"{field} exceeds its bounded payload limit")
    return encoded
class ControlPlaneStore:
    def __init__(self,path:str|Path|None=None)->None:
        self.path=Path(path) if path is not None else default_control_plane_path();self.path.parent.mkdir(parents=True,exist_ok=True);self._initialize()
    @contextmanager
    def connection(self)->Iterator[sqlite3.Connection]:
        connection=sqlite3.connect(str(self.path),timeout=30);connection.row_factory=sqlite3.Row;connection.execute("PRAGMA foreign_keys=ON");connection.execute("PRAGMA busy_timeout=5000");connection.execute("PRAGMA journal_mode=WAL")
        try:yield connection
        finally:connection.close()
    @contextmanager
    def transaction(self)->Iterator[sqlite3.Connection]:
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:yield connection
            except BaseException:connection.rollback();raise
            else:connection.commit()
    def _initialize(self)->None:
        with self.connection() as db:
            version=int(db.execute("PRAGMA user_version").fetchone()[0])
            if version>SCHEMA_VERSION:raise ControlPlaneError(f"control-plane schema {version} is newer than supported {SCHEMA_VERSION}")
            db.executescript(SCHEMA_SQL);db.execute(f"PRAGMA user_version={SCHEMA_VERSION}");db.execute("INSERT INTO control_meta(key,value) VALUES('schema_version',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(str(SCHEMA_VERSION),))
    def create_workflow(self,objective:str,*,workflow_id:str|None=None,trace_id:str|None=None)->Workflow:
        now=_now();identity=workflow_id or str(uuid.uuid4());trace=trace_id or str(uuid.uuid4())
        with self.transaction() as db:db.execute("INSERT INTO workflows(id,objective,status,trace_id,created_at,updated_at) VALUES(?,?,?,?,?,?)",(identity,_clean_text(objective,"objective"),"pending",trace,now,now))
        return self.workflow(identity)
    def workflow(self,workflow_id:str)->Workflow:
        with self.connection() as db:row=db.execute("SELECT * FROM workflows WHERE id=?",(workflow_id,)).fetchone()
        if row is None:raise NotFoundError(f"Unknown workflow: {workflow_id}")
        return Workflow(row["id"],row["objective"],WorkflowStatus(row["status"]),row["trace_id"],row["created_at"],row["updated_at"])
    def transition_workflow(self,workflow_id:str,target:WorkflowStatus)->Workflow:
        current=self.workflow(workflow_id)
        if target==current.status:return current
        if target not in WORKFLOW_TRANSITIONS[current.status]:raise StateTransitionError(f"Illegal workflow transition: {current.status.value} -> {target.value}")
        with self.transaction() as db:db.execute("UPDATE workflows SET status=?,updated_at=? WHERE id=?",(target.value,_now(),workflow_id))
        return self.workflow(workflow_id)
    def create_task(self,workflow_id:str,*,kind:str,objective:str,dependencies:tuple[str,...]=(),acceptance_criteria:tuple[str,...]=(),task_id:str|None=None)->Task:
        self.workflow(workflow_id);identity=task_id or str(uuid.uuid4());now=_now();criteria=tuple(_clean_text(x,"acceptance criterion",limit=2000) for x in acceptance_criteria)
        with self.transaction() as db:db.execute("INSERT INTO tasks(id,workflow_id,kind,objective,status,acceptance_criteria_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",(identity,workflow_id,_clean_text(kind,"kind",limit=128),_clean_text(objective,"objective"),"pending",_json(criteria,field="acceptance criteria",limit=64*1024),now,now))
        try:
            for dep in dependencies:self.add_dependency(identity,dep)
        except BaseException:
            with self.transaction() as db:db.execute("DELETE FROM tasks WHERE id=?",(identity,))
            raise
        return self.task(identity)
    def task(self,task_id:str)->Task:
        with self.connection() as db:
            row=db.execute("SELECT * FROM tasks WHERE id=?",(task_id,)).fetchone()
            deps=tuple(x[0] for x in db.execute("SELECT depends_on_task_id FROM task_dependencies WHERE task_id=? ORDER BY depends_on_task_id",(task_id,)).fetchall()) if row is not None else ()
        if row is None:raise NotFoundError(f"Unknown task: {task_id}")
        return Task(row["id"],row["workflow_id"],row["kind"],row["objective"],TaskStatus(row["status"]),deps,tuple(json.loads(row["acceptance_criteria_json"])),row["created_at"],row["updated_at"])
    def add_dependency(self,task_id:str,depends_on_task_id:str)->Task:
        task=self.task(task_id);dependency=self.task(depends_on_task_id)
        if task.workflow_id!=dependency.workflow_id:raise ControlPlaneError("Task dependencies cannot cross workflows")
        if task_id==depends_on_task_id:raise DependencyCycleError("Task cannot depend on itself")
        with self.connection() as db:cycle=db.execute("""WITH RECURSIVE reachable(id) AS (SELECT depends_on_task_id FROM task_dependencies WHERE task_id=? UNION SELECT d.depends_on_task_id FROM task_dependencies d JOIN reachable r ON d.task_id=r.id) SELECT 1 FROM reachable WHERE id=? LIMIT 1""",(depends_on_task_id,task_id)).fetchone()
        if cycle is not None:raise DependencyCycleError(f"Dependency would create a cycle: {task_id} -> {depends_on_task_id}")
        with self.transaction() as db:db.execute("INSERT OR IGNORE INTO task_dependencies(task_id,depends_on_task_id) VALUES(?,?)",(task_id,depends_on_task_id))
        return self.task(task_id)
    def transition_task(self,task_id:str,target:TaskStatus)->Task:
        current=self.task(task_id)
        if target==current.status:return current
        if target not in TASK_TRANSITIONS[current.status]:raise StateTransitionError(f"Illegal task transition: {current.status.value} -> {target.value}")
        if target is TaskStatus.READY:
            with self.connection() as db:blocking=db.execute("SELECT d.depends_on_task_id FROM task_dependencies d JOIN tasks t ON t.id=d.depends_on_task_id WHERE d.task_id=? AND t.status<>'complete' LIMIT 1",(task_id,)).fetchone()
            if blocking is not None:raise StateTransitionError(f"Task dependency is not complete: {blocking[0]}")
        with self.transaction() as db:db.execute("UPDATE tasks SET status=?,updated_at=? WHERE id=?",(target.value,_now(),task_id))
        return self.task(task_id)
    def create_job(self,task_id:str,*,executor:str|None=None,trace_context:dict[str,Any]|None=None,job_id:str|None=None)->Job:
        self.task(task_id);identity=job_id or str(uuid.uuid4())
        with self.transaction() as db:
            attempt=int(db.execute("SELECT COALESCE(MAX(attempt_number),0)+1 FROM jobs WHERE task_id=?",(task_id,)).fetchone()[0])
            db.execute("INSERT INTO jobs(id,task_id,attempt_number,status,executor,trace_json) VALUES(?,?,?,?,?,?)",(identity,task_id,attempt,"queued",executor,_json(trace_context or {},field="trace context",limit=16*1024)))
        return self.job(identity)
    def job(self,job_id:str)->Job:
        with self.connection() as db:row=db.execute("SELECT * FROM jobs WHERE id=?",(job_id,)).fetchone()
        if row is None:raise NotFoundError(f"Unknown job: {job_id}")
        return Job(row["id"],row["task_id"],int(row["attempt_number"]),JobStatus(row["status"]),row["executor"],dict(json.loads(row["trace_json"])),row["started_at"],row["finished_at"],row["error_code"],row["result_ref"])
    def jobs_for_task(self,task_id:str)->tuple[Job,...]:
        self.task(task_id)
        with self.connection() as db:ids=[r[0] for r in db.execute("SELECT id FROM jobs WHERE task_id=? ORDER BY attempt_number",(task_id,)).fetchall()]
        return tuple(self.job(i) for i in ids)
    def transition_job(self,job_id:str,target:JobStatus,*,error_code:str|None=None,result_ref:str|None=None)->Job:
        current=self.job(job_id)
        if target==current.status:return current
        if target not in JOB_TRANSITIONS[current.status]:raise StateTransitionError(f"Illegal job transition: {current.status.value} -> {target.value}")
        now=_now();started=current.started_at
        if target in {JobStatus.ACQUIRING_RESOURCES,JobStatus.RUNNING} and started is None:started=now
        finished=current.finished_at
        if target in {JobStatus.SUCCEEDED,JobStatus.FAILED,JobStatus.CANCELLED,JobStatus.TIMED_OUT}:finished=now
        with self.transaction() as db:db.execute("UPDATE jobs SET status=?,started_at=?,finished_at=?,error_code=?,result_ref=? WHERE id=?",(target.value,started,finished,error_code,result_ref,job_id))
        return self.job(job_id)
    def append_event(self,event_type:str,*,actor:str,subject_ids:tuple[str,...]=(),trace_context:dict[str,Any]|None=None,payload:dict[str,Any]|None=None,schema_version:int=1,event_id:str|None=None)->Event:
        event=Event(event_id or str(uuid.uuid4()),_clean_text(event_type,"event type",limit=128),_now(),dict(trace_context or {}),_clean_text(actor,"actor",limit=256),tuple(subject_ids),int(schema_version),dict(payload or {}))
        with self.transaction() as db:db.execute("INSERT INTO events(id,event_type,occurred_at,trace_json,actor,subject_json,schema_version,payload_json) VALUES(?,?,?,?,?,?,?,?)",(event.id,event.event_type,event.occurred_at,_json(event.trace_context,field="trace context",limit=16*1024),event.actor,_json(event.subject_ids,field="subjects",limit=16*1024),event.schema_version,_json(event.payload,field="event payload",limit=MAX_EVENT_PAYLOAD_BYTES)))
        return event
    def events(self,*,event_type:str|None=None)->tuple[Event,...]:
        with self.connection() as db:rows=db.execute("SELECT * FROM events"+(" WHERE event_type=?" if event_type else "")+" ORDER BY sequence",((event_type,) if event_type else ())).fetchall()
        return tuple(Event(r["id"],r["event_type"],r["occurred_at"],dict(json.loads(r["trace_json"])),r["actor"],tuple(json.loads(r["subject_json"])),int(r["schema_version"]),dict(json.loads(r["payload_json"]))) for r in rows)
    def create_artifact(self,artifact_type:str,*,schema_version:int=1,content_ref:str|None=None,inline_content:str|None=None,content_hash:str|None=None,producer_job_id:str|None=None,parent_ids:tuple[str,...]=(),provenance:dict[str,Any]|None=None,artifact_id:str|None=None)->Artifact:
        if content_ref is None and inline_content is None:raise ValueError("Artifact requires content_ref or inline_content")
        if inline_content is not None:
            raw=inline_content.encode("utf-8")
            if len(raw)>MAX_INLINE_ARTIFACT_BYTES:raise ValueError("Inline artifact exceeds bounded storage limit")
            digest=hashlib.sha256(raw).hexdigest()
            if content_hash is not None and content_hash!=digest:raise ValueError("Artifact content_hash does not match inline content")
            content_hash=digest
        elif not content_hash:raise ValueError("Referenced artifact requires an explicit content_hash")
        if producer_job_id is not None:self.job(producer_job_id)
        for parent in parent_ids:self.artifact(parent)
        identity=artifact_id or str(uuid.uuid4())
        with self.transaction() as db:
            db.execute("INSERT INTO artifacts(id,artifact_type,schema_version,content_ref,inline_content,content_hash,producer_job_id,provenance_json,validation_state,promotion_state,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",(identity,_clean_text(artifact_type,"artifact type",limit=128),int(schema_version),content_ref,inline_content,content_hash,producer_job_id,_json(provenance or {},field="provenance",limit=64*1024),"unvalidated","unpromoted",_now()))
            for parent in parent_ids:db.execute("INSERT INTO artifact_parents(artifact_id,parent_id) VALUES(?,?)",(identity,parent))
        return self.artifact(identity)
    def artifact(self,artifact_id:str)->Artifact:
        with self.connection() as db:
            row=db.execute("SELECT * FROM artifacts WHERE id=?",(artifact_id,)).fetchone()
            parents=tuple(x[0] for x in db.execute("SELECT parent_id FROM artifact_parents WHERE artifact_id=? ORDER BY parent_id",(artifact_id,)).fetchall()) if row is not None else ()
        if row is None:raise NotFoundError(f"Unknown artifact: {artifact_id}")
        return Artifact(row["id"],row["artifact_type"],int(row["schema_version"]),row["content_ref"],row["inline_content"],row["content_hash"],row["producer_job_id"],parents,dict(json.loads(row["provenance_json"])),ValidationState(row["validation_state"]),PromotionState(row["promotion_state"]),row["created_at"])
    def validate_artifact(self,artifact_id:str,*,accepted:bool)->Artifact:
        current=self.artifact(artifact_id)
        if current.validation_state is not ValidationState.UNVALIDATED:
            if (accepted and current.validation_state is ValidationState.VALIDATED) or (not accepted and current.validation_state is ValidationState.REJECTED):return current
            raise ArtifactStateError("Artifact validation decision is immutable")
        target=ValidationState.VALIDATED if accepted else ValidationState.REJECTED
        with self.transaction() as db:db.execute("UPDATE artifacts SET validation_state=? WHERE id=?",(target.value,artifact_id))
        return self.artifact(artifact_id)
    def promote_artifact(self,artifact_id:str)->Artifact:
        current=self.artifact(artifact_id)
        if current.validation_state is not ValidationState.VALIDATED:raise ArtifactStateError("Only validated artifacts may be promoted")
        if current.promotion_state is PromotionState.PROMOTED:return current
        with self.transaction() as db:db.execute("UPDATE artifacts SET promotion_state='promoted' WHERE id=?",(artifact_id,))
        return self.artifact(artifact_id)
