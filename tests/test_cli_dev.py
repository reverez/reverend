from __future__ import annotations

from reverend import cli
from reverend.development import (
    command as dev_command,
)


def test_dev_implement_dispatch(
    tmp_path,
    monkeypatch,
):
    captured = {}

    def fake(
        project_path,
        request,
        *,
        acceptance=None,
        max_repairs=2,
        json_output=False,
    ):
        captured.update(
            {
                "project": project_path,
                "request": request,
                "acceptance": acceptance,
                "max_repairs": max_repairs,
                "json": json_output,
            }
        )

        return 0

    monkeypatch.setattr(
        dev_command,
        "command_dev_implement",
        fake,
    )

    result = cli.main(
        [
            "dev",
            "implement",
            "--project",
            str(tmp_path),
            "--request",
            "Implement feature.",
            "--acceptance",
            "Tests pass.",
            "--max-repairs",
            "3",
            "--json",
        ]
    )

    assert result == 0

    assert (
        captured["request"]
        == "Implement feature."
    )

    assert (
        captured["acceptance"]
        == "Tests pass."
    )

    assert (
        captured["max_repairs"]
        == 3
    )

    assert (
        captured["json"]
        is True
    )


def test_legacy_code_alias_uses_verified_development_engine(
    tmp_path,
    monkeypatch,
    capsys,
):
    captured = {}

    def fake(
        project_path,
        request,
        *,
        acceptance=None,
        max_repairs=2,
        json_output=False,
    ):
        captured.update(
            project=project_path,
            request=request,
            max_repairs=max_repairs,
            json=json_output,
        )
        return 0

    monkeypatch.setattr(
        dev_command,
        "command_dev_implement",
        fake,
    )

    result = cli.main(
        [
            "code",
            str(tmp_path),
            "Fix the parser.",
        ]
    )

    assert result == 0
    assert captured["project"] == tmp_path
    assert captured["request"] == "Fix the parser."
    assert captured["max_repairs"] == 2
    assert captured["json"] is False
    assert "compatibility alias" in capsys.readouterr().err
