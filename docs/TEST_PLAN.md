# Test plan

How NoteMind is verified, from fastest to slowest. CI runs everything except the live-LLM
tests and the smoke test.

| Layer | What | Command | In CI |
|---|---|---|---|
| Lint and types | ruff, ESLint, TypeScript | `uv run ruff check .` · `npm run lint` · `npm run typecheck` | yes |
| Backend unit + integration | API, RLS, auth, bot checks, rate limits, ingestion, retrieval, answers, quizzes (fake models and LLM, real Postgres + pgvector) | `cd backend && uv run pytest` | yes |
| Backend with real models | embedding and reranker behaviour | `uv run pytest -m slow` | no |
| Live LLM | grounded answer, refusal, citation filter against the real provider | `uv run pytest -m llm` (needs `LLM_API_KEY`) | no |
| Frontend unit | API client, SSE parser, validation | `npm test` | yes |
| Browser (Playwright) | public pages, metadata, axe accessibility incl. contrast, broken links, 404, robots/sitemap, headers, cookie consent and analytics, form validation and bot fields, mobile menu and no horizontal scroll; desktop + mobile | `npm run build && npm run test:e2e` | yes |
| Client bundle | no secrets in browser JavaScript | `npm run check:bundle` | yes |
| Retrieval regression | Recall@6, MRR, refusal on the seed eval set | `python -m ml.eval.run retrieval --set seed --only baseline …` | yes |
| End to end, real stack | 196 MB / 1,500-page PDF upload, search, cited answers, refusal, quizzes, size limit, sharing, export, deletion | `scripts/smoke_test.py` (see README) | no (needs Docker + LLM) |
| Performance | Lighthouse mobile on public pages | see below | no |
| Load | k6 up to 10,000 users through the edge ([PERFORMANCE.md](PERFORMANCE.md)) | `docker compose -f docker-compose.yml -f docker-compose.loadtest.yml run --rm k6` | CD: 300 users on every release |
| Live sign-in flow | sign-up, emailed code, courses, log-in again; screenshots | `node frontend/e2e-live/flow.mjs <out-dir>` against the running stack | no |

## Release checklist (before and after deploying)

- [ ] CI green on the commit
- [ ] Smoke test passes against the target environment
- [ ] Sign up, upload, ask, quiz, share, export and delete work on a phone and a laptop
- [ ] Error and analytics endpoints receive data (`/insights` as admin)
- [ ] HTTPS redirect and HSTS present (`FORCE_HTTPS=true` build)

## Latest results (21 Oct 2026)

- Backend: 289 tests pass (incl. RLS, hardening, OTP 12, transcription 16); eval 23/23;
  retrieval gate passes; migrations round-trip on an empty database.
- Playwright: 32 passed (desktop + mobile), including the one-time-code step.
- Smoke test (real stack, RLS on, two-step sign-in): 39/39 checks; 196 MB PDF searchable in
  107 s; answers start in 2.1–4.1 s.
- Handwriting: a photo of notebook notes was transcribed by Gemini and found by search.
- Load: see [PERFORMANCE.md](PERFORMANCE.md).
- Lighthouse mobile (performance / accessibility / best practices / SEO):
  home 98/100/100/100, features 98/100/100/100, privacy 97/100/100/100,
  signup 95/100/96/100 (the 96 is a 404 for the bot-check token when no backend is running).
