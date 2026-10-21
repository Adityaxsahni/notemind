import math

import pytest

from ml.eval.metrics import (
    any_hit_at_k,
    best_threshold,
    dedupe,
    ndcg_at_k,
    percentile,
    recall_at_k,
    reciprocal_rank,
    refusal_metrics,
)

A1, A2, A3, B1 = ("a.pdf", 1), ("a.pdf", 2), ("a.pdf", 3), ("b.pdf", 1)


def test_dedupe_keeps_first_occurrence_order():
    assert dedupe([A2, A1, A2, A3, A1]) == [A2, A1, A3]


def test_recall_counts_pages_not_chunks():
    ranking = [A2, A2, A2, A1]  # three chunks of page 2 must not push page 1 out of top 2
    assert recall_at_k(ranking, {A1}, 2) == 1.0
    assert recall_at_k(ranking, {A1}, 1) == 0.0


def test_recall_for_multi_hop_is_fractional():
    assert recall_at_k([A1, B1, A3], {A1, A2}, 3) == 0.5
    assert recall_at_k([A1, A2], {A1, A2}, 2) == 1.0


def test_recall_requires_gold():
    with pytest.raises(ValueError):
        recall_at_k([A1], set(), 1)


def test_any_hit():
    assert any_hit_at_k([B1, A2], {A1, A2}, 2) == 1.0
    assert any_hit_at_k([B1, A2], {A1, A2}, 1) == 0.0


def test_reciprocal_rank():
    assert reciprocal_rank([B1, A1, A1, A2], {A2}) == pytest.approx(1 / 3)
    assert reciprocal_rank([B1], {A2}) == 0.0


def test_ndcg_perfect_and_partial():
    assert ndcg_at_k([A1, A2, B1], {A1, A2}, 3) == pytest.approx(1.0)
    worse = ndcg_at_k([B1, A1, A2], {A1, A2}, 3)
    assert 0 < worse < 1
    assert ndcg_at_k([B1, A3], {A1}, 2) == 0.0


def test_refusal_metrics():
    scores = [5.0, 2.0, -8.0, -12.0]
    answerable = [True, True, False, False]
    m = refusal_metrics(scores, answerable, threshold=-6.0)
    assert m == {"refusal_recall": 1.0, "false_refusal": 0.0, "balanced_accuracy": 1.0}
    m = refusal_metrics(scores, answerable, threshold=3.0)
    assert m["false_refusal"] == 0.5


def test_refusal_metrics_without_unanswerable_questions():
    assert math.isnan(refusal_metrics([1.0], [True], 0.0)["refusal_recall"])


def test_best_threshold_lands_in_the_gap():
    scores = [5.0, -3.0, -10.0, -12.0]
    threshold, m = best_threshold(scores, [True, True, False, False])
    assert -10.0 < threshold < -3.0
    assert m["balanced_accuracy"] == 1.0


def test_percentile():
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert percentile(values, 50) == 3.0
    assert percentile(values, 100) == 5.0
    assert percentile([7.0], 95) == 7.0
