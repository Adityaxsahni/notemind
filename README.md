# NoteMind

Ask questions about your own college notes and get answers with page-level citations,
plus auto-generated quizzes. A RAG system built with FastAPI, PostgreSQL + pgvector, Redis
and a Next.js frontend.

> Work in progress. See [CLAUDE.md](CLAUDE.md) for architecture and security rules, and
> [docs/design.md](docs/design.md) for the design and threat model.

## Run locally

Requires Docker Desktop. Copy the env file and fill in `SECRET_KEY` and `POSTGRES_PASSWORD`
(and `LLM_API_KEY` to enable answers; without it, search and "not in your notes" still work):

```bash
cp .env.example .env
```

**Everything in Docker** — open http://localhost:3000:

```bash
docker compose up --build
```

**Frontend with hot reload** — run the backend services in Docker and the UI with npm:

```bash
docker compose up -d postgres redis backend worker indexer
cd frontend
npm install
npm run dev          # http://localhost:3000 (stop the `frontend` container first if it runs)
```

The browser only talks to the frontend's origin. Next.js forwards `/auth`, `/me`,
`/collections`, `/invites` and `/health` to the backend (`BACKEND_URL`, default
`http://127.0.0.1:8000`), so the httpOnly auth cookies stay first-party and no CORS is needed.

## Tests

```bash
cd backend && uv run pytest             # fakes for models and the LLM
cd backend && uv run pytest -m slow     # real embedding + reranker models
cd backend && uv run pytest -m llm      # real LLM API (needs LLM_API_KEY, costs cents)
cd frontend && npm test && npm run lint && npm run typecheck
```

## Evaluation

Retrieval and answer quality are measured on labelled question sets in `ml/eval/`; results,
ablations and the recommended configuration are in [ml/eval/REPORT.md](ml/eval/REPORT.md).
CI fails if baseline retrieval on the seed set drops below its thresholds.

```bash
uv run --project backend --group eval python -m ml.eval.run retrieval --set seed   # free
uv run --project backend python -m ml.eval.run answers --set seed --dry-run        # free
uv run --project backend python -m ml.eval.run answers --set seed --yes            # uses LLM credit
```

## Development

```bash
uvx pre-commit install   # lint, format and secret scanning on every commit
```
