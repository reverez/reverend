import pytest
from reverend.assets.image import AssetRequest,AssetWorkflowRegistry,GeneratedImage,technical_qa

class FakeProvider:
    def generate(self,request):
        return GeneratedImage(b"\x89PNG\r\n\x1a\n"+b"x"*32,"image/png",{"seed":1})

def request(**overrides):
    data=dict(request_id="asset-1",prompt="diagram",purpose="project visual",width=512,height=512,resource_lease_id="lease-1",provider="fake")
    data.update(overrides);return AssetRequest(**data)

def test_image_generation_requires_resource_lease():
    with pytest.raises(ValueError,match="ResourceLease"):request(resource_lease_id="")

def test_asset_workflow_generates_qa_validated_generated_artifact():
    registry=AssetWorkflowRegistry();registry.register("fake",FakeProvider())
    artifact,content=registry.generate_image(request())
    assert artifact.provenance_class=="GENERATED"
    assert artifact.resource_lease_id=="lease-1"
    assert "signature_matches_media_type" in artifact.qa_checks
    assert content.startswith(b"\x89PNG")

def test_technical_qa_rejects_media_signature_mismatch():
    with pytest.raises(ValueError,match="signature"):
        technical_qa(GeneratedImage(b"not-png","image/png"))

def test_unknown_provider_fails_closed():
    with pytest.raises(ValueError,match="Unknown image provider"):
        AssetWorkflowRegistry().generate_image(request())
