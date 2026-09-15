"""Wave-2 Asset Image MVP: one provider workflow with deterministic technical QA."""
from __future__ import annotations
import hashlib
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any,Mapping,Protocol

_ALLOWED_MEDIA={"image/png","image/jpeg","image/webp"}
_MAX_IMAGE_BYTES=32*1024*1024

@dataclass(frozen=True)
class AssetRequest:
    request_id:str
    prompt:str
    purpose:str
    width:int
    height:int
    resource_lease_id:str
    provider:str
    def __post_init__(self):
        if not self.request_id or not self.prompt.strip() or not self.purpose.strip(): raise ValueError("Asset request identity/prompt/purpose are required")
        if not 64<=self.width<=4096 or not 64<=self.height<=4096: raise ValueError("Asset dimensions out of bounds")
        if not self.resource_lease_id: raise ValueError("Image generation requires a ResourceLease")
        if not self.provider: raise ValueError("Asset provider is required")

@dataclass(frozen=True)
class GeneratedImage:
    content:bytes
    media_type:str
    provider_metadata:Mapping[str,Any]=MappingProxyType({})
    def __post_init__(self):
        if self.media_type not in _ALLOWED_MEDIA: raise ValueError("Unsupported generated image media type")
        object.__setattr__(self,"provider_metadata",MappingProxyType(dict(self.provider_metadata)))

@dataclass(frozen=True)
class TechnicalQA:
    passed:bool
    checks:tuple[str,...]
    byte_count:int
    content_hash:str
    media_type:str

@dataclass(frozen=True)
class ImageAssetArtifact:
    request_id:str
    media_type:str
    content_hash:str
    byte_count:int
    width:int
    height:int
    provider:str
    resource_lease_id:str
    provenance_class:str="GENERATED"
    qa_checks:tuple[str,...]=()
    metadata:Mapping[str,Any]=MappingProxyType({})
    def __post_init__(self):
        if self.provenance_class!="GENERATED": raise ValueError("Generated assets remain GENERATED")
        object.__setattr__(self,"metadata",MappingProxyType(dict(self.metadata)))

class ImageProvider(Protocol):
    def generate(self,request:AssetRequest)->GeneratedImage: ...

def technical_qa(image:GeneratedImage)->TechnicalQA:
    content=image.content
    if not isinstance(content,(bytes,bytearray)) or not content: raise ValueError("Generated image content is empty")
    if len(content)>_MAX_IMAGE_BYTES: raise ValueError("Generated image exceeds byte budget")
    checks=["non_empty","bounded_bytes","allowed_media_type"]
    if image.media_type=="image/png" and not content.startswith(b"\x89PNG\r\n\x1a\n"): raise ValueError("PNG signature mismatch")
    if image.media_type=="image/jpeg" and not content.startswith(b"\xff\xd8\xff"): raise ValueError("JPEG signature mismatch")
    if image.media_type=="image/webp" and not (content.startswith(b"RIFF") and content[8:12]==b"WEBP"): raise ValueError("WebP signature mismatch")
    checks.append("signature_matches_media_type")
    digest=hashlib.sha256(bytes(content)).hexdigest()
    return TechnicalQA(True,tuple(checks),len(content),digest,image.media_type)

class AssetWorkflowRegistry:
    def __init__(self)->None:self._providers={}
    def register(self,name:str,provider:ImageProvider)->None:
        if not name or name in self._providers: raise ValueError("Provider name missing or already registered")
        self._providers[name]=provider
    def generate_image(self,request:AssetRequest)->tuple[ImageAssetArtifact,bytes]:
        try:provider=self._providers[request.provider]
        except KeyError as exc: raise ValueError(f"Unknown image provider: {request.provider}") from exc
        generated=provider.generate(request)
        qa=technical_qa(generated)
        artifact=ImageAssetArtifact(
            request_id=request.request_id,media_type=qa.media_type,content_hash=qa.content_hash,
            byte_count=qa.byte_count,width=request.width,height=request.height,provider=request.provider,
            resource_lease_id=request.resource_lease_id,qa_checks=qa.checks,
            metadata={"provider_metadata":dict(generated.provider_metadata)},
        )
        return artifact,bytes(generated.content)
