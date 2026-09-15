"""Versioned specialist and selected-context contracts."""
from __future__ import annotations
from dataclasses import dataclass,field
from types import MappingProxyType
from typing import Any,Mapping
from reverend.runtime import ModelRole

@dataclass(frozen=True)
class ContextPolicy:
    max_input_tokens:int
    allowed_layers:tuple[str,...]
    mandatory_layers:tuple[str,...]=("system","authoritative_task","current_request")
    max_item_tokens:int=4096
    def __post_init__(self):
        if not 128<=self.max_input_tokens<=262144:raise ValueError("Context input budget is invalid")
        if not 64<=self.max_item_tokens<=self.max_input_tokens:raise ValueError("Context item budget is invalid")
        if len(set(self.allowed_layers))!=len(self.allowed_layers):raise ValueError("Context layers must be unique")
        if any(layer not in self.allowed_layers for layer in self.mandatory_layers):raise ValueError("Mandatory context layer must be allowed")

@dataclass(frozen=True)
class SpecialistSpec:
    id:str
    version:int
    name:str
    model_role:ModelRole
    methodology_binding:str
    context_policy:ContextPolicy
    tool_policy:tuple[str,...]=()
    required_capabilities:tuple[str,...]=()
    input_artifact_types:tuple[str,...]=()
    output_artifact_types:tuple[str,...]=()
    authority_profile:str="read_only"
    independent_verifier:bool=False
    metadata:Mapping[str,Any]=field(default_factory=dict)
    def __post_init__(self):
        if not self.id or len(self.id)>128 or not self.name:raise ValueError("Specialist identity is invalid")
        if not isinstance(self.version,int) or isinstance(self.version,bool) or self.version<1:raise ValueError("Specialist version must be positive")
        if not isinstance(self.model_role,ModelRole):raise ValueError("Specialist model binding must use ModelRole")
        if not self.methodology_binding or len(self.methodology_binding)>256:raise ValueError("Specialist methodology binding is required")
        for field_name,values in (("tool_policy",self.tool_policy),("required_capabilities",self.required_capabilities),("input_artifact_types",self.input_artifact_types),("output_artifact_types",self.output_artifact_types)):
            if len(set(values))!=len(values) or any(not isinstance(v,str) or not v or len(v)>160 for v in values):raise ValueError(f"{field_name} contains invalid values")
        if self.independent_verifier and any(v in {"patch","implementation_patch","code_change"} for v in self.output_artifact_types):
            raise ValueError("Independent verifier cannot produce implementation artifacts")
        object.__setattr__(self,"metadata",MappingProxyType(dict(self.metadata)))

@dataclass(frozen=True)
class ResolvedSpecialist:
    spec:SpecialistSpec
    resolved_version:int

@dataclass(frozen=True)
class ContextItem:
    id:str
    layer:str
    text:str
    priority:int=0
    mandatory:bool=False
    estimated_tokens:int|None=None
    provenance:Mapping[str,Any]=field(default_factory=dict)
    def __post_init__(self):
        if not self.id or not self.layer or not isinstance(self.text,str):raise ValueError("Context item is invalid")
        if self.estimated_tokens is not None and self.estimated_tokens<0:raise ValueError("Context token estimate cannot be negative")
        object.__setattr__(self,"provenance",MappingProxyType(dict(self.provenance)))

@dataclass(frozen=True)
class ContextSelection:
    items:tuple[ContextItem,...]
    estimated_tokens:int
    omitted_ids:tuple[str,...]
    mandatory_ids:tuple[str,...]
