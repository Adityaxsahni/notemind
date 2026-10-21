import hashlib
import re
from collections.abc import Iterator

import numpy as np

from app.llm.providers import Completion, LLMEvent, LLMRequest, LLMUnavailable, TextDelta
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


_STOPWORDS = frozenset("a an and are does how in is it of on the to what which who why".split())


class FakeReranker:
    """Scores by words shared with the query, on the real model's logit scale: no overlap
    gives -10 (below the default retrieval_min_score of -6), each shared word adds 3."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str]]] = []

    def score(self, query: str, passages: list[str]) -> list[float]:
        self.calls.append((query, passages))
        query_words = _content_words(query)
        return [-10.0 + 3.0 * len(query_words & _content_words(p)) for p in passages]


def _content_words(text: str) -> set[str]:
    return set(re.findall(r"\w+", text.lower())) - _STOPWORDS


class FakeLLM:
    """Scripted LLMProvider: streams `reply` piece by piece, then a Completion."""

    def __init__(self) -> None:
        self.requests: list[LLMRequest] = []
        self.reply: list[str] = ["Third normal form removes transitive dependencies [S1]."]
        self.stop_reason = "end_turn"
        self.fail_after: int | None = None  # raise LLMUnavailable after this many pieces
        self.input_tokens = 1000
        self.output_tokens = 200

    def stream(self, request: LLMRequest) -> Iterator[LLMEvent]:
        self.requests.append(request)
        for i, piece in enumerate(self.reply):
            if self.fail_after == i:
                raise LLMUnavailable
            yield TextDelta(piece)
        if self.fail_after == len(self.reply):
            raise LLMUnavailable
        yield Completion(
            model="fake-model",
            stop_reason=self.stop_reason,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
        )


class FakeVisionLLM:
    """Scripted transcriber: each page image in a request reads `text` plus its position."""

    def __init__(self) -> None:
        self.requests: list[LLMRequest] = []
        self.text = "Handwritten: mitochondria make ATP by oxidative phosphorylation"
        self.configured = True  # False: as if no API key were set
        self.error: Exception | None = None
        self.markers = True  # False: forget the page markers, as models sometimes do

    def stream(self, request: LLMRequest) -> Iterator[LLMEvent]:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        pages = [f"{self.text} (image {i})" for i in range(1, len(request.images) + 1)]
        if self.markers:
            body = "\n".join(f"=== PAGE {i} ===\n{p}" for i, p in enumerate(pages, start=1))
        else:
            body = "\n\n".join(pages)
        yield TextDelta(body)
        yield Completion(
            model="fake-vision", stop_reason="end_turn", input_tokens=1500, output_tokens=300
        )
