# Decision log

Permanent technical decisions. The core RAG and infrastructure decisions (pgvector, local
embeddings, hybrid retrieval, chunking, reranker, token budgets, prompt structure, upload
streaming, worker isolation…) are recorded with alternatives in
[SYSTEM_DESIGN.md §7](SYSTEM_DESIGN.md#7-key-design-decisions). Decisions made since:

| Date | Decision | Alternatives | Why |
|---|---|---|---|
| 2026-10-21 | **Evaluation-driven retrieval config** (`ml/eval/REPORT.md`); CI fails on retrieval regressions | Tune by feel | Changes to chunking or ranking are measured, not guessed |
| 2026-10-21 | **Gemini as a second LLM provider**; the model name picks the vendor | Anthropic only | Free tier for development; same gateway, budgets and citation checks |
| 2026-10-21 | **Upload limit 200 MB / 2,000 pages, 1 GB per user** | 20 MB / 300 pages | Real course packs are large; verified end to end (196 MB, 1,500 pages ready in 42 s) |
| 2026-10-21 | **Answer stream sends `Cache-Control: no-transform`** | Disable compression globally | The Next.js server gzipped the event stream, buffering tokens until the end |
| 2026-10-21 | **Postgres row-level security** with a restricted app role and a per-transaction user id | Application checks only | Defence in depth: a missing `WHERE` clause returns nothing instead of another tenant's data |
| 2026-10-21 | **Users and refresh tokens outside RLS** | RLS everywhere | Sign-in has to look a user up before anyone is signed in |
| 2026-10-21 | **Append-only audit log**, readable only by admins; admin rights granted only from the CLI | Admin UI for roles | Privilege changes can't be made through a compromised web session; history can't be rewritten by the app |
| 2026-10-21 | **Bot checks: honeypot + signed form token + optional Cloudflare Turnstile** | reCAPTCHA; nothing | Turnstile is privacy-friendly and free; the cheap layers work without any third party |
| 2026-10-21 | **First-party, cookieless, opt-in analytics** stored in Postgres | Google Analytics, Plausible | No third-party scripts, no cookies, no personal data; still opt-in out of respect |
| 2026-10-21 | **Self-hosted error reporting** to the backend log | Sentry | No account or SDK needed; scrubbing under our control. Sentry can be added later behind the same `reportError` |
| 2026-10-21 | **CORS off** (same-origin proxy) | Allow-list the frontend origin | Nothing cross-origin is needed; wildcard origins are rejected by config validation |
| 2026-10-21 | **Trust `X-Forwarded-For` only from the frontend's fixed container address** | Trust all proxies | Otherwise every visitor shares one IP for rate limits, or anyone can fake theirs |
| 2026-10-21 | **Static marketing pages, inline SVG art, self-hosted font** | Images, web fonts from a CDN | Lighthouse mobile 95–98 performance; nothing third-party to load |
| 2026-10-21 | **HTTPS enforcement at build time** (`FORCE_HTTPS=true`): HSTS, upgrade-insecure-requests, redirect on `X-Forwarded-Proto: http` | Always on | Local Docker serves plain `http://localhost`; production sits behind TLS |
| 2026-10-21 | **Keep our stack** (FastAPI + Postgres + own auth) rather than the guide's beginner defaults (Supabase, Vercel) | Rewrite | Already built and tested; the guide's process (docs, slices, tests, environments) applies to any stack |
| 2026-10-21 | **Handwriting read by the vision LLM** through the gateway, 4 pages per request, only for pages without a text layer | Tesseract; a local handwriting model (TrOCR) | Tesseract is good on print but poor on handwriting; TrOCR needs line segmentation and a GPU to be fast. The LLM is already configured, and batching keeps free-tier request counts low |
| 2026-10-21 | **Separate daily budget for transcription** | Share the answer budget | One handwritten course pack would use up a day of questions |
| 2026-10-21 | **nginx edge in front of Next.js and the API** | Next.js proxies everything | At 10,000 users the single Node process proxying every API call was the first thing to fall over ([PERFORMANCE.md](PERFORMANCE.md)) |
| 2026-10-21 | **Several API processes (`WEB_CONCURRENCY`) and a larger DB pool** | One process | One Python process is bound by the GIL; requests queued for 15 pooled connections |
| 2026-10-21 | **Paper-and-ink design, light only**, from the city-explorer handoff | Previous indigo gradient look | The user asked for that exact style; contrast re-checked for every token |
| 2026-10-21 | **CD publishes images to GHCR and load-tests the exact images** before an optional SSH deploy | Deploy from source on the server | What's tested is what's deployed; rollback is a tag change |
