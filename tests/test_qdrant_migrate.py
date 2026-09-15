from pathlib import Path
from types import SimpleNamespace

import pytest
from qdrant_client import models

from reverend.qdrant_migrate import migrate_collection


VECTOR_CONFIG = models.VectorParams(
    size=3,
    distance=models.Distance.COSINE,
)


class FakeClient:
    def __init__(
        self,
        records=None,
        *,
        exists=True,
        fail_upsert_call=None,
    ):
        self.records = list(records or [])
        self.exists = exists
        self.fail_upsert_call = fail_upsert_call
        self.upsert_calls = 0
        self.points = {}
        self.payload_schema = {
            "corpus": SimpleNamespace(
                data_type=models.PayloadSchemaType.KEYWORD
            )
        }

    def count(self, collection_name, exact=True):
        if self.records:
            count = len(self.records)
        else:
            count = len(self.points)

        return SimpleNamespace(count=count)

    def collection_exists(self, collection_name):
        return self.exists

    def get_collection(self, collection_name):
        return SimpleNamespace(
            config=SimpleNamespace(
                params=SimpleNamespace(
                    vectors=VECTOR_CONFIG
                )
            ),
            payload_schema=self.payload_schema,
        )

    def create_collection(
        self,
        collection_name,
        vectors_config,
    ):
        self.exists = True

    def create_payload_index(
        self,
        collection_name,
        field_name,
        field_schema,
        wait=True,
    ):
        return None

    def scroll(
        self,
        *,
        collection_name,
        limit,
        offset,
        with_payload,
        with_vectors,
    ):
        start = int(offset or 0)
        end = min(start + limit, len(self.records))

        batch = self.records[start:end]

        next_offset = (
            end
            if end < len(self.records)
            else None
        )

        return batch, next_offset

    def upsert(
        self,
        *,
        collection_name,
        points,
        wait=True,
    ):
        self.upsert_calls += 1

        if self.upsert_calls == self.fail_upsert_call:
            raise RuntimeError("simulated interruption")

        for point in points:
            self.points[str(point.id)] = point


def record(number):
    return SimpleNamespace(
        id=number,
        vector=[
            float(number),
            0.0,
            1.0,
        ],
        payload={
            "content": f"chunk {number}",
            "corpus": "test",
        },
    )


def test_migration_copies_vectors_and_is_idempotent(
    tmp_path: Path,
):
    source = FakeClient(
        [record(1), record(2), record(3)]
    )

    target = FakeClient(
        exists=False,
    )

    state = tmp_path / "migration.json"

    report = migrate_collection(
        source,
        target,
        source_collection="source",
        target_collection="target",
        state_path=state,
        batch_size=2,
    )

    assert report["complete"] is True
    assert report["source_points"] == 3
    assert report["target_points"] == 3
    assert set(target.points) == {"1", "2", "3"}

    second = migrate_collection(
        source,
        target,
        source_collection="source",
        target_collection="target",
        state_path=state,
        batch_size=2,
    )

    assert second["complete"] is True
    assert second["resumed"] is True
    assert len(target.points) == 3


def test_migration_resumes_after_interruption(
    tmp_path: Path,
):
    source = FakeClient(
        [
            record(1),
            record(2),
            record(3),
            record(4),
            record(5),
        ]
    )

    target = FakeClient(
        exists=False,
        fail_upsert_call=2,
    )

    state = tmp_path / "migration.json"

    with pytest.raises(
        RuntimeError,
        match="simulated interruption",
    ):
        migrate_collection(
            source,
            target,
            source_collection="source",
            target_collection="target",
            state_path=state,
            batch_size=2,
        )

    assert set(target.points) == {"1", "2"}

    target.fail_upsert_call = None

    report = migrate_collection(
        source,
        target,
        source_collection="source",
        target_collection="target",
        state_path=state,
        batch_size=2,
    )

    assert report["complete"] is True
    assert report["resumed"] is True
    assert set(target.points) == {
        "1",
        "2",
        "3",
        "4",
        "5",
    }
