from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace

import pytest

from reverend.codeintel import (
    compile_task_context,
)
from reverend.development import (
    TaskState,
    create_task,
    create_task_worktree,
    database,
    register_project,
    transition_task,
)
from reverend.development.repair import (
    RepairDiagnostics,
    RepairRequest,
)
from reverend.development.repair_model import (
    RepairModelResponseError,
    _build_snapshots,
    build_repair_prompt,
    generate_repair_proposals,
    parse_repair_response,
)
from reverend.runtime import (
    ModelRole,
)


def git(repo, *args):
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
    repo = tmp_path / "repo"
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
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    path = repo / "value.py"

    path.write_text(
        (
            "def value():\n"
            "    return 1\n"
        ),
        encoding="utf-8",
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
        "Initial",
    )

    return repo


def setup_task(tmp_path):
    repo = make_repo(tmp_path)

    context_manager = database(
        tmp_path / "development.db"
    )

    connection = (
        context_manager.__enter__()
    )

    project = register_project(
        connection,
        repo,
    )

    task = create_task(
        connection,
        project.id,
        title="Repair value function",
        request=(
            "Make value return two."
        ),
    )

    task = transition_task(
        connection,
        task.id,
        TaskState.PREPARING,
    )

    worktree = create_task_worktree(
        connection,
        task.id,
        root=tmp_path / "worktrees",
    )

    task = transition_task(
        connection,
        task.id,
        TaskState.RUNNING,
    )

    return (
        context_manager,
        connection,
        task,
        worktree,
    )


def request():
    return RepairRequest(
        task_id="task",
        attempt=1,
        diagnostics=(
            RepairDiagnostics(
                attempt=1,
                text="AssertionError: expected 2",
                failed_checks=("pytest",),
            )
        ),
    )


class FakeScheduler:
    def __init__(
        self,
        response,
    ):
        self.response = response
        self.calls = []

    def generate(
        self,
        role,
        prompt,
        **kwargs,
    ):
        self.calls.append(
            (
                role,
                prompt,
                kwargs,
            )
        )

        return SimpleNamespace(
            role=role,
            model="qwen3-coder:30b",
            digest="digest",
            context=16384,
            think=False,
            exclusive_memory=True,
            elapsed_seconds=1.0,
            response={
                "response": (
                    self.response
                ),
                "prompt_eval_count": 100,
                "eval_count": 50,
            },
        )


def snapshots_for(
    connection,
    task,
):
    context = compile_task_context(
        connection,
        task.id,
        max_chars=14000,
    )

    return _build_snapshots(
        task.worktree_path,
        context,
        max_snapshots=4,
        max_chars=10000,
    )


def test_valid_response_parses(
    tmp_path,
):
    (
        manager,
        connection,
        task,
        _,
    ) = setup_task(tmp_path)

    try:
        snapshots = snapshots_for(
            connection,
            task,
        )

        snapshot = next(
            item
            for item in snapshots
            if item.path == "value.py"
        )

        text = json.dumps(
            {
                "summary": (
                    "Return two."
                ),
                "edits": [
                    {
                        "path": "value.py",
                        "action": "replace",
                        "expected_sha256": (
                            snapshot.sha256
                        ),
                        "content": (
                            "def value():\n"
                            "    return 2\n"
                        ),
                    }
                ],
                "needs_more_context": False,
            }
        )

        _, proposals, more = (
            parse_repair_response(
                text,
                snapshots,
            )
        )

        assert len(proposals) == 1
        assert not more

    finally:
        manager.__exit__(
            None,
            None,
            None,
        )


def test_path_outside_snapshots_rejected(
    tmp_path,
):
    (
        manager,
        connection,
        task,
        _,
    ) = setup_task(tmp_path)

    try:
        snapshots = snapshots_for(
            connection,
            task,
        )

        text = json.dumps(
            {
                "summary": "Bad path",
                "edits": [
                    {
                        "path": "other.py",
                        "action": "create",
                        "expected_sha256": None,
                        "content": "bad\n",
                    }
                ],
                "needs_more_context": False,
            }
        )

        with pytest.raises(
            RepairModelResponseError
        ):
            parse_repair_response(
                text,
                snapshots,
            )

    finally:
        manager.__exit__(
            None,
            None,
            None,
        )


def test_wrong_sha_rejected(
    tmp_path,
):
    (
        manager,
        connection,
        task,
        _,
    ) = setup_task(tmp_path)

    try:
        snapshots = snapshots_for(
            connection,
            task,
        )

        text = json.dumps(
            {
                "summary": "Wrong hash",
                "edits": [
                    {
                        "path": "value.py",
                        "action": "replace",
                        "expected_sha256": "0" * 64,
                        "content": "x = 1\n",
                    }
                ],
                "needs_more_context": False,
            }
        )

        with pytest.raises(
            RepairModelResponseError
        ):
            parse_repair_response(
                text,
                snapshots,
            )

    finally:
        manager.__exit__(
            None,
            None,
            None,
        )


def test_prompt_contains_diagnostics_and_hash(
    tmp_path,
):
    (
        manager,
        connection,
        task,
        _,
    ) = setup_task(tmp_path)

    try:
        context = compile_task_context(
            connection,
            task.id,
            max_chars=14000,
        )

        snapshots = _build_snapshots(
            task.worktree_path,
            context,
            max_snapshots=4,
            max_chars=10000,
        )

        prompt = build_repair_prompt(
            context=context,
            request=request(),
            snapshots=snapshots,
        )

        snapshot = next(
            item
            for item in snapshots
            if item.path == "value.py"
        )

        assert (
            "AssertionError: expected 2"
            in prompt
        )

        assert (
            snapshot.sha256
            in prompt
        )

    finally:
        manager.__exit__(
            None,
            None,
            None,
        )


def test_generate_uses_strong_code(
    tmp_path,
):
    (
        manager,
        connection,
        task,
        _,
    ) = setup_task(tmp_path)

    try:
        snapshots = snapshots_for(
            connection,
            task,
        )

        snapshot = next(
            item
            for item in snapshots
            if item.path == "value.py"
        )

        scheduler = FakeScheduler(
            json.dumps(
                {
                    "summary": "Fix value",
                    "edits": [
                        {
                            "path": "value.py",
                            "action": "replace",
                            "expected_sha256": (
                                snapshot.sha256
                            ),
                            "content": (
                                "def value():\n"
                                "    return 2\n"
                            ),
                        }
                    ],
                    "needs_more_context": False,
                }
            )
        )

        result = generate_repair_proposals(
            connection,
            task.id,
            scheduler,
            request(),
        )

        role, _, kwargs = (
            scheduler.calls[0]
        )

        assert (
            role
            == ModelRole.STRONG_CODE
        )

        assert (
            kwargs["context"]
            == 16384
        )

        assert (
            kwargs[
                "exclusive_memory"
            ]
            is True
        )

        assert len(
            result.proposals
        ) == 1

    finally:
        manager.__exit__(
            None,
            None,
            None,
        )


def test_model_run_is_persisted(
    tmp_path,
):
    (
        manager,
        connection,
        task,
        _,
    ) = setup_task(tmp_path)

    try:
        snapshots = snapshots_for(
            connection,
            task,
        )

        snapshot = next(
            item
            for item in snapshots
            if item.path == "value.py"
        )

        scheduler = FakeScheduler(
            json.dumps(
                {
                    "summary": "Fix",
                    "edits": [
                        {
                            "path": "value.py",
                            "action": "replace",
                            "expected_sha256": (
                                snapshot.sha256
                            ),
                            "content": (
                                "def value():\n"
                                "    return 2\n"
                            ),
                        }
                    ],
                    "needs_more_context": False,
                }
            )
        )

        result = generate_repair_proposals(
            connection,
            task.id,
            scheduler,
            request(),
        )

        row = connection.execute(
            """
            SELECT
                role,
                model,
                success
            FROM model_runs
            WHERE id = ?
            """,
            (
                result.model_run_id,
            ),
        ).fetchone()

        assert row is not None
        assert (
            row["role"]
            == "strong_code"
        )
        assert row["success"] == 1

    finally:
        manager.__exit__(
            None,
            None,
            None,
        )


def test_extract_json_recovers_literal_controls_inside_content():
    from reverend.development.repair_model import _extract_json

    raw = '''{
  "summary": "add subtraction",
  "edits": [
    {
      "path": "calculator.py",
      "action": "replace",
      "expected_sha256": "abc",
      "content": "def add(a, b):
\treturn a + b

def subtract(a, b):
\treturn a - b
"
    }
  ],
  "needs_more_context": false
}'''

    value = _extract_json(raw)

    assert value["summary"] == "add subtraction"

    assert value["edits"][0]["content"] == (
        "def add(a, b):\n"
        "\treturn a + b\n"
        "\n"
        "def subtract(a, b):\n"
        "\treturn a - b\n"
    )


def test_extract_json_still_rejects_structural_corruption():
    import pytest

    from reverend.development.repair_model import (
        RepairModelResponseError,
        _extract_json,
    )

    raw = '''{
      "summary": "broken",
      "edits": [,
      "needs_more_context": false
    }'''

    with pytest.raises(
        RepairModelResponseError,
        match="not valid JSON",
    ):
        _extract_json(raw)



def test_repair_prompt_includes_structured_failure_delta(tmp_path):
    manager, connection, task, _ = setup_task(tmp_path)
    try:
        from reverend.codeintel import compile_task_context
        from reverend.development.repair import RepairDiagnostics, RepairRequest

        context = compile_task_context(connection, task.id, max_chars=8000)
        snapshots = _build_snapshots(
            task.worktree_path,
            context,
            max_snapshots=4,
            max_chars=8000,
        )
        request = RepairRequest(
            task_id=task.id,
            attempt=1,
            diagnostics=RepairDiagnostics(
                attempt=1,
                text="pytest failed",
                failed_checks=("pytest",),
                failure_kind="test_assertion",
                failing_tests=("tests/test_value.py::test_value",),
                changed_paths=("value.py",),
                acceptance_criteria=("AC-01: value returns two",),
            ),
        )
        prompt = build_repair_prompt(
            context=context,
            request=request,
            snapshots=snapshots,
        )

        assert "STRUCTURED FAILURE DELTA" in prompt
        assert '"failure_kind": "test_assertion"' in prompt
        assert "tests/test_value.py::test_value" in prompt
        assert "AC-01: value returns two" in prompt
    finally:
        manager.__exit__(None, None, None)
