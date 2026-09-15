"""Compatibility entrypoint for the safe, document-batched ingestion path."""
from pathlib import Path
from .sync import ingest_path


def ingest_bulk(root: Path, trust: str, corpus: str) -> dict:
    return ingest_path(root, trust, corpus)
