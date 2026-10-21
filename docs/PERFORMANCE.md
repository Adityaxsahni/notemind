# Performance: 10,000 concurrent users

How NoteMind behaves as traffic grows to 10,000 concurrent users, what broke first, and what
was changed. Reproduce with the commands in the README ("Load test").

## Method

- **Tool:** k6 2.3 ([loadtest/notemind.js](../loadtest/notemind.js)), running in Docker on the
  same network as the app. Its HTML report (charts over time) and JSON summary land in
  `loadtest/results/`.
- **Users:** 70% anonymous visitors (landing, features, legal, sign-up and log-in pages; a cold
  first visit also downloads the page's JavaScript and CSS; opt-in analytics events) and 30%
  signed-in students (log in once with the bot checks, then: course list, profile, course
  page, documents, and a search on 10% of visits). Think time 3–15 s between actions, like
  real people.
- **Realistic addresses:** each virtual user sends its own client IP, trusted only from the
  load generator, so per-IP rate limits and login limits behave as with real visitors.
- **Ramp:** 1,000 users (1 min) → 5,000 (2 min) → 10,000 (2 min) → hold 10,000 (5 min) → 0.
- **Not tested under load:** asking the LLM and quizzes (they call Gemini, whose free tier
  allows a few dozen requests a day; at scale they are bounded by the provider and the daily
  token budgets, not by this system), and uploads (background workers, measured separately:
  a 196 MB PDF is searchable in 42 s).
- **Pass criteria:** under 1% failed requests; p95 under 800 ms for pages and API calls,
  under 3 s for log-in and search.
- **Hardware:** one laptop (12 threads, 16 GB RAM, Docker limited to 8 GB) running both
  the whole system and the 10,000-user generator. The generator alone needs ~5 GB and up to
  5 CPU cores, so these numbers understate what the system does on its own hardware.

## Baseline: the original setup

Browser → Next.js (one Node process proxying every API call) → one uvicorn process with
SQLAlchemy's default 15 database connections.

| Metric | Result |
|---|---|
| Failed requests | **20.8%** (76,902 of 370,181) |
| API p95 | 60 s (timeouts) |
| Page p95 | 52.9 s |
| Throughput | 553 requests/s |
| Verdict | **Fail**: fell over at ~5,000 users |

What broke, in order:

1. **The backend's single Python process** (321% CPU, GIL-bound): requests waited for one of
   15 pooled database connections while 40 threads competed for them, then timed out.
2. **The Next.js server**, a single Node process that relayed every API call as well as
   serving pages, stopped accepting connections (`dial: i/o timeout`).

## Changes

| Change | Where | Why |
|---|---|---|
| **nginx edge** in front: pages cached for 60 s and build assets for 30 days; API paths go straight to the backend (streaming and uploads unbuffered) | `deploy/nginx/` | Node no longer relays API traffic; repeated page views never reach it |
| **Several API processes** (`WEB_CONCURRENCY`) | `docker-compose.yml` | Uses more than one core for Python |
| **Database pool 10 + 10 per process** (was 5 + 10) | `app/config.py`, `app/db.py` | No queueing for connections under load |
| **Torch limited to 2 threads per process** (`API_TORCH_THREADS`) | `docker-compose.yml` | Several processes don't oversubscribe the CPU during search |
| nginx: 16,384 connections per worker, buffered access log | `deploy/nginx/nginx.conf` | The image default (1,024) is exhausted by a few thousand visitors |

## After the changes

At 300 concurrent users (2-minute run, CD's release check): **0 failed requests**, pages p95
1 ms (served from the edge cache), API p95 16 ms, log-in p95 104 ms, search p95 255 ms.

The 10,000-user run is in progress; its results replace this paragraph.

## Scaling further

- Search is the most expensive request (embedding + cross-encoder reranking on CPU, ~200 ms of
  CPU each). Add API processes or machines; each process needs ~0.9 GB for the models.
- Beyond ~4 API processes, put PgBouncer in front of Postgres (100 connections by default).
- Pages and assets can move to a CDN; the edge config already sets cache lifetimes.
- Answers and quizzes scale with the LLM provider's rate limits and the token budgets.
