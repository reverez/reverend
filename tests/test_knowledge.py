from types import SimpleNamespace

from reverend.knowledge import KnowledgeFabric


class Scheduler:
    def __init__(self):
        self.calls = []

    def embed(self, texts):
        self.calls.append(list(texts))
        vectors = []
        for text in texts:
            value = text.lower()
            if value == "mercury planet":
                vectors.append([1.0, 0.0])
            elif "planet" in value and "records" not in value:
                vectors.append([0.95, 0.05])
            else:
                vectors.append([0.05, 0.95])
        return vectors


def rows():
    return [
        {
            "source": "zim://fixture/records",
            "source_title": "Mercury Records",
            "content": "Mercury planet music label and records.",
            "reference_method": "lexical",
            "relevance": 1.0,
        },
        {
            "source": "zim://fixture/planet",
            "source_title": "Mercury (planet)",
            "content": "Mercury is the smallest planet in the Solar System.",
            "reference_method": "title_index",
            "relevance": 0.5,
        },
    ]


def test_semantic_rerank_can_overturn_provider_rank(tmp_path):
    scheduler = Scheduler()
    fabric = KnowledgeFabric(tmp_path / "fabric.db")

    ranked = fabric.rerank(
        "mercury planet",
        rows(),
        scheduler=scheduler,
        limit=2,
    )

    assert [row["source"] for row in ranked] == [
        "zim://fixture/planet",
        "zim://fixture/records",
    ]
    assert ranked[0]["fabric_rank"] == 1
    assert ranked[0]["semantic_score"] > ranked[1]["semantic_score"]
    assert len(scheduler.calls) == 1
    assert len(scheduler.calls[0]) == 3


def test_lazy_cache_reuses_passage_embeddings(tmp_path):
    scheduler = Scheduler()
    fabric = KnowledgeFabric(tmp_path / "fabric.db")

    first = fabric.rerank(
        "mercury planet",
        rows(),
        scheduler=scheduler,
        limit=2,
    )
    second = fabric.rerank(
        "mercury planet",
        rows(),
        scheduler=scheduler,
        limit=2,
    )

    assert all(row["embedding_cache_hit"] is False for row in first)
    assert all(row["embedding_cache_hit"] is True for row in second)
    assert len(scheduler.calls) == 2
    assert len(scheduler.calls[0]) == 3
    assert scheduler.calls[1] == ["mercury planet"]
    assert fabric.cache.count() == 2


def test_model_budget_reserves_answer_call_and_skips_embedding(tmp_path):
    scheduler = Scheduler()
    scheduler.budget = SimpleNamespace(max_model_calls=1)
    scheduler.runs = []
    fabric = KnowledgeFabric(tmp_path / "fabric.db")

    ranked = fabric.rerank(
        "mercury planet",
        rows(),
        scheduler=scheduler,
        limit=2,
        reserve_model_calls=1,
    )

    assert scheduler.calls == []
    assert all(
        row["fabric_rerank_status"] == "skipped_model_budget"
        for row in ranked
    )
    assert all(row["semantic_score"] is None for row in ranked)


def test_empty_candidates_never_call_embedding(tmp_path):
    scheduler = Scheduler()
    fabric = KnowledgeFabric(tmp_path / "fabric.db")

    assert fabric.rerank(
        "mercury planet",
        [],
        scheduler=scheduler,
        limit=5,
    ) == []
    assert scheduler.calls == []


def test_cache_key_changes_when_passage_changes(tmp_path):
    scheduler = Scheduler()
    fabric = KnowledgeFabric(tmp_path / "fabric.db")
    initial = rows()

    fabric.rerank(
        "mercury planet",
        initial,
        scheduler=scheduler,
        limit=2,
    )
    changed = [dict(row) for row in initial]
    changed[1]["content"] += " It has a heavily cratered surface."

    reranked = fabric.rerank(
        "mercury planet",
        changed,
        scheduler=scheduler,
        limit=2,
    )

    by_source = {row["source"]: row for row in reranked}
    assert by_source["zim://fixture/records"]["embedding_cache_hit"] is True
    assert by_source["zim://fixture/planet"]["embedding_cache_hit"] is False


def test_embedding_failure_falls_back_without_losing_provenance(tmp_path):
    class Broken:
        def embed(self, texts):
            raise RuntimeError("offline")

    fabric = KnowledgeFabric(tmp_path / "fabric.db")
    ranked = fabric.rerank(
        "mercury planet",
        rows(),
        scheduler=Broken(),
        limit=2,
    )

    assert {row["source"] for row in ranked} == {
        "zim://fixture/records",
        "zim://fixture/planet",
    }
    assert all(
        row["fabric_rerank_status"] == "fallback_embedding_error"
        for row in ranked
    )


def test_wrapper_without_real_embed_skips_without_spending_budget(tmp_path):
    class Base:
        pass

    class Wrapper:
        def __init__(self):
            self._scheduler = Base()

        def embed(self, texts):
            raise AssertionError("delegating wrapper should be detected as unavailable")

    fabric = KnowledgeFabric(tmp_path / "fabric.db")
    ranked = fabric.rerank(
        "mercury planet",
        rows(),
        scheduler=Wrapper(),
        limit=2,
    )

    assert all(
        row["fabric_rerank_status"] == "skipped_embedding_unavailable"
        for row in ranked
    )
