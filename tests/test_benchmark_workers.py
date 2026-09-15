from reverend.benchmarks.evaluator import evaluate_expectations
from reverend.benchmarks.workers import (
    WorkerOrchestrationExecutor,
    worker_cases,
)


def test_worker_reverendbench_cases_pass_deterministically():
    executor = WorkerOrchestrationExecutor()

    for case in worker_cases():
        observation = executor(case)
        assertions = evaluate_expectations(case, observation)
        assert assertions
        assert all(assertion.passed for assertion in assertions), (
            case.case_id,
            assertions,
        )


def test_worker_bench_records_verifier_as_separate_worker():
    case = next(
        case
        for case in worker_cases()
        if case.case_id == 'm11-verifier-rejection'
    )
    observation = WorkerOrchestrationExecutor()(case)

    assert observation.metadata['stop_reason'] == 'verifier_rejected'
    assert [row['role'] for row in observation.metadata['records']] == [
        'coder',
        'critic_verifier',
    ]
    assert observation.metadata['records'][0]['verified_by'] == 'coder:verify'



def test_development_worker_bench_uses_real_engine_and_isolation():
    case = next(
        case
        for case in worker_cases()
        if case.case_id == "m11-development-engine-workers"
    )
    observation = WorkerOrchestrationExecutor()(case)
    assertions = evaluate_expectations(case, observation)

    assert all(assertion.passed for assertion in assertions)
    assert observation.metadata["roles"] == [
        "code_localizer",
        "coder",
        "critic_verifier",
    ]
    assert observation.metadata["primary_checkout_unchanged"] is True
    assert observation.metadata["worktree_changed"] is True
