# Deploying NoteMind

## Free right now: a public link from your own machine

No account and no card: a Cloudflare quick tunnel gives the stack running on your machine a
public HTTPS address. The link works while the machine and Docker are on, and changes every
time the tunnel restarts.

```bash
docker compose -f docker-compose.yml -f docker-compose.tunnel.yml up -d
docker compose -f docker-compose.yml -f docker-compose.tunnel.yml logs tunnel | grep trycloudflare
```

While exposed, the backend runs in production mode (no API docs, sign-in codes never shown
on screen), and nginx takes visitor addresses only from the tunnel container's
`CF-Connecting-IP`. Sign-in is password-only until SMTP is configured; then set
`OTP_REQUIRED=true` (in `.env`) and restart. Stop sharing with `docker compose stop tunnel`.

## Hosted

**Choice: Vercel for the website, a Docker host for the backend.**

- **Vercel vs GitHub Pages.** GitHub Pages serves static files only. It can't run the
  Next.js server, which proxies the API (keeping auth cookies first-party), adds security
  headers and renders the social image. On Pages only the marketing pages would work, and
  nobody could sign in. Vercel runs Next.js natively, with HTTPS, a CDN, and automatic
  deploys from GitHub (previews for every pull request).
- **The backend can't run on Vercel.** It needs PyTorch models (~1.5 GB RAM), two background
  workers, Postgres with pgvector and Redis. Neon (Postgres + pgvector) and Upstash (Redis)
  have free tiers without a card, both available through Vercel's marketplace. A host with
  enough memory for the API is no longer free: Hugging Face Docker Spaces now need PRO
  ($9/month, October 2026), and the card-free tiers elsewhere (Render, Koyeb) give 512 MB.

```
Browser ──HTTPS──> Vercel (Next.js: pages, CDN)
                     │ /auth /me /collections … (rewrite, + PROXY_SECRET header)
                     ▼
                   Hugging Face Space (FastAPI + ingestion + indexing workers)
                     ├──> Neon (Postgres 16 + pgvector, row-level security)
                     ├──> Upstash (Redis: rate limits, queue, budgets)
                     └──> Gemini / Claude API, SMTP for sign-in codes
```

## 1. Database and Redis (5 minutes)

1. **Neon** (neon.tech): create a project (Postgres 16). Copy the connection string and
   change the scheme to `postgresql+psycopg://`, keeping `?sslmode=require`.
2. **Upstash** (upstash.com): create a Redis database in the region closest to your Neon
   project. Copy the `rediss://…` URL.

Migrations run automatically when the backend starts. They create the `vector` extension,
the tables, the restricted `notemind_app` role, and the row-level-security policies.

## 2. Email for sign-in codes

Sign-in is password + a 6-digit code by email, so the backend needs SMTP. The simplest is
Gmail with an **app password** (Google Account → Security → 2-Step Verification → App
passwords): `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`, `SMTP_USERNAME=you@gmail.com`,
`SMTP_PASSWORD=<16-character app password>`, `SMTP_FROM=NoteMind <you@gmail.com>`. Brevo,
Resend or Amazon SES work the same way.

## 3. Backend on a Hugging Face Space

1. On GitHub, make the backend image public: your profile → **Packages** →
   `notemind-backend` → Package settings → Change visibility → Public. CD publishes it on every
   green push to `main`.
2. huggingface.co → **New Space** → SDK **Docker** (blank), hardware **CPU basic (free)**.
3. Upload the three files from [`deploy/huggingface/`](../deploy/huggingface/) (Dockerfile,
   start.sh, README.md) to the Space.
4. Space **Settings → Variables and secrets** (all as *secrets*):

   | Name | Value |
   |---|---|
   | `ENVIRONMENT` | `production` |
   | `SECRET_KEY` | 48+ random characters: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
   | `DATABASE_URL` | Neon URL from step 1 |
   | `REDIS_URL` | Upstash URL from step 1 |
   | `LLM_API_KEY`, `LLM_ANSWER_MODEL` | your Gemini (or Anthropic) key and model |
   | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM` | step 2 |
   | `PROXY_SECRET` | another random value; the same one goes into Vercel |

5. The Space builds and starts. `https://<user>-<space>.hf.space/health` should answer
   `{"status":"ok"}`.

To pick up a new release, use **Factory rebuild** in the Space settings (it pulls `latest`).

## 4. Website on Vercel

1. vercel.com → **Add New → Project → Import** `Adityaxsahni/notemind`.
2. **Root Directory:** `frontend` (Vercel detects Next.js).
3. **Environment variables:**

   | Name | Value |
   |---|---|
   | `BACKEND_URL` | `https://<user>-<space>.hf.space` |
   | `PROXY_SECRET` | same value as on the Space |
   | `NEXT_PUBLIC_SITE_URL` | `https://<project>.vercel.app` (or your domain) |
   | `NEXT_PUBLIC_CONTACT_EMAIL` | the address for privacy requests |
   | `FORCE_HTTPS` | `true` |
   | `NEXT_PUBLIC_TURNSTILE_SITE_KEY` | optional CAPTCHA key (then set `TURNSTILE_SECRET_KEY` on the Space) |

4. **Deploy.** Every push to `main` redeploys; pull requests get preview URLs.

## Checks after deploying

- Sign up: the code arrives by email and signing in works; `/courses` loads.
- Upload a PDF and a photo of handwritten notes; both reach "ready" and are searchable.
- Ask a question: the answer streams and cites pages.
- `curl -I https://<project>.vercel.app/` shows `Strict-Transport-Security` and the CSP.

## Limits of the free setup

- **Storage:** the Space's disk is reset on restart. Extracted text and search indexes live in
  Neon and survive, but "download original" stops working for older files. Enable the
  Space's persistent storage and set `UPLOAD_DIR=/data/uploads` to keep files.
- **Sleep:** free Spaces sleep after 48 hours without traffic. The first request after that
  waits about a minute for the models to load.
- **Upload size:** uploads pass through Vercel's proxy. Very large files (the 200 MB maximum)
  may hit Vercel request limits; check with a large PDF after deploying.
- For more traffic, run the same images on any Docker host with the CD deploy job
  ([CI_CD.md](CI_CD.md)) and the nginx edge ([PERFORMANCE.md](PERFORMANCE.md)).
