#!/usr/bin/env python3
"""Regenerate focused Mermaid subsystem views from the canonical mega-diagram."""

from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "system-complete-mermaid-diagram.mmd"
OUT = HERE / "Subsystems"

text = SOURCE.read_text()
styles_start = text.index("%% STYLES")
root_start = text.index("%% ROOT")
styles = text[styles_start:root_start].strip()

matches = list(re.finditer(r"^%%\s+(\d+)\.\s+(.+)$", text, flags=re.MULTILINE))
if len(matches) < 35:
    raise SystemExit(f"Unexpected section count: {len(matches)}")

def slugify(value: str) -> str:
    value = value.lower().replace("&", "and").replace("/", " ").replace("–", "-").replace("—", "-")
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return re.sub(r"-+", "-", value).strip("-")

def section_slice(index: int) -> str:
    match = matches[index]
    start = text.rfind("%% =========================================================", 0, match.start())
    if start < 0:
        start = match.start()
    if index + 1 < len(matches):
        nxt = matches[index + 1]
        end = text.rfind("%% =========================================================", 0, nxt.start())
        if end < start:
            end = nxt.start()
    else:
        end = len(text)
    return text[start:end].strip()

OUT.mkdir(parents=True, exist_ok=True)

expected = set()
for index, match in enumerate(matches):
    number = int(match.group(1))
    title = match.group(2).strip()
    if number > 34:
        continue
    filename = f"{number:02d}-{slugify(title)}.mmd"
    expected.add(filename)
    body = section_slice(index)
    content = f"""flowchart TB

{styles}

ROOT["REVEREND CLOUD v1<br/>Focused subsystem view"]:::authority

%% =========================================================
%% FOCUSED VIEW
%% Source: ../system-complete-mermaid-diagram.mmd
%% Section {number}: {title}
%% External cross-subsystem references may render as compact interface nodes.
%% =========================================================

{body}
"""
    (OUT / filename).write_text(content)

for path in OUT.glob("*.mmd"):
    if path.name not in expected:
        path.unlink()

print(f"Generated {len(expected)} subsystem diagrams in {OUT}")
