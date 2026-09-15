from pathlib import Path

from reverend.metadata import WINDOWS_EPOCH_TICKS, bulk_metadata, parse_manifest, windows_path
from reverend import sync
from test_sync import test_sync_baseline_and_change_detection as check_baseline


def test_manifest_unicode_and_integer_timestamps():
    root = Path('/mnt/c/Notes with spaces')
    stamp = 1780000000123456700
    raw = f'C:\\Notes with spaces\\Moiré Åström.md\t42\t{WINDOWS_EPOCH_TICKS + stamp // 100}\r\n'
    result = parse_manifest(raw.encode('utf-8-sig'), root)
    assert result[str(root / 'Moiré Åström.md')] == (42, stamp)
    assert windows_path(Path('/tmp/test')) is None
    assert bulk_metadata(Path('/tmp/test')) == ({}, 'stat', None)


def test_provider_does_not_add_membership(tmp_path, monkeypatch):
    def provider(root):
        metadata = {str(p): (p.stat().st_size, p.stat().st_mtime_ns) for p in root.glob('*.md')}
        metadata[str(root / 'ignored.md')] = (42, 123)
        return metadata, 'powershell', None
    monkeypatch.setattr(sync, 'bulk_metadata', provider)
    check_baseline(tmp_path)


def test_powershell_unavailable(monkeypatch):
    monkeypatch.setattr('reverend.metadata.shutil.which', lambda name: None)
    result = bulk_metadata(Path('/mnt/c/Notes'))
    assert result == ({}, 'stat', 'PowerShell unavailable')
