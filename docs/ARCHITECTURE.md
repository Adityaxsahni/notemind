# Architecture

How NoteMind is built. Rules for changing it are in [RULES.md](RULES.md); why each choice
was made is in [DECISIONS.md](DECISIONS.md).

## Components

```
Browser ──HTTPS──> TLS terminator ──> nginx edge (:8080)
                                        │  pages + /_next/static: cached (60 s / 30 days)
                                        │  API paths: straight to the backend, streamed
                     Next.js (frontend, :3000)  static HTML pages + client app pages
                     │  (in development, Next.js also proxies the API paths itself)
                     ▼
                   FastAPI (backend, :8000, WEB_CONCURRENCY processes) ──> PostgreSQL 16 + pgvector (row-level security)
                     │                     └──> Redis (rate limits, token budgets, cache, queue)
                     │                     └──> LLM provider (Anthropic or Gemini) via one gateway
                     ▼ enqueue (RQ)
          worker  (ingestion queue): parse untrusted files in a forked, memory-capped process
          indexer (indexing queue):  chunk + embed (bge-small) with the model kept loaded
```

The browser only ever talks to one origin, so auth cookies are first-party
(`SameSite=Strict`) and CORS is off. The backend trusts `X-Forwarded-For` only from the
edge's and the frontend's fixed addresses; the edge overwrites the header with the TCP peer.
Capacity measurements and the reasons for the edge are in [PERFORMANCE.md](PERFORMANCE.md).

## Request flows

**Ask a question:** auth cookie → `get_current_user` (sets the row-level-security user) →
`assert_can_access` → hybrid search (pgvector HNSW + Postgres full-text, tenant-filtered in
SQL) → RRF fusion → cross-encoder rerank → low confidence? reply "not in your notes" without
an LLM call : reserve token budget → LLM gateway → stream tokens through the citation filter
→ settle budget → cache.

**Upload:** raw body streamed to disk with a byte counter (abort at 200 MB) → magic-byte
check (PDF, DOCX, PPTX, JPEG, PNG, WebP) → `documents` row → `ingestion` job: extract text
per page (PyMuPDF / python-pptx / python-docx) → transcribe pages that are pictures of text
(below) → clean, store pages → `indexing` job: heading-aware chunks, embed, store.

**Handwriting and scans** (`app/ingestion/ocr.py`): a PDF page with fewer than 25 typed
characters but something drawn on it, or an uploaded photo, is rendered to a 2,000 px JPEG
(photos are turned upright from EXIF and capped at 60 megapixels) and sent, four pages per
request, to the configured vision model through the LLM gateway, charged to the uploader's
separate daily transcription budget. The model returns `=== PAGE n ===` sections; if the
markers don't match, those pages are retried one at a time. Transcribed pages are then
cleaned, chunked, cited and searched like typed ones.

## Data isolation, in three layers

1. **Application:** every route resolves access through `app/authz.py`; document lookups
   filter on both document and collection id (IDOR guard).
2. **Query:** every search filters `(user_id, collection_id)` inside the SQL statement.
3. **Database:** Postgres row-level security (`app/rls.py`). The app connects as the
   restricted role `notemind_app`; each transaction carries the signed-in user's id, and
   policies hide or refuse rows from collections the user doesn't own or belong to. Workers
   act as the document's owner. Audit rows are append-only.

## Folder structure

```
backend/app/
  api/            HTTP routes (one module per resource; admin.py, telemetry.py)
  ingestion/      upload validation, extraction, transcription (ocr.py), cleaning, chunking, RQ jobs
  rag/            retriever, reranker, answer pipeline, quiz generation
  llm/            gateway (budgets, logging) + providers (only place vendor SDKs are imported)
  security/       passwords, tokens, bot checks
  rls.py          row-level security SQL (applied by migrations and tests)
  audit.py        audit-log helper;  admin.py: operator CLI (grant admin, prune)
backend/tests/    pytest; every API test runs under row-level security
frontend/src/
  app/            routes: landing, features, privacy, terms, (app)/ for signed-in pages
  components/     header, footer, cookie banner, forms, panels, icons
  lib/            API client, consent, telemetry, validation, site settings
frontend/e2e/     Playwright browser tests (API mocked)
ml/eval/          retrieval and answer-quality evaluation
scripts/          end-to-end smoke test against the running stack
loadtest/         k6 load test (10,000 users) and its seed script
deploy/nginx/     edge proxy configuration
docs/             this folder
```

## Observability

- Backend logs: request id on every response (`X-Request-ID`), unhandled errors logged with
  it, never request content. LLM calls log model, tokens and latency only.
- Browser errors: `error.tsx`, `global-error.tsx` and a global listener post scrubbed reports
  to `/telemetry/errors`, which lands in the same backend log stream.
- Analytics: cookieless page views after opt-in (`/analytics/event`), viewable by admins at
  `/insights`; every admin view is audited.
