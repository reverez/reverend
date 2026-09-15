"""Versioned SpecialistSpec registry."""
from __future__ import annotations
from .models import ResolvedSpecialist,SpecialistSpec

class SpecialistRegistryError(RuntimeError):pass

class SpecialistRegistry:
    def __init__(self)->None:self._specs={}
    def register(self,spec:SpecialistSpec)->SpecialistSpec:
        key=(spec.id,spec.version)
        existing=self._specs.get(key)
        if existing is not None and existing!=spec:raise SpecialistRegistryError(f"Specialist version already exists: {spec.id}@{spec.version}")
        self._specs[key]=spec;return spec
    def versions(self,specialist_id:str)->tuple[int,...]:
        return tuple(sorted(version for identity,version in self._specs if identity==specialist_id))
    def resolve(self,specialist_id:str,version:int|None=None)->ResolvedSpecialist:
        versions=self.versions(specialist_id)
        if not versions:raise SpecialistRegistryError(f"Unknown specialist: {specialist_id}")
        selected=max(versions) if version is None else version
        try:spec=self._specs[(specialist_id,selected)]
        except KeyError as exc:raise SpecialistRegistryError(f"Unknown specialist version: {specialist_id}@{selected}") from exc
        return ResolvedSpecialist(spec=spec,resolved_version=selected)
    def retire(self,specialist_id:str,version:int)->SpecialistSpec:
        try:return self._specs.pop((specialist_id,version))
        except KeyError as exc:raise SpecialistRegistryError(f"Unknown specialist version: {specialist_id}@{version}") from exc
