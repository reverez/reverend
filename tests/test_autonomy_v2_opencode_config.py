from __future__ import annotations

import json
from pathlib import Path


def test_project_opencode_config_pins_reverend_coder30():
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / ".opencode" / "opencode.json").read_text(encoding="utf-8"))

    ollama = config["providers"]["ollama"]
    assert ollama["settings"]["baseURL"] == "http://127.0.0.1:11434/v1"

    model = ollama["models"]["reverend-coder30"]
    assert model["modelID"] == "reverend-coder30:latest"
    assert model["capabilities"]["tools"] is True
    assert model["capabilities"]["input"] == ["text"]
    assert model["capabilities"]["output"] == ["text"]
    assert model["limit"] == {"context": 16384, "output": 4096}
