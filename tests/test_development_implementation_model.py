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
    CodingPlan,
    PlannedFile,
)
from reverend.development.implementation_model import (
    ImplementationResponseError,
    _planned_snapshots,
    build_implementation_prompt,
    generate_implementation_proposals,
    parse_implementation_response,
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
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    (
        repo
        / "value.py"
    ).write_text(
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

    manager = database(
        tmp_path / "development.db"
    )

    connection = (
        manager.__enter__()
    )

    project = register_project(
        connection,
        repo,
    )

    task = create_task(
        connection,
        project.id,
        title="Return two",
        request=(
            "Change value() so it returns 2."
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
        manager,
        connection,
        task,
        worktree,
    )


def plan(
    *,
    create=False,
):
    files = [
        PlannedFile(
            path="value.py",
            action="modify",
            reason="Contains value().",
        )
    ]

    if create:
        files.append(
            PlannedFile(
                path="new_module.py",
                action="create",
                reason="New helper module.",
            )
        )

    return CodingPlan(
        summary="Implement requested value change.",
        files=tuple(files),
        implementation_steps=(
            "Update the approved files.",
        ),
        verification=(
            "Run deterministic tests.",
        ),
        risks=(),
        needs_more_context=False,
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
            digest="implementation-digest",
            context=16384,
            think=False,
            exclusive_memory=True,
            elapsed_seconds=1.25,
            response={
                "response": (
                    self.response
                ),
                "prompt_eval_count": 500,
                "eval_count": 120,
            },
        )


def response_for(
    snapshot,
):
    return json.dumps(
        {
            "summary": (
                "Change value() to return two."
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


def test_planned_snapshots_include_existing_and_create(
    tmp_path,
):
    (
        manager,
        _,
        task,
        _,
    ) = setup_task(tmp_path)

    try:
        snapshots = (
            _planned_snapshots(
                task.worktree_path,
                plan(create=True),
            )
        )

        by_path = {
            item.path: item
            for item in snapshots
        }

        assert (
            by_path["value.py"]
            .exists
        )

        assert (
            by_path["value.py"]
            .sha256
        )

        assert not (
            by_path["new_module.py"]
            .exists
        )

    finally:
        manager.__exit__(
            None,
            None,
            None,
        )


def test_valid_response_matches_plan(
    tmp_path,
):
    (
        manager,
        _,
        task,
        _,
    ) = setup_task(tmp_path)

    try:
        coding_plan = plan()

        snapshots = (
            _planned_snapshots(
                task.worktree_path,
                coding_plan,
            )
        )

        summary, proposals, more = (
            parse_implementation_response(
                response_for(
                    snapshots[0]
                ),
                coding_plan,
                snapshots,
            )
        )

        assert summary
        assert not more
        assert len(proposals) == 1
        assert (
            proposals[0].action
            == "replace"
        )

    finally:
        manager.__exit__(
            None,
            None,
            None,
        )


def test_plan_action_mismatch_rejected(
    tmp_path,
):
    (
        manager,
        _,
        task,
        _,
    ) = setup_task(tmp_path)

    try:
        coding_plan = plan()

        snapshots = (
            _planned_snapshots(
                task.worktree_path,
                coding_plan,
            )
        )

        value = json.loads(
            response_for(
                snapshots[0]
            )
        )

        value["edits"][0][
            "action"
        ] = "delete"

        value["edits"][0][
            "content"
        ] = None

        with pytest.raises(
            ImplementationResponseError
        ):
            parse_implementation_response(
                json.dumps(value),
                coding_plan,
                snapshots,
            )

    finally:
        manager.__exit__(
            None,
            None,
            None,
        )


def test_prompt_contains_plan_and_hash(
    tmp_path,
):
    (
        manager,
        connection,
        task,
        _,
    ) = setup_task(tmp_path)

    try:
        coding_plan = plan()

        from reverend.codeintel import (
            compile_task_context,
        )

        context = compile_task_context(
            connection,
            task.id,
            max_chars=14000,
        )

        snapshots = (
            _planned_snapshots(
                task.worktree_path,
                coding_plan,
            )
        )

        prompt = (
            build_implementation_prompt(
                context=context,
                plan=coding_plan,
                snapshots=snapshots,
            )
        )

        assert (
            "APPROVED CODING PLAN"
            in prompt
        )

        assert (
            snapshots[0].sha256
            in prompt
        )

        assert (
            "value.py"
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
        coding_plan = plan()

        snapshots = (
            _planned_snapshots(
                task.worktree_path,
                coding_plan,
            )
        )

        scheduler = FakeScheduler(
            response_for(
                snapshots[0]
            )
        )

        result = (
            generate_implementation_proposals(
                connection,
                task.id,
                scheduler,
                coding_plan,
            )
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

        assert kwargs["response_format"]=="json"

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
        coding_plan = plan()

        snapshots = (
            _planned_snapshots(
                task.worktree_path,
                coding_plan,
            )
        )

        scheduler = FakeScheduler(
            response_for(
                snapshots[0]
            )
        )

        result = (
            generate_implementation_proposals(
                connection,
                task.id,
                scheduler,
                coding_plan,
            )
        )

        row = connection.execute(
            """
            SELECT
                role,
                model,
                success,
                metadata_json
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
            "initial_implementation"
            in row["metadata_json"]
        )

    finally:
        manager.__exit__(
            None,
            None,
            None,
        )


def test_modify_missing_file_is_rejected(
    tmp_path,
):
    (
        manager,
        _,
        task,
        _,
    ) = setup_task(tmp_path)

    try:
        bad_plan = CodingPlan(
            summary="Modify missing file.",
            files=(
                PlannedFile(
                    path="missing.py",
                    action="modify",
                    reason="Pretend it exists.",
                ),
            ),
            implementation_steps=("Modify it.",),
            verification=("Run tests.",),
            risks=(),
            needs_more_context=False,
        )

        from reverend.development.implementation_model import (
            ImplementationContextError,
        )

        with pytest.raises(
            ImplementationContextError
        ):
            _planned_snapshots(
                task.worktree_path,
                bad_plan,
            )

    finally:
        manager.__exit__(
            None,
            None,
            None,
        )


def test_create_existing_file_is_rejected(
    tmp_path,
):
    (
        manager,
        _,
        task,
        _,
    ) = setup_task(tmp_path)

    try:
        bad_plan = CodingPlan(
            summary="Create existing file.",
            files=(
                PlannedFile(
                    path="value.py",
                    action="create",
                    reason="Incorrectly treat it as new.",
                ),
            ),
            implementation_steps=("Create it.",),
            verification=("Run tests.",),
            risks=(),
            needs_more_context=False,
        )

        from reverend.development.implementation_model import (
            ImplementationContextError,
        )

        with pytest.raises(
            ImplementationContextError
        ):
            _planned_snapshots(
                task.worktree_path,
                bad_plan,
            )

    finally:
        manager.__exit__(
            None,
            None,
            None,
        )



def test_generate_prompt_includes_localization_and_acceptance_evidence(tmp_path):
    manager, connection, task, _ = setup_task(tmp_path)
    try:
        coding_plan = plan()
        snapshots = _planned_snapshots(task.worktree_path, coding_plan)
        scheduler = FakeScheduler(response_for(snapshots[0]))

        generate_implementation_proposals(
            connection,
            task.id,
            scheduler,
            coding_plan,
        )

        prompt_text = scheduler.calls[0][1]
        assert "DETERMINISTIC LOCALIZATION EVIDENCE" in prompt_text
        assert "ACCEPTANCE CONTRACT" in prompt_text
        assert "value.py" in prompt_text
        assert "excluded_paths" in prompt_text
    finally:
        manager.__exit__(None, None, None)


def test_implementation_prompt_includes_bounded_host_validation_feedback(tmp_path):
    manager, connection, task, _ = setup_task(tmp_path)
    try:
        coding_plan=plan()
        from reverend.codeintel import compile_task_context
        context=compile_task_context(
            connection,
            task.id,
            max_chars=14000,
        )
        snapshots=_planned_snapshots(
            task.worktree_path,
            coding_plan,
        )
        prompt=build_implementation_prompt(
            context=context,
            plan=coding_plan,
            snapshots=snapshots,
            corrective_feedback=(
                "Applied edits failed Git whitespace validation: "
                "value.py:9: trailing whitespace."
            ),
        )
        assert "HOST EDIT VALIDATION FEEDBACK" in prompt
        assert "value.py:9: trailing whitespace" in prompt
        assert "same approved plan" not in prompt or "approved plan" in prompt
    finally:
        manager.__exit__(None,None,None)


def test_implementation_prompt_explicitly_forbids_diff_check_whitespace(tmp_path):
    manager, connection, task, _ = setup_task(tmp_path)
    try:
        coding_plan=plan()
        from reverend.codeintel import compile_task_context
        context=compile_task_context(
            connection,
            task.id,
            max_chars=14000,
        )
        snapshots=_planned_snapshots(
            task.worktree_path,
            coding_plan,
        )
        prompt=build_implementation_prompt(
            context=context,
            plan=coding_plan,
            snapshots=snapshots,
        )
        assert "must pass git diff --check" in prompt
        assert "Never put spaces or tabs at the end of any line" in prompt
        assert "blank line must be truly empty" in prompt
    finally:
        manager.__exit__(None,None,None)


def test_retry_feedback_reiterates_zero_length_blank_lines(tmp_path):
    manager, connection, task, _ = setup_task(tmp_path)
    try:
        coding_plan=plan()
        from reverend.codeintel import compile_task_context
        context=compile_task_context(
            connection,
            task.id,
            max_chars=14000,
        )
        snapshots=_planned_snapshots(
            task.worktree_path,
            coding_plan,
        )
        prompt=build_implementation_prompt(
            context=context,
            plan=coding_plan,
            snapshots=snapshots,
            corrective_feedback=(
                "Applied edits failed Git whitespace validation: "
                "value.py:9: trailing whitespace."
            ),
        )
        assert "every blank line is zero-length" in prompt
        assert "no trailing spaces/tabs" in prompt
    finally:
        manager.__exit__(None,None,None)
