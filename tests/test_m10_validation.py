from reverend.benchmarks.m10_validation import quality_decision


def test_quality_decision_requires_non_regression_and_improvement():
    improved = quality_decision({
        'baseline': {'hit_at_1': 0.5, 'hit_at_k': 0.8, 'mrr_at_k': 0.6},
        'reranked': {'hit_at_1': 0.6, 'hit_at_k': 0.8, 'mrr_at_k': 0.65},
    })
    assert improved == {
        'quality_non_regression': True,
        'quality_improved': True,
        'recommended_default': True,
    }

    equal = quality_decision({
        'baseline': {'hit_at_1': 0.5, 'hit_at_k': 0.8, 'mrr_at_k': 0.6},
        'reranked': {'hit_at_1': 0.5, 'hit_at_k': 0.8, 'mrr_at_k': 0.6},
    })
    assert equal['quality_non_regression'] is True
    assert equal['quality_improved'] is False
    assert equal['recommended_default'] is False

    regressed = quality_decision({
        'baseline': {'hit_at_1': 0.5, 'hit_at_k': 0.8, 'mrr_at_k': 0.6},
        'reranked': {'hit_at_1': 0.6, 'hit_at_k': 0.7, 'mrr_at_k': 0.65},
    })
    assert regressed['quality_non_regression'] is False
    assert regressed['recommended_default'] is False
