from __future__ import annotations
import pytest
from reverend.runtime import ModelRole
from reverend.specialists import ContextBroker,ContextBudgetExceeded,ContextItem,ContextPolicy,SpecialistRegistry,SpecialistRegistryError,SpecialistSpec,specialist_from_worker
from reverend.workers import WorkerRole

def policy(budget=500):return ContextPolicy(budget,("system","authoritative_task","current_request","evidence","history"),max_item_tokens=min(400,budget))

def test_registry_resolves_latest_version_without_erasing_history():
    registry=SpecialistRegistry()
    one=SpecialistSpec("architect",1,"Architect",ModelRole.DEEP_REASON,"architecture.v1",policy(),output_artifact_types=("architecture_decision",))
    two=SpecialistSpec("architect",2,"Architect",ModelRole.DEEP_REASON,"architecture.v2",policy(),output_artifact_types=("architecture_decision",))
    registry.register(one);registry.register(two)
    assert registry.versions("architect")== (1,2)
    assert registry.resolve("architect").resolved_version==2
    assert registry.resolve("architect",1).spec.methodology_binding=="architecture.v1"

def test_conflicting_specialist_version_is_rejected():
    registry=SpecialistRegistry();spec=SpecialistSpec("x",1,"X",ModelRole.FAST_GENERAL,"m1",policy());registry.register(spec)
    with pytest.raises(SpecialistRegistryError):registry.register(SpecialistSpec("x",1,"X",ModelRole.FAST_GENERAL,"m2",policy()))

def test_worker_adapter_preserves_existing_model_and_authority_policy():
    coder=specialist_from_worker(WorkerRole.CODER)
    assert coder.model_role is ModelRole.STRONG_CODE
    assert set(coder.required_capabilities)=={"repo.read","repo.propose_edit"}
    assert coder.output_artifact_types==("implementation_patch",)
    verifier=specialist_from_worker(WorkerRole.CRITIC_VERIFIER)
    assert verifier.independent_verifier is True
    assert verifier.output_artifact_types==("verification_result",)
    assert "verify.run" in verifier.required_capabilities

def test_verifier_cannot_be_configured_as_implementation_producer():
    with pytest.raises(ValueError,match="cannot produce"):
        SpecialistSpec("verifier",1,"Verifier",ModelRole.CRITIC,"verify.v1",policy(),output_artifact_types=("implementation_patch",),independent_verifier=True)

def test_context_broker_never_evicts_authoritative_layers():
    broker=ContextBroker()
    items=(
        ContextItem("sys","system","s"*60,mandatory=True,estimated_tokens=20),
        ContextItem("task","authoritative_task","t"*60,estimated_tokens=20),
        ContextItem("req","current_request","r"*60,estimated_tokens=20),
        ContextItem("evidence","evidence","e"*300,priority=10,estimated_tokens=100),
        ContextItem("history","history","h"*900,priority=1,estimated_tokens=350),
    )
    selected=broker.select(items,policy(200))
    assert selected.mandatory_ids==("sys","task","req")
    assert {item.id for item in selected.items}=={"sys","task","req","evidence"}
    assert selected.omitted_ids==("history",)

def test_mandatory_context_overflow_fails_before_optional_selection():
    broker=ContextBroker()
    items=(ContextItem("task","authoritative_task","x",estimated_tokens=300),ContextItem("request","current_request","y",estimated_tokens=300))
    with pytest.raises(ContextBudgetExceeded):broker.select(items,policy(500))

def test_disallowed_layers_are_not_context_channel():
    broker=ContextBroker()
    items=(ContextItem("req","current_request","hello",estimated_tokens=5),ContextItem("secret","private_reasoning","never include",priority=100,estimated_tokens=5))
    selected=broker.select(items,policy())
    assert [item.id for item in selected.items]==["req"]
