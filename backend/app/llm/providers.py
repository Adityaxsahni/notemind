"""LLM providers behind one small interface. Only this module imports a vendor SDK; the
gateway (budgets, logging) and the answer pipeline work with any LLMProvider. Anthropic and
Google Gemini are supported; the model name picks the vendor."""

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

import anthropic
import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types

from app.config import Settings, get_settings

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


class GeminiProvider:
    # Gemini has no "xhigh"/"max" thinking level; HIGH is its ceiling.
    _THINKING = {
        "low": genai_types.ThinkingLevel.LOW,
        "medium": genai_types.ThinkingLevel.MEDIUM,
        "high": genai_types.ThinkingLevel.HIGH,
        "xhigh": genai_types.ThinkingLevel.HIGH,
        "max": genai_types.ThinkingLevel.HIGH,
    }
    # Finish reasons mapped onto the Anthropic-style stop reasons the pipeline checks.
    _STOP = {
        genai_types.FinishReason.STOP: "end_turn",
        genai_types.FinishReason.MAX_TOKENS: "max_tokens",
        genai_types.FinishReason.SAFETY: "refusal",
        genai_types.FinishReason.PROHIBITED_CONTENT: "refusal",
        genai_types.FinishReason.BLOCKLIST: "refusal",
        genai_types.FinishReason.SPII: "refusal",
    }

    def __init__(
        self, api_key: str, model: str, effort: str, timeout: float, max_retries: int
    ) -> None:
        self._client = genai.Client(
            api_key=api_key,
            http_options=genai_types.HttpOptions(
                timeout=int(timeout * 1000),  # milliseconds
                # Retries 408/429/5xx with exponential backoff; attempts include the first.
                retry_options=genai_types.HttpRetryOptions(attempts=max_retries + 1),
            ),
        )
        self._model = model
        self._config = genai_types.GenerateContentConfig(
            thinking_config=genai_types.ThinkingConfig(thinking_level=self._THINKING[effort])
        )

    def stream(self, request: LLMRequest) -> Iterator[LLMEvent]:
        config = self._config.model_copy(
            update={"system_instruction": request.system, "max_output_tokens": request.max_tokens}
        )
        model, finish, blocked, usage = self._model, None, False, None
        try:
            for chunk in self._client.models.generate_content_stream(
                model=self._model, contents=request.user, config=config
            ):
                if chunk.text:
                    yield TextDelta(chunk.text)
                model = chunk.model_version or model
                usage = chunk.usage_metadata or usage
                if chunk.prompt_feedback and chunk.prompt_feedback.block_reason:
                    blocked = True  # the prompt itself was refused: no candidates at all
                if chunk.candidates and chunk.candidates[0].finish_reason:
                    finish = chunk.candidates[0].finish_reason
        except genai_errors.APIError as exc:
            level = logging.WARNING if exc.code == 429 else logging.ERROR
            logger.log(level, "llm error status=%s %s", exc.code, exc.status)
            raise LLMUnavailable from exc
        except httpx.TransportError as exc:  # connection failures and timeouts
            logger.error("llm connection failed: %s", type(exc).__name__)
            raise LLMUnavailable from exc

        if blocked:
            stop_reason = "refusal"
        elif finish is None:
            stop_reason = None
        else:
            stop_reason = self._STOP.get(finish, finish.value.lower())
        yield Completion(
            model=model,
            stop_reason=stop_reason,
            input_tokens=(usage and usage.prompt_token_count) or 0,
            # Thinking tokens are billed as output.
            output_tokens=((usage and usage.candidates_token_count) or 0)
            + ((usage and usage.thoughts_token_count) or 0),
        )


def make_provider(model: str, effort: str, settings: Settings) -> LLMProvider:
    """The vendor follows from the model name; LLM_API_KEY must be that vendor's key."""
    if settings.llm_api_key is None or not settings.llm_api_key.get_secret_value():
        raise ValueError("LLM_API_KEY is not set")
    provider = GeminiProvider if model.startswith("gemini-") else AnthropicProvider
    return provider(
        api_key=settings.llm_api_key.get_secret_value(),
        model=model,
        effort=effort,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )


@lru_cache
def get_llm_provider() -> LLMProvider | None:
    """None when no API key is configured: answering is disabled, everything else works."""
    settings = get_settings()
    if settings.llm_api_key is None or not settings.llm_api_key.get_secret_value():
        return None
    return make_provider(settings.llm_answer_model, settings.llm_answer_effort, settings)
