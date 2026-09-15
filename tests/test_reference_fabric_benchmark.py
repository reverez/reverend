from reverend.benchmarks.reference_fabric import (
    expected_rank,
    normalize_title,
    rank_metrics,
    run_reference_fabric_benchmark,
)


def test_title_normalization_and_rank():
    rows = [
        {'source_title': 'Mercury Records'},
        {'source_title': 'Mercury (planet)'},
    ]
    assert normalize_title('Mercury_(planet)') == 'mercury planet'
    assert expected_rank(rows, ['Mercury (planet)'], limit=5) == 2
    assert expected_rank(rows, ['Venus'], limit=5) is None


def test_rank_metrics_are_bounded():
    metrics = rank_metrics([1, 2, None, 5], cutoff=5)
    assert metrics == {
        'count': 4,
        'hit_at_1': 0.25,
        'hit_at_k': 0.75,
        'mrr_at_k': 0.425,
    }


def test_reference_fabric_benchmark_compares_baseline_cold_and_warm():
    class Provider:
        def retrieve(self, query, *, mode, limit):
            assert mode == 'hybrid'
            assert limit == 12
            return [
                {
                    'source': 'zim://wrong',
                    'source_title': 'Mercury Records',
                    'content': 'A music label.',
                },
                {
                    'source': 'zim://right',
                    'source_title': 'Mercury (planet)',
                    'content': 'Mercury is a planet.',
                },
            ]

    class Fabric:
        def __init__(self):
            self.calls = 0

        def rerank(self, query, rows, *, scheduler, limit, reserve_model_calls):
            self.calls += 1
            assert reserve_model_calls == 0
            ordered = [dict(rows[1]), dict(rows[0])]
            for row in ordered:
                row['fabric_rerank_status'] = 'semantic_embedding'
                row['embedding_cache_hit'] = self.calls > 1
            return ordered[:limit]

    report = run_reference_fabric_benchmark(
        Provider(),
        Fabric(),
        object(),
        [{
            'case_id': 'mercury',
            'query': 'mercury planet',
            'expected_titles': ['Mercury (planet)'],
        }],
        limit=2,
    )

    assert report['baseline']['hit_at_1'] == 0.0
    assert report['baseline']['hit_at_k'] == 1.0
    assert report['reranked']['hit_at_1'] == 1.0
    assert report['quality_delta']['hit_at_1'] == 1.0
    assert report['quality_delta']['hit_at_k'] == 0.0
    assert report['cache']['cold_hits'] == 0
    assert report['cache']['warm_hits'] == 2
    assert report['cache']['passage_entries'] is None
    assert report['results'][0]['baseline_rank'] == 2
    assert report['results'][0]['reranked_rank'] == 1
