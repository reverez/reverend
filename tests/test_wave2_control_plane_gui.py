from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_control_plane_route_is_read_only_get_surface():
    server=(ROOT/"src/reverend/workstation/server.py").read_text(encoding="utf-8")
    assert "path=='/api/control-plane'" in server
    get_block=server.split("def do_GET",1)[1].split("def do_POST",1)[0]
    post_block=server.split("def do_POST",1)[1]
    assert "/api/control-plane" in get_block
    assert "/api/control-plane" not in post_block

def test_control_plane_view_is_shipped_in_local_ui():
    html=(ROOT/"src/reverend/ui/index.html").read_text(encoding="utf-8")
    script=(ROOT/"src/reverend/ui/app.js").read_text(encoding="utf-8")
    assert 'data-view="control-plane"' in html
    assert 'id="control-plane-view"' in html
    assert "await api('control-plane')" in script
    assert "read_only" in script
    for label in ("Workflows & tasks","Specialists","Models & resources","Artifacts","Verification"):
        assert label in script

def test_control_plane_service_uses_authoritative_data_root_store():
    service=(ROOT/"src/reverend/workstation/service.py").read_text(encoding="utf-8")
    assert "ControlPlaneStore(self.root/'control-plane.db')" in service
    assert "control_plane_snapshot" in service
