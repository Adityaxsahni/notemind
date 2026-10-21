"""GeminiProvider against a fake client that streams real SDK response objects (no network)."""

import pytest
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import SecretStr

from app.config import get_settings
from app.llm.providers import (
    AnthropicProvider,
    Completion,
    GeminiProvider,
    LLMRequest,
    LLMUnavailable,
    TextDelta,
    make_provider,
)

REQUEST = LLMRequest(system="be brief", user="what is 2PL?", max_tokens=500)


def chunk(text=None, finish=None, usage=None, blocked=False) -> types.GenerateContentResponse:
    parts = [types.Part(text=text)] if text is not None else []
    return types.GenerateContentResponse(
        model_version="gemini-test-001",
        candidates=None
        if blocked
        else [
            types.Candidate(content=types.Content(role="model", parts=parts), finish_reason=finish)
        ],
        prompt_feedback=types.GenerateContentResponsePromptFeedback(
            block_reason=types.BlockedReason.SAFETY
        )
        if blocked
        else None,
        usage_metadata=usage,
    )


class FakeModels:
    def __init__(self, chunks=(), error=None):
        self.chunks, self.error, self.calls = chunks, error, []

    def generate_content_stream(self, *, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        yield from self.chunks
        if self.error:
            raise self.error


def provider_with(models: FakeModels, effort: str = "low") -> GeminiProvider:
    provider = GeminiProvider(
        api_key="test",  # pragma: allowlist secret
        model="gemini-test",
        effort=effort,
        timeout=5,
        max_retries=0,
    )
    provider._client = type("FakeClient", (), {"models": models})()
    return provider


def test_streams_text_then_one_completion_with_billed_tokens():
    usage = types.GenerateContentResponseUsageMetadata(
        prompt_token_count=120, candidates_token_count=30, thoughts_token_count=50
    )
    models = FakeModels(
        [chunk("Two-phase "), chunk("locking [S1]."), chunk("", types.FinishReason.STOP, usage)]
    )
    events = list(provider_with(models).stream(REQUEST))

    assert [e.text for e in events if isinstance(e, TextDelta)] == ["Two-phase ", "locking [S1]."]
    assert events[-1] == Completion(
        model="gemini-test-001", stop_reason="end_turn", input_tokens=120, output_tokens=80
    )
    assert sum(isinstance(e, Completion) for e in events) == 1


def test_request_carries_system_prompt_limit_and_thinking_level():
    models = FakeModels([chunk("ok", types.FinishReason.STOP)])
    list(provider_with(models, effort="medium").stream(REQUEST))

    call = models.calls[0]
    assert call["model"] == "gemini-test"
    assert call["contents"] == REQUEST.user
    assert call["config"].system_instruction == REQUEST.system
    assert call["config"].max_output_tokens == REQUEST.max_tokens
    assert call["config"].thinking_config.thinking_level == types.ThinkingLevel.MEDIUM


@pytest.mark.parametrize(
    ("finish", "expected"),
    [
        (types.FinishReason.MAX_TOKENS, "max_tokens"),
        (types.FinishReason.SAFETY, "refusal"),
        (types.FinishReason.PROHIBITED_CONTENT, "refusal"),
        (types.FinishReason.RECITATION, "recitation"),
    ],
)
def test_finish_reasons_map_to_pipeline_stop_reasons(finish, expected):
    events = list(provider_with(FakeModels([chunk("partial", finish)])).stream(REQUEST))
    assert events[-1].stop_reason == expected


def test_blocked_prompt_is_a_refusal():
    events = list(provider_with(FakeModels([chunk(blocked=True)])).stream(REQUEST))
    assert events == [
        Completion(model="gemini-test-001", stop_reason="refusal", input_tokens=0, output_tokens=0)
    ]


@pytest.mark.parametrize("code", [429, 500])
def test_api_errors_become_llm_unavailable(code):
    error = genai_errors.APIError(code, {"error": {"message": "nope", "status": "X"}})
    with pytest.raises(LLMUnavailable):
        list(provider_with(FakeModels([chunk("par")], error=error)).stream(REQUEST))


def test_model_name_picks_the_vendor():
    settings = get_settings().model_copy(update={"llm_api_key": SecretStr("test")})
    assert isinstance(make_provider("gemini-test", "low", settings), GeminiProvider)
    assert isinstance(make_provider("claude-opus-5-5", "low", settings), AnthropicProvider)
    with pytest.raises(ValueError, match="LLM_API_KEY"):
        make_provider("gemini-test", "low", settings.model_copy(update={"llm_api_key": None}))


class _Scripted:
    def __init__(self, events=(), error_after=None):
        self.events, self.error_after, self.calls = list(events), error_after, 0

    def stream(self, request):
        self.calls += 1
        for i, event in enumerate(self.events):
            if self.error_after == i:
                raise LLMUnavailable
            yield event
        if self.error_after == len(self.events):
            raise LLMUnavailable


def test_fallback_uses_the_next_model_when_one_is_unavailable():
    from app.llm.providers import FallbackProvider

    done = Completion(model="m2", stop_reason="end_turn", input_tokens=1, output_tokens=1)
    busy, healthy = _Scripted(error_after=0), _Scripted([TextDelta("hi"), done])
    events = list(FallbackProvider([busy, healthy]).stream(REQUEST))
    assert [type(e) for e in events] == [TextDelta, Completion]
    assert (busy.calls, healthy.calls) == (1, 1)


def test_fallback_never_splices_two_answers():
    from app.llm.providers import FallbackProvider

    half, other = _Scripted([TextDelta("half an ans")], error_after=1), _Scripted([TextDelta("x")])
    with pytest.raises(LLMUnavailable):
        list(FallbackProvider([half, other]).stream(REQUEST))
    assert other.calls == 0


def test_fallback_raises_when_every_model_is_unavailable():
    from app.llm.providers import FallbackProvider

    with pytest.raises(LLMUnavailable):
        list(FallbackProvider([_Scripted(error_after=0), _Scripted(error_after=0)]).stream(REQUEST))


def test_make_provider_wraps_fallback_models(monkeypatch):
    from app.llm.providers import FallbackProvider

    settings = get_settings()
    monkeypatch.setattr(settings, "llm_api_key", SecretStr("k"))
    assert isinstance(make_provider("gemini-a", "low", settings), GeminiProvider)
    wrapped = make_provider("gemini-a", "low", settings, fallbacks=["gemini-b", "gemini-a"])
    assert isinstance(wrapped, FallbackProvider)
    assert [p._model for p in wrapped._providers] == ["gemini-a", "gemini-b"]
