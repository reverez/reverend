"""Compatibility adapters for existing Reverend safety policy surfaces."""
from __future__ import annotations
from reverend.intelligence.contracts import NetworkPolicy
from reverend.workers import WorkerPolicy
from .models import Capability,Permission,PermissionDecision,RiskClass
from .engine import CapabilityRegistry

DEFAULT_CAPABILITIES=(
    Capability("repo.read","read repository data","repository_adapter",scope_dimensions=("project_id",)),
    Capability("repo.propose_edit","propose isolated repository edits","development_worktree_adapter",RiskClass.ELEVATED,scope_dimensions=("project_id",)),
    Capability("tool.execute","execute bounded tools","execution_adapter",RiskClass.HIGH,scope_dimensions=("project_id",)),
    Capability("memory.propose","propose memory updates","memory_adapter",RiskClass.ELEVATED),
    Capability("verify.run","run independent verification","verification_adapter",RiskClass.ELEVATED,scope_dimensions=("project_id",)),
    Capability("network.public_read","read public network sources","research_network_adapter",RiskClass.ELEVATED,scope_dimensions=("provider",)),
)

def default_capability_registry()->CapabilityRegistry:
    registry=CapabilityRegistry()
    for capability in DEFAULT_CAPABILITIES:registry.register(capability)
    return registry

def permissions_for_worker(subject:str,policy:WorkerPolicy,*,project_id:str|None=None)->tuple[Permission,...]:
    scope={"project_id":project_id} if project_id else {}
    permissions=[]
    if policy.repository_read:permissions.append(Permission(subject,"repo.read",PermissionDecision.ALLOW,"worker_policy",scope))
    if policy.propose_edits:permissions.append(Permission(subject,"repo.propose_edit",PermissionDecision.ALLOW,"worker_policy",scope))
    if policy.execute_tools:permissions.append(Permission(subject,"tool.execute",PermissionDecision.ALLOW,"worker_policy",scope))
    if policy.propose_memory:permissions.append(Permission(subject,"memory.propose",PermissionDecision.ALLOW,"worker_policy"))
    if policy.verify:permissions.append(Permission(subject,"verify.run",PermissionDecision.ALLOW,"worker_policy",scope))
    return tuple(permissions)

def network_permission(subject:str,policy:NetworkPolicy,*,provider:str="public")->Permission:
    decision={NetworkPolicy.OFF:PermissionDecision.DENY,NetworkPolicy.ASK:PermissionDecision.APPROVAL_REQUIRED,NetworkPolicy.AUTO:PermissionDecision.ALLOW}[policy]
    return Permission(subject,"network.public_read",decision,"network_policy",{"provider":provider})

def project_scope(project)->dict[str,str]:
    """Return scope metadata only; trust mode itself never grants a capability."""
    return {"project_id":str(project.id),"trust_mode":str(getattr(project.trust_mode,"value",project.trust_mode))}
