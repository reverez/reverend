# Wave 2 — Asset Image MVP

V1 implements exactly one transactional image path:

`AssetRequest → registered image provider → deterministic technical QA → GENERATED artifact`.

Rules:
- every generation request carries a ResourceLease ID;
- providers are replaceable adapters;
- no new daemon/service is introduced;
- image bytes are bounded and media signatures are verified;
- hashes and provider metadata are recorded;
- generated images remain `GENERATED`, never factual evidence;
- semantic/aesthetic QA and ComfyUI integration can be layered later without changing the artifact contract.
