import asyncio
import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    admin,
    ask,
    auth,
    collections,
    documents,
    health,
    invites,
    me,
    quiz,
    search,
    telemetry,
)
from app.config import get_settings
from app.embeddings import get_embedder
from app.rag.reranker import get_reranker
from app.rate_limit import global_rate_limit

logger = logging.getLogger(__name__)

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


def _load_models() -> None:
    get_embedder()
    get_reranker()


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Load models before serving, not during the first user's question (~10 s).
        if settings.environment != "test":
            await asyncio.to_thread(_load_models)
        yield

    # Interactive docs are handy locally but expose the API surface in production.
    docs_enabled = not settings.is_production
    app = FastAPI(
        title=settings.app_name,
        docs_url="/docs" if docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if docs_enabled else None,
        lifespan=lifespan,
        debug=False,  # never return tracebacks, whatever the environment
        # A baseline per-IP limit on every route; sensitive routes add tighter ones.
        dependencies=[Depends(global_rate_limit)],
    )

    # The browser reaches the API through the Next.js origin, so CORS is off by default.
    # It's enabled only for origins listed explicitly in CORS_ORIGINS (never "*").
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PATCH", "DELETE"],
            allow_headers=["Content-Type"],
        )

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next) -> Response:
        # A request id ties a user's error report to the server log line.
        request_id = uuid.uuid4().hex[:16]
        request.state.request_id = request_id
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "unhandled error request_id=%s method=%s path=%s",
                request_id,
                request.method,
                request.url.path,
            )
            response = JSONResponse(
                status_code=500,
                content={"detail": "Something went wrong on our side.", "request_id": request_id},
            )
        response.headers["X-Request-ID"] = request_id
        response.headers.update(SECURITY_HEADERS)
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        # FastAPI's default 422 body echoes the submitted value ("input"), which would send
        # passwords and tokens back into responses and logs. Return location + message only.
        errors = [{"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": errors})

    for module in (
        health,
        auth,
        me,
        collections,
        documents,
        invites,
        search,
        ask,
        quiz,
        telemetry,
        admin,
    ):
        app.include_router(module.router)
    return app


app = create_app()
