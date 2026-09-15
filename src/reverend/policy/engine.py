"""Fail-closed capability registry and permission evaluator."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Mapping
from .models import Capability,Permission,PermissionDecision

class PolicyError(RuntimeError):pass
class CapabilityNotRegistered(PolicyError):pass
class PermissionDenied(PolicyError):pass
class ApprovalRequired(PolicyError):pass

@dataclass(frozen=True)
class PolicyResult:
    subject:str
    capability:str
    decision:PermissionDecision
    matched_permissions:tuple[Permission,...]
    reason:str

class CapabilityRegistry:
    def __init__(self)->None:self._capabilities={}
    def register(self,capability:Capability)->Capability:
        existing=self._capabilities.get(capability.name)
        if existing is not None and existing!=capability:raise PolicyError(f"Capability already registered with different definition: {capability.name}")
        self._capabilities[capability.name]=capability;return capability
    def get(self,name:str)->Capability:
        try:return self._capabilities[name]
        except KeyError as exc:raise CapabilityNotRegistered(name) from exc
    def names(self)->tuple[str,...]:return tuple(sorted(self._capabilities))

class PermissionEvaluator:
    """Resolve explicit grants without allowing prompts/models to create authority."""
    def __init__(self,registry:CapabilityRegistry,permissions:tuple[Permission,...]=())->None:
        self.registry=registry;self._permissions=[]
        for permission in permissions:self.add(permission)
    def add(self,permission:Permission)->Permission:
        self.registry.get(permission.capability)
        source=permission.source.casefold()
        if source in {"model","llm","classifier","prompt","specialist_prompt"} or source.startswith("model:"):
            raise PolicyError("Model/classifier output cannot create execution authority")
        capability=self.registry.get(permission.capability)
        unknown=set(permission.scope)-set(capability.scope_dimensions)
        if unknown:raise PolicyError(f"Unsupported capability scope dimensions: {sorted(unknown)}")
        self._permissions.append(permission);return permission
    @staticmethod
    def _matches(permission:Permission,subject:str,resource:Mapping[str,str])->bool:
        if permission.subject!=subject:return False
        return all(str(resource.get(key,""))==value for key,value in permission.scope.items())
    def decide(self,subject:str,capability_name:str,*,resource:Mapping[str,str]|None=None,now:datetime|None=None)->PolicyResult:
        self.registry.get(capability_name);resource=dict(resource or {})
        matches=tuple(p for p in self._permissions if p.capability==capability_name and p.active(now) and self._matches(p,subject,resource))
        if not matches:return PolicyResult(subject,capability_name,PermissionDecision.DENY,(),"default_deny")
        decisions={p.decision for p in matches}
        if PermissionDecision.DENY in decisions:decision=PermissionDecision.DENY;reason="explicit_deny"
        elif PermissionDecision.APPROVAL_REQUIRED in decisions:decision=PermissionDecision.APPROVAL_REQUIRED;reason="approval_required"
        else:decision=PermissionDecision.ALLOW;reason="explicit_allow"
        return PolicyResult(subject,capability_name,decision,matches,reason)
    def require(self,subject:str,capability_name:str,*,resource:Mapping[str,str]|None=None,now:datetime|None=None)->PolicyResult:
        result=self.decide(subject,capability_name,resource=resource,now=now)
        if result.decision is PermissionDecision.DENY:raise PermissionDenied(f"{subject} lacks {capability_name}: {result.reason}")
        if result.decision is PermissionDecision.APPROVAL_REQUIRED:raise ApprovalRequired(f"{subject} requires approval for {capability_name}")
        return result
