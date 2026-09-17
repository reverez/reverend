from __future__ import annotations

import json
from pathlib import Path


def test_project_opencode_config_pins_reverend_coder30():
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / ".opencode" / "opencode.json").read_text(encoding="utf-8"))

    # OpenCode 1.18.x uses the V1 provider schema: provider/npm/options.
    ollama = config["provider"]["ollama"]
    assert ollama["npm"] == "@ai-sdk/openai-compatible"
    assert ollama["options"]["baseURL"] == "http://127.0.0.1:11434/v1"

    model = ollama["models"]["reverend-coder30"]
    assert model["name"] == "Reverend Coder 30B"
