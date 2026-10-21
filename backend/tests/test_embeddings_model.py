"""Checks against the real bge-small model. Run with `uv run pytest -m slow` (~130 MB download)."""

import numpy as np
import pytest

from app.embeddings import get_embedder
from app.models import EMBEDDING_DIM

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def embedder():
    return get_embedder()


def test_document_vectors_are_normalized_and_sized_for_the_column(embedder):
    vectors = embedder.embed_documents(["Third normal form.", "Two-phase locking."])
    assert vectors.shape == (2, EMBEDDING_DIM)
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=1e-5)


def test_query_is_closest_to_the_relevant_passage(embedder):
    passages = embedder.embed_documents(
        [
            "Normalization\n3NF removes transitive dependencies between non-key attributes.",
            "Photosynthesis converts light energy into chemical energy in plants.",
            "Two-phase locking guarantees conflict-serializable schedules.",
        ]
    )
    query = embedder.embed_query("what does third normal form eliminate?")
    assert query.shape == (EMBEDDING_DIM,)
    assert int(np.argmax(passages @ query)) == 0


def test_token_count_uses_the_model_tokenizer(embedder):
    # WordPiece splits rare words, so tokens != words; no [CLS]/[SEP] counted.
    assert embedder.count_tokens("Normalization") >= 1
    assert embedder.count_tokens("transitive dependencies") > 2
    assert embedder.count_tokens("") == 0


def test_reranker_separates_relevant_from_off_topic_with_default_threshold():
    from app.config import get_settings
    from app.rag.reranker import get_reranker

    passages = [
        "3.1 Normalization\nThird normal form removes transitive dependencies.",
        "4 Concurrency\nTwo-phase locking can deadlock.",
    ]
    reranker = get_reranker()
    on_topic = reranker.score("what does third normal form eliminate?", passages)
    off_topic = reranker.score("who won the football world cup", passages)

    threshold = get_settings().retrieval_min_score
    assert on_topic[0] > threshold > max(off_topic)
    assert on_topic[0] > on_topic[1]
