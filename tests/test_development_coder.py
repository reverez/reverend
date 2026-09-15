from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace

import pytest

from reverend.development import (
    TaskState,
    create_task,
    create_task_worktree,
    database,
    register_project,
    transition_task,
)
from reverend.development.coder import (
    CoderPlanConsistencyError,
    CoderResponseError,
    build_coder_prompt,
    generate_coding_plan,
    parse_coding_plan,
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

    files = {
        "pyproject.toml": (
            "[project]\n"
            'name = "example"\n'
        ),
        "src/example/tasks.py": (
            "def transition_task(task, target):\n"
            "    task.state = target\n"
            "    return task\n"
        ),
        "src/example/unrelated.py": (
            "def unrelated():\n"
            "    return 'opaque'\n"
        ),
        "tests/test_tasks.py": (
            "def test_transition():\n"
            "    assert True\n"
        ),
    }

    for relative, content in files.items():
        path = repo / relative
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        path.write_text(
            content,
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
        "Initial commit",
    )

    return repo


def setup_task(tmp_path):
    repo = make_repo(
        tmp_path
    )

    context = database(
        tmp_path
        / "development.db"
    )

    connection = (
        context.__enter__()
    )

    project = register_project(
        connection,
        repo,
    )

    task = create_task(
        connection,
        project.id,
        title="Fix task transitions",
        request=(
            "Validate task state transitions "
            "and update tests."
        ),
        acceptance_criteria=(
            "Invalid transitions are rejected."
        ),
    )

    task = transition_task(
        connection,
        task.id,
        TaskState.PREPARING,
    )

    create_task_worktree(
        connection,
        task.id,
        root=tmp_path / "worktrees",
    )

    return (
        context,
        connection,
        task,
    )


def valid_response():
    return {
        "summary": (
            "Add explicit transition validation."
        ),
        "files": [
            {
                "path": (
                    "src/example/tasks.py"
                ),
                "action": "modify",
                "reason": (
                    "Contains task transition logic."
                ),
            },
            {
                "path": (
                    "tests/test_tasks.py"
                ),
                "action": "modify",
                "reason": (
                    "Add invalid-transition coverage."
                ),
            },
        ],
        "implementation_steps": [
            "Define allowed transitions.",
            "Reject invalid transitions.",
        ],
        "verification": [
            "python -m pytest -q"
        ],
        "risks": [
            "Existing callers may rely on permissive behavior."
        ],
        "needs_more_context": False,
    }


class FakeScheduler:
    def __init__(
        self,
        response_text,
    ):
        self.response_text = (
            response_text
        )
        self.responses = (
            list(response_text)
            if isinstance(response_text, (list, tuple))
            else [response_text]
        )
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
            digest="test-digest",
            context=16384,
            think=False,
            exclusive_memory=True,
            elapsed_seconds=1.25,
            response={
                "response": (
                    self.responses[
                        min(
                            len(self.calls) - 1,
                            len(self.responses) - 1,
                        )
                    ]
                ),
                "prompt_eval_count": 1000,
                "eval_count": 200,
            },
        )


def test_parse_valid_plan():
    plan = parse_coding_plan(
        json.dumps(
            valid_response()
        )
    )

    assert (
        plan.summary
        == "Add explicit transition validation."
    )

    assert (
        plan.files[0].path
        == "src/example/tasks.py"
    )

    assert (
        plan.files[0].action
        == "modify"
    )

    assert not (
        plan.needs_more_context
    )


def test_fenced_json_is_accepted():
    text = (
        "```json\n"
        + json.dumps(
            valid_response()
        )
        + "\n```"
    )

    plan = parse_coding_plan(
        text
    )

    assert len(
        plan.files
    ) == 2


def test_absolute_path_is_rejected():
    value = valid_response()

    value["files"][0][
        "path"
    ] = "/etc/passwd"

    with pytest.raises(
        CoderResponseError
    ):
        parse_coding_plan(
            json.dumps(value)
        )


def test_parent_escape_is_rejected():
    value = valid_response()

    value["files"][0][
        "path"
    ] = "../outside.py"

    with pytest.raises(
        CoderResponseError
    ):
        parse_coding_plan(
            json.dumps(value)
        )


def test_unknown_action_is_rejected():
    value = valid_response()

    value["files"][0][
        "action"
    ] = "execute"

    with pytest.raises(
        CoderResponseError
    ):
        parse_coding_plan(
            json.dumps(value)
        )


def test_generate_plan_uses_strong_code(
    tmp_path,
):
    (
        context,
        connection,
        task,
    ) = setup_task(tmp_path)

    try:
        scheduler = FakeScheduler(
            json.dumps(
                valid_response()
            )
        )

        result = generate_coding_plan(
            connection,
            task.id,
            scheduler,
        )

        assert (
            scheduler.calls[0][0]
            == ModelRole.STRONG_CODE
        )

        kwargs = (
            scheduler.calls[0][2]
        )

        assert (
            kwargs["context"]
            == 16384
        )

        assert (
            kwargs["think"]
            is False
        )

        assert (
            kwargs[
                "exclusive_memory"
            ]
            is True
        )

        assert (
            result.model
            == "qwen3-coder:30b"
        )

    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_model_run_is_persisted(
    tmp_path,
):
    (
        context,
        connection,
        task,
    ) = setup_task(tmp_path)

    try:
        scheduler = FakeScheduler(
            json.dumps(
                valid_response()
            )
        )

        result = generate_coding_plan(
            connection,
            task.id,
            scheduler,
        )

        row = connection.execute(
            """
            SELECT *
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
        assert (
            row["model"]
            == "qwen3-coder:30b"
        )
        assert row["success"] == 1
        assert (
            row["prompt_tokens"]
            == 1000
        )
        assert (
            row["generated_tokens"]
            == 200
        )

    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_invalid_response_is_recorded_as_failure(
    tmp_path,
):
    (
        context,
        connection,
        task,
    ) = setup_task(tmp_path)

    try:
        scheduler = FakeScheduler(
            "not json"
        )

        with pytest.raises(
            CoderResponseError
        ):
            generate_coding_plan(
                connection,
                task.id,
                scheduler,
            )

        row = connection.execute(
            """
            SELECT success
            FROM model_runs
            WHERE task_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (
                task.id,
            ),
        ).fetchone()

        assert row is not None
        assert row["success"] == 0

    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_prompt_contains_authoritative_repository_paths(
    tmp_path,
):
    (
        context,
        connection,
        task,
    ) = setup_task(tmp_path)

    try:
        scheduler = FakeScheduler(
            json.dumps(
                valid_response()
            )
        )

        generate_coding_plan(
            connection,
            task.id,
            scheduler,
        )

        prompt = (
            scheduler.calls[0][1]
        )

        assert (
            "AUTHORITATIVE EXISTING FILE PATHS"
            in prompt
        )

        assert (
            "src/example/tasks.py"
            in prompt
        )

    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_hallucinated_modify_path_is_rejected(
    tmp_path,
):
    (
        context,
        connection,
        task,
    ) = setup_task(tmp_path)

    try:
        value = valid_response()

        value["files"][0][
            "path"
        ] = "src/example/invented.py"

        scheduler = FakeScheduler(
            json.dumps(value)
        )

        with pytest.raises(
            CoderResponseError
        ):
            generate_coding_plan(
                connection,
                task.id,
                scheduler,
            )

        row = connection.execute(
            """
            SELECT success
            FROM model_runs
            WHERE task_id = ?
            ORDER BY rowid DESC
            LIMIT 1
            """,
            (
                task.id,
            ),
        ).fetchone()

        assert row is not None
        assert row["success"] == 0

    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_existing_file_outside_authoritative_context_is_rejected(
    tmp_path,
):
    (
        context,
        connection,
        task,
    ) = setup_task(tmp_path)

    try:
        value = valid_response()
        value["files"][0][
            "path"
        ] = "src/example/unrelated.py"

        scheduler = FakeScheduler(
            json.dumps(value)
        )

        with pytest.raises(
            CoderResponseError,
            match=(
                "outside the authoritative context"
            ),
        ):
            generate_coding_plan(
                connection,
                task.id,
                scheduler,
            )

        row = connection.execute(
            """
            SELECT success
            FROM model_runs
            WHERE task_id = ?
            ORDER BY rowid DESC
            LIMIT 1
            """,
            (
                task.id,
            ),
        ).fetchone()

        assert row is not None
        assert row["success"] == 0

    finally:
        context.__exit__(
            None,
            None,
            None,
        )



def test_inconsistent_plan_allowlist_is_corrected_once(
    tmp_path,
):
    (
        context,
        connection,
        task,
    ) = setup_task(tmp_path)

    try:
        first = valid_response()
        first["files"] = []
        first["implementation_steps"] = [
            "Create calculator.py with arithmetic functions.",
            "Implement unit tests in test_calculator.py.",
        ]

        corrected = valid_response()
        corrected["files"] = [
            {
                "path": "calculator.py",
                "action": "create",
                "reason": "Add calculator implementation.",
            },
            {
                "path": "test_calculator.py",
                "action": "create",
                "reason": "Add calculator tests.",
            },
        ]
        corrected["implementation_steps"] = list(
            first["implementation_steps"]
        )

        scheduler = FakeScheduler(
            [
                json.dumps(first),
                json.dumps(corrected),
            ]
        )

        result = generate_coding_plan(
            connection,
            task.id,
            scheduler,
        )

        assert len(scheduler.calls) == 2
        assert {
            planned.path
            for planned in result.plan.files
        } == {
            "calculator.py",
            "test_calculator.py",
        }
        assert (
            "HOST PLAN CONTRACT FAILURE"
            in scheduler.calls[1][1]
        )
        assert (
            "calculator.py"
            in scheduler.calls[1][1]
        )
        assert (
            "test_calculator.py"
            in scheduler.calls[1][1]
        )

        rows = connection.execute(
            """
            SELECT success, metadata_json
            FROM model_runs
            WHERE task_id = ?
            ORDER BY rowid
            """,
            (task.id,),
        ).fetchall()

        assert [row["success"] for row in rows] == [0, 1]
        assert (
            "structured files allowlist"
            in json.loads(rows[0]["metadata_json"])[
                "parse_error"
            ]
        )
    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_inconsistent_plan_retry_remains_bounded(
    tmp_path,
):
    (
        context,
        connection,
        task,
    ) = setup_task(tmp_path)

    try:
        inconsistent = valid_response()
        inconsistent["files"] = [
            {
                "path": "pyproject.toml",
                "action": "modify",
                "reason": "Update project metadata.",
            }
        ]
        inconsistent["implementation_steps"] = [
            "Create calculator.py with arithmetic functions.",
        ]

        scheduler = FakeScheduler(
            [
                json.dumps(inconsistent),
                json.dumps(inconsistent),
            ]
        )

        with pytest.raises(
            CoderPlanConsistencyError,
            match="calculator.py",
        ):
            generate_coding_plan(
                connection,
                task.id,
                scheduler,
            )

        assert len(scheduler.calls) == 2

        rows = connection.execute(
            """
            SELECT success
            FROM model_runs
            WHERE task_id = ?
            ORDER BY rowid
            """,
            (task.id,),
        ).fetchall()

        assert [row["success"] for row in rows] == [0, 0]
    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_corrective_feedback_is_bounded_and_marked_as_host_diagnostic(
    tmp_path,
):
    (
        context,
        connection,
        task,
    ) = setup_task(tmp_path)

    try:
        scheduler = FakeScheduler(
            json.dumps(
                valid_response()
            )
        )

        feedback=(
            "Fresh verifier: implementation omitted the requested UI. "
            * 500
        )

        generate_coding_plan(
            connection,
            task.id,
            scheduler,
            corrective_feedback=feedback,
        )

        prompt=scheduler.calls[0][1]

        assert "HOST CORRECTIVE FEEDBACK" in prompt
        assert "Fresh verifier: implementation omitted" in prompt
        assert len(prompt) < 40000

    finally:
        context.__exit__(
            None,
            None,
            None,
        )


def test_planner_prompt_contains_localization_and_acceptance_contracts(tmp_path):
    context, connection, task = setup_task(tmp_path)
    try:
        scheduler = FakeScheduler(json.dumps(valid_response()))
        result = generate_coding_plan(connection, task.id, scheduler)

        prompt = scheduler.calls[0][1]
        assert "DETERMINISTIC LOCALIZATION CONTRACT" in prompt
        assert "ACCEPTANCE CONTRACT" in prompt
        assert "AC-01" in prompt
        assert "src/example/tasks.py" in prompt
        assert result.localization is not None
        assert result.acceptance_contract is not None
        assert result.acceptance_contract.criterion_ids == ("AC-01",)
    finally:
        context.__exit__(None, None, None)
