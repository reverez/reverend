from __future__ import annotations

import json
import subprocess
import sys
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
from reverend.development.acceptance import compile_acceptance_criteria
from reverend.development.verification import (
    VerificationCheck,
    run_verification_plan,
)
from reverend.development.verifier import (
    FreshVerifierResponseError,
    _bounded_changes,
    _latest_deterministic_evidence,
    _enforce_acceptance_coverage,
    parse_verifier_response,
    run_fresh_verifier,
    VerifierFinding,
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
        acceptance_criteria=(
            "value() returns 2 and verification passes."
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

    (
        worktree.path
        / "value.py"
    ).write_text(
        (
            "def value():\n"
            "    return 2\n"
        ),
        encoding="utf-8",
    )

    return (
        manager,
        connection,
        task,
        worktree,
    )


def add_passing_evidence(
    connection,
    task,
):
    return run_verification_plan(
        connection,
        task.id,
        [
            VerificationCheck(
                name="value-check",
                kind="test",
                argv=(
                    sys.executable,
                    "-c",
                    (
                        "from pathlib import Path; "
                        "ns={}; "
                        "exec(Path('value.py').read_text(), ns); "
                        "raise SystemExit("
                        "0 if ns['value']() == 2 else 1)"
                    ),
                ),
            )
        ],
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
            digest="verifier-digest",
            context=16384,
            think=False,
            exclusive_memory=True,
            elapsed_seconds=1.5,
            response={
                "response": (
                    self.response
                ),
                "prompt_eval_count": 500,
                "eval_count": 100,
            },
        )


def valid_response():
    return json.dumps(
        {
            "verdict": "pass",
            "summary": (
                "The requested change is present "
                "and directly verified."
            ),
            "findings": [
                {
                    "criterion": (
                        "AC-01: value() returns 2 and verification passes"
                    ),
                    "status": "met",
                    "evidence": (
                        "Current diff changes the return "
                        "value to 2 and value-check passed."
                    ),
                }
            ],
            "risks": [],
        }
    )


def test_valid_response_parses():
    (
        verdict,
        _,
        findings,
        risks,
    ) = parse_verifier_response(
        valid_response()
    )

    assert verdict == "pass"
    assert len(findings) == 1
    assert risks == ()


def test_unknown_response_field_rejected():
    value = json.loads(
        valid_response()
    )

    value["self_score"] = 10

    with pytest.raises(
        FreshVerifierResponseError
    ):
        parse_verifier_response(
            json.dumps(value)
        )


def test_untracked_file_is_visible(
    tmp_path,
):
    (
        manager,
        _,
        _,
        worktree,
    ) = setup_task(tmp_path)

    try:
        (
            worktree.path
            / "new.py"
        ).write_text(
            "NEW_MARKER = True\n",
            encoding="utf-8",
        )

        changes = _bounded_changes(
            worktree.path,
            max_chars=10000,
        )

        assert (
            "UNTRACKED FILE: new.py"
            in changes
        )

        assert (
            "NEW_MARKER = True"
            in changes
        )

    finally:
        manager.__exit__(
            None,
            None,
            None,
        )


def test_no_evidence_is_unverified_without_model(
    tmp_path,
):
    (
        manager,
        connection,
        task,
        _,
    ) = setup_task(tmp_path)

    try:
        scheduler = FakeScheduler(
            valid_response()
        )

        result = run_fresh_verifier(
            connection,
            task.id,
            scheduler,
        )

        assert (
            result.verdict
            == "unverified"
        )

        assert (
            scheduler.calls
            == []
        )

    finally:
        manager.__exit__(
            None,
            None,
            None,
        )


def test_failed_required_check_fails_without_model(
    tmp_path,
):
    (
        manager,
        connection,
        task,
        _,
    ) = setup_task(tmp_path)

    try:
        run_verification_plan(
            connection,
            task.id,
            [
                VerificationCheck(
                    name="forced-failure",
                    kind="test",
                    argv=(
                        sys.executable,
                        "-c",
                        "raise SystemExit(3)",
                    ),
                )
            ],
        )

        scheduler = FakeScheduler(
            valid_response()
        )

        result = run_fresh_verifier(
            connection,
            task.id,
            scheduler,
        )

        assert (
            result.verdict
            == "fail"
        )

        assert (
            scheduler.calls
            == []
        )

    finally:
        manager.__exit__(
            None,
            None,
            None,
        )


def test_latest_evidence_wins(
    tmp_path,
):
    (
        manager,
        connection,
        task,
        _,
    ) = setup_task(tmp_path)

    try:
        run_verification_plan(
            connection,
            task.id,
            [
                VerificationCheck(
                    name="same-check",
                    kind="test",
                    argv=(
                        sys.executable,
                        "-c",
                        "raise SystemExit(1)",
                    ),
                )
            ],
        )

        run_verification_plan(
            connection,
            task.id,
            [
                VerificationCheck(
                    name="same-check",
                    kind="test",
                    argv=(
                        sys.executable,
                        "-c",
                        "raise SystemExit(0)",
                    ),
                )
            ],
        )

        evidence = (
            _latest_deterministic_evidence(
                connection,
                task.id,
            )
        )

        same = next(
            item
            for item in evidence
            if item.name
            == "same-check"
        )

        assert (
            same.status
            == "passed"
        )

    finally:
        manager.__exit__(
            None,
            None,
            None,
        )


def test_passing_evidence_invokes_fresh_model(
    tmp_path,
):
    (
        manager,
        connection,
        task,
        _,
    ) = setup_task(tmp_path)

    try:
        report = add_passing_evidence(
            connection,
            task,
        )

        assert report.passed

        scheduler = FakeScheduler(
            valid_response()
        )

        result = run_fresh_verifier(
            connection,
            task.id,
            scheduler,
        )

        assert result.passed

        role, prompt, kwargs = (
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

        assert (
            "ORIGINAL TASK"
            in prompt
        )

        assert (
            "CURRENT REPOSITORY CHANGES"
            in prompt
        )

        assert (
            "DETERMINISTIC VERIFICATION EVIDENCE"
            in prompt
        )
        assert "Host-observed deterministic check statuses are authoritative" in prompt

        row = connection.execute(
            """
            SELECT
                kind,
                status
            FROM verifications
            WHERE id = ?
            """,
            (
                result.verification_id,
            ),
        ).fetchone()

        assert (
            row["kind"]
            == "fresh_verifier"
        )

        assert (
            row["status"]
            == "passed"
        )

        model_row = connection.execute(
            """
            SELECT
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

        assert (
            model_row["model"]
            == "qwen3-coder:30b"
        )

        assert (
            model_row["success"]
            == 1
        )

        assert (
            "fresh_verifier"
            in model_row[
                "metadata_json"
            ]
        )

    finally:
        manager.__exit__(
            None,
            None,
            None,
        )



def test_unrelated_diff_fails_before_model(tmp_path):
    manager, connection, task, worktree = setup_task(tmp_path)
    try:
        add_passing_evidence(connection, task)
        (worktree.path / "unrelated.py").write_text("x = 1\n", encoding="utf-8")
        scheduler = FakeScheduler(valid_response())

        result = run_fresh_verifier(
            connection,
            task.id,
            scheduler,
            expected_paths=("value.py",),
        )

        assert result.verdict == "fail"
        assert scheduler.calls == []
        assert any(
            item.criterion == "host:unrelated-diff"
            and "unrelated.py" in item.evidence
            for item in result.findings
        )
    finally:
        manager.__exit__(None, None, None)


def test_explicitly_excluded_path_fails_before_model(tmp_path):
    manager, connection, task, worktree = setup_task(tmp_path)
    try:
        add_passing_evidence(connection, task)
        (worktree.path / "legacy.py").write_text("bad = True\n", encoding="utf-8")
        scheduler = FakeScheduler(valid_response())

        result = run_fresh_verifier(
            connection,
            task.id,
            scheduler,
            expected_paths=("value.py", "legacy.py"),
            excluded_paths=("legacy.py",),
        )

        assert result.verdict == "fail"
        assert scheduler.calls == []
        assert any(item.criterion == "host:path-constraints" for item in result.findings)
    finally:
        manager.__exit__(None, None, None)


def test_missing_acceptance_finding_downgrades_false_pass(tmp_path):
    manager, connection, task, _ = setup_task(tmp_path)
    try:
        add_passing_evidence(connection, task)
        response = json.loads(valid_response())
        response["findings"][0]["criterion"] = "generic task success"
        scheduler = FakeScheduler(json.dumps(response))

        result = run_fresh_verifier(
            connection,
            task.id,
            scheduler,
            expected_paths=("value.py",),
        )

        assert result.verdict == "unverified"
        assert any(
            item.criterion == "AC-01" and item.status == "unverified"
            for item in result.findings
        )
    finally:
        manager.__exit__(None, None, None)


def test_exact_natural_criterion_wording_can_be_labeled_without_semantic_inference():
    contract=compile_acceptance_criteria(
        "Existing mean behaviour must remain unchanged. "
        "Empty input must raise ValueError."
    )
    findings=(
        VerifierFinding(
            criterion="Existing mean behaviour must remain unchanged.",
            status="met",
            evidence="Existing mean test passed.",
        ),
        VerifierFinding(
            criterion="Empty input must raise ValueError.",
            status="met",
            evidence="Empty-input test passed.",
        ),
    )
    verdict,normalized=_enforce_acceptance_coverage(
        "pass",
        findings,
        contract,
    )
    assert verdict=="pass"
    assert normalized[0].criterion.startswith("AC-01:")
    assert normalized[1].criterion.startswith("AC-02:")


def test_generic_positive_finding_still_cannot_satisfy_acceptance_coverage():
    contract=compile_acceptance_criteria(
        "Empty input must raise ValueError."
    )
    findings=(
        VerifierFinding(
            criterion="implementation correctness",
            status="met",
            evidence="Looks correct.",
        ),
    )
    verdict,normalized=_enforce_acceptance_coverage(
        "pass",
        findings,
        contract,
    )
    assert verdict=="unverified"
    assert any(
        item.criterion=="AC-01" and item.status=="unverified"
        for item in normalized
    )


class SequenceScheduler:
    def __init__(self,*responses):
        self.responses=list(responses)
        self.calls=[]

    def generate(self,role,prompt,**kwargs):
        self.calls.append((role,prompt,kwargs))
        if not self.responses:
            raise AssertionError("unexpected verifier model call")
        response=self.responses.pop(0)
        return SimpleNamespace(
            role=role,
            model="qwen3-coder:30b",
            digest="verifier-digest",
            context=16384,
            think=False,
            exclusive_memory=True,
            elapsed_seconds=1.0,
            response={
                "response":response,
                "prompt_eval_count":400,
                "eval_count":80,
            },
        )


def deterministic_contradiction_response():
    return json.dumps(
        {
            "verdict":"fail",
            "summary":"The value-check test is not passing.",
            "findings":[
                {
                    "criterion":"AC-01: value() returns 2 and verification passes",
                    "status":"not_met",
                    "evidence":"The test value-check is not passing.",
                }
            ],
            "risks":[],
        }
    )


def legitimate_code_review_failure_response():
    return json.dumps(
        {
            "verdict":"fail",
            "summary":"Independent code review found a semantic defect.",
            "findings":[
                {
                    "criterion":"AC-01: value() returns 2 and verification passes",
                    "status":"not_met",
                    "evidence":"The current implementation returns the wrong constant in the reviewed diff.",
                }
            ],
            "risks":[],
        }
    )


def test_deterministic_contradiction_gets_one_fresh_corrective_verifier_call(tmp_path):
    manager,connection,task,_=setup_task(tmp_path)
    try:
        add_passing_evidence(connection,task)
        scheduler=SequenceScheduler(
            deterministic_contradiction_response(),
            valid_response(),
        )

        result=run_fresh_verifier(
            connection,
            task.id,
            scheduler,
            expected_paths=("value.py",),
        )

        assert result.verdict=="pass"
        assert len(scheduler.calls)==2
        assert "HOST CORRECTION AFTER INVALID VERIFIER RESPONSE" in scheduler.calls[1][1]

        rows=connection.execute(
            """
            SELECT success,metadata_json
            FROM model_runs
            WHERE task_id=?
              AND role=?
            ORDER BY rowid ASC
            """,
            (task.id,ModelRole.STRONG_CODE.value),
        ).fetchall()
        assert rows[-2]["success"]==0
        assert "contradicted host-observed deterministic" in rows[-2]["metadata_json"]
        assert rows[-1]["success"]==1
    finally:
        manager.__exit__(None,None,None)


def test_repeated_deterministic_contradiction_becomes_unverified(tmp_path):
    manager,connection,task,_=setup_task(tmp_path)
    try:
        add_passing_evidence(connection,task)
        scheduler=SequenceScheduler(
            deterministic_contradiction_response(),
            deterministic_contradiction_response(),
        )

        result=run_fresh_verifier(
            connection,
            task.id,
            scheduler,
            expected_paths=("value.py",),
        )

        assert result.verdict=="unverified"
        assert len(scheduler.calls)==2
        assert any(
            item.criterion=="host:deterministic-contradiction"
            and item.status=="unverified"
            for item in result.findings
        )
    finally:
        manager.__exit__(None,None,None)


def test_legitimate_code_review_failure_requires_independent_confirmation(tmp_path):
    manager,connection,task,_=setup_task(tmp_path)
    try:
        add_passing_evidence(connection,task)
        scheduler=SequenceScheduler(
            legitimate_code_review_failure_response(),
            legitimate_code_review_failure_response(),
        )

        result=run_fresh_verifier(
            connection,
            task.id,
            scheduler,
            expected_paths=("value.py",),
        )

        assert result.verdict=="fail"
        assert len(scheduler.calls)==2
        assert "SECOND INDEPENDENT SEMANTIC VETO CONFIRMATION" in scheduler.calls[1][1]
        assert not any(
            item.criterion=="host:deterministic-contradiction"
            for item in result.findings
        )
    finally:
        manager.__exit__(None,None,None)


def live_style_false_nonmutation_veto_response():
    return json.dumps(
        {
            "verdict":"fail",
            "summary":(
                "The implementation fails to meet the requirement that "
                "median must not mutate its input."
            ),
            "findings":[
                {
                    "criterion":"AC-01: value() returns 2 and verification passes",
                    "status":"not_met",
                    "evidence":(
                        "The implementation relies on the passing test rather "
                        "than explicitly verifying the behavior in production code."
                    ),
                }
            ],
            "risks":[],
        }
    )


def unverified_response():
    return json.dumps(
        {
            "verdict":"unverified",
            "summary":"The available evidence is insufficient for a semantic veto.",
            "findings":[
                {
                    "criterion":"AC-01: value() returns 2 and verification passes",
                    "status":"unverified",
                    "evidence":"No concrete counterexample was established.",
                }
            ],
            "risks":[],
        }
    )


def test_false_semantic_veto_rejected_by_independent_adjudicator(tmp_path):
    manager,connection,task,_=setup_task(tmp_path)
    try:
        add_passing_evidence(connection,task)
        scheduler=SequenceScheduler(
            live_style_false_nonmutation_veto_response(),
            valid_response(),
        )

        result=run_fresh_verifier(
            connection,
            task.id,
            scheduler,
            expected_paths=("value.py",),
        )

        assert result.verdict=="pass"
        assert len(scheduler.calls)==2
        assert "SECOND INDEPENDENT SEMANTIC VETO CONFIRMATION" in scheduler.calls[1][1]
        assert "does not need to contain an explicit self-check" in scheduler.calls[1][1]
        assert any(
            "initial semantic verifier proposed a veto" in risk.casefold()
            for risk in result.risks
        )
    finally:
        manager.__exit__(None,None,None)


def test_unconfirmed_semantic_veto_becomes_unverified(tmp_path):
    manager,connection,task,_=setup_task(tmp_path)
    try:
        add_passing_evidence(connection,task)
        scheduler=SequenceScheduler(
            legitimate_code_review_failure_response(),
            unverified_response(),
        )

        result=run_fresh_verifier(
            connection,
            task.id,
            scheduler,
            expected_paths=("value.py",),
        )

        assert result.verdict=="unverified"
        assert len(scheduler.calls)==2
        assert any(
            item.criterion=="host:semantic-veto-disagreement"
            and item.status=="unverified"
            for item in result.findings
        )
    finally:
        manager.__exit__(None,None,None)


def test_passing_semantic_verifier_does_not_trigger_adjudication(tmp_path):
    manager,connection,task,_=setup_task(tmp_path)
    try:
        add_passing_evidence(connection,task)
        scheduler=SequenceScheduler(valid_response())

        result=run_fresh_verifier(
            connection,
            task.id,
            scheduler,
            expected_paths=("value.py",),
        )

        assert result.verdict=="pass"
        assert len(scheduler.calls)==1
    finally:
        manager.__exit__(None,None,None)
