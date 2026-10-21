import uuid

from fastapi import APIRouter, HTTPException, status

from app.authz import Action, assert_can_access
from app.deps import CurrentUser, EmbedderDep, LLMGatewayDep, RedisDep, RerankerDep, SessionDep
from app.llm.gateway import BudgetExceeded, LLMNotConfigured
from app.llm.providers import LLMUnavailable
from app.rag.quiz import QuizUnavailable, generate_quiz, select_sources
from app.rate_limit import enforce_rate_limit
from app.schemas import QuizIn, QuizOut

router = APIRouter(prefix="/collections/{collection_id}", tags=["quiz"])


@router.post("/quiz", response_model=QuizOut, responses={429: {}, 502: {}, 503: {}})
def create_quiz(
    collection_id: uuid.UUID,
    body: QuizIn,
    user: CurrentUser,
    session: SessionDep,
    redis: RedisDep,
    embedder: EmbedderDep,
    reranker: RerankerDep,
    gateway: LLMGatewayDep,
):
    """Multiple-choice questions from the collection's notes, each citing its source page.
    `found` is false (and `questions` empty) when the notes don't cover the topic."""
    access = assert_can_access(session, user, collection_id, Action.READ)
    enforce_rate_limit(redis, "quiz", str(user.id), limit=5, window_seconds=60)
    sources = select_sources(
        session,
        embedder,
        reranker,
        owner_id=access.collection.owner_id,
        collection_id=collection_id,
        topic=body.topic,
        count=min(body.num_questions + 2, 8),
    )
    try:
        return generate_quiz(
            gateway,
            user_id=user.id,
            sources=sources,
            num_questions=body.num_questions,
            topic=body.topic,
        )
    except BudgetExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="You've reached today's question limit. It resets at midnight UTC.",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from None
    except (LLMNotConfigured, LLMUnavailable):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Quizzes aren't available right now. Please try again in a minute.",
        ) from None
    except QuizUnavailable:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Couldn't write a quiz from these notes. Try again or pick a topic.",
        ) from None
