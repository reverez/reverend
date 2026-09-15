"""Explicit capability and permission contracts for Reverend vNext."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Mapping

class RiskClass(str,Enum):
    LOW="low"; ELEVATED="elevated"; HIGH="high"

class PermissionDecision(str,Enum):
    ALLOW="allow"; DENY="deny"; APPROVAL_REQUIRED="approval_required"

@dataclass(frozen=True)
class Capability:
    name:str
    action:str
    enforcement_point:str
    risk:RiskClass=RiskClass.LOW
    version:int=1
    scope_dimensions:tuple[str,...]=()
    def __post_init__(self):
        if not self.name or len(self.name)>160:raise ValueError("Capability name is invalid")
        if not self.action or not self.enforcement_point:raise ValueError("Capability requires action and enforcement point")
        if self.version<1:raise ValueError("Capability version must be positive")
        if len(set(self.scope_dimensions))!=len(self.scope_dimensions):raise ValueError("Capability scope dimensions must be unique")

@dataclass(frozen=True)
class Permission:
    subject:str
    capability:str
    decision:PermissionDecision
    source:str
    scope:Mapping[str,str]=field(default_factory=dict)
    expires_at:str|None=None
    def __post_init__(self):
        if not self.subject or not self.capability or not self.source:raise ValueError("Permission identity fields are required")
        clean={str(k):str(v) for k,v in dict(self.scope).items()}
        if any(not k or not v for k,v in clean.items()):raise ValueError("Permission scope values must be non-empty")
        object.__setattr__(self,"scope",MappingProxyType(clean))
        if self.expires_at is not None:
            try:parsed=datetime.fromisoformat(self.expires_at)
            except ValueError as exc:raise ValueError("Permission expiry must be ISO-8601") from exc
            if parsed.tzinfo is None:raise ValueError("Permission expiry must include a timezone")

    def active(self,now:datetime|None=None)->bool:
        if self.expires_at is None:return True
        current=now or datetime.now(timezone.utc)
        return datetime.fromisoformat(self.expires_at)>current
