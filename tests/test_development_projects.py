from __future__ import annotations

import subprocess

import pytest

from reverend.development import (
    NotGitRepositoryError,
    ProjectRegistryError,
    TrustMode,
    database,
    get_project,
    get_project_by_path,
    inspect_repository,
    list_projects,
    project_id_for_path,
    register_project,
)


def git(
    repo,
    *args,
):
    return subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            *args,
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )


def make_repo(tmp_path):
    repo = tmp_path / "example-repo"
    repo.mkdir()

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
        text=True,
    )

    (repo / "README.md").write_text(
        "# Example\n",
        encoding="utf-8",
    )

    git(
        repo,
        "add",
        "README.md",
    )

    git(
        repo,
        "-c",
        "user.name=Reverend Test",
        "-c",
        "user.email=reverend@example.invalid",
        "commit",
        "-m",
        "Initial commit",
    )

    return repo


def test_inspect_repository(
    tmp_path,
):
    repo = make_repo(
        tmp_path
    )

    snapshot = inspect_repository(
        repo
    )

    assert snapshot.root == repo
    assert snapshot.real_root == (
        repo.resolve()
    )
    assert snapshot.name == (
        "example-repo"
    )
    assert snapshot.current_branch == (
        "main"
    )
    assert snapshot.default_branch == (
        "main"
    )
    assert len(
        snapshot.head_commit
    ) == 40
    assert snapshot.is_dirty is False


def test_inspect_repository_detects_dirty_state(
    tmp_path,
):
    repo = make_repo(
        tmp_path
    )

    (repo / "dirty.txt").write_text(
        "dirty\n",
        encoding="utf-8",
    )

    snapshot = inspect_repository(
        repo
    )

    assert snapshot.is_dirty is True


def test_non_git_directory_is_rejected(
    tmp_path,
):
    directory = (
        tmp_path
        / "not-a-repository"
    )
    directory.mkdir()

    with pytest.raises(
        NotGitRepositoryError
    ):
        inspect_repository(
            directory
        )


def test_project_id_is_stable(
    tmp_path,
):
    repo = make_repo(
        tmp_path
    )

    first = project_id_for_path(
        repo
    )

    second = project_id_for_path(
        repo.resolve()
    )

    assert first == second


def test_register_project_is_idempotent(
    tmp_path,
):
    repo = make_repo(
        tmp_path
    )

    db_path = (
        tmp_path
        / "development.db"
    )

    with database(
        db_path
    ) as connection:
        first = register_project(
            connection,
            repo,
        )

        second = register_project(
            connection,
            repo,
        )

        assert first.id == second.id

        projects = list_projects(
            connection
        )

        assert len(projects) == 1
        assert projects[0].name == (
            "example-repo"
        )
        assert (
            projects[0].default_branch
            == "main"
        )


def test_project_can_be_read_by_id_and_path(
    tmp_path,
):
    repo = make_repo(
        tmp_path
    )

    with database(
        tmp_path
        / "development.db"
    ) as connection:
        registered = register_project(
            connection,
            repo,
            name="Example",
            trust_mode=(
                TrustMode.UNTRUSTED_REPO
            ),
        )

        by_id = get_project(
            connection,
            registered.id,
        )

        by_path = get_project_by_path(
            connection,
            repo,
        )

        assert by_id == registered
        assert by_path == registered
        assert (
            registered.trust_mode
            == TrustMode.UNTRUSTED_REPO
        )


def test_reregistration_cannot_change_project_trust(
    tmp_path,
):
    repo = make_repo(
        tmp_path
    )

    with database(
        tmp_path
        / "development.db"
    ) as connection:
        registered = register_project(
            connection,
            repo,
            trust_mode=(
                TrustMode.UNTRUSTED_REPO
            ),
        )

        with pytest.raises(
            ProjectRegistryError,
            match="trust mode cannot change",
        ):
            register_project(
                connection,
                repo,
                trust_mode=(
                    TrustMode.TRUSTED_REPO
                ),
            )

        unchanged = get_project(
            connection,
            registered.id,
        )

        assert (
            unchanged.trust_mode
            is TrustMode.UNTRUSTED_REPO
        )


def test_reregistration_cannot_silently_downgrade_trust(
    tmp_path,
):
    repo = make_repo(
        tmp_path
    )

    with database(
        tmp_path
        / "development.db"
    ) as connection:
        registered = register_project(
            connection,
            repo,
            trust_mode=(
                TrustMode.TRUSTED_REPO
            ),
        )

        with pytest.raises(
            ProjectRegistryError,
            match="trust mode cannot change",
        ):
            register_project(
                connection,
                repo,
                trust_mode=(
                    TrustMode.UNTRUSTED_REPO
                ),
            )

        unchanged = get_project(
            connection,
            registered.id,
        )

        assert (
            unchanged.trust_mode
            is TrustMode.TRUSTED_REPO
        )
