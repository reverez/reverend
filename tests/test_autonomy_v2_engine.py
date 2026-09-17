from __future__ import annotations

import subprocess
from pathlib import Path

from reverend.autonomy_v2.controller import AutonomousController, IssueSpec
from reverend.autonomy_v2.engine import EngineConfig, IssueEngine
from reverend.autonomy_v2.execution import AgentResult
from reverend.autonomy_v2.state import IssuePhase


def _git(cwd: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=True,
    )
    return completed.stdout.strip()


def _repository(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "Documentation" / "Design").mkdir(parents=True)
    (root / "src").mkdir()
    (root / "tests").mkdir()
    (root / ".gitignore").write_text(
        ".autonomy/\n.worktrees/\n__pycache__/\n.pytest_cache/\n",
        encoding="utf-8",
    )
    (root / "Documentation" / "Design" / "D0.md").write_text(
        "# Contracts\nVALUE must become 2.\n",
        encoding="utf-8",
    )
    (root / "src" / "feature.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "tests" / "test_feature.py").write_text(
        "from pathlib import Path\n\n"
        "def test_feature_changed():\n"
        "    assert 'VALUE = 2' in Path('src/feature.py').read_text()\n",
        encoding="utf-8",
    )
    _git(root, "init")
    _git(root, "add", ".")
    _git(
        root,
        "-c",
        "user.name=Reverend Test",
        "-c",
        "user.email=reverend@example.invalid",
        "commit",
        "-m",
        "initial",
    )
    return root


class _FakeRunner:
    def __init__(self, *, make_edit: bool = True) -> None:
        self.make_edit = make_edit
        self.calls: list[str] = []

    def run(self, invocation):
        self.calls.append(invocation.kind)
        invocation.log_path.parent.mkdir(parents=True, exist_ok=True)
        if invocation.kind == "plan":
            output = (
                "AUTONOMY_PLAN_JSON_BEGIN\n"
                '{"files_to_modify":["src/feature.py"],'
                '"files_to_create":[],'
                '"tests_to_add_or_modify":["tests/test_feature.py"],'
                '"acceptance_checks":["pytest"],"risks":[]}\n'
                "AUTONOMY_PLAN_JSON_END\n"
            )
        elif invocation.kind == "implement":
            if self.make_edit:
                (invocation.worktree / "src" / "feature.py").write_text(
                    "VALUE = 2\n", encoding="utf-8"
                )
            output = "implementation complete\n"
        elif invocation.kind.startswith("repair-"):
            output = "repair complete\n"
        elif invocation.kind == "review":
            output = (
                "AUTONOMY_REVIEW_JSON_BEGIN\n"
                '{"verdict":"PASS","defects":[]}\n'
                "AUTONOMY_REVIEW_JSON_END\n"
            )
        else:
            raise AssertionError(invocation.kind)
        invocation.log_path.write_text(output, encoding="utf-8")
        return AgentResult(
            command=("fake",),
            returncode=0,
            timed_out=False,
            output=output,
            log_path=invocation.log_path,
        )


def _prepared(root: Path):
    controller = AutonomousController(root)
    issue = IssueSpec(number=66, milestone="C0", title="Common IDs")
    run_id = controller.initialize_run(queue=[issue], run_id="run-engine-test")
    prepared = controller.prepare_issue(
        run_id=run_id,
        issue=issue,
        requirements=["VALUE must become 2"],
        design_sources=["Documentation/Design/D0.md"],
        candidate_source_files=["src/feature.py"],
        candidate_tests=["tests/test_feature.py"],
        acceptance=["tests pass"],
    )
    return controller, prepared


def test_issue_engine_accepts_only_after_diff_tests_and_review(tmp_path):
    root = _repository(tmp_path)
    controller, prepared = _prepared(root)
    runner = _FakeRunner()
    engine = IssueEngine(
        controller,
        config=EngineConfig(model="fake/model", max_repairs=1),
        runner=runner,
    )

    outcome = engine.run(prepared)
    assert outcome.accepted is True
    assert outcome.commit is not None
    state = controller.store.get_issue(prepared.run_id, 66)
    assert state.phase is IssuePhase.ACCEPTED
    assert state.accepted_commit == outcome.commit
    assert _git(prepared.worktree.path, "show", "HEAD:src/feature.py") == "VALUE = 2"
    assert runner.calls == ["plan", "implement", "review"]

    controller.worktrees.remove_worktree(prepared.worktree, force=True)


def test_issue_engine_quarantines_model_that_produces_no_diff(tmp_path):
    root = _repository(tmp_path)
    controller, prepared = _prepared(root)
    runner = _FakeRunner(make_edit=False)
    engine = IssueEngine(
        controller,
        config=EngineConfig(
            model="fake/model",
            max_implement_attempts=1,
            max_repairs=1,
        ),
        runner=runner,
    )

    outcome = engine.run(prepared)
    assert outcome.phase is IssuePhase.QUARANTINED
    assert outcome.accepted is False
    assert controller.store.get_issue(prepared.run_id, 66).accepted_commit is None

    controller.worktrees.remove_worktree(prepared.worktree, force=True)


def test_planner_prompt_uses_prevalidated_bounded_context(tmp_path):
    root = _repository(tmp_path)
    controller, prepared = _prepared(root)

    prompt = IssueEngine._planner_prompt(prepared)

    assert "ZERO-TOOL PLANNING MODE" in prompt
    assert "Do not call Read, Glob, Grep" in prompt
    assert "BOUNDED_CONTEXT:" in prompt
    assert "Documentation/Design/D0.md" in prompt
    assert "# Contracts" in prompt
    assert "VALUE must become 2" in prompt
    assert "src/feature.py" in prompt
    assert "VALUE = 1" in prompt
    assert "AUTONOMY_PLAN_JSON_BEGIN" in prompt
    assert EngineConfig(model="fake/model").planner_agent == (
        "autonomy-v2-planner-bounded"
    )

    controller.worktrees.remove_worktree(prepared.worktree, force=True)

