from pathlib import Path
from reverend.cli import text_chunks

def test_markdown_heading_chunks(tmp_path: Path):
    source = tmp_path / "sample.md"
    source.write_text("# Alpha\nFirst fact.\n## Beta\nSecond fact.", encoding="utf-8")
    chunks = text_chunks(source)
    assert [item[0] for item in chunks] == ["Alpha", "Beta"]
    assert "Second fact" in chunks[1][1]
