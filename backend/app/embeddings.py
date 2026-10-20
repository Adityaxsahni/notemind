"""Local embedding model. Notes are embedded on our own servers and never sent to a vendor."""

from functools import lru_cache
from typing import Protocol

import numpy as np

from app.config import get_settings

# bge's recommended instruction for short queries; passages are embedded without one.
QUERY_PROMPT = "Represent this sentence for searching relevant passages: "


class Embedder(Protocol):
    def count_tokens(self, text: str) -> int: ...

    def embed_documents(self, texts: list[str]) -> np.ndarray: ...

    def embed_query(self, text: str) -> np.ndarray: ...


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str, revision: str, batch_size: int) -> None:
        # Imported here: torch takes seconds to import, and only workers embed passages.
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name, revision=revision, device="cpu")
        self._tokenizer = self._model.tokenizer.backend_tokenizer
        self._batch_size = batch_size

    def count_tokens(self, text: str) -> int:
        return len(self._tokenizer.encode(text, add_special_tokens=False).ids)

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return self._model.encode(
            texts, batch_size=self._batch_size, normalize_embeddings=True, convert_to_numpy=True
        )

    def embed_query(self, text: str) -> np.ndarray:
        return self._model.encode(
            [text], prompt=QUERY_PROMPT, normalize_embeddings=True, convert_to_numpy=True
        )[0]


@lru_cache
def get_embedder() -> Embedder:
    """Loaded once per process; workers call this at startup so the first job isn't slow."""
    settings = get_settings()
    return SentenceTransformerEmbedder(
        settings.embedding_model, settings.embedding_model_revision, settings.embedding_batch_size
    )
