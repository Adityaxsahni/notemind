import uuid

from fastapi import APIRouter

from app.authz import Action, assert_can_access
from app.deps import CurrentUser, EmbedderDep, RedisDep, RerankerDep, SessionDep
from app.rag.retriever import RetrievalResult, retrieve
from app.rate_limit import enforce_rate_limit
from app.schemas import SearchIn, SearchOut

router = APIRouter(prefix="/collections/{collection_id}", tags=["search"])


# Sync handler: FastAPI runs it in a threadpool, so model inference doesn't block the event loop.
@router.post("/search", response_model=SearchOut)
def search(
    collection_id: uuid.UUID,
    body: SearchIn,
    user: CurrentUser,
    session: SessionDep,
    redis: RedisDep,
    embedder: EmbedderDep,
    reranker: RerankerDep,
) -> RetrievalResult:
    """The passages a question would be answered from, best first. Viewers may search too."""
    access = assert_can_access(session, user, collection_id, Action.READ)
    enforce_rate_limit(redis, "search", str(user.id), limit=60, window_seconds=60)
    return retrieve(
        session,
        embedder,
        reranker,
        # Chunks are stored under the collection owner, so a viewer searches the owner's
        # chunks in this collection only.
        owner_id=access.collection.owner_id,
        collection_id=collection_id,
        question=body.query,
    )
