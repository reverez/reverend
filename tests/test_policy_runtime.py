from __future__ import annotations
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
import pytest
from reverend.intelligence.contracts import NetworkPolicy
from reverend.policy import ApprovalRequired,Capability,CapabilityRegistry,Permission,PermissionDecision,PermissionDenied,PermissionEvaluator,PolicyError,default_capability_registry,network_permission,permissions_for_worker,project_scope
from reverend.runtime import ModelRole
from reverend.workers import WorkerPolicy,WorkerRole

def test_default_deny_and_explicit_allow():
    registry=default_capability_registry();engine=PermissionEvaluator(registry)
    with pytest.raises(PermissionDenied):engine.require("coder","repo.read",resource={"project_id":"p"})
    engine.add(Permission("coder","repo.read",PermissionDecision.ALLOW,"worker_policy",{"project_id":"p"}))
    assert engine.require("coder","repo.read",resource={"project_id":"p"}).decision is PermissionDecision.ALLOW
    with pytest.raises(PermissionDenied):engine.require("coder","repo.read",resource={"project_id":"other"})

def test_deny_precedes_allow_and_approval_precedes_allow():
    registry=default_capability_registry()
    engine=PermissionEvaluator(registry,(
        Permission("actor","tool.execute",PermissionDecision.ALLOW,"policy",{"project_id":"p"}),
        Permission("actor","tool.execute",PermissionDecision.DENY,"project_policy",{"project_id":"p"}),
    ))
    with pytest.raises(PermissionDenied):engine.require("actor","tool.execute",resource={"project_id":"p"})
    approval=PermissionEvaluator(registry,(
        Permission("actor","network.public_read",PermissionDecision.ALLOW,"policy",{"provider":"public"}),
        Permission("actor","network.public_read",PermissionDecision.APPROVAL_REQUIRED,"user_policy",{"provider":"public"}),
    ))
    with pytest.raises(ApprovalRequired):approval.require("actor","network.public_read",resource={"provider":"public"})

def test_model_output_cannot_create_authority():
    registry=default_capability_registry();engine=PermissionEvaluator(registry)
    with pytest.raises(PolicyError,match="cannot create"):
        engine.add(Permission("coder","repo.read",PermissionDecision.ALLOW,"model",{"project_id":"p"}))

def test_expired_permission_fails_closed():
    registry=default_capability_registry()
    past=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
    engine=PermissionEvaluator(registry,(Permission("actor","repo.read",PermissionDecision.ALLOW,"policy",{"project_id":"p"},past),))
    with pytest.raises(PermissionDenied):engine.require("actor","repo.read",resource={"project_id":"p"})

def test_capability_requires_real_enforcement_point_and_valid_scope():
    with pytest.raises(ValueError):Capability("bad","read","")
    registry=CapabilityRegistry();registry.register(Capability("x","do x","adapter",scope_dimensions=("project_id",)))
    engine=PermissionEvaluator(registry)
    with pytest.raises(PolicyError,match="scope"):engine.add(Permission("a","x",PermissionDecision.ALLOW,"policy",{"unknown":"x"}))

def test_worker_policy_adapter_never_expands_authority():
    policy=WorkerPolicy(WorkerRole.CODER,ModelRole.STRONG_CODE,repository_read=True,propose_edits=True,execute_tools=False)
    permissions=permissions_for_worker("coder",policy,project_id="p")
    assert {p.capability for p in permissions}=={"repo.read","repo.propose_edit"}
    assert all(p.scope=={"project_id":"p"} for p in permissions)

def test_network_policy_maps_off_ask_auto_without_model_discretion():
    assert network_permission("research",NetworkPolicy.OFF).decision is PermissionDecision.DENY
    assert network_permission("research",NetworkPolicy.ASK).decision is PermissionDecision.APPROVAL_REQUIRED
    assert network_permission("research",NetworkPolicy.AUTO).decision is PermissionDecision.ALLOW

def test_project_trust_is_scope_metadata_not_a_grant():
    project=SimpleNamespace(id="project",trust_mode=SimpleNamespace(value="untrusted_repo"))
    assert project_scope(project)=={"project_id":"project","trust_mode":"untrusted_repo"}
