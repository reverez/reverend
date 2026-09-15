import pytest
from reverend.intelligence.architecture_specialist import architecture_methodology,architect_specialist_spec,build_architecture_pack,run_architect
from reverend.runtime import ModelRole

def valid_pack(**overrides):
    data=dict(
        objective="Add a scheduler",
        requirements=("atomic resources",),
        invariants=("one authoritative control plane",),
        alternatives=("extend runtime","new service"),
        decision="extend runtime",
        interfaces=("ResourceLease",),
        state_ownership=("Resource Runtime owns leases",),
        failure_semantics=("failed acquisition grants nothing",),
        migration_steps=("add adapter",),
        risks=("compatibility",),
        rationale="Keeps the modular monolith.",
        evidence_refs=("artifact:evidence",),
    );data.update(overrides);return build_architecture_pack(**data)

def test_architect_is_proposal_only_and_deep_reasoned():
    spec=architect_specialist_spec()
    assert spec.model_role is ModelRole.DEEP_REASON
    assert spec.authority_profile=="architecture_proposal"
    assert spec.output_artifact_types==("architecture_decision",)

def test_architecture_pack_requires_alternatives_invariants_and_failure_semantics():
    with pytest.raises(ValueError,match="two alternatives"):valid_pack(alternatives=("only",),decision="only")
    with pytest.raises(ValueError,match="invariants"):valid_pack(invariants=())
    with pytest.raises(ValueError,match="failure semantics"):valid_pack(failure_semantics=())

def test_decision_must_be_one_of_compared_alternatives():
    with pytest.raises(ValueError,match="select"):valid_pack(decision="third option")

def test_methodology_covers_state_failure_migration_and_tradeoffs():
    steps=architecture_methodology()
    for required in ("analyse_state_ownership","analyse_failure_modes","analyse_migration","compare_tradeoffs","produce_adr"):
        assert required in steps


class FakeResult:
    model="deep";digest="digest"
    response={"response":'{"invariants":["one authority"],"alternatives":[{"id":"A","description":"extend"},{"id":"B","description":"replace"}],"decision_id":"A","interfaces":["API"],"state_ownership":["runtime owns state"],"failure_semantics":["fail closed"],"migration_steps":["adapter"],"risks":["drift"],"rationale":"least coupling"}'}
class FakeScheduler:
    def generate(self,role,prompt,**kwargs):
        assert role is ModelRole.DEEP_REASON
        assert kwargs["context"]==8192 and kwargs["think"] is False
        response_schema=kwargs["response_format"]
        assert response_schema["type"]=="object"
        assert response_schema["additionalProperties"] is False
        alternative_schema=response_schema["properties"]["alternatives"]["items"]
        assert alternative_schema["additionalProperties"] is False
        assert set(alternative_schema["required"])=={"id","description"}
        assert "decision_id MUST exactly equal" in prompt
        return FakeResult()

def test_architect_invocation_returns_validated_pack():
    pack=run_architect(FakeScheduler(),objective="Improve runtime",requirements=("preserve API",),current_architecture="modular monolith",evidence_refs=("e1",))
    assert pack.decision=="extend"
    assert pack.evidence_refs==("e1",)
    assert pack.metadata["model"]=="deep"
    assert pack.metadata["decision_id"]=="A"


def test_architect_decision_id_must_select_a_listed_alternative():
    class BadResult:
        model="deep"
        digest="digest"
        response={
            "response": (
                '{"invariants":["one authority"],'
                '"alternatives":[{"id":"A","description":"extend"},'
                '{"id":"B","description":"replace"}],'
                '"decision_id":"C","interfaces":["API"],'
                '"state_ownership":["runtime owns state"],'
                '"failure_semantics":["fail closed"],'
                '"migration_steps":["adapter"],"risks":["drift"],'
                '"rationale":"least coupling"}'
            )
        }

    class BadScheduler:
        def generate(self,*args,**kwargs):
            return BadResult()

    with pytest.raises(ValueError,match="decision_id"):
        run_architect(
            BadScheduler(),
            objective="Improve runtime",
            requirements=("preserve API",),
            current_architecture="modular monolith",
        )


def test_architect_decision_uses_selected_description_not_id():
    pack=run_architect(
        FakeScheduler(),
        objective="Improve runtime",
        requirements=("preserve API",),
        current_architecture="modular monolith",
    )
    assert pack.alternatives==("extend","replace")
    assert pack.decision=="extend"


def test_architect_ignores_non_authoritative_alternative_metadata():
    class ExtraResult:
        model="deep"
        digest="digest"
        response={
            "response": (
                '{"invariants":["one authority"],'
                '"alternatives":['
                '{"id":"A","description":"extend","pros":["simple"],"score":9},'
                '{"id":"B","description":"replace","cons":["migration"]}'
                '],"decision_id":"A","interfaces":["API"],'
                '"state_ownership":["runtime owns state"],'
                '"failure_semantics":["fail closed"],'
                '"migration_steps":["adapter"],"risks":["drift"],'
                '"rationale":"least coupling"}'
            )
        }

    class ExtraScheduler:
        def generate(self,*args,**kwargs):
            return ExtraResult()

    pack=run_architect(
        ExtraScheduler(),
        objective="Improve runtime",
        requirements=("preserve API",),
        current_architecture="modular monolith",
    )
    assert pack.decision=="extend"
    assert pack.metadata["decision_id"]=="A"
    assert pack.metadata["ignored_alternative_fields"]==[
        "cons","pros","score"
    ]


def test_architect_still_rejects_alternative_missing_authoritative_fields():
    class MissingResult:
        model="deep"
        digest="digest"
        response={
            "response": (
                '{"invariants":["one authority"],'
                '"alternatives":[{"id":"A"},{"id":"B","description":"replace"}],'
                '"decision_id":"A","interfaces":["API"],'
                '"state_ownership":["runtime owns state"],'
                '"failure_semantics":["fail closed"],'
                '"migration_steps":["adapter"],"risks":["drift"],'
                '"rationale":"least coupling"}'
            )
        }

    class MissingScheduler:
        def generate(self,*args,**kwargs):
            return MissingResult()

    with pytest.raises(ValueError,match="contain id and description"):
        run_architect(
            MissingScheduler(),
            objective="Improve runtime",
            requirements=("preserve API",),
            current_architecture="modular monolith",
        )
