from __future__ import annotations

from pathlib import Path


ROOT=Path(__file__).resolve().parents[1]
UI=ROOT/"src"/"reverend"/"ui"


def test_m18_workspace_shell_and_inspector_are_shipped():
    html=(UI/"index.html").read_text(encoding="utf-8")
    css=(UI/"app.css").read_text(encoding="utf-8")
    assert 'id="chat-workspace"' in html
    assert 'id="inspector"' in html
    assert 'id="inspector-toggle"' in html
    assert 'data-inspector-tab="sources"' in html
    assert 'data-inspector-tab="details"' in html
    assert 'data-inspector-tab="preview"' in html
    assert '.inspector-open #inspector' in css
    assert '.artifact-frame' in css


def test_artifact_preview_is_sandboxed_and_sanitized():
    script=(UI/"app.js").read_text(encoding="utf-8")
    assert "frame.setAttribute('sandbox','')" in script
    assert "DOMPurify.sanitize(preview.source" in script
    assert "default-src 'none'" in script
    assert "FORBID_TAGS:['script','iframe','object','embed'" in script
    assert "allow-scripts" not in script
    assert "openArtifactPreview" in script


def test_source_interaction_prefers_persistent_inspector():
    script=(UI/"sources.js").read_text(encoding="utf-8")
    assert "window.openInspectorSource" in script
    assert "source.search_provider" in script
    assert "source.search_freshness" in script


def test_workstation_scripts_remain_local_assets_only():
    html=(UI/"index.html").read_text(encoding="utf-8")
    assert '<script defer src="http://' not in html
    assert '<script defer src="https://' not in html



def test_local_diagram_renderer_is_loaded_without_remote_dependency():
    html=(UI/"index.html").read_text(encoding="utf-8")
    app=(UI/"app.js").read_text(encoding="utf-8")
    diagrams=(UI/"diagrams.js").read_text(encoding="utf-8")
    assert 'src="/assets/diagrams.js"' in html
    assert "renderReverendDiagram" in app
    assert "MAX_NODES=40" in diagrams
    assert "MAX_EDGES=80" in diagrams
    assert "createElementNS" in diagrams
    assert "innerHTML" not in diagrams



def test_search_images_use_only_local_binary_proxy():
    app=(UI/"app.js").read_text(encoding="utf-8")
    sources=(UI/"sources.js").read_text(encoding="utf-8")
    server=(ROOT/"src"/"reverend"/"workstation"/"server.py").read_text(encoding="utf-8")
    assert "/api/research/images/" in app
    assert "URL.createObjectURL" in app
    assert "URL.revokeObjectURL" in app
    assert "source.image_id" in sources
    assert "img.src=source.url" not in app+sources
    assert "img.src=source.source" not in app+sources
    assert "img-src 'self' data: blob:;" in server
    assert "img-src 'self' data: https:" not in server
    assert "md = window.markdownit({html:false,linkify:true}).disable('image')" in app



def test_m18_workstation_polish_has_visual_gallery_wide_preview_and_activity_states():
    app=(UI/"app.js").read_text(encoding="utf-8")
    sources=(UI/"sources.js").read_text(encoding="utf-8")
    css=(UI/"app.css").read_text(encoding="utf-8")
    assert "setInspectorWide" in app
    assert "generationLabel" in app
    assert "Searching the web…" in app
    assert "Reading web sources…" in app
    assert "source-gallery" in sources
    assert "source.image_id" in sources
    assert ".inspector-open.inspector-wide" in css
    assert "@keyframes reverend-pulse" in css



def test_source_inspector_navigation_keeps_response_source_context():
    app=(UI/"app.js").read_text(encoding="utf-8")
    sources=(UI/"sources.js").read_text(encoding="utf-8")
    css=(UI/"app.css").read_text(encoding="utf-8")
    assert "sourceSet:[]" in app
    assert "selectInspectorSource" in app
    assert "← Previous" in app and "Next →" in app
    assert "openSource(source,index,sources)" in sources
    assert "openSource(sources[index],index,sources)" in sources
    assert ".source-nav" in css


def test_m19_live_activity_and_development_pipeline_are_present():
    app=(UI/"app.js").read_text(encoding="utf-8")
    css=(UI/"app.css").read_text(encoding="utf-8")
    assert "liveActivity(job)" in app
    assert "activityStep('Route'" in app
    assert "activityStep('Search'" in app
    assert "activityStep('Read'" in app
    assert "activityStep('Answer'" in app
    assert "developmentPipeline" in app
    assert "phaseNode('Plan'" in app
    assert "phaseNode('Implement'" in app
    assert "phaseNode('Verify'" in app
    assert ".activity-ribbon" in css
    assert ".phase-rail" in css


def test_m19_source_cards_surface_provenance_without_remote_image_urls():
    sources=(UI/"sources.js").read_text(encoding="utf-8")
    assert "function sourceDomain" in sources
    assert "source.published_at" in sources
    assert "source.search_rank" in sources
    assert "source.search_freshness" in sources
    assert "source-card-content" in sources
    assert "img.src=source.url" not in sources
    assert "img.src=source.source" not in sources


def test_m19_web_policy_is_visible_and_sent_to_chat_backend():
    html=(UI/"index.html").read_text(encoding="utf-8")
    app=(UI/"app.js").read_text(encoding="utf-8")
    assert 'id="network-policy"' in html
    assert 'id="web-policy-pill"' in html
    assert '<option value="AUTO">' in html
    assert "defaultNetworkPolicy" in app
    assert "mode==='research'?'AUTO':mode==='develop'?'OFF':'ASK'" in app
    assert "network_policy:$('#network-policy').value" in app
    assert "syncNetworkPolicy" in app


def test_m19_conversations_support_rename_and_delete():
    app=(UI/"app.js").read_text(encoding="utf-8")
    css=(UI/"app.css").read_text(encoding="utf-8")
    server=(ROOT/"src"/"reverend"/"workstation"/"server.py").read_text(encoding="utf-8")
    assert "renameConversation" in app
    assert "deleteConversation" in app
    assert "conversations/rename" in app
    assert "conversations/delete" in app
    assert "/api/conversations/rename" in server
    assert "/api/conversations/delete" in server
    assert ".conversation-actions" in css


def test_m19_renamed_title_survives_reopening():
    app=(UI/"app.js").read_text(encoding="utf-8")
    assert "openConversation(c.id,c.privacy_mode||'normal',c.title)" in app
    assert "async function openConversation(id,privacyMode='normal',title='')" in app
    assert "title||messages[0]?.content.slice(0,60)" in app


def test_m20_consolidated_workstation_shell_ports_new_gui_features():
    html=(UI/"index.html").read_text(encoding="utf-8")
    app=(UI/"app.js").read_text(encoding="utf-8")
    css=(UI/"app.css").read_text(encoding="utf-8")
    for identifier in (
        'id="sidebar-collapse"',
        'id="conversation-search"',
        'id="active-workflow"',
        'id="active-model"',
        'id="inspector-expand"',
        'id="workflow-help"',
    ):
        assert identifier in html
    assert '<option value="ASK" selected>' in html
    assert "function filterConversations" in app
    assert "function resizePrompt" in app
    assert "function updateTopbarMetadata" in app
    assert "function approveWebRetry" in app
    assert "network_approval_required" in app
    assert "html-preview" in app and "artifact-html" in app
    assert "reverend-sidebar-collapsed" in app
    assert ".sidebar-collapsed" in css
    assert "M20 consolidated workstation shell" in css


def test_m20_new_shell_preserves_accepted_m18_m19_features():
    app=(UI/"app.js").read_text(encoding="utf-8")
    html=(UI/"index.html").read_text(encoding="utf-8")
    assert 'src="/assets/diagrams.js"' in html
    assert 'src="/assets/sources.js"' in html
    assert "renderReverendDiagram" in app
    assert "sourceImageObjectUrl" in app
    assert "liveActivity(job)" in app
    assert "developmentPipeline" in app
    assert "renameConversation" in app
    assert "deleteConversation" in app
    assert "network_policy:$('#network-policy').value" in app


def test_gui_optimization_surfaces_bounded_observability_and_accessibility():
    html=(UI/"index.html").read_text(encoding="utf-8")
    app=(UI/"app.js").read_text(encoding="utf-8")
    sources=(UI/"sources.js").read_text(encoding="utf-8")
    css=(UI/"app.css").read_text(encoding="utf-8")
    assert 'id="context-usage"' in html
    assert 'id="privacy-pill"' in html
    assert "function contextUsageFromMetadata" in app
    assert "context_utilization_percent" in app
    assert "input_budget_tokens" in app
    assert "actual_provider_prompt_tokens" in app
    assert "physical_context_utilization_percent" in app
    assert "used/inputBudget*100" in app
    assert "used/windowSize" not in app
    assert "function syncPrivacy" in app
    assert "aria-current" in app
    assert "sourceEvidenceTags" in sources
    assert "source.source_transport==='fetched_page'" in sources
    assert ".source-evidence-tag" in css
    assert "prefers-reduced-motion:reduce" in css
    assert ":focus-visible" in css
