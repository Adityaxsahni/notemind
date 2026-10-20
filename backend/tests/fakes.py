import hashlib
import re

import numpy as np

from app.models import EMBEDDING_DIM


class FakeEmbedder:
    """Deterministic bag-of-words vectors: texts sharing words are similar. No model download.

    Tokens are whitespace-separated words, which keeps chunk-size assertions easy to reason about.
    """

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def count_tokens(self, text: str) -> int:
        return len(text.split())

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        self.calls.append(texts)
        return np.stack([self._embed(t) for t in texts])

    def embed_query(self, text: str) -> np.ndarray:
        return self._embed(text)

    @staticmethod
    def _embed(text: str) -> np.ndarray:
        vector = np.zeros(EMBEDDING_DIM, dtype=np.float32)
        for word in re.findall(r"\w+", text.lower()):
            bucket = int.from_bytes(hashlib.sha256(word.encode()).digest()[:4], "big")
            vector[bucket % EMBEDDING_DIM] += 1.0
        norm = np.linalg.norm(vector)
        if norm == 0:
            vector[0] = 1.0
            return vector
        return vector / norm
