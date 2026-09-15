from __future__ import annotations

import subprocess

from reverend.codeintel.retrieval import (
    search_code,
    tokenize_query,
)


def git(repo, *args):
    return subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            *args,
        ],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def make_repo(tmp_path):
    repo = tmp_path / "repo"

    (repo / "apps" / "cli").mkdir(
        parents=True
    )

    (repo / "apps" / "gui").mkdir(
        parents=True
    )

    (repo / "docs").mkdir()

    (
        repo
        / "apps"
        / "cli"
        / "main.cpp"
    ).write_text(
        (
            "#include <iostream>\n\n"
            "int main(int argc, char** argv) {\n"
            "    return 0;\n"
            "}\n"
        ),
        encoding="utf-8",
    )

    (
        repo
        / "apps"
        / "gui"
        / "main.cpp"
    ).write_text(
        (
            "// Application graphical interface.\n"
            "// Version information and user interface.\n"
            "int main() { return 0; }\n"
        ),
        encoding="utf-8",
    )

    (
        repo
        / "docs"
        / "guide.md"
    ).write_text(
        (
            "# Application Guide\n\n"
            "Version option interface command application existing "
            "tests version option interface command application.\n"
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            "git",
            "init",
            "-b",
            "main",
            str(repo),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    git(repo, "add", ".")

    git(
        repo,
        "-c",
        "user.name=Reverend Test",
        "-c",
        "user.email=reverend@example.invalid",
        "commit",
        "-m",
        "Fixture",
    )

    return repo


def test_command_line_expands_to_cli():
    tokens = tokenize_query(
        "Add a command-line interface version option."
    )

    assert "cli" in tokens


def test_cli_path_outranks_generic_gui_and_docs(
    tmp_path,
):
    repo = make_repo(tmp_path)

    result = search_code(
        repo,
        (
            "Add a command-line interface version option "
            "and preserve existing application behaviour."
        ),
        limit=10,
    )

    assert result.paths

    assert (
        result.paths[0]
        == "apps/cli/main.cpp"
    )

    cli_hit = result.hits[0]

    assert any(
        reason.startswith(
            "path-intent:cli"
        )
        for reason in cli_hit.reasons
    )
