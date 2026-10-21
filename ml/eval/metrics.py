"""Retrieval and refusal metrics. Pure functions over (document, page) rankings.

Relevance is page-level: a retrieved chunk is relevant if its page is a gold page. A ranking
is first de-duplicated by page (several chunks of one page count once), because users get
page citations and a page cited twice adds nothing.
"""

import math
import statistics
from collections.abc import Sequence
from itertools import pairwise

import numpy as np

Page = tuple[str, int]


def dedupe(ranking: Sequence[Page]) -> list[Page]:
    seen: set[Page] = set()
    return [p for p in ranking if not (p in seen or seen.add(p))]


def recall_at_k(ranking: Sequence[Page], gold: set[Page], k: int) -> float:
    """Fraction of gold pages in the top k. For single-page questions this is hit@k."""
    if not gold:
        raise ValueError("recall is undefined without gold pages")
    return len(set(dedupe(ranking)[:k]) & gold) / len(gold)


def any_hit_at_k(ranking: Sequence[Page], gold: set[Page], k: int) -> float:
    """1 if any acceptable page is in the top k (questions that several pages answer)."""
    return float(bool(set(dedupe(ranking)[:k]) & gold))


def reciprocal_rank(ranking: Sequence[Page], gold: set[Page]) -> float:
    for rank, page in enumerate(dedupe(ranking), start=1):
        if page in gold:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(ranking: Sequence[Page], gold: set[Page], k: int) -> float:
    """Binary-relevance nDCG: rewards relevant pages near the top."""
    ranked = dedupe(ranking)[:k]
    dcg = sum(1.0 / math.log2(i + 2) for i, page in enumerate(ranked) if page in gold)
    ideal = sum(1.0 / math.log2(i + 2) for i in range(min(len(gold), k)))
    return dcg / ideal


def refusal_metrics(
    best_scores: Sequence[float], answerable: Sequence[bool], threshold: float
) -> dict[str, float]:
    """How a confidence cutoff on the top reranker score separates the two groups.

    refusal_recall: unanswerable questions correctly flagged as "not in your notes".
    false_refusal: answerable questions wrongly flagged (the student gets no answer).
    """
    flagged = [score < threshold for score in best_scores]
    unanswerable = [f for f, a in zip(flagged, answerable, strict=True) if not a]
    answerable_flags = [f for f, a in zip(flagged, answerable, strict=True) if a]
    refusal_recall = sum(unanswerable) / len(unanswerable) if unanswerable else math.nan
    false_refusal = sum(answerable_flags) / len(answerable_flags) if answerable_flags else math.nan
    return {
        "refusal_recall": refusal_recall,
        "false_refusal": false_refusal,
        "balanced_accuracy": (refusal_recall + 1 - false_refusal) / 2,
    }


def best_threshold(
    best_scores: Sequence[float], answerable: Sequence[bool]
) -> tuple[float, dict[str, float]]:
    """The cutoff with the highest balanced accuracy; ties go to the lowest false-refusal
    rate (refusing a covered question is worse than a hedged answer), then to the midpoint
    of the gap between neighbouring scores so the cutoff isn't fitted to one example."""
    values = sorted(set(best_scores))
    candidates = [values[0] - 1.0] + [(a + b) / 2 for a, b in pairwise(values)] + [values[-1] + 1.0]
    scored = [(t, refusal_metrics(best_scores, answerable, t)) for t in candidates]
    return max(scored, key=lambda tm: (tm[1]["balanced_accuracy"], -tm[1]["false_refusal"]))


def percentile(values: Sequence[float], q: float) -> float:
    return float(np.percentile(values, q))


def mean(values: Sequence[float]) -> float:
    return statistics.fmean(values) if values else math.nan
