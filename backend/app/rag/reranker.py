"""Cross-encoder reranker: reads question and passage together, so it judges relevance far
better than comparing two independently computed embeddings."""

from functools import lru_cache
from typing import Protocol

from app.config import get_settings


class Reranker(Protocol):
    def score(self, query: str, passages: list[str]) -> list[float]: ...


class CrossEncoderReranker:
    def __init__(self, model_name: str, revision: str) -> None:
        # Imported here: torch takes seconds to import.
        import torch
        from sentence_transformers import CrossEncoder

        # Identity, not sigmoid: retrieval_min_score is calibrated on raw logits.
        self._model = CrossEncoder(
            model_name,
            revision=revision,
            device="cpu",
            max_length=512,
            activation_fn=torch.nn.Identity(),
        )

    def score(self, query: str, passages: list[str]) -> list[float]:
        if not passages:
            return []
        scores = self._model.predict([(query, p) for p in passages], batch_size=32)
        return [float(s) for s in scores]


@lru_cache
def get_reranker() -> Reranker:
    settings = get_settings()
    return CrossEncoderReranker(settings.reranker_model, settings.reranker_model_revision)
