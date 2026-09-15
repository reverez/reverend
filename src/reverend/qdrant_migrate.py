"""Safe, resumable migration from embedded Qdrant to Qdrant Server."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable

from qdrant_client import QdrantClient, models

from .config import COLLECTION, DATA_ROOT, QDRANT_PATH


DEFAULT_TARGET_URL = "http://127.0.0.1:6333"
DEFAULT_TARGET_COLLECTION = "local_knowledge_v3"
DEFAULT_STATE_PATH = (
    DATA_ROOT / "migrations" / "qdrant-v2-to-v3.json"
)


def _model_value(value: Any) -> Any:
    """Convert pydantic/Qdrant config objects to stable Python data."""
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "dict"):
        return value.dict()
    return value


def _json_offset(value: Any) -> str | int | None:
    if value is None or isinstance(value, (str, int)):
        return value
    return str(value)


def _write_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(state, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    os.replace(temporary, path)


def _read_state(path: Path) -> dict | None:
    if not path.exists():
        return None

    return json.loads(path.read_text(encoding="utf-8"))


def _ensure_target_collection(
    source: QdrantClient,
    target: QdrantClient,
    source_collection: str,
    target_collection: str,
) -> None:
    """
    Create the target collection from source vector configuration.

    Existing collections are never deleted. Vector configuration must match.
    Payload indexes are copied where possible.
    """
    source_info = source.get_collection(source_collection)
    source_vectors = source_info.config.params.vectors

    if target.collection_exists(target_collection):
        target_info = target.get_collection(target_collection)

        if (
            _model_value(target_info.config.params.vectors)
            != _model_value(source_vectors)
        ):
            raise RuntimeError(
                "Target collection exists with incompatible "
                "vector configuration."
            )
    else:
        target.create_collection(
            collection_name=target_collection,
            vectors_config=source_vectors,
        )

    source_schema = source_info.payload_schema or {}
    target_schema = (
        target.get_collection(target_collection).payload_schema or {}
    )

    for field_name, schema in source_schema.items():
        if field_name in target_schema:
            continue

        data_type = getattr(schema, "data_type", None)
        if data_type is None:
            continue

        target.create_payload_index(
            collection_name=target_collection,
            field_name=field_name,
            field_schema=data_type,
            wait=True,
        )


def migrate_collection(
    source: QdrantClient,
    target: QdrantClient,
    *,
    source_collection: str,
    target_collection: str,
    state_path: Path,
    batch_size: int = 256,
    target_url: str = DEFAULT_TARGET_URL,
    reset_state: bool = False,
    progress: Callable[[dict], None] | None = None,
) -> dict:
    """
    Copy one Qdrant collection without re-embedding.

    Properties:
    - source is never modified
    - target writes are idempotent upserts
    - vectors and payloads are copied
    - progress is checkpointed after every successful batch
    - interruption resumes from the last persisted scroll offset
    """
    if batch_size < 1:
        raise ValueError("batch_size must be positive")

    if reset_state and state_path.exists():
        state_path.unlink()

    source_count = source.count(
        source_collection,
        exact=True,
    ).count

    _ensure_target_collection(
        source,
        target,
        source_collection,
        target_collection,
    )

    state = _read_state(state_path)

    if state is not None:
        expected = {
            "source_collection": source_collection,
            "target_collection": target_collection,
        }

        for key, expected_value in expected.items():
            if state.get(key) != expected_value:
                raise RuntimeError(
                    f"Migration state {key} mismatch: "
                    f"{state.get(key)!r} != {expected_value!r}"
                )

        recorded_count = state.get("source_count")

        if (
            recorded_count is not None
            and int(recorded_count) != source_count
        ):
            raise RuntimeError(
                "Source collection changed since migration began: "
                f"{recorded_count} -> {source_count}"
            )

        if state.get("complete"):
            target_count = target.count(
                target_collection,
                exact=True,
            ).count

            if target_count != source_count:
                raise RuntimeError(
                    "Migration state says complete but target count "
                    f"is {target_count}, expected {source_count}."
                )

            return {
                "source_collection": source_collection,
                "target_collection": target_collection,
                "source_points": source_count,
                "target_points": target_count,
                "processed_points": int(
                    state.get("processed_points", source_count)
                ),
                "batches": int(state.get("batches", 0)),
                "complete": True,
                "resumed": True,
                "state_path": str(state_path),
            }

    resumed = state is not None

    if state is None:
        state = {
            "version": 1,
            "source_collection": source_collection,
            "target_collection": target_collection,
            "target_url": target_url,
            "source_count": source_count,
            "next_offset": None,
            "processed_points": 0,
            "batches": 0,
            "complete": False,
        }

        _write_state(state_path, state)

    offset = state.get("next_offset")
    processed = int(state.get("processed_points", 0))
    batches = int(state.get("batches", 0))

    while True:
        records, next_offset = source.scroll(
            collection_name=source_collection,
            limit=batch_size,
            offset=offset,
            with_payload=True,
            with_vectors=True,
        )

        if not records:
            break

        points = [
            models.PointStruct(
                id=record.id,
                vector=record.vector,
                payload=record.payload or {},
            )
            for record in records
        ]

        target.upsert(
            collection_name=target_collection,
            points=points,
            wait=True,
        )

        processed += len(records)
        batches += 1

        state.update(
            {
                "next_offset": _json_offset(next_offset),
                "processed_points": processed,
                "batches": batches,
            }
        )

        _write_state(state_path, state)

        if progress is not None:
            progress(
                {
                    "processed_points": processed,
                    "source_points": source_count,
                    "batches": batches,
                    "next_offset": state["next_offset"],
                }
            )

        if next_offset is None:
            break

        offset = next_offset

    final_source_count = source.count(
        source_collection,
        exact=True,
    ).count

    if final_source_count != source_count:
        raise RuntimeError(
            "Source collection changed during migration: "
            f"{source_count} -> {final_source_count}"
        )

    target_count = target.count(
        target_collection,
        exact=True,
    ).count

    complete = target_count == source_count

    state.update(
        {
            "source_count": source_count,
            "target_count": target_count,
            "complete": complete,
            "next_offset": None if complete else state.get(
                "next_offset"
            ),
        }
    )

    _write_state(state_path, state)

    if not complete:
        raise RuntimeError(
            "Migration finished scrolling but point counts differ: "
            f"source={source_count}, target={target_count}"
        )

    return {
        "source_collection": source_collection,
        "target_collection": target_collection,
        "source_points": source_count,
        "target_points": target_count,
        "processed_points": processed,
        "batches": batches,
        "complete": True,
        "resumed": resumed,
        "state_path": str(state_path),
    }


def command_migrate_qdrant(
    *,
    target_url: str = DEFAULT_TARGET_URL,
    target_collection: str = DEFAULT_TARGET_COLLECTION,
    source_collection: str = COLLECTION,
    batch_size: int = 256,
    state_path: str | Path | None = None,
    reset_state: bool = False,
) -> int:
    migration_state = (
        Path(state_path)
        if state_path is not None
        else DEFAULT_STATE_PATH
    )

    source = QdrantClient(path=str(QDRANT_PATH))
    target = QdrantClient(
        url=target_url,
        timeout=120,
    )

    def show_progress(report: dict) -> None:
        processed = report["processed_points"]
        total = report["source_points"]

        if (
            report["batches"] == 1
            or report["batches"] % 25 == 0
            or processed >= total
        ):
            percentage = (
                100.0 * processed / total
                if total
                else 100.0
            )

            print(
                f"[qdrant-migrate] "
                f"{processed}/{total} "
                f"({percentage:.1f}%) "
                f"batches={report['batches']}"
            )

    try:
        result = migrate_collection(
            source,
            target,
            source_collection=source_collection,
            target_collection=target_collection,
            state_path=migration_state,
            batch_size=batch_size,
            target_url=target_url,
            reset_state=reset_state,
            progress=show_progress,
        )

        print(json.dumps(result, indent=2))
        return 0

    finally:
        source.close()
        target.close()
