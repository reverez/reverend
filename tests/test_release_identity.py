from __future__ import annotations

from pathlib import Path
import tomllib

import pytest

import reverend
from reverend import cli


ROOT = Path(__file__).resolve().parents[1]


def test_release_version_is_single_package_authority():
    assert reverend.__version__ == "0.4.0"

    data = tomllib.loads(
        (ROOT / "pyproject.toml").read_text(
            encoding="utf-8"
        )
    )

    project = data["project"]
    dynamic = set(
        project.get(
            "dynamic",
            [],
        )
    )

    assert "version" in dynamic
    assert "version" not in project
    assert (
        data[
            "tool"
        ][
            "setuptools"
        ][
            "dynamic"
        ][
            "version"
        ][
            "attr"
        ]
        == "reverend.__version__"
    )


def test_cli_version_matches_package(
    capsys,
):
    with pytest.raises(
        SystemExit
    ) as exc:
        cli.main(
            [
                "--version",
            ]
        )

    assert exc.value.code == 0

    output = (
        capsys.readouterr()
        .out.strip()
    )

    assert output == (
        "reverend "
        + reverend.__version__
    )


def test_release_environment_example_is_portable():
    text = (
        ROOT
        / ".env.example"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "192.168."
        not in text
    )
    assert (
        "/home/you/"
        in text
    )
    assert (
        "QDRANT_API_KEY="
        not in text
    )
    assert (
        "OLLAMA_HOST="
        in text
    )
    assert (
        "AI_DATA_ROOT="
        in text
    )
