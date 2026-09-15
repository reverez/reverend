"""Encrypted chat/job persistence with explicit Reverend privacy modes."""
from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from .crypto import StateCipher


RELEVANCE_QUERY_MAX_CHARS = 12_000


class PrivacyMode(str, Enum):
    NORMAL = "normal"
    PRIVATE = "private"
    EPHEMERAL = "ephemeral"


def _privacy_mode(value: PrivacyMode | str) -> PrivacyMode:
    try:
        return (
            value
            if isinstance(value, PrivacyMode)
            else PrivacyMode(str(value).lower())
        )
    except ValueError as exc:
        raise ValueError(
            "Unknown privacy mode"
        ) from exc


SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations(
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    privacy_mode TEXT NOT NULL DEFAULT 'normal',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS messages(
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id),
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS jobs(
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    conversation_id TEXT,
    task_id TEXT,
    response TEXT NOT NULL DEFAULT '',
    details TEXT NOT NULL DEFAULT '{}',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS authoritative_tasks(
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'active'
        CHECK(state IN ('active','blocked','complete','failed','cancelled')),
    objective TEXT NOT NULL,
    authoritative_specification TEXT NOT NULL,
    specification_hash TEXT NOT NULL,
    specification_version INTEGER NOT NULL DEFAULT 1
        CHECK(specification_version >= 1),
    immutable_requirements TEXT NOT NULL,
    acceptance_criteria TEXT NOT NULL,
    decisions TEXT NOT NULL,
    completed_steps TEXT NOT NULL,
    current_step TEXT NOT NULL,
    remaining_steps TEXT NOT NULL,
    blocked_state TEXT NOT NULL,
    checkpoint TEXT NOT NULL,
    relevant_project TEXT NOT NULL,
    provenance TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS messages_conversation ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS authoritative_tasks_conversation
    ON authoritative_tasks(conversation_id);
CREATE UNIQUE INDEX IF NOT EXISTS authoritative_tasks_one_open
    ON authoritative_tasks(conversation_id)
    WHERE state IN ('active','blocked');
"""


def _now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


class WorkspaceStore:
    """Encrypt durable state and keep Ephemeral state process-local."""

    def __init__(
        self,
        path: str | Path,
        *,
        key_path: str | Path | None = None,
    ):
        self.path = Path(path)
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        try:
            os.chmod(
                self.path.parent,
                0o700,
            )
        except OSError:
            pass

        self._cipher = StateCipher(
            key_path
            if key_path is not None
            else (
                self.path.parent
                / ".workspace-state-v1.key"
            )
        )
        self.key_path = (
            self._cipher.key_path
        )
        self._lock = (
            threading.RLock()
        )
        self._ephemeral_conversations: dict[
            str,
            dict,
        ] = {}
        self._ephemeral_messages: dict[
            str,
            list[dict],
        ] = {}
        self._ephemeral_jobs: dict[
            str,
            dict,
        ] = {}
        self._ephemeral_tasks: dict[
            str,
            dict,
        ] = {}

        migrated = False

        with self.connect() as db:
            db.executescript(
                SCHEMA
            )
            columns = {
                row["name"]
                for row in db.execute(
                    "PRAGMA table_info(conversations)"
                )
            }
            if (
                "privacy_mode"
                not in columns
            ):
                db.execute(
                    "ALTER TABLE conversations "
                    "ADD COLUMN privacy_mode TEXT NOT NULL "
                    "DEFAULT 'normal'"
                )

            migrated = (
                self._encrypt_legacy_rows(
                    db
                )
            )
            self._verify_encryption_key(
                db
            )

        if migrated:
            self._compact_after_migration()

        self._secure_state_files()

    def _secure_state_files(
        self,
    ) -> None:
        for candidate in (
            self.path,
            Path(
                str(self.path)
                + "-wal"
            ),
            Path(
                str(self.path)
                + "-shm"
            ),
        ):
            try:
                if candidate.exists():
                    os.chmod(
                        candidate,
                        0o600,
                    )
            except OSError:
                pass

    @contextmanager
    def connect(self):
        db = sqlite3.connect(
            self.path,
            timeout=10,
        )
        db.row_factory = (
            sqlite3.Row
        )
        db.execute(
            "PRAGMA foreign_keys=ON"
        )
        db.execute(
            "PRAGMA secure_delete=ON"
        )
        db.execute(
            "PRAGMA journal_mode=WAL"
        )

        try:
            with db:
                yield db
        finally:
            db.close()
            self._secure_state_files()

    def _encrypt_legacy_rows(
        self,
        db: sqlite3.Connection,
    ) -> bool:
        migrated = False

        protected = (
            (
                "conversations",
                ("title",),
            ),
            (
                "messages",
                (
                    "content",
                    "metadata",
                ),
            ),
            (
                "jobs",
                (
                    "response",
                    "details",
                ),
            ),
            (
                "authoritative_tasks",
                (
                    "objective",
                    "authoritative_specification",
                    "immutable_requirements",
                    "acceptance_criteria",
                    "decisions",
                    "completed_steps",
                    "current_step",
                    "remaining_steps",
                    "blocked_state",
                    "checkpoint",
                    "relevant_project",
                    "provenance",
                ),
            ),
        )

        for table, fields in protected:
            rows = db.execute(
                "SELECT rowid,"
                + ",".join(fields)
                + f" FROM {table}"
            ).fetchall()

            for row in rows:
                updates = {}

                for field in fields:
                    value = row[
                        field
                    ]
                    if not (
                        self._cipher
                        .is_encrypted(
                            value
                        )
                    ):
                        updates[
                            field
                        ] = (
                            self._cipher
                            .encrypt(
                                value
                            )
                        )

                if not updates:
                    continue

                migrated = True
                db.execute(
                    f"UPDATE {table} SET "
                    + ",".join(
                        field + "=?"
                        for field
                        in updates
                    )
                    + " WHERE rowid=?",
                    (
                        *updates.values(),
                        row["rowid"],
                    ),
                )

        return migrated

    def _verify_encryption_key(
        self,
        db: sqlite3.Connection,
    ) -> None:
        probes = (
            (
                "conversations",
                "title",
            ),
            (
                "messages",
                "content",
            ),
            (
                "jobs",
                "response",
            ),
            (
                "authoritative_tasks",
                "objective",
            ),
        )

        for table, field in probes:
            row = db.execute(
                f"SELECT {field} FROM {table} "
                "LIMIT 1"
            ).fetchone()

            if row is not None:
                self._cipher.decrypt(
                    row[field]
                )

    def _compact_after_migration(
        self,
    ) -> None:
        db = sqlite3.connect(
            self.path,
            timeout=10,
            isolation_level=None,
        )

        try:
            db.execute(
                "PRAGMA secure_delete=ON"
            )
            db.execute(
                "PRAGMA wal_checkpoint(TRUNCATE)"
            )
            db.execute(
                "VACUUM"
            )
            db.execute(
                "PRAGMA wal_checkpoint(TRUNCATE)"
            )
        finally:
            db.close()
            self._secure_state_files()

    def privacy_mode(
        self,
        identity: str,
    ) -> PrivacyMode:
        with self._lock:
            row = (
                self._ephemeral_conversations
                .get(identity)
            )
            if row is not None:
                return (
                    PrivacyMode.EPHEMERAL
                )

        with self.connect() as db:
            row = db.execute(
                "SELECT privacy_mode "
                "FROM conversations "
                "WHERE id=?",
                (identity,),
            ).fetchone()

        if row is None:
            raise KeyError(
                "Unknown conversation"
            )

        return _privacy_mode(
            row["privacy_mode"]
        )

    def conversations(
        self,
    ) -> list[dict]:
        with self.connect() as db:
            persisted = []

            for row in db.execute(
                "SELECT * FROM conversations "
                "ORDER BY rowid DESC LIMIT 100"
            ):
                item = dict(
                    row
                )
                item[
                    "title"
                ] = (
                    self._cipher
                    .decrypt(
                        row["title"]
                    )
                )
                persisted.append(
                    item
                )

        with self._lock:
            ephemeral = [
                dict(row)
                for row in (
                    self._ephemeral_conversations
                    .values()
                )
            ]

        ephemeral.sort(
            key=lambda row: (
                row["created_at"]
            ),
            reverse=True,
        )

        return (
            ephemeral
            + persisted
        )[:100]

    def create_conversation(
        self,
        title: str = (
            "New conversation"
        ),
        privacy_mode: (
            PrivacyMode | str
        ) = PrivacyMode.NORMAL,
    ) -> str:
        mode = _privacy_mode(
            privacy_mode
        )
        identity = (
            uuid.uuid4().hex
        )
        clean_title = (
            title[:120]
        )

        if (
            mode
            is PrivacyMode.EPHEMERAL
        ):
            with self._lock:
                self._ephemeral_conversations[
                    identity
                ] = {
                    "id": identity,
                    "title": clean_title,
                    "privacy_mode": (
                        mode.value
                    ),
                    "created_at": _now(),
                }
                self._ephemeral_messages[
                    identity
                ] = []

            return identity

        with self.connect() as db:
            db.execute(
                "INSERT INTO conversations"
                "(id,title,privacy_mode) "
                "VALUES(?,?,?)",
                (
                    identity,
                    self._cipher.encrypt(
                        clean_title
                    ),
                    mode.value,
                ),
            )

        return identity

    def rename_conversation(
        self,
        identity: str,
        title: str,
    ) -> dict:
        if (
            not isinstance(identity, str)
            or not identity
            or len(identity) > 128
        ):
            raise ValueError("Invalid conversation identifier")
        if not isinstance(title, str):
            raise ValueError("Conversation title must be text")
        clean_title = title.strip()
        if (
            not clean_title
            or len(clean_title) > 120
            or any(ord(char) < 32 for char in clean_title)
        ):
            raise ValueError(
                "Conversation title must contain 1–120 printable characters"
            )

        with self._lock:
            row = self._ephemeral_conversations.get(identity)
            if row is not None:
                row["title"] = clean_title
                return dict(row)

        with self.connect() as db:
            existing = db.execute(
                "SELECT id,privacy_mode,created_at "
                "FROM conversations WHERE id=?",
                (identity,),
            ).fetchone()
            if existing is None:
                raise KeyError("Unknown conversation")
            db.execute(
                "UPDATE conversations SET title=? WHERE id=?",
                (
                    self._cipher.encrypt(clean_title),
                    identity,
                ),
            )

        return {
            "id": identity,
            "title": clean_title,
            "privacy_mode": existing["privacy_mode"],
            "created_at": existing["created_at"],
        }

    def delete_conversation(
        self,
        identity: str,
    ) -> dict:
        if (
            not isinstance(identity, str)
            or not identity
            or len(identity) > 128
        ):
            raise ValueError("Invalid conversation identifier")

        with self._lock:
            ephemeral = self._ephemeral_conversations.get(identity)
            if ephemeral is not None:
                if any(
                    row.get("conversation_id") == identity
                    and row.get("status") in {"queued", "running", "stopping"}
                    for row in self._ephemeral_jobs.values()
                ):
                    raise ValueError(
                        "Cannot delete a conversation with an active response"
                    )
                self._ephemeral_conversations.pop(identity, None)
                self._ephemeral_messages.pop(identity, None)
                self._ephemeral_jobs = {
                    key: row
                    for key, row in self._ephemeral_jobs.items()
                    if row.get("conversation_id") != identity
                }
                self._ephemeral_tasks = {
                    key: row
                    for key, row in self._ephemeral_tasks.items()
                    if row.get("conversation_id") != identity
                }
                return {"id": identity, "deleted": True}

        with self.connect() as db:
            existing = db.execute(
                "SELECT id FROM conversations WHERE id=?",
                (identity,),
            ).fetchone()
            if existing is None:
                raise KeyError("Unknown conversation")
            active = db.execute(
                "SELECT 1 FROM jobs WHERE conversation_id=? "
                "AND status IN ('queued','running','stopping') LIMIT 1",
                (identity,),
            ).fetchone()
            if active is not None:
                raise ValueError(
                    "Cannot delete a conversation with an active response"
                )
            db.execute(
                "DELETE FROM authoritative_tasks WHERE conversation_id=?",
                (identity,),
            )
            db.execute(
                "DELETE FROM messages WHERE conversation_id=?",
                (identity,),
            )
            db.execute(
                "DELETE FROM jobs WHERE conversation_id=?",
                (identity,),
            )
            db.execute(
                "DELETE FROM conversations WHERE id=?",
                (identity,),
            )

        return {"id": identity, "deleted": True}

    def messages(
        self,
        identity: str,
        limit: int = 100,
    ) -> list[dict]:
        if (
            not isinstance(limit,int)
            or isinstance(limit,bool)
            or not 1<=limit<=1000
        ):
            raise ValueError(
                "Message history limit must be between 1 and 1000"
            )
        with self._lock:
            if (
                identity
                in self._ephemeral_conversations
            ):
                return [
                    {
                        **row,
                        "metadata": dict(
                            row["metadata"]
                        ),
                    }
                    for row in (
                        self._ephemeral_messages
                        .get(
                            identity,
                            [],
                        )[-limit:]
                    )
                ]

        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM ("
                "SELECT rowid,* FROM messages "
                "WHERE conversation_id=? "
                "ORDER BY rowid DESC LIMIT ?"
                ") ORDER BY rowid",
                (
                    identity,
                    limit,
                ),
            ).fetchall()

        result = []

        for row in rows:
            item = dict(
                row
            )
            item[
                "content"
            ] = (
                self._cipher
                .decrypt(
                    row["content"]
                )
            )
            metadata_text = (
                self._cipher
                .decrypt(
                    row["metadata"]
                )
            )
            item[
                "metadata"
            ] = json.loads(
                metadata_text
            )
            result.append(
                item
            )

        return result


    def relevant_messages(
        self,
        identity: str,
        query: str,
        *,
        limit: int = 6,
        exclude_ids=(),
        scan_limit: int = 500,
    ) -> list[dict]:
        """Retrieve older turns deterministically without trusting a summary."""

        if (
            not isinstance(query,str)
            or not query.strip()
        ):
            return []

        query_text=query.strip()
        if len(query_text)>RELEVANCE_QUERY_MAX_CHARS:
            half=RELEVANCE_QUERY_MAX_CHARS//2
            query_text=(
                query_text[:half]
                +"\n"
                +query_text[-half:]
            )
        if (
            not isinstance(limit,int)
            or isinstance(limit,bool)
            or not 0<=limit<=20
        ):
            raise ValueError(
                "Relevant-message limit must be between 0 and 20"
            )
        if limit==0:
            return []
        if (
            not isinstance(scan_limit,int)
            or isinstance(scan_limit,bool)
            or not 1<=scan_limit<=1000
        ):
            raise ValueError(
                "Relevant-message scan limit must be between 1 and 1000"
            )

        excluded=set(
            str(value)
            for value in exclude_ids
        )
        terms={
            token
            for token in re.findall(
                r"[A-Za-z0-9_+.#-]{3,}",
                query_text.lower(),
            )
            if token not in {
                "the","and","for","with","this",
                "that","from","what","when","where",
                "continue","resume","please",
            }
        }
        if not terms:
            return []

        phrase=query_text.lower()
        rows=self.messages(
            identity,
            limit=scan_limit,
        )
        scored=[]

        for position,row in enumerate(rows):
            if str(row.get("id","")) in excluded:
                continue
            content=str(
                row.get("content","")
            )
            lower=content.lower()
            tokens=set(
                re.findall(
                    r"[A-Za-z0-9_+.#-]{3,}",
                    lower,
                )
            )
            overlap=len(
                terms & tokens
            )
            phrase_hit=(
                len(phrase)>=8
                and phrase in lower
            )
            if overlap==0 and not phrase_hit:
                continue

            score=(
                overlap*10
                + (25 if phrase_hit else 0)
                + (
                    position
                    / max(1,len(rows))
                )
            )
            item={
                **row,
                "retrieval_score":round(
                    score,
                    6,
                ),
            }
            scored.append(
                (
                    -score,
                    -position,
                    item,
                )
            )

        scored.sort(
            key=lambda value:(
                value[0],
                value[1],
                str(
                    value[2].get(
                        "id",""
                    )
                ),
            )
        )
        return [
            value[2]
            for value in scored[:limit]
        ]

    def add_message(
        self,
        identity: str,
        role: str,
        content: str,
        metadata: dict | None = None,
    ) -> str:
        message_id = (
            uuid.uuid4().hex
        )

        with self._lock:
            conversation = (
                self._ephemeral_conversations
                .get(identity)
            )
            if conversation is not None:
                self._ephemeral_messages.setdefault(
                    identity,
                    [],
                ).append(
                    {
                        "id": message_id,
                        "conversation_id": (
                            identity
                        ),
                        "role": role,
                        "content": content,
                        "metadata": dict(
                            metadata
                            or {}
                        ),
                        "created_at": (
                            _now()
                        ),
                    }
                )

                if (
                    role == "user"
                    and conversation[
                        "title"
                    ]
                    == "New conversation"
                ):
                    conversation[
                        "title"
                    ] = (
                        content[:80]
                    )

                return message_id

        with self.connect() as db:
            conversation = db.execute(
                "SELECT title "
                "FROM conversations "
                "WHERE id=?",
                (identity,),
            ).fetchone()

            if conversation is None:
                raise KeyError(
                    "Unknown conversation"
                )

            db.execute(
                "INSERT INTO messages"
                "(id,conversation_id,role,"
                "content,metadata) "
                "VALUES(?,?,?,?,?)",
                (
                    message_id,
                    identity,
                    role,
                    self._cipher.encrypt(
                        content
                    ),
                    self._cipher.encrypt(
                        json.dumps(
                            metadata
                            or {}
                        )
                    ),
                ),
            )

            if (
                role == "user"
                and self._cipher.decrypt(
                    conversation[
                        "title"
                    ]
                )
                == "New conversation"
            ):
                db.execute(
                    "UPDATE conversations "
                    "SET title=? "
                    "WHERE id=?",
                    (
                        self._cipher
                        .encrypt(
                            content[:80]
                        ),
                        identity,
                    ),
                )

        return message_id


    def _task_from_row(
        self,
        row,
        *,
        encrypted: bool,
    ):
        from .task_state import (
            AuthoritativeTask,
            AuthoritativeTaskStatus,
        )

        item = dict(row)

        def text(field: str) -> str:
            value = item[field]
            return (
                self._cipher.decrypt(value)
                if encrypted
                else value
            )

        def sequence(field: str) -> tuple[str, ...]:
            value = (
                json.loads(text(field))
                if encrypted
                else item[field]
            )
            return tuple(value)

        def mapping(field: str) -> dict:
            value = (
                json.loads(text(field))
                if encrypted
                else item[field]
            )
            return dict(value)

        current_step = text("current_step")
        blocked_state = text("blocked_state")
        relevant_project = text("relevant_project")

        return AuthoritativeTask(
            id=item["id"],
            conversation_id=item["conversation_id"],
            kind=item["kind"],
            state=AuthoritativeTaskStatus(
                item["state"]
            ),
            objective=text("objective"),
            authoritative_specification=text(
                "authoritative_specification"
            ),
            specification_hash=item[
                "specification_hash"
            ],
            specification_version=int(
                item["specification_version"]
            ),
            immutable_requirements=sequence(
                "immutable_requirements"
            ),
            acceptance_criteria=sequence(
                "acceptance_criteria"
            ),
            decisions=sequence("decisions"),
            completed_steps=sequence(
                "completed_steps"
            ),
            current_step=(
                current_step or None
            ),
            remaining_steps=sequence(
                "remaining_steps"
            ),
            blocked_state=(
                blocked_state or None
            ),
            checkpoint=mapping("checkpoint"),
            relevant_project=(
                relevant_project or None
            ),
            provenance=mapping("provenance"),
            created_at=item["created_at"],
            updated_at=item["updated_at"],
        )

    def create_authoritative_task(
        self,
        conversation_id: str,
        objective: str,
        authoritative_specification: str,
        *,
        kind: str = "chat",
        immutable_requirements=(),
        acceptance_criteria=(),
        relevant_project: str | None = None,
        provenance: dict | None = None,
    ):
        from .task_state import (
            AuthoritativeTaskStatus,
            specification_hash,
        )

        if (
            not isinstance(objective, str)
            or not objective.strip()
            or len(objective) > 1000
        ):
            raise ValueError(
                "Task objective must contain 1–1000 characters"
            )
        if (
            not isinstance(
                authoritative_specification,
                str,
            )
            or not authoritative_specification.strip()
        ):
            raise ValueError(
                "Authoritative task specification must contain non-whitespace text"
            )
        if (
            not isinstance(kind, str)
            or not kind
            or len(kind) > 64
        ):
            raise ValueError("Invalid task kind")

        requirements = tuple(
            immutable_requirements
        )
        criteria = tuple(
            acceptance_criteria
        )
        if (
            len(requirements) > 64
            or len(criteria) > 64
            or any(
                not isinstance(value, str)
                or not value.strip()
                or len(value) > 2000
                for value in (
                    *requirements,
                    *criteria,
                )
            )
        ):
            raise ValueError(
                "Invalid authoritative task requirements"
            )
        if (
            relevant_project is not None
            and (
                not isinstance(
                    relevant_project,
                    str,
                )
                or len(relevant_project) > 500
            )
        ):
            raise ValueError(
                "Invalid task project reference"
            )
        if (
            provenance is not None
            and not isinstance(
                provenance,
                dict,
            )
        ):
            raise ValueError(
                "Task provenance must be an object"
            )

        existing = self.active_authoritative_task(
            conversation_id
        )
        if existing is not None:
            raise ValueError(
                "Conversation already has an active authoritative task"
            )

        identity = uuid.uuid4().hex
        now = _now()
        digest = specification_hash(
            authoritative_specification
        )
        raw = {
            "id": identity,
            "conversation_id": conversation_id,
            "kind": kind,
            "state": (
                AuthoritativeTaskStatus
                .ACTIVE
                .value
            ),
            "objective": objective.strip(),
            "authoritative_specification": (
                authoritative_specification
            ),
            "specification_hash": digest,
            "specification_version": 1,
            "immutable_requirements": requirements,
            "acceptance_criteria": criteria,
            "decisions": (),
            "completed_steps": (),
            "current_step": "",
            "remaining_steps": (),
            "blocked_state": "",
            "checkpoint": {},
            "relevant_project": (
                relevant_project or ""
            ),
            "provenance": dict(
                provenance or {}
            ),
            "created_at": now,
            "updated_at": now,
        }

        if (
            self.privacy_mode(
                conversation_id
            )
            is PrivacyMode.EPHEMERAL
        ):
            with self._lock:
                self._ephemeral_tasks[
                    identity
                ] = raw

            return self._task_from_row(
                raw,
                encrypted=False,
            )

        encrypted_text = {
            "objective": raw["objective"],
            "authoritative_specification": raw[
                "authoritative_specification"
            ],
            "immutable_requirements": json.dumps(
                list(requirements)
            ),
            "acceptance_criteria": json.dumps(
                list(criteria)
            ),
            "decisions": "[]",
            "completed_steps": "[]",
            "current_step": "",
            "remaining_steps": "[]",
            "blocked_state": "",
            "checkpoint": "{}",
            "relevant_project": (
                relevant_project or ""
            ),
            "provenance": json.dumps(
                raw["provenance"]
            ),
        }

        with self.connect() as db:
            conversation = db.execute(
                "SELECT id FROM conversations "
                "WHERE id=?",
                (conversation_id,),
            ).fetchone()
            if conversation is None:
                raise KeyError(
                    "Unknown conversation"
                )

            db.execute(
                "INSERT INTO authoritative_tasks("
                "id,conversation_id,kind,state,"
                "objective,authoritative_specification,"
                "specification_hash,specification_version,"
                "immutable_requirements,acceptance_criteria,"
                "decisions,completed_steps,current_step,"
                "remaining_steps,blocked_state,checkpoint,"
                "relevant_project,provenance,created_at,updated_at"
                ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    identity,
                    conversation_id,
                    kind,
                    raw["state"],
                    *(
                        self._cipher.encrypt(
                            encrypted_text[field]
                        )
                        for field in (
                            "objective",
                            "authoritative_specification",
                        )
                    ),
                    digest,
                    1,
                    *(
                        self._cipher.encrypt(
                            encrypted_text[field]
                        )
                        for field in (
                            "immutable_requirements",
                            "acceptance_criteria",
                            "decisions",
                            "completed_steps",
                            "current_step",
                            "remaining_steps",
                            "blocked_state",
                            "checkpoint",
                            "relevant_project",
                            "provenance",
                        )
                    ),
                    now,
                    now,
                ),
            )

        return self.authoritative_task(
            identity
        )

    def authoritative_task(
        self,
        identity: str,
    ):
        with self._lock:
            row = self._ephemeral_tasks.get(
                identity
            )
            if row is not None:
                return self._task_from_row(
                    row,
                    encrypted=False,
                )

        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM authoritative_tasks "
                "WHERE id=?",
                (identity,),
            ).fetchone()

        if row is None:
            raise KeyError(
                "Unknown authoritative task"
            )

        return self._task_from_row(
            row,
            encrypted=True,
        )

    def active_authoritative_task(
        self,
        conversation_id: str,
    ):
        with self._lock:
            rows = [
                row
                for row in self._ephemeral_tasks.values()
                if (
                    row["conversation_id"]
                    == conversation_id
                    and row["state"]
                    in {"active", "blocked"}
                )
            ]
            if rows:
                rows.sort(
                    key=lambda row: row[
                        "created_at"
                    ],
                    reverse=True,
                )
                return self._task_from_row(
                    rows[0],
                    encrypted=False,
                )

        if (
            conversation_id
            in self._ephemeral_conversations
        ):
            return None

        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM authoritative_tasks "
                "WHERE conversation_id=? "
                "AND state IN ('active','blocked') "
                "ORDER BY rowid DESC LIMIT 1",
                (conversation_id,),
            ).fetchone()

        return (
            None
            if row is None
            else self._task_from_row(
                row,
                encrypted=True,
            )
        )

    def require_authoritative_task(
        self,
        conversation_id: str,
    ):
        from .task_state import (
            AuthoritativeTaskMissingError,
        )

        task = self.active_authoritative_task(
            conversation_id
        )
        if task is None:
            raise (
                AuthoritativeTaskMissingError(
                    "Authoritative task state is unavailable; "
                    "Reverend will not reconstruct it from model intuition."
                )
            )
        return task

    def update_authoritative_task(
        self,
        identity: str,
        **values,
    ) -> None:
        from .task_state import (
            AuthoritativeTaskStatus,
        )

        allowed = {
            "state",
            "decisions",
            "completed_steps",
            "current_step",
            "remaining_steps",
            "blocked_state",
            "checkpoint",
            "relevant_project",
            "provenance",
        }
        if not values.keys() <= allowed:
            raise ValueError(
                "Authoritative specification and immutable requirements "
                "cannot be overwritten by progress updates"
            )

        if "state" in values:
            state = values["state"]
            state = (
                state
                if isinstance(
                    state,
                    AuthoritativeTaskStatus,
                )
                else AuthoritativeTaskStatus(
                    str(state)
                )
            )
            values["state"] = state.value

        sequence_fields = {
            "decisions",
            "completed_steps",
            "remaining_steps",
        }
        mapping_fields = {
            "checkpoint",
            "provenance",
        }
        text_fields = {
            "current_step",
            "blocked_state",
            "relevant_project",
        }

        for field in sequence_fields:
            if field in values:
                value = tuple(values[field])
                if (
                    len(value) > 128
                    or any(
                        not isinstance(item, str)
                        or len(item) > 4000
                        for item in value
                    )
                ):
                    raise ValueError(
                        "Invalid task progress sequence"
                    )
                values[field] = value

        for field in mapping_fields:
            if (
                field in values
                and not isinstance(
                    values[field],
                    dict,
                )
            ):
                raise ValueError(
                    "Task checkpoint/provenance must be objects"
                )

        for field in text_fields:
            if field in values:
                value = values[field]
                if value is None:
                    value = ""
                if (
                    not isinstance(value, str)
                    or len(value) > 4000
                ):
                    raise ValueError(
                        "Invalid task progress text"
                    )
                values[field] = value

        with self._lock:
            row = self._ephemeral_tasks.get(
                identity
            )
            if row is not None:
                for field, value in values.items():
                    row[field] = (
                        tuple(value)
                        if field in sequence_fields
                        else dict(value)
                        if field in mapping_fields
                        else value
                    )
                row["updated_at"] = _now()
                return

        persisted = {}
        if "state" in values:
            persisted["state"] = values[
                "state"
            ]

        for field in (
            sequence_fields
            | mapping_fields
            | text_fields
        ):
            if field not in values:
                continue
            value = values[field]
            if field in sequence_fields:
                value = json.dumps(
                    list(value)
                )
            elif field in mapping_fields:
                value = json.dumps(value)
            persisted[field] = (
                self._cipher.encrypt(
                    value
                )
            )

        if not persisted:
            return

        with self.connect() as db:
            cursor = db.execute(
                "UPDATE authoritative_tasks SET "
                + ",".join(
                    field + "=?"
                    for field in persisted
                )
                + ",updated_at=? WHERE id=?",
                (
                    *persisted.values(),
                    _now(),
                    identity,
                ),
            )
            if cursor.rowcount == 0:
                raise KeyError(
                    "Unknown authoritative task"
                )

    def new_job(
        self,
        kind: str,
        conversation_id: (
            str | None
        ) = None,
    ) -> str:
        identity = (
            uuid.uuid4().hex
        )

        if (
            conversation_id
            is not None
            and self.privacy_mode(
                conversation_id
            )
            is PrivacyMode.EPHEMERAL
        ):
            now = _now()

            with self._lock:
                self._ephemeral_jobs[
                    identity
                ] = {
                    "id": identity,
                    "kind": kind,
                    "status": "queued",
                    "conversation_id": (
                        conversation_id
                    ),
                    "task_id": None,
                    "response": "",
                    "details": {},
                    "created_at": now,
                    "updated_at": now,
                }

            return identity

        with self.connect() as db:
            db.execute(
                "INSERT INTO jobs"
                "(id,kind,status,"
                "conversation_id,response,details) "
                "VALUES(?,?,'queued',?,?,?)",
                (
                    identity,
                    kind,
                    conversation_id,
                    self._cipher.encrypt(
                        ""
                    ),
                    self._cipher.encrypt(
                        "{}"
                    ),
                ),
            )

        return identity

    def update_job(
        self,
        identity: str,
        **values,
    ) -> None:
        allowed = {
            "status",
            "task_id",
            "response",
            "details",
        }

        if not (
            values.keys()
            <= allowed
        ):
            raise ValueError(
                "Invalid job fields"
            )

        with self._lock:
            row = (
                self._ephemeral_jobs
                .get(identity)
            )
            if row is not None:
                for key, value in (
                    values.items()
                ):
                    row[key] = (
                        dict(value)
                        if (
                            key
                            == "details"
                            and isinstance(
                                value,
                                dict,
                            )
                        )
                        else value
                    )

                row[
                    "updated_at"
                ] = _now()
                return

        persisted = dict(
            values
        )

        if (
            "response"
            in persisted
        ):
            persisted[
                "response"
            ] = (
                self._cipher
                .encrypt(
                    str(
                        persisted[
                            "response"
                        ]
                    )
                )
            )

        if (
            "details"
            in persisted
        ):
            persisted[
                "details"
            ] = (
                self._cipher
                .encrypt(
                    json.dumps(
                        persisted[
                            "details"
                        ]
                    )
                )
            )

        with self.connect() as db:
            cursor = db.execute(
                "UPDATE jobs SET "
                + ",".join(
                    key + "=?"
                    for key
                    in persisted
                )
                + ",updated_at="
                "CURRENT_TIMESTAMP "
                "WHERE id=?",
                (
                    *persisted.values(),
                    identity,
                ),
            )

            if (
                cursor.rowcount
                == 0
            ):
                raise KeyError(
                    "Unknown job"
                )

    def job(
        self,
        identity: str,
    ) -> dict:
        with self._lock:
            row = (
                self._ephemeral_jobs
                .get(identity)
            )
            if row is not None:
                return {
                    **row,
                    "details": dict(
                        row["details"]
                    ),
                }

        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM jobs "
                "WHERE id=?",
                (identity,),
            ).fetchone()

        if row is None:
            raise KeyError(
                "Unknown job"
            )

        item = dict(
            row
        )
        item[
            "response"
        ] = (
            self._cipher
            .decrypt(
                row["response"]
            )
        )
        item[
            "details"
        ] = json.loads(
            self._cipher.decrypt(
                row["details"]
            )
        )

        return item

    def jobs(
        self,
    ) -> list[dict]:
        with self.connect() as db:
            persisted = [
                dict(row)
                for row in db.execute(
                    "SELECT id,kind,status,"
                    "conversation_id,task_id,"
                    "created_at "
                    "FROM jobs "
                    "ORDER BY rowid DESC "
                    "LIMIT 100"
                )
            ]

        with self._lock:
            ephemeral = [
                {
                    key: row[key]
                    for key in (
                        "id",
                        "kind",
                        "status",
                        "conversation_id",
                        "task_id",
                        "created_at",
                    )
                }
                for row in (
                    self._ephemeral_jobs
                    .values()
                )
            ]

        ephemeral.sort(
            key=lambda row: (
                row["created_at"]
            ),
            reverse=True,
        )

        return (
            ephemeral
            + persisted
        )[:100]

    def clear_ephemeral(
        self,
    ) -> None:
        with self._lock:
            self._ephemeral_tasks.clear()
            self._ephemeral_jobs.clear()
            self._ephemeral_messages.clear()
            self._ephemeral_conversations.clear()
