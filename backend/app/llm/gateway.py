"""The single path to an LLM (CLAUDE.md rule 4).

Enforces per-user and global daily token budgets in Redis and logs token counts and
latency, never prompts or answers (rule 3).

Budgets use reserve-then-settle: before a call, the worst case (estimated input +
max_tokens) is added to today's counters atomically, so concurrent requests can't overshoot
the budget together. Afterwards the hold is corrected to the tokens actually billed.
"""

import logging
import math
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from redis import Redis

from app.llm.providers import Completion, LLMEvent, LLMProvider, LLMRequest, TextDelta

logger = logging.getLogger(__name__)

_COUNTER_TTL_SECONDS = 2 * 24 * 3600
_CHARS_PER_TOKEN = 3  # conservative for English (real ratio is ~4), so holds err high


class BudgetExceeded(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("daily token budget exceeded")
        self.retry_after_seconds = retry_after_seconds


class LLMNotConfigured(Exception):
    """No API key: answering is unavailable."""


@dataclass(frozen=True)
class Reservation:
    user_key: str
    global_key: str
    tokens: int


class LLMGateway:
    def __init__(
        self,
        provider: LLMProvider | None,
        redis: Redis,
        *,
        user_daily_budget: int,
        global_daily_budget: int,
    ) -> None:
        self._provider = provider
        self._redis = redis
        self._user_budget = user_daily_budget
        self._global_budget = global_daily_budget

    def reserve(self, user_id: uuid.UUID, request: LLMRequest) -> Reservation:
        """Hold the worst-case token cost, or raise BudgetExceeded / LLMNotConfigured."""
        if self._provider is None:
            raise LLMNotConfigured
        now = datetime.now(UTC)
        day = now.strftime("%Y-%m-%d")
        reservation = Reservation(
            user_key=f"llm:tokens:user:{user_id}:{day}",
            global_key=f"llm:tokens:global:{day}",
            tokens=estimate_input_tokens(request) + request.max_tokens,
        )
        pipe = self._redis.pipeline()
        pipe.incrby(reservation.user_key, reservation.tokens)
        pipe.expire(reservation.user_key, _COUNTER_TTL_SECONDS)
        pipe.incrby(reservation.global_key, reservation.tokens)
        pipe.expire(reservation.global_key, _COUNTER_TTL_SECONDS)
        user_total, _, global_total, _ = pipe.execute()

        if user_total > self._user_budget or global_total > self._global_budget:
            self._adjust(reservation, -reservation.tokens)
            logger.info(
                "llm budget exceeded user_id=%s scope=%s",
                user_id,
                "user" if user_total > self._user_budget else "global",
            )
            midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            raise BudgetExceeded(retry_after_seconds=math.ceil((midnight - now).total_seconds()))
        return reservation

    def stream(self, reservation: Reservation, request: LLMRequest) -> Iterator[LLMEvent]:
        """Stream from the provider, then settle the reservation however the stream ends."""
        if self._provider is None:
            raise LLMNotConfigured
        started = time.perf_counter()
        first_token_at: float | None = None
        completion: Completion | None = None
        try:
            for event in self._provider.stream(request):
                if isinstance(event, TextDelta) and first_token_at is None:
                    first_token_at = time.perf_counter()
                elif isinstance(event, Completion):
                    completion = event
                yield event
        finally:
            if completion is not None:
                used = completion.input_tokens + completion.output_tokens
            elif first_token_at is None:
                used = 0  # failed before generating anything: don't charge the user
            else:
                used = reservation.tokens  # cut off mid-answer: usage unknown, keep the hold
            self._adjust(reservation, used - reservation.tokens)
            logger.info(
                "llm call model=%s stop_reason=%s input_tokens=%s output_tokens=%s "
                "ttft_ms=%s total_ms=%d",
                completion.model if completion else None,
                completion.stop_reason if completion else "incomplete",
                completion.input_tokens if completion else None,
                completion.output_tokens if completion else None,
                round((first_token_at - started) * 1000) if first_token_at else None,
                (time.perf_counter() - started) * 1000,
            )

    def _adjust(self, reservation: Reservation, delta: int) -> None:
        if delta:
            pipe = self._redis.pipeline()
            pipe.incrby(reservation.user_key, delta)
            pipe.incrby(reservation.global_key, delta)
            pipe.execute()


def estimate_input_tokens(request: LLMRequest) -> int:
    return math.ceil((len(request.system) + len(request.user)) / _CHARS_PER_TOKEN)
