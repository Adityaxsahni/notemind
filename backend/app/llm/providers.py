"""LLM providers behind one small interface. Only this module imports a vendor SDK; the
gateway (budgets, logging) and the answer pipeline work with any LLMProvider."""

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

import anthropic

from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LLMRequest:
    system: str
    user: str
    max_tokens: int


@dataclass(frozen=True)
class TextDelta:
    text: str


@dataclass(frozen=True)
class Completion:
    model: str  # the model that finished the answer (a refusal fallback may differ)
    stop_reason: str | None  # "end_turn", "max_tokens", "refusal", ...
    input_tokens: int
    output_tokens: int


LLMEvent = TextDelta | Completion


class LLMUnavailable(Exception):
    """The provider failed after its retries. Details are logged, not shown to users."""


class LLMProvider(Protocol):
    def stream(self, request: LLMRequest) -> Iterator[LLMEvent]:
        """Yield TextDeltas as they arrive, then exactly one Completion."""
        ...


class AnthropicProvider:
    # Server-side refusal fallback: if a safety classifier declines, the API re-runs the
    # request on Anthropic's recommended model for that category, on the same stream.
    _FALLBACK_BETA = "server-side-fallback-2026-07-01"

    def __init__(
        self, api_key: str, model: str, effort: str, timeout: float, max_retries: int
    ) -> None:
        self._client = anthropic.Anthropic(
            api_key=api_key,
            timeout=anthropic.Timeout(timeout, connect=5.0),
            max_retries=max_retries,  # exponential backoff on 408/409/429/5xx/connection
        )
        self._model = model
        self._effort = effort

    def stream(self, request: LLMRequest) -> Iterator[LLMEvent]:
        try:
            with self._client.beta.messages.stream(
                model=self._model,
                max_tokens=request.max_tokens,
                system=request.system,
                messages=[{"role": "user", "content": request.user}],
                output_config={"effort": self._effort},
                betas=[self._FALLBACK_BETA],
                fallbacks="default",
            ) as stream:
                for text in stream.text_stream:
                    yield TextDelta(text)
                message = stream.get_final_message()
        except anthropic.RateLimitError as exc:
            logger.warning("llm rate limited request_id=%s", exc.request_id)
            raise LLMUnavailable from exc
        except anthropic.APIStatusError as exc:
            logger.error("llm error status=%s request_id=%s", exc.status_code, exc.request_id)
            raise LLMUnavailable from exc
        except anthropic.APIConnectionError as exc:  # includes timeouts
            logger.error("llm connection failed: %s", type(exc).__name__)
            raise LLMUnavailable from exc

        input_tokens, output_tokens = _billed_tokens(message.usage)
        yield Completion(
            model=message.model,
            stop_reason=message.stop_reason,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )


def _billed_tokens(usage) -> tuple[int, int]:
    """With a fallback, top-level usage covers only the last attempt; iterations has all."""
    iterations = getattr(usage, "iterations", None) or [usage]
    input_tokens = sum(
        (getattr(it, "input_tokens", 0) or 0)
        + (getattr(it, "cache_creation_input_tokens", 0) or 0)
        + (getattr(it, "cache_read_input_tokens", 0) or 0)
        for it in iterations
    )
    output_tokens = sum(getattr(it, "output_tokens", 0) or 0 for it in iterations)
    return input_tokens, output_tokens


@lru_cache
def get_llm_provider() -> LLMProvider | None:
    """None when no API key is configured: answering is disabled, everything else works."""
    settings = get_settings()
    if settings.llm_api_key is None or not settings.llm_api_key.get_secret_value():
        return None
    return AnthropicProvider(
        api_key=settings.llm_api_key.get_secret_value(),
        model=settings.llm_answer_model,
        effort=settings.llm_answer_effort,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )
