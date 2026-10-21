"""Anonymous page-view analytics and browser error reports. Both are public (visitors may not
be signed in), so both are rate limited per IP, size-capped, and store nothing that
identifies a person.
"""

import logging
import re
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Header, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import insert

from app.deps import RedisDep, SessionDep
from app.models import AnalyticsEvent
from app.rate_limit import client_ip, enforce_rate_limit

logger = logging.getLogger(__name__)
router = APIRouter(tags=["telemetry"])

_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_MOBILE = re.compile(r"Mobi|Android|iPhone|iPad", re.I)


class PageViewIn(BaseModel):
    path: str = Field(max_length=500)
    referrer: str | None = Field(default=None, max_length=500)


class ClientErrorIn(BaseModel):
    message: str = Field(max_length=2000)
    path: str = Field(default="", max_length=500)
    digest: str | None = Field(default=None, max_length=100)  # Next.js server error id
    stack: str | None = Field(default=None, max_length=8000)


def normalize_path(path: str) -> str:
    """/c/3f2a...-.../x?q=1 -> /c/:id/x. Ids would let analytics be joined back to people."""
    path = urlsplit(path).path or "/"
    return _UUID.sub(":id", path)[:200]


def _referrer_host(referrer: str | None, request: Request) -> str | None:
    host = urlsplit(referrer or "").hostname
    own = request.headers.get("host", "").split(":")[0]
    return None if not host or host == own else host[:100]


@router.post("/analytics/event", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def page_view(
    body: PageViewIn,
    request: Request,
    session: SessionDep,
    redis: RedisDep,
    user_agent: Annotated[str, Header()] = "",
    dnt: Annotated[str | None, Header()] = None,
    sec_gpc: Annotated[str | None, Header()] = None,
) -> Response:
    """Records one page view. The frontend sends it only after the visitor accepted analytics;
    Do Not Track and Global Privacy Control are honoured here as well."""
    enforce_rate_limit(redis, "analytics", client_ip(request), limit=120, window_seconds=60)
    if dnt == "1" or sec_gpc == "1":
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    # Plain INSERT (no RETURNING): visitors may write page views but never read them back.
    session.connection().execute(  # Core: no ORM RETURNING
        insert(AnalyticsEvent.__table__).values(
            path=normalize_path(body.path),
            referrer_host=_referrer_host(body.referrer, request),
            device="mobile" if _MOBILE.search(user_agent) else "desktop",
        )
    )
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/telemetry/errors", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def client_error(body: ClientErrorIn, request: Request, redis: RedisDep) -> Response:
    """A crash in someone's browser, logged next to server errors (same log pipeline).
    Emails and ids are scrubbed; the stack is kept to the first lines."""
    enforce_rate_limit(redis, "client-error", client_ip(request), limit=30, window_seconds=60)

    def scrub(text: str) -> str:
        return _UUID.sub(":id", _EMAIL.sub("<email>", text))

    stack = "\n".join((body.stack or "").splitlines()[:8])
    logger.error(
        "client_error path=%s digest=%s message=%s stack=%s",
        normalize_path(body.path),
        body.digest,
        scrub(body.message)[:500],
        scrub(stack),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
