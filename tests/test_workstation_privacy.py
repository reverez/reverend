from __future__ import annotations

import sqlite3
import stat

import pytest

from reverend.workstation.crypto import (
    ENCRYPTED_PREFIX,
    StateEncryptionError,
)
from reverend.workstation.store import PrivacyMode, WorkspaceStore


def test_existing_workspace_migrates_to_normal_privacy(tmp_path):
    path = tmp_path / "workstation.db"

    with sqlite3.connect(path) as db:
        db.execute(
            "CREATE TABLE conversations("
            "id TEXT PRIMARY KEY,"
            "title TEXT NOT NULL,"
            "created_at TEXT DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
        db.execute(
            "INSERT INTO conversations(id,title) VALUES(?,?)",
            ("legacy", "Legacy conversation"),
        )

    store = WorkspaceStore(path)

    assert store.privacy_mode("legacy") is PrivacyMode.NORMAL

    with sqlite3.connect(path) as db:
        columns = {
            row[1]
            for row in db.execute("PRAGMA table_info(conversations)")
        }
        row = db.execute(
            "SELECT privacy_mode FROM conversations WHERE id='legacy'"
        ).fetchone()

    assert "privacy_mode" in columns
    assert row == ("normal",)


def test_private_conversation_persists_with_explicit_mode(tmp_path):
    path = tmp_path / "workstation.db"
    store = WorkspaceStore(path)

    identity = store.create_conversation(
        privacy_mode=PrivacyMode.PRIVATE
    )
    store.add_message(
        identity,
        "user",
        "private message",
        {"marker": 1},
    )
    job = store.new_job("chat", identity)
    store.update_job(
        job,
        status="complete",
        response="private answer",
        details={"ok": True},
    )

    reopened = WorkspaceStore(path)

    assert reopened.privacy_mode(identity) is PrivacyMode.PRIVATE
    assert reopened.messages(identity)[0]["content"] == "private message"
    assert reopened.messages(identity)[0]["metadata"] == {"marker": 1}
    assert reopened.job(job)["status"] == "complete"
    assert reopened.job(job)["details"] == {"ok": True}


def test_ephemeral_conversation_and_job_never_enter_sqlite(tmp_path):
    path = tmp_path / "workstation.db"
    store = WorkspaceStore(path)

    identity = store.create_conversation(
        privacy_mode=PrivacyMode.EPHEMERAL
    )
    message = store.add_message(
        identity,
        "user",
        "temporary",
        {"temporary": True},
    )
    job = store.new_job("chat", identity)
    store.update_job(
        job,
        status="running",
        response="partial",
        details={"phase": "generate"},
    )

    assert store.privacy_mode(identity) is PrivacyMode.EPHEMERAL
    assert store.messages(identity)[0]["id"] == message
    assert store.job(job)["status"] == "running"
    assert any(
        row["id"] == identity
        for row in store.conversations()
    )
    assert any(
        row["id"] == job
        for row in store.jobs()
    )

    with sqlite3.connect(path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM conversations WHERE id=?",
            (identity,),
        ).fetchone()[0] == 0
        assert db.execute(
            "SELECT COUNT(*) FROM messages WHERE conversation_id=?",
            (identity,),
        ).fetchone()[0] == 0
        assert db.execute(
            "SELECT COUNT(*) FROM jobs WHERE id=?",
            (job,),
        ).fetchone()[0] == 0


def test_ephemeral_state_disappears_on_reopen_or_clear(tmp_path):
    path = tmp_path / "workstation.db"
    store = WorkspaceStore(path)

    identity = store.create_conversation(
        privacy_mode="ephemeral"
    )
    store.add_message(identity, "user", "temporary")

    reopened = WorkspaceStore(path)

    with pytest.raises(KeyError, match="Unknown conversation"):
        reopened.privacy_mode(identity)

    assert all(
        row["id"] != identity
        for row in reopened.conversations()
    )

    store.clear_ephemeral()

    with pytest.raises(KeyError, match="Unknown conversation"):
        store.privacy_mode(identity)


def test_invalid_privacy_mode_is_rejected(tmp_path):
    store = WorkspaceStore(tmp_path / "workstation.db")

    with pytest.raises(ValueError, match="Unknown privacy mode"):
        store.create_conversation(
            privacy_mode="stealth"
        )


def test_workspace_state_files_are_owner_only(tmp_path):
    path = tmp_path / "state" / "workstation.db"
    store = WorkspaceStore(path)
    identity = store.create_conversation()
    store.add_message(identity, "user", "private by default")

    assert stat.S_IMODE(
        path.parent.stat().st_mode
    ) == 0o700
    assert stat.S_IMODE(
        path.stat().st_mode
    ) == 0o600


def test_durable_workspace_payloads_are_encrypted_at_rest(
    tmp_path,
):
    path = tmp_path / "workstation.db"
    store = WorkspaceStore(
        path
    )

    identity = store.create_conversation(
        title="Sensitive title",
        privacy_mode="private",
    )
    store.add_message(
        identity,
        "user",
        "Sensitive message body",
        {
            "source": "Sensitive metadata"
        },
    )
    job = store.new_job(
        "chat",
        identity,
    )
    store.update_job(
        job,
        response="Sensitive response",
        details={
            "detail": "Sensitive job details"
        },
    )

    with sqlite3.connect(path) as db:
        title = db.execute(
            "SELECT title FROM conversations WHERE id=?",
            (identity,),
        ).fetchone()[0]
        content, metadata = db.execute(
            "SELECT content,metadata FROM messages "
            "WHERE conversation_id=?",
            (identity,),
        ).fetchone()
        response, details = db.execute(
            "SELECT response,details FROM jobs WHERE id=?",
            (job,),
        ).fetchone()

    protected = (
        title,
        content,
        metadata,
        response,
        details,
    )

    assert all(
        value.startswith(
            ENCRYPTED_PREFIX
        )
        for value in protected
    )

    serialized = "\n".join(
        protected
    )
    for plaintext in (
        "Sensitive title",
        "Sensitive message body",
        "Sensitive metadata",
        "Sensitive response",
        "Sensitive job details",
    ):
        assert plaintext not in serialized

    assert (
        store.conversations()[0]["title"]
        == "Sensitive title"
    )
    assert (
        store.messages(identity)[0]["content"]
        == "Sensitive message body"
    )
    assert (
        store.messages(identity)[0]["metadata"]
        == {
            "source": "Sensitive metadata"
        }
    )
    assert (
        store.job(job)["response"]
        == "Sensitive response"
    )
    assert (
        store.job(job)["details"]
        == {
            "detail": "Sensitive job details"
        }
    )


def test_plaintext_legacy_rows_are_migrated_to_ciphertext(
    tmp_path,
):
    path = tmp_path / "workstation.db"

    with sqlite3.connect(path) as db:
        db.executescript(
            """
            CREATE TABLE conversations(
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE messages(
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT NOT NULL DEFAULT '{}',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE jobs(
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
            """
        )
        db.execute(
            "INSERT INTO conversations(id,title) VALUES(?,?)",
            ("legacy", "Legacy secret title"),
        )
        db.execute(
            "INSERT INTO messages("
            "id,conversation_id,role,content,metadata"
            ") VALUES(?,?,?,?,?)",
            (
                "message",
                "legacy",
                "user",
                "Legacy secret content",
                '{"secret":"metadata"}',
            ),
        )
        db.execute(
            "INSERT INTO jobs("
            "id,kind,status,conversation_id,response,details"
            ") VALUES(?,?,?,?,?,?)",
            (
                "job",
                "chat",
                "complete",
                "legacy",
                "Legacy secret response",
                '{"secret":"details"}',
            ),
        )

    store = WorkspaceStore(
        path
    )

    assert (
        store.messages("legacy")[0]["content"]
        == "Legacy secret content"
    )
    assert (
        store.job("job")["response"]
        == "Legacy secret response"
    )

    with sqlite3.connect(path) as db:
        rows = [
            db.execute(
                "SELECT title FROM conversations WHERE id='legacy'"
            ).fetchone()[0],
            *db.execute(
                "SELECT content,metadata FROM messages "
                "WHERE id='message'"
            ).fetchone(),
            *db.execute(
                "SELECT response,details FROM jobs WHERE id='job'"
            ).fetchone(),
        ]

    assert all(
        value.startswith(
            ENCRYPTED_PREFIX
        )
        for value in rows
    )


def test_state_key_is_owner_only_and_wrong_key_fails_closed(
    tmp_path,
):
    path = tmp_path / "workstation.db"
    key_path = tmp_path / "primary.key"

    store = WorkspaceStore(
        path,
        key_path=key_path,
    )
    identity = (
        store.create_conversation(
            title="Encrypted title"
        )
    )

    assert stat.S_IMODE(
        key_path.stat().st_mode
    ) == 0o600
    assert stat.S_IMODE(
        key_path.parent.stat().st_mode
    ) == 0o700

    other = WorkspaceStore(
        tmp_path / "other.db",
        key_path=(
            tmp_path / "other.key"
        ),
    )
    other.create_conversation(
        title="Different key"
    )

    with pytest.raises(
        StateEncryptionError,
        match="authentication failed",
    ):
        WorkspaceStore(
            path,
            key_path=(
                tmp_path / "other.key"
            ),
        )

    assert (
        store.conversations()[0]["id"]
        == identity
    )


def test_tampered_persistent_ciphertext_is_rejected(
    tmp_path,
):
    path = tmp_path / "workstation.db"
    key_path = tmp_path / "state.key"
    store = WorkspaceStore(
        path,
        key_path=key_path,
    )
    identity = store.create_conversation(
        title="Protected"
    )

    with sqlite3.connect(path) as db:
        token = db.execute(
            "SELECT title FROM conversations WHERE id=?",
            (identity,),
        ).fetchone()[0]
        replacement = (
            token[:-1]
            + (
                "A"
                if token[-1] != "A"
                else "B"
            )
        )
        db.execute(
            "UPDATE conversations SET title=? WHERE id=?",
            (
                replacement,
                identity,
            ),
        )

    with pytest.raises(
        StateEncryptionError,
        match="authentication failed",
    ):
        WorkspaceStore(
            path,
            key_path=key_path,
        )



def test_authoritative_task_state_is_encrypted_and_recovers(
    tmp_path,
):
    from reverend.workstation.task_state import (
        specification_hash,
    )

    path=tmp_path/'workstation.db'
    store=WorkspaceStore(path)
    conversation=store.create_conversation(
        privacy_mode='private'
    )
    task=store.create_authoritative_task(
        conversation,
        'Exercise 8',
        'Exercise 8 — preserve this exact specification.',
        immutable_requirements=(
            'Do not invent missing requirements.',
        ),
        acceptance_criteria=(
            'Original specification remains authoritative.',
        ),
        relevant_project='project-1',
        provenance={'source':'user_message'},
    )

    assert task.specification_version==1
    assert task.specification_hash==specification_hash(
        task.authoritative_specification
    )

    with sqlite3.connect(path) as db:
        row=db.execute(
            'SELECT objective,authoritative_specification,'
            'immutable_requirements,acceptance_criteria,'
            'relevant_project,provenance '
            'FROM authoritative_tasks WHERE id=?',
            (task.id,),
        ).fetchone()

    assert all(
        value.startswith(ENCRYPTED_PREFIX)
        for value in row
    )
    assert 'Exercise 8' not in '\n'.join(row)

    reopened=WorkspaceStore(path)
    recovered=reopened.require_authoritative_task(
        conversation
    )
    assert recovered.id==task.id
    assert recovered.authoritative_specification==(
        'Exercise 8 — preserve this exact specification.'
    )
    assert recovered.immutable_requirements==(
        'Do not invent missing requirements.',
    )
    assert recovered.acceptance_criteria==(
        'Original specification remains authoritative.',
    )
    assert recovered.relevant_project=='project-1'
    assert recovered.provenance=={
        'source':'user_message'
    }


def test_ephemeral_authoritative_task_never_enters_sqlite(
    tmp_path,
):
    path=tmp_path/'workstation.db'
    store=WorkspaceStore(path)
    conversation=store.create_conversation(
        privacy_mode='ephemeral'
    )
    task=store.create_authoritative_task(
        conversation,
        'Temporary task',
        'Temporary authoritative specification',
    )

    assert (
        store.require_authoritative_task(
            conversation
        ).id
        == task.id
    )

    with sqlite3.connect(path) as db:
        assert db.execute(
            'SELECT COUNT(*) FROM authoritative_tasks'
        ).fetchone()[0]==0

    reopened=WorkspaceStore(path)
    with pytest.raises(
        KeyError,
        match='Unknown conversation',
    ):
        reopened.privacy_mode(conversation)


def test_progress_updates_cannot_overwrite_task_authority(
    tmp_path,
):
    path=tmp_path/'workstation.db'
    store=WorkspaceStore(path)
    conversation=store.create_conversation()
    task=store.create_authoritative_task(
        conversation,
        'Immutable task',
        'Do exactly the original task.',
    )

    with pytest.raises(
        ValueError,
        match='cannot be overwritten',
    ):
        store.update_authoritative_task(
            task.id,
            authoritative_specification='Invented replacement',
        )

    store.update_authoritative_task(
        task.id,
        current_step='verify',
        completed_steps=('plan',),
        checkpoint={'segment':1},
    )
    updated=store.authoritative_task(task.id)
    assert updated.authoritative_specification==(
        'Do exactly the original task.'
    )
    assert updated.current_step=='verify'
    assert updated.completed_steps==('plan',)
    assert updated.checkpoint=={'segment':1}


def test_conversation_rename_is_encrypted_and_delete_cleans_state(tmp_path):
    path=tmp_path/"workstation.db"
    store=WorkspaceStore(path)
    identity=store.create_conversation(title="Original")
    store.add_message(identity,"user","hello")
    job=store.new_job("chat",identity)
    store.update_job(job,status="complete",response="done")
    task=store.create_authoritative_task(identity,"Task","Keep this task.")

    renamed=store.rename_conversation(identity,"Renamed chat")
    assert renamed["title"]=="Renamed chat"
    assert store.conversations()[0]["title"]=="Renamed chat"

    with sqlite3.connect(path) as db:
        raw=db.execute("SELECT title FROM conversations WHERE id=?",(identity,)).fetchone()[0]
        assert raw.startswith(ENCRYPTED_PREFIX)
        assert "Renamed chat" not in raw

    deleted=store.delete_conversation(identity)
    assert deleted=={"id":identity,"deleted":True}
    assert all(row["id"]!=identity for row in store.conversations())
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM conversations WHERE id=?",(identity,)).fetchone()[0]==0
        assert db.execute("SELECT COUNT(*) FROM messages WHERE conversation_id=?",(identity,)).fetchone()[0]==0
        assert db.execute("SELECT COUNT(*) FROM jobs WHERE conversation_id=?",(identity,)).fetchone()[0]==0
        assert db.execute("SELECT COUNT(*) FROM authoritative_tasks WHERE id=?",(task.id,)).fetchone()[0]==0


def test_ephemeral_conversation_can_be_renamed_and_deleted(tmp_path):
    store=WorkspaceStore(tmp_path/"workstation.db")
    identity=store.create_conversation(title="Temp",privacy_mode="ephemeral")
    store.add_message(identity,"user","temporary")
    store.rename_conversation(identity,"Renamed temporary")
    assert store.conversations()[0]["title"]=="Renamed temporary"
    assert store.delete_conversation(identity)["deleted"] is True
    with pytest.raises(KeyError,match="Unknown conversation"):
        store.privacy_mode(identity)


def test_active_conversation_cannot_be_deleted(tmp_path):
    store=WorkspaceStore(tmp_path/"workstation.db")
    identity=store.create_conversation()
    store.new_job("chat",identity)
    with pytest.raises(ValueError,match="active response"):
        store.delete_conversation(identity)
