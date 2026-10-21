# Security

How NoteMind is protected, where each control lives, and how it is tested. The threat model
(STRIDE, T1–T13) is in [SYSTEM_DESIGN.md §6](SYSTEM_DESIGN.md#6-threat-model-stride).

## Reporting a vulnerability

Email the address on the [privacy page](../frontend/src/lib/site.ts) (`NEXT_PUBLIC_CONTACT_EMAIL`)
with steps to reproduce. Please don't open a public issue for security problems.

## Controls

| Control | Where | Tested by |
|---|---|---|
| **Row-level security**: Postgres refuses other tenants' rows even without a `WHERE` clause | `app/rls.py`, `app/db.py` | `tests/test_rls.py`; every API test runs as the restricted role |
| **Auth on every API route** except an explicit public list | `app/deps.py` | `test_every_api_route_requires_login_unless_explicitly_public` |
| **IDOR protection**: lookups filter on parent and child id; strangers get 404 | `app/authz.py`, `api/documents.py`, `api/invites.py` | stranger/viewer tests per endpoint + RLS |
| **Never trust the frontend**: Pydantic validation, server-side authz, size limits while streaming, magic-byte checks, forwarded IP trusted only from the proxy | `schemas.py`, `api/*`, compose | validation, upload and spoofed-header tests |
| **Rate limiting**: global per-IP ceiling plus tighter per-route limits | `app/rate_limit.py` | `test_global_rate_limit…`, per-route tests |
| **Input sanitization**: control and bidi characters rejected; filenames sanitized; document text HTML-escaped into prompts; React text rendering only | `schemas.py`, `ingestion/validation.py`, `rag/answer.py` | `test_control_characters_are_rejected`, injection tests |
| **Parameterized queries**: SQLAlchemy everywhere; ruff `S608` blocks string-built SQL | all | ruff in pre-commit and CI |
| **CORS locked down**: off by default, exact origins only, `*` refused | `main.py`, `config.py` | `test_cors_is_off…`, `test_wildcard_cors…` |
| **HTTPS everywhere**: HSTS (backend in production; frontend with `FORCE_HTTPS`), redirect, `upgrade-insecure-requests`, Secure cookies | `main.py`, `next.config.ts`, `api/auth.py` | cookie tests, header tests |
| **Debug off in production**: `debug=False`, generic 500 with request id, docs disabled in production, no server header | `main.py`, Dockerfile | `test_unhandled_errors_return_a_generic_500…` |
| **Bot and spam protection**: honeypot, signed form token with minimum fill time, Cloudflare Turnstile CAPTCHA when configured | `security/bot.py`, `AuthForm.tsx` | bot tests (backend), form tests (Playwright) |
| **Audit log of admin actions** and security events (deletions, sharing changes); append-only, admin-read-only | `audit.py`, `api/admin.py`, `admin.py` | `test_sensitive_actions_are_audited`, RLS tests |
| **Secrets off the frontend**: only `NEXT_PUBLIC_*` reach the browser; bundle scanned after every build | `scripts/check-client-bundle.mjs` | CI step |
| **Secrets out of git**: detect-secrets pre-commit hook; `.env` ignored | `.pre-commit-config.yaml` | pre-commit, CI |
| **Dependencies**: pip-audit, bandit, pinned lockfiles | CI | CI |
| **Security headers**: CSP, X-Frame-Options, nosniff, Referrer-Policy, Permissions-Policy | `next.config.ts`, `main.py` | Playwright + backend header tests |
| **Edge proxy**: overwrites `X-Forwarded-For` with the TCP peer (never appends); caches only responses without `Set-Cookie`; same upload limit | `deploy/nginx/` | load test, header checks |
| **Untrusted images** (photos, scanned pages): decoded only in the memory-capped worker; 60-megapixel cap against decompression bombs; re-encoded to JPEG before leaving the server; HEIC refused | `ingestion/ocr.py`, `ingestion/validation.py` | `tests/test_transcription.py` |
| **Prompt injection in handwriting**: the transcription prompt treats image text as content, never instructions; output is only stored as that user's own page text, which the answer pipeline already escapes | `ingestion/ocr.py`, `rag/answer.py` | transcription and injection tests |
| **Transcription spend**: per-user daily token budget separate from answers, shared global cap, 300 handwritten pages per file | `ingestion/ocr.py`, `llm/gateway.py` | `test_transcription_has_its_own_daily_budget` |

## Operating it safely

- Set a random `SECRET_KEY` (≥ 32 chars); production refuses the default.
- Build the frontend with `FORCE_HTTPS=true` and `NEXT_PUBLIC_SITE_URL=https://…` behind TLS.
- Set `TURNSTILE_SECRET_KEY` and `NEXT_PUBLIC_TURNSTILE_SITE_KEY` to turn on the CAPTCHA.
- Behind a different reverse proxy, run uvicorn with `--proxy-headers --forwarded-allow-ips
  <proxy address>`; never `*` if the backend port is reachable.
- Grant admin only from the server: `python -m app.admin grant you@example.com`.
- Run `python -m app.admin prune --days 365` daily to honour the privacy policy's retention.
- Use a paid LLM tier for real users if notes may contain personal data (see the privacy page);
  handwritten pages are sent to the provider as images.
- Behind your TLS terminator, add a file to `/etc/nginx/real-ip/` on the edge naming it
  (`set_real_ip_from <its address>; real_ip_header X-Forwarded-For;`), or every visitor will
  share its address in rate limits.

## Known limits

- RLS protects against application bugs, not SQL injection (which could set the user id
  itself); parameterized queries are the defence there.
- The form token raises the cost of naive bots only; Turnstile is the real bot check.
- No email verification yet: sign-up confirms an address exists (TODO in `api/auth.py`).
- CSP still allows inline scripts (Next.js); nonce-based CSP is a planned hardening step.
