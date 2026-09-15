from __future__ import annotations

from pathlib import Path

from reverend.workstation.service import Workstation


def test_workstation_defaults_knowledge_to_state_root(tmp_path):
    workstation = Workstation.__new__(Workstation)

    root = tmp_path / "state"

    # Mirror constructor path policy without starting runtime services.
    workstation.root = root
    workstation.knowledge_db_path = root / "platform.db"

    assert workstation.knowledge_db_path == (
        root / "platform.db"
    )


def test_workstation_supports_separate_knowledge_database(tmp_path):
    state_root = tmp_path / "benchmark-state"
    knowledge_db = tmp_path / "canonical" / "platform.db"

    workstation = Workstation.__new__(Workstation)
    workstation.root = state_root
    workstation.knowledge_db_path = knowledge_db

    assert workstation.root != (
        workstation.knowledge_db_path.parent
    )
    assert workstation.knowledge_db_path == knowledge_db
