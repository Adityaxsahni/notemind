# NoteMind

Ask questions about your own college notes and get answers with page-level citations,
plus auto-generated quizzes. A RAG system built with FastAPI, PostgreSQL + pgvector, Redis
and a Next.js frontend.

## Features

- **Upload notes** (PDF, PPTX with speaker notes, DOCX) into a collection per course;
  extraction runs in a memory-capped background worker with live progress.
- **Ask questions** and get answers streamed token by token, citing the page each statement
  came from. When the notes don't cover a question, NoteMind says so instead of guessing.
- **Quiz yourself**: multiple-choice questions written from your notes, on a topic or across
  the whole course, each linked to its source page.
- **Share a course** read-only with classmates through a revocable invite link.
- **Own your data**: export everything as JSON, or delete your account and all files.

## How it works

Hybrid retrieval (pgvector HNSW + Postgres full-text, fused with RRF) → cross-encoder rerank
→ top 6 passages → LLM with a grounded prompt → citation check. Low reranker confidence
skips the LLM entirely ("not in your notes"). The LLM can be Anthropic Claude or Google
Gemini (`LLM_ANSWER_MODEL`), behind one gateway that enforces per-user and global daily
token budgets.

The retrieval choices are measured, not assumed: [ml/eval/REPORT.md](ml/eval/REPORT.md) has
Recall@k / MRR / nDCG and refusal rates across 15 configurations (chunk size, overlap,
vector vs hybrid, reranker, pool size), and CI fails if retrieval quality regresses.

Security is designed in: tenant isolation enforced in every SQL query, prompt-injection
defences, httpOnly cookie auth with refresh-token rotation, upload validation, rate limits,
and a STRIDE threat model. See [docs/design.md](docs/design.md) and [CLAUDE.md](CLAUDE.md).

## Run locally

Requires Docker Desktop. Copy the env file and fill in `SECRET_KEY` and `POSTGRES_PASSWORD`
(and `LLM_API_KEY` to enable answers and quizzes; without it, search and "not in your notes"
still work). `LLM_API_KEY` is an Anthropic key for `claude-*` models or a Google Gemini key
for `gemini-*` models (set `LLM_ANSWER_MODEL=gemini-3.8-flash`, for example):

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

## Check that it works

With the stack running, an end-to-end smoke test drives the app through the frontend the
way a browser does. It builds a 1,500-page, ~196 MB PDF (just under the 200 MB upload
limit), uploads it, waits for indexing, then checks search, cited answers, refusals,
quizzes, the size limit, sharing, export and account deletion:

```bash
uv run --project backend python scripts/make_big_pdf.py course-pack.pdf
uv run --project backend python scripts/smoke_test.py course-pack.pdf   # a few LLM calls
```

On a laptop CPU the 196 MB PDF is searchable about 45 s after upload.

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
