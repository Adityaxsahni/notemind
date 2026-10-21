# --- build stage: resolve and install dependencies with uv ---
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.11.28 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy HF_HOME=/app/hf
WORKDIR /app
COPY pyproject.toml uv.lock ./
# Cache mount: dependency changes don't re-download torch (~190 MB) on every rebuild.
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
# Bake the pinned models into the image: containers never download code or weights.
RUN .venv/bin/python -c "from app.main import _load_models; _load_models()"

# --- runtime stage: no build tools, non-root user ---
FROM python:3.12-slim
RUN useradd --create-home --uid 1000 app \
    && mkdir -p /data/uploads && chown app:app /data/uploads
WORKDIR /app
COPY --from=builder --chown=app:app /app /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 HF_HOME=/app/hf HF_HUB_OFFLINE=1
USER app
EXPOSE 8000
# Behind a reverse proxy, also pass --proxy-headers --forwarded-allow-ips <proxy address>.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header"]
