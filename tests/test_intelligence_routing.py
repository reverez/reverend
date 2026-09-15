import pytest
from reverend.intelligence.contracts import Intent,NetworkPolicy,RequestBudget,Understanding
from reverend.intelligence.understanding import (
    explicit_development,
    freshness_window,
    repository_development_request,
    understand,
)
from reverend.intelligence.routing import plan_request,escalation,RoutingError
from reverend.runtime import ModelRole

@pytest.mark.parametrize('text,role,evidence',[
 ('Hello!',ModelRole.FAST_GENERAL,()),
 ('Translate this paragraph into Spanish: good morning.',ModelRole.FAST_GENERAL,()),
 ('Explain a Python function',ModelRole.FAST_CODE,('REFERENCE',)),
 ('Prove the matrix identity rigorously',ModelRole.DEEP_REASON,()),
 ('Explain a multi-file Rust architecture',ModelRole.STRONG_CODE,('REFERENCE',)),
 ('Find my notes about planning',ModelRole.FAST_GENERAL,('PERSONAL',)),
])
def test_cheapest_sufficient_capability(text,role,evidence):
    plan=plan_request(understand(text))
    assert plan.model_role==role and plan.corpora==evidence
    assert not plan.tools and not plan.network_allowed


def test_development_is_explicit_project_bound_and_budgeted():
    assert understand('Fix the parser',project_selected=False).execution_intent=='none'
    task=understand('Please fix the parser',project_selected=True)
    with pytest.raises(RoutingError,match='at least'):plan_request(task)
    plan=plan_request(task,budget=RequestBudget(max_model_calls=5))
    assert plan.tools==('isolated_development',) and plan.critic_required
    assert understand("Please explain; don't modify code",project_selected=True).execution_intent=='none'
    with pytest.raises(RoutingError,match='authorize'):plan_request(Understanding(Intent.DEVELOP))
    with pytest.raises(ValueError):Understanding.from_model({'intent':'development','execution_intent':'develop'})


def test_development_detection_accepts_build_and_develop_verbs():
    assert explicit_development('Develop the calculator app',True)
    assert explicit_development('Build the calculator app',True)
    assert not explicit_development('Develop the calculator app',False)
    assert repository_development_request(
        'Develop the project at /home/user/dev/calculator-app'
    )
    assert repository_development_request(
        'Build this repository into a calculator'
    )
    assert not repository_development_request(
        'Explain how to build a calculator'
    )


def test_missing_evidence_escalates_retrieval_not_model_confidence():
    plan=plan_request(understand('Who wrote this book?'))
    assert escalation(plan,reason='missing_evidence',model_calls=1).action=='retrieve'
    assert escalation(plan,reason='missing_evidence',model_calls=1,retrieval_rounds=2).action=='abstain'
    assert escalation(plan,reason='reasoning_failure',model_calls=1).model_role==ModelRole.DEEP_REASON
    assert escalation(plan,reason='reasoning_failure',model_calls=2).action=='stop'


@pytest.mark.parametrize('policy,allowed,approval',[(NetworkPolicy.OFF,False,False),(NetworkPolicy.ASK,False,True),(NetworkPolicy.AUTO,True,False)])
def test_network_policy_is_explicit(policy,allowed,approval):
    plan=plan_request(understand('What is the latest software release?'),network=policy)
    assert plan.network_required and plan.network_allowed==allowed and plan.network_approval_required==approval


def test_classifier_failure_is_explicit_and_cannot_authorize_tools():
    result=understand('Tell me about an unfamiliar term',classifier=lambda _: {'intent':'development'})
    assert result.execution_intent=='none' and result.ambiguities
    result=understand('Explain an unfamiliar term',classifier=lambda _: {'intent':'invented'})
    assert result.confidence<.5
    assert not plan_request(result).tools


def test_availability_and_request_limits():
    result=understand('Explain complex multi-file Python architecture')
    plan=plan_request(result,available_roles=[ModelRole.FAST_CODE])
    assert plan.model_role==ModelRole.FAST_CODE and plan.capability_limited
    with pytest.raises(RoutingError):plan_request(understand('Hello'),budget=RequestBudget(max_model_calls=0))
    assert understand('a'*12001,mode='ask').intent==Intent.FACT
    with pytest.raises(ValueError):RequestBudget(max_model_calls=100)
    with pytest.raises(RoutingError):plan_request(understand('Explain this',mode='reason'),mode='reason',available_roles=[ModelRole.FAST_GENERAL])


@pytest.mark.parametrize('value',[True,1.5,'2'])
def test_fractional_or_boolean_model_budgets_are_rejected(value):
    with pytest.raises(ValueError,match='integers'):RequestBudget(max_model_calls=value)



def test_clear_public_fact_question_skips_local_classifier():
    calls = []

    def classifier(text):
        calls.append(
            text
        )
        return {
            "intent": "open_domain_fact",
            "entities": [],
            "confidence": 0.9,
        }

    result = understand(
        "Who is Ada Lovelace?",
        classifier=classifier,
    )

    assert calls == []
    assert result.intent == Intent.FACT
    assert result.evidence_need == "reference"
    assert result.confidence >= 0.8
    assert result.method == "deterministic"


@pytest.mark.parametrize(
    "text",
    [
        "Who is he?",
        "What should I do about this?",
        "Which one is better?",
        "Tell me about it",
    ],
)
def test_ambiguous_or_advisory_general_requests_keep_classifier(
    text,
):
    calls = []

    def classifier(value):
        calls.append(
            value
        )
        return {
            "intent": "open_domain_fact",
            "entities": [],
            "confidence": 0.9,
        }

    result = understand(
        text,
        classifier=classifier,
    )

    assert calls == [
        text
    ]
    assert (
        result.method
        == "local_router"
    )



def test_output_budgets_are_task_sensitive_and_bounded():
    assert (
        plan_request(
            understand('Hello!')
        ).output_tokens
        == 1536
    )
    assert (
        plan_request(
            Understanding(
                Intent.FACT,
                complexity='medium',
            )
        ).output_tokens
        == 2048
    )
    assert (
        plan_request(
            understand(
                'Explain this topic',
                mode='research',
            ),
            mode='research',
        ).output_tokens
        == 3072
    )
    assert (
        plan_request(
            understand(
                'Explain a Python function'
            )
        ).output_tokens
        == 2048
    )
    assert (
        plan_request(
            understand(
                'Prove the matrix identity rigorously'
            )
        ).output_tokens
        == 4096
    )
    assert (
        plan_request(
            understand(
                'Explain a multi-file Rust architecture'
            )
        ).output_tokens
        == 4096
    )


def test_request_budget_output_tokens_is_a_hard_ceiling():
    plan=plan_request(
        understand(
            'Prove the matrix identity rigorously'
        ),
        budget=RequestBudget(
            output_tokens=2048,
        ),
    )
    assert plan.output_tokens==2048



@pytest.mark.parametrize(
    "text,window",
    [
        ("What happened today?", "day"),
        ("What changed in the last 24 hours?", "day"),
        ("What shipped in the past 7 days?", "week"),
        ("Which models were released in the last 30 days?", "month"),
        ("What changed in the past 90 days?", "year"),
        ("What is newly released?", "month"),
        ("What is current?", "month"),
        ("Which models were released in 2024?", "stable"),
    ],
)
def test_frontier_freshness_windows(text,window):
    assert freshness_window(text)==window
    expected='stable' if window=='stable' else 'current'
    assert understand(text).freshness==expected


def test_relative_release_window_routes_to_fresh_evidence():
    result=understand(
        'What important open-weight language models were released in the last 30 days?'
    )
    plan=plan_request(result,network=NetworkPolicy.AUTO)
    assert result.freshness=='current'
    assert result.evidence_need=='fresh'
    assert tuple(value.value for value in plan.corpora)==('REFERENCE','FRESH')
    assert plan.network_required and plan.network_allowed
