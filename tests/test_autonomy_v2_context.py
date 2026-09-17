from __future__ import annotations

import json
from pathlib import Path

import pytest

from reverend.autonomy_v2.context import ContextBuilder, UnsafeRepositoryPath


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "Documentation" / "Design").mkdir(parents=True)
    (root / "src" / "reverend").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "Documentation" / "Design" / "D0.md").write_text("# D0\n", encoding="utf-8")
    (root / "src" / "reverend" / "contracts.py").write_text("SCHEMA_VERSION = 1\n", encoding="utf-8")
    (root / "tests" / "test_contracts.py").write_text("def test_ok(): assert True\n", encoding="utf-8")
    return root


def test_context_packet_only_contains_verified_relative_paths(tmp_path):
    root = _repo(tmp_path)
    builder = ContextBuilder(root)
    packet = builder.build(
        issue_number=66,
        title="Common IDs",
        milestone="C0",
        base_commit="a" * 40,
        requirements=["opaque UUID4 identifiers", "schema_version = 1"],
        design_sources=["Documentation/Design/D0.md"],
        candidate_source_files=["src/reverend/contracts.py"],
        candidate_tests=["tests/test_contracts.py"],
        acceptance=["targeted tests pass"],
    )

    assert packet.design_sources == ("Documentation/Design/D0.md",)
    assert packet.candidate_source_files == ("src/reverend/contracts.py",)


def test_context_builder_rejects_escape_absolute_and_missing_paths(tmp_path):
    root = _repo(tmp_path)
    builder = ContextBuilder(root)

    for bad_path in ("../outside.md", "/etc/passwd"):
        with pytest.raises(UnsafeRepositoryPath):
            builder.build(
                issue_number=66,
                title="Common IDs",
                milestone="C0",
                base_commit="a" * 40,
                requirements=[],
                design_sources=[bad_path],
            )

    with pytest.raises(FileNotFoundError):
        builder.build(
            issue_number=66,
            title="Common IDs",
            milestone="C0",
            base_commit="a" * 40,
            requirements=[],
            design_sources=["Documentation/Design/does-not-exist.md"],
        )


def test_packet_write_is_atomic_and_can_use_separate_runtime_root(tmp_path):
    root = _repo(tmp_path)
    runtime = tmp_path / "runtime"
    builder = ContextBuilder(root)
    packet = builder.build(
        issue_number=66,
        title="Common IDs",
        milestone="C0",
        base_commit="a" * 40,
        requirements=["schema_version = 1"],
        design_sources=["Documentation/Design/D0.md"],
    )

    destination = runtime / "packets" / "issue-66.json"
    written = builder.write_atomic(packet, destination, destination_root=runtime)
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["issue_number"] == 66
    assert payload["design_sources"] == ["Documentation/Design/D0.md"]
    assert list(destination.parent.glob("*.tmp")) == []

    with pytest.raises(UnsafeRepositoryPath):
        builder.write_atomic(
            packet,
            tmp_path / "escaped.json",
            destination_root=runtime,
        )
