"""Hybrid retrieval: vector + full-text search, fused with RRF, then cross-encoder reranked.

Tenant isolation (CLAUDE.md rule 1): every query below filters on the collection owner's
user_id AND the collection_id in its WHERE clause. Results are never fetched first and
filtered afterwards, which would both leak data on a bug and let other tenants' chunks
crowd a user's own chunks out of the top-k.
"""

import logging
import time
import uuid
from collections.abc import Hashable, Sequence
from dataclasses import dataclass

from sqlalchemy import Text, cast, func, select, text
from sqlalchemy.dialects.postgresql import TSQUERY
from sqlalchemy.orm import Session

from app.config import get_settings
from app.embeddings import Embedder
from app.ingestion.chunking import with_heading
from app.models import Chunk, Document
from app.rag.reranker import Reranker

logger = logging.getLogger(__name__)

RRF_K = 60  # standard constant from the RRF paper; damps the influence of top ranks


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    page: int
    heading: str | None
    text: str
    score: float  # reranker logit (higher is more relevant); the RRF score when not reranking


@dataclass(frozen=True)
class RetrievalResult:
    chunks: list[RetrievedChunk]
    # True when even the best chunk is below retrieval_min_score: the caller should answer
    # "I couldn't find this in your notes" without calling the LLM (CLAUDE.md rule 5).
    low_confidence: bool


@dataclass(frozen=True)
class RetrievalOptions:
    """Knobs the app takes from settings and the Phase 7 ablations vary."""

    candidates: int  # per search method, and how many fused results get reranked
    top_k: int
    min_score: float
    use_vector: bool = True
    use_keyword: bool = True
    rerank: bool = True  # without it, RRF order is final and confidence can't be judged

    @classmethod
    def from_settings(cls) -> "RetrievalOptions":
        settings = get_settings()
        return cls(
            candidates=settings.retrieval_candidates,
            top_k=settings.retrieval_top_k,
            min_score=settings.retrieval_min_score,
        )


def retrieve(
    session: Session,
    embedder: Embedder,
    reranker: Reranker,
    *,
    owner_id: uuid.UUID,
    collection_id: uuid.UUID,
    question: str,
    options: RetrievalOptions | None = None,
) -> RetrievalResult:
    opts = options or RetrievalOptions.from_settings()
    n = opts.candidates
    tenant = (Chunk.user_id == owner_id, Chunk.collection_id == collection_id)
    started = time.perf_counter()

    vector_ids = (
        _vector_search(session, embedder.embed_query(question), tenant, n)
        if opts.use_vector
        else []
    )
    keyword_ids = _keyword_search(session, question, tenant, n) if opts.use_keyword else []
    fused = reciprocal_rank_fusion([vector_ids, keyword_ids])[:n]
    searched = time.perf_counter()

    rows = session.execute(
        select(Chunk, Document.filename)
        .join(Document, Document.id == Chunk.document_id)
        .where(*tenant, Chunk.id.in_(fused))
    ).all()
    if opts.rerank:
        scores = reranker.score(question, [with_heading(c.heading, c.text) for c, _ in rows])
    else:
        rank = {chunk_id: i for i, chunk_id in enumerate(fused, start=1)}
        scores = [1.0 / (RRF_K + rank[c.id]) for c, _ in rows]
    ranked = sorted(zip(rows, scores, strict=True), key=lambda pair: pair[1], reverse=True)
    chunks = [
        RetrievedChunk(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            document_title=filename,
            page=chunk.page,
            heading=chunk.heading,
            text=chunk.text,
            score=score,
        )
        for (chunk, filename), score in ranked[: opts.top_k]
    ]
    low_confidence = not chunks or (opts.rerank and chunks[0].score < opts.min_score)

    # IDs, counts and timings only: never the question or chunk text (CLAUDE.md rule 3).
    logger.info(
        "retrieval collection_id=%s vector=%d keyword=%d reranked=%d low_confidence=%s "
        "search_ms=%d rerank_ms=%d",
        collection_id,
        len(vector_ids),
        len(keyword_ids),
        len(rows) if opts.rerank else 0,
        low_confidence,
        (searched - started) * 1000,
        (time.perf_counter() - searched) * 1000,
    )
    return RetrievalResult(chunks=chunks, low_confidence=low_confidence)


def _vector_search(session: Session, query_vector, tenant, limit: int) -> list[uuid.UUID]:
    # With a WHERE filter, a plain HNSW scan returns the ef_search nearest chunks of ALL
    # tenants and then filters, which can leave fewer than `limit` rows. Iterative scans
    # (pgvector >= 0.8) keep walking the graph until enough rows pass the filter.
    session.execute(text("SET LOCAL hnsw.iterative_scan = 'relaxed_order'"))
    distance = Chunk.embedding.cosine_distance(query_vector)
    rows = session.execute(
        select(Chunk.id, distance.label("distance")).where(*tenant).order_by(distance).limit(limit)
    ).all()
    # relaxed_order may return rows slightly out of order; restore exact order.
    return [row.id for row in sorted(rows, key=lambda row: row.distance)]


def _keyword_search(session: Session, question: str, tenant, limit: int) -> list[uuid.UUID]:
    # plainto_tsquery ANDs every word, so "what does 3NF eliminate" would need all of them.
    # Rewrite its (already sanitized) output to OR; ts_rank_cd still favours chunks
    # matching more of the words, close together.
    query = cast(
        func.replace(cast(func.plainto_tsquery("english", question), Text), "&", "|"), TSQUERY
    )
    rank = func.ts_rank_cd(Chunk.tsv, query)
    return list(
        session.scalars(
            select(Chunk.id)
            .where(*tenant, Chunk.tsv.op("@@")(query))
            .order_by(rank.desc())
            .limit(limit)
        )
    )


def reciprocal_rank_fusion[T: Hashable](rankings: Sequence[Sequence[T]], k: int = RRF_K) -> list[T]:
    """Merge ranked lists by summing 1 / (k + rank). Uses ranks only, so the two searches'
    incomparable scores (cosine distance vs ts_rank) never need normalizing."""
    scores: dict[T, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    return sorted(scores, key=lambda item: scores[item], reverse=True)
