"""Retrieval experiments: run each question through the app's retriever under a variant
and score the ranked pages against the gold labels."""

import math
import time
from dataclasses import asdict, dataclass, field

from sqlalchemy.orm import Session

from app.embeddings import Embedder
from app.rag.reranker import Reranker
from app.rag.retriever import RetrievalOptions, retrieve

from .dataset import Question
from .index import COMBINED, ChunkConfig, CourseIndex
from .metrics import (
    any_hit_at_k,
    best_threshold,
    mean,
    ndcg_at_k,
    percentile,
    recall_at_k,
    reciprocal_rank,
    refusal_metrics,
)

KS = (1, 3, 6)

# Pinned like the production models: a re-pushed checkpoint can't change results silently.
RERANKERS = {
    "minilm-l6": (
        "cross-encoder/ms-marco-MiniLM-L6-v2",
        "233902d25c440f23af6f7d6e94d2946bac0bee0a",  # pragma: allowlist secret
    ),
    "bge-base": (
        "BAAI/bge-reranker-base",
        "2cfc18c9415c912f9d8155881c133215df768a70",  # pragma: allowlist secret
    ),
}


@dataclass(frozen=True)
class Variant:
    name: str
    chunks: ChunkConfig = field(default_factory=lambda: ChunkConfig(400, 60))
    candidates: int = 30
    top_k: int = 6
    use_vector: bool = True
    use_keyword: bool = True
    rerank: bool = True
    reranker: str = "minilm-l6"
    combined: bool = False  # all courses in one collection

    def options(self, min_score: float) -> RetrievalOptions:
        return RetrievalOptions(
            candidates=self.candidates,
            top_k=self.top_k,
            min_score=min_score,
            use_vector=self.use_vector,
            use_keyword=self.use_keyword,
            rerank=self.rerank,
        )

    def describe(self) -> dict:
        data = asdict(self)
        data["chunks"] = self.chunks.label
        return data


def recall(question: Question, ranking: list[tuple[str, int]], k: int) -> float:
    """Single-page questions accept any gold page; multi-hop needs all of them."""
    if question.type == "multi_hop":
        return recall_at_k(ranking, question.gold_pages, k)
    return any_hit_at_k(ranking, question.gold_pages, k)


def run_variant(
    session: Session,
    embedder: Embedder,
    reranker: Reranker,
    variant: Variant,
    questions: list[Question],
    indexes: dict[str, CourseIndex],
    *,
    min_score: float,
) -> dict:
    options = variant.options(min_score)
    rows = []
    for q in questions:
        index = indexes[COMBINED] if variant.combined else indexes[q.course]
        started = time.perf_counter()
        result = retrieve(
            session,
            embedder,
            reranker,
            owner_id=index.owner_id,
            collection_id=index.collection_id,
            question=q.question,
            options=options,
        )
        latency = time.perf_counter() - started
        session.rollback()  # end the transaction (and its SET LOCAL) between questions
        ranking = [(c.document_title, c.page) for c in result.chunks]
        rows.append(
            {
                "id": q.id,
                "type": q.type,
                "ranking": ranking,
                "best_score": result.chunks[0].score if result.chunks else -math.inf,
                "low_confidence": result.low_confidence,
                "latency_s": latency,
                **(
                    {
                        **{f"recall@{k}": recall(q, ranking, k) for k in KS},
                        "mrr": reciprocal_rank(ranking, q.gold_pages),
                        "ndcg@6": ndcg_at_k(ranking, q.gold_pages, 6),
                    }
                    if q.gold
                    else {}
                ),
            }
        )
    return {
        "variant": variant.describe(),
        "metrics": summarize(rows, variant, min_score),
        "questions": rows,
    }


def summarize(rows: list[dict], variant: Variant, min_score: float) -> dict:
    answerable = [r for r in rows if r["type"] != "unanswerable"]
    summary: dict = {f"recall@{k}": mean([r[f"recall@{k}"] for r in answerable]) for k in KS} | {
        "mrr": mean([r["mrr"] for r in answerable]),
        "ndcg@6": mean([r["ndcg@6"] for r in answerable]),
        "multi_hop_recall@6": mean([r["recall@6"] for r in answerable if r["type"] == "multi_hop"]),
        "latency_p50_s": percentile([r["latency_s"] for r in rows], 50),
        "latency_p95_s": percentile([r["latency_s"] for r in rows], 95),
        "questions": len(rows),
    }
    if variant.rerank:
        scores = [r["best_score"] for r in rows]
        is_answerable = [r["type"] != "unanswerable" for r in rows]
        at_default = refusal_metrics(scores, is_answerable, min_score)
        threshold, at_best = best_threshold(scores, is_answerable)
        summary |= {
            "refusal_recall": at_default["refusal_recall"],
            "false_refusal": at_default["false_refusal"],
            "best_threshold": threshold,
            "best_threshold_balanced_accuracy": at_best["balanced_accuracy"],
        }
    return summary
