# NoteMind

Ask questions about your own college notes and get answers with page-level citations,
plus auto-generated quizzes. A RAG system built with FastAPI, PostgreSQL + pgvector, Redis
and a Next.js frontend.

## Features

- **Upload notes** (PDF, PPTX with speaker notes, DOCX) into a collection per course;
  extraction runs in a memory-capped background worker with live progress.
- **Handwritten notes too**: scanned or handwritten PDFs and photos of notebook pages (JPG,
  PNG, WebP) are transcribed by the vision model, then searched and cited like typed pages.
- **Ask questions** and get answers streamed token by token, citing the page each statement
  came from. When the notes don't cover a question, NoteMind says so instead of guessing.
- **Quiz yourself**: multiple-choice questions written from your notes, on a topic or across
  the whole course, each linked to its source page.
- **Share a course** read-only with classmates through a revocable invite link.
- **Own your data**: export everything as JSON, or delete your account and all files.
- **A proper public site**: landing and features pages, privacy policy, terms, cookie
  consent, opt-in cookieless analytics, social previews, sitemap, and a custom 404.
  Lighthouse (mobile): 95–98 performance, 100 accessibility, 100 SEO. Editorial
  paper-and-ink design ([docs/DESIGN.md](docs/DESIGN.md)).
- **Load-tested at 10,000 concurrent users** with k6 through an nginx edge
  ([docs/PERFORMANCE.md](docs/PERFORMANCE.md)), and **CI/CD** that publishes images, load-tests
  every release and deploys over SSH ([docs/CI_CD.md](docs/CI_CD.md)).

## How it works

Hybrid retrieval (pgvector HNSW + Postgres full-text, fused with RRF) → cross-encoder rerank
→ top 6 passages → LLM with a grounded prompt → citation check. Low reranker confidence
skips the LLM entirely ("not in your notes"). The LLM can be Anthropic Claude or Google
Gemini (`LLM_ANSWER_MODEL`), behind one gateway that enforces per-user and global daily
token budgets.

The retrieval choices are measured, not assumed: [ml/eval/REPORT.md](ml/eval/REPORT.md) has
Recall@k / MRR / nDCG and refusal rates across 15 configurations (chunk size, overlap,
vector vs hybrid, reranker, pool size), and CI fails if retrieval quality regresses.

Security is designed in: Postgres row-level security under every query, tenant filters in
SQL, login required on every API route (enforced by a test), prompt-injection defences,
httpOnly cookie auth with refresh-token rotation, bot checks and optional CAPTCHA, per-IP
and per-user rate limits, an append-only audit log, and a STRIDE threat model. See
[docs/SECURITY.md](docs/SECURITY.md) for every control and the test that proves it.

## Documentation

| Doc | What's in it |
|---|---|
| [PRD](docs/PRD.md) | Problem, users, scope, success measures |
| [Architecture](docs/ARCHITECTURE.md) | Components, request flows, folder structure |
| [Design system](docs/DESIGN.md) | Colours, type, components, motion, accessibility |
| [Security](docs/SECURITY.md) | Controls, where they live, how they're tested |
| [Test plan](docs/TEST_PLAN.md) | Test layers, commands, release checklist, latest results |
| [Performance](docs/PERFORMANCE.md) | 10,000-user load test: method, results, bottlenecks fixed |
| [CI/CD](docs/CI_CD.md) | Pipelines, image publishing, release load test, deployment setup |
| [Decisions](docs/DECISIONS.md) · [System design](docs/SYSTEM_DESIGN.md) | Why things are the way they are; threat model |
| [Rules](docs/RULES.md) · [Tasks](docs/TASKS.md) · [Memory](docs/MEMORY.md) | How to contribute, what's next, current state |

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

**Production-style entry point**: http://localhost:8080 is the nginx edge (cached pages, API
straight to the backend), the same path the load test and a deployment use.

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

## Admin and operations

```bash
docker compose exec backend python -m app.admin grant you@example.com   # then open /insights
docker compose exec backend python -m app.admin prune --days 365        # run daily
```

Admins see anonymous analytics and the audit log at `/insights`; every view is audited.
For production: build the frontend with `FORCE_HTTPS=true` and `NEXT_PUBLIC_SITE_URL`, set
the Turnstile keys to enable the CAPTCHA, and see [docs/SECURITY.md](docs/SECURITY.md).

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

## Load test (10,000 users)

```bash
docker compose -f docker-compose.yml -f docker-compose.loadtest.yml up -d
docker compose exec -T backend python - --students 3000 < loadtest/seed.py
docker compose -f docker-compose.yml -f docker-compose.loadtest.yml run --rm k6
```

Results land in `loadtest/results/` (k6's HTML report with charts, and a JSON summary).
`PEAK_USERS=500 PROFILE=quick` runs a two-minute version. See
[docs/PERFORMANCE.md](docs/PERFORMANCE.md).

## Tests

```bash
cd backend && uv run pytest             # fakes for models and the LLM
cd backend && uv run pytest -m slow     # real embedding + reranker models
cd backend && uv run pytest -m llm      # real LLM API (needs LLM_API_KEY, costs cents)
cd frontend && npm test && npm run lint && npm run typecheck
cd frontend && npm run build && npm run check:bundle && npm run test:e2e   # Playwright
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
