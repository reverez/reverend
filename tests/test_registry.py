import json
from pathlib import Path

from reverend.registry import import_legacy_state, stats


def test_legacy_state_import(tmp_path: Path):
    state = {
        "sources": {
            "/tmp/a.md": {
                "hash": "aaa",
                "chunks": 3,
                "corpus": "obsidian",
                "trust_class": "TRUSTED_PERSONAL",
            },
            "/tmp/b.md": {
                "hash": "bbb",
                "chunks": 5,
                "corpus": "synthetic",
                "trust_class": "TRUSTED_PRIMARY",
            },
        }
    }

    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(state), encoding="utf-8")

    db_path = tmp_path / "platform.db"

    imported = import_legacy_state(
        state_path=state_path,
        db_path=db_path,
    )

    assert imported["documents"] == 2
    assert imported["declared_chunks"] == 8
    assert imported["materialized_chunks"] == 0
    assert imported["by_corpus"]["obsidian"] == 1
    assert imported["by_corpus"]["synthetic"] == 1

    current = stats(db_path)
    assert current["documents"] == 2
