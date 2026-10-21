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

## Release checklist (before and after deploying)

- [ ] CI green on the commit
- [ ] Smoke test passes against the target environment
- [ ] Sign up, upload, ask, quiz, share, export and delete work on a phone and a laptop
- [ ] Error and analytics endpoints receive data (`/insights` as admin)
- [ ] HTTPS redirect and HSTS present (`FORCE_HTTPS=true` build)

## Latest results (21 Oct 2026)

- Backend: 252 tests pass (incl. RLS 8/8, hardening 27/27); eval 23/23; retrieval gate passes.
- Playwright: 30 passed (desktop + mobile).
- Smoke test (real stack, RLS on): 36/36 checks; 196 MB PDF searchable in 42 s; answers start in 1.0–1.8 s.
- Lighthouse mobile (performance / accessibility / best practices / SEO):
  home 98/100/100/100, features 98/100/100/100, privacy 97/100/100/100,
  signup 95/100/96/100 (the 96 is a 404 for the bot-check token when no backend is running).
