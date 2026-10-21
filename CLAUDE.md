# NoteMind

RAG study assistant: students upload their own notes/slides (PDF, PPTX, DOCX), ask
questions and get answers with page-level citations, and generate quizzes from their material.

## Stack
- Backend: Python 3.12, FastAPI, SQLAlchemy 2 + Alembic, Pydantic v2, pydantic-settings
- Data: PostgreSQL 16 + pgvector; Redis (cache, rate limits, token budgets) + RQ (jobs)
- ML: sentence-transformers (bge-small-en-v1.5), cross-encoder reranker, LLM behind a
  provider-agnostic gateway (`backend/app/llm/`)
- Frontend: Next.js + Tailwind (`frontend/`)
- Tooling: uv, ruff (lint + format), pytest, bandit, pip-audit, pre-commit, GitHub Actions

## Layout
- `backend/app/` — API (`api/`), config, db, worker; `backend/tests/`; `backend/alembic/`
- `backend/app/ingestion/` — upload validation, extraction, cleaning, chunking, RQ jobs.
  Two queues: `ingestion` (parses untrusted files) → `indexing` (chunks + embeds)
- `backend/app/rag/` — hybrid retriever + reranker, grounded answer pipeline (prompt, citations, cache)
- `backend/app/llm/` — the LLM gateway (budgets, logging) and providers (only place a vendor SDK is imported)
- `ml/` — evaluation sets, experiments, reports
- `frontend/` — Next.js 16 + Tailwind 4 UI. Read `frontend/AGENTS.md` first: this Next version
  differs from older docs. Browser calls are same-origin; `next.config.ts` rewrites API paths
  to the backend (keep page routes off `/auth`, `/me`, `/collections`, `/invites`)
- `infra/` — deployment config
- `docs/` — design.md, performance.md, runbook

## Commands (run from `backend/`)
- `uv sync` — install deps
- `uv run pytest` — tests (fake models and LLM); `uv run pytest -m slow` — real local models;
  `uv run pytest -m llm` — real LLM API (needs `LLM_API_KEY`, costs a few cents)
- `uv run ruff check . && uv run ruff format .` — lint/format
- `uv run uvicorn app.main:app --reload` — dev server
- `uv run alembic revision --autogenerate -m "msg"` / `uv run alembic upgrade head`
- From repo root: `docker compose up --build` — full stack (UI on http://localhost:3000)
- From `frontend/`: `npm run dev`, `npm test`, `npm run lint`, `npm run typecheck`, `npm run build`

## Conventions
- Type hints everywhere; Pydantic models validate every request body and query param
- Config only through `app.config.get_settings()`; never read os.environ elsewhere
- Every new endpoint gets tests, including an unauthorized-access test
- Money/time-sensitive or security-relevant logic gets a unit test before merge

## NON-NEGOTIABLE security rules
1. Every vector/keyword search MUST filter by `user_id` (and `collection_id`) inside the
   SQL query itself — never fetch-then-filter.
2. Uploaded document text is untrusted data. It is never treated as instructions to the
   LLM; it goes inside delimited `<source>` tags only.
3. Never log document content, user questions, or LLM answers. Log IDs, counts, latency.
4. Every LLM call goes through the single gateway that enforces per-user token budgets.
5. Answers must cite sources. If retrieval confidence is low, return
   "I couldn't find this in your notes" without calling the LLM.
6. Secrets only via environment variables. `.env` is never committed.
7. Authorization checks go through one helper (`assert_can_access`), used by every endpoint.
