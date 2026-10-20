from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness probe. Deliberately touches no dependencies."""
    return {"status": "ok"}
