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

**300 users** (2-minute run; CD runs the same check on every release): **0 failed
requests**, pages p95 1 ms (from the edge cache), API p95 16 ms, log-in p95 104 ms, search
p95 255 ms.

**10,000 users:** pages held up: the edge served them all and none failed. The backend
didn't. API calls started timing out from about 3,000–4,000 users, k6 itself ran out of
memory after 8 minutes (no summary written), and Docker Desktop's engine stopped answering.
Looking at the database afterwards showed why the backend never recovered:

### Bug found: leaked connections under overload

Even with no traffic, `/health` hung and Postgres showed all 40 connections (2 processes ×
20) "idle in transaction". When a client gave up on a slow request, FastAPI cancelled it
before running the cleanup of the synchronous `get_session` dependency (that cleanup needs
a worker thread), so the session was never closed and its connection never returned. After
40 abandoned requests the API was dead for good. Fixed by making `get_session` an async
generator, whose cleanup runs inline even on cancellation, plus a 10 s pool timeout that
answers 503 "busy, retry" instead of hanging (`app/db.py`, `app/main.py`; regression tests
in `tests/test_hardening.py`). Without the load test, this would have appeared in
production during the first traffic spike.

### After the fix: 2,000 users with a sign-in burst

`PROFILE=quick` ramps to 2,000 users in 30 seconds, so 600 students sign in at once:

| Metric | Result |
|---|---|
| Failed requests | **1.09%** (of 73,044) |
| Pages | median 4 ms, p95 1.2 s |
| API calls | median 22.5 s, p95 timeouts |
| Verdict | **Fail**, but the backend recovers afterwards (no leak) |

**The next bottleneck is sign-in.** Each Argon2id password check (RFC 9106 parameters: 64 MB
of memory, 3 passes, 4 lanes) costs tens of milliseconds of CPU on several cores, on
purpose, to slow down password cracking. Hundreds per second fill both processes' 40 worker
threads, and cheap requests queue behind them. Real traffic spreads sign-ins out (sessions
last 30 days through refresh tokens), but a class all signing in when a lecture starts looks
much like this.

## Honest limits of these numbers

One laptop can't run both the system and a 10,000-user generator: k6 needs about 5 GB and 6
CPU threads for that many users, and the API gets what's left. The pass at 300 users and the
fixes above hold. A clean 10,000-user result needs a separate load-generator machine and
more than two API processes.

## Next steps, in order

1. Run password hashing on a small dedicated thread pool (for example 4 per process), so a
   sign-in burst waits on itself instead of blocking every other request.
2. More API processes or machines behind the edge (each needs ~0.9 GB for the models), and
   PgBouncer once that goes past ~4 processes.
3. Re-run the 10,000-user profile from separate hardware (k6 Cloud, or a second machine
   pointed at the edge).

## Scaling further

- Search is the most expensive request (embedding + cross-encoder reranking on CPU, ~200 ms of
  CPU each). Add API processes or machines; each process needs ~0.9 GB for the models.
- Beyond ~4 API processes, put PgBouncer in front of Postgres (100 connections by default).
- Pages and assets can move to a CDN; the edge config already sets cache lifetimes.
- Answers and quizzes scale with the LLM provider's rate limits and the token budgets.
