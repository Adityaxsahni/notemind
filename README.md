# NoteMind

Ask questions about your own college notes and get answers with page-level citations,
plus auto-generated quizzes. A RAG system built with FastAPI, PostgreSQL + pgvector and Redis.

> Work in progress. See [CLAUDE.md](CLAUDE.md) for architecture and security rules.

## Run locally

Backend only (no database needed yet):

```bash
cd backend
uv sync
uv run pytest
uv run uvicorn app.main:app --reload   # http://localhost:8000/docs
```

Full stack (requires Docker Desktop):

```bash
cp .env.example .env    # then fill in SECRET_KEY and POSTGRES_PASSWORD
docker compose up --build
```

## Development

```bash
uvx pre-commit install   # lint, format and secret scanning on every commit
```
