from reverend.benchmarks.evaluator import (
    evaluate_expectations,
)
from reverend.benchmarks.runtime import (
    RuntimeInventoryExecutor,
    runtime_cases,
    runtime_optimization_cases,
)


def test_m14_runtime_benchmark_cases_pass():
    executor = RuntimeInventoryExecutor()

    for case in runtime_cases():
        observation = executor(
            case
        )
        assertions = (
            evaluate_expectations(
                case,
                observation,
            )
        )

        assert all(
            item.passed
            for item in assertions
        )


def test_m14_inventory_benchmark_reuses_one_provider_read():
    case = next(
        item
        for item
        in runtime_cases()
        if (
            item.case_id
            == "m14-inventory-burst"
        )
    )
    observation = (
        RuntimeInventoryExecutor()(
            case
        )
    )

    assert (
        observation.metadata[
            "inventory_calls"
        ]
        == 1
    )
    assert (
        observation.metadata[
            "model_calls"
        ]
        == 0
    )


def test_m14_router_optimisation_keeps_ambiguity_guard():
    executor = RuntimeInventoryExecutor()
    clear = next(
        item
        for item
        in runtime_cases()
        if item.case_id
        == "m14-clear-fact-fast-path"
    )
    ambiguous = next(
        item
        for item
        in runtime_cases()
        if item.case_id
        == "m14-ambiguous-router-guard"
    )

    clear_observation = executor(
        clear
    )
    ambiguous_observation = executor(
        ambiguous
    )

    assert (
        clear_observation.metadata[
            "classifier_calls"
        ]
        == 0
    )
    assert (
        ambiguous_observation.metadata[
            "classifier_calls"
        ]
        == 1
    )



def test_runtime_inventory_session_window_reuses_one_provider_read():
    case = next(
        item
        for item in runtime_optimization_cases()
        if (
            item.case_id
            == "runtime-inventory-session-window"
        )
    )
    observation = RuntimeInventoryExecutor()(
        case
    )

    assert (
        observation.metadata[
            "baseline_inventory_calls"
        ]
        == 3
    )
    assert (
        observation.metadata[
            "optimized_inventory_calls"
        ]
        == 1
    )
    assert (
        observation.metadata[
            "provider_read_delta"
        ]
        == -2
    )
    assert (
        observation.metadata[
            "optimized_cache_hits"
        ]
        == 2
    )
    assert (
        observation.metadata[
            "inventory_ttl_seconds"
        ]
        == 30.0
    )



def test_runtime_optimization_benchmark_cases_pass():
    executor = RuntimeInventoryExecutor()

    for case in runtime_optimization_cases():
        observation = executor(
            case
        )
        assertions = (
            evaluate_expectations(
                case,
                observation,
            )
        )

        assert all(
            item.passed
            for item in assertions
        )
