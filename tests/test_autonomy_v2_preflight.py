from __future__ import annotations

import subprocess

from reverend.autonomy_v2.preflight import ModelPreflight


def test_planner_preflight_prompt_is_explicitly_read_only(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    preflight = ModelPreflight(
        tmp_path,
        opencode_model="fake/model",
        ollama_model="fake-model",
    )

    prompt = preflight._planner_prompt()

    assert "READ-ONLY planner canary" in prompt
    assert "DO NOT create" in prompt
    assert "canary file intentionally does not exist yet" in prompt
    assert "Do not perform the plan" in prompt
    assert ModelPreflight.CANARY_NAME in prompt
