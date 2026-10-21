import json
import uuid
from collections.abc import Iterator
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.authz import Action, assert_can_access
from app.deps import CurrentUser, EmbedderDep, LLMGatewayDep, RedisDep, RerankerDep, SessionDep
from app.llm.gateway import BudgetExceeded, LLMNotConfigured
from app.rag.answer import AnswerDone, AnswerError, AnswerEvent, AnswerText, prepare_answer
from app.rate_limit import enforce_rate_limit
from app.schemas import AskIn

router = APIRouter(prefix="/collections/{collection_id}", tags=["ask"])


@router.post(
    "/ask",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}, 429: {}, 503: {}},
)
def ask(
    collection_id: uuid.UUID,
    body: AskIn,
    user: CurrentUser,
    session: SessionDep,
    redis: RedisDep,
    embedder: EmbedderDep,
    reranker: RerankerDep,
    gateway: LLMGatewayDep,
) -> StreamingResponse:
    """Answer a question from the collection's notes, streamed as server-sent events:

    - `token`: `{"text": "..."}`, a piece of the answer
    - `done`: `{"answer", "citations": [{id, document_id, document_title, page, ...}],
      "grounded", "cached", "truncated"}`
    - `error`: `{"message": "..."}`; discard any text received so far
    """
    access = assert_can_access(session, user, collection_id, Action.READ)
    enforce_rate_limit(redis, "ask", str(user.id), limit=20, window_seconds=60)
    try:
        events = prepare_answer(
            session,
            redis,
            embedder,
            reranker,
            gateway,
            user_id=user.id,
            owner_id=access.collection.owner_id,
            collection_id=collection_id,
            question=body.question,
        )
    except BudgetExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="You've reached today's question limit. It resets at midnight UTC.",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from None
    except LLMNotConfigured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Answering questions isn't available right now.",
        ) from None
    return StreamingResponse(
        _sse(events),
        media_type="text/event-stream",
        # no-store: answers are private. no-transform: compressing proxies (including the
        # Next.js server in front of us) must not gzip the stream, because gzip buffers tokens
        # until the end. X-Accel-Buffering: nginx-style proxies pass tokens straight through.
        headers={"Cache-Control": "no-store, no-transform", "X-Accel-Buffering": "no"},
    )


def _sse(events: Iterator[AnswerEvent]) -> Iterator[str]:
    for event in events:
        if isinstance(event, AnswerText):
            name, data = "token", {"text": event.text}
        elif isinstance(event, AnswerDone):
            name, data = "done", asdict(event)
        elif isinstance(event, AnswerError):
            name, data = "error", {"message": event.message}
        yield f"event: {name}\ndata: {json.dumps(data, default=str)}\n\n"
