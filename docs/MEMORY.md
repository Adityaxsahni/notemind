# Project memory

The current state, for whoever (or whichever AI session) picks the project up next. Update
it at the end of each working session.

**Last updated:** 21 October 2026

## State

- All MVP stories done and tested; public website and security hardening done.
- Runs locally with `docker compose up --build` → http://localhost:3000.
- Repository: https://github.com/Adityaxsahni/notemind (public), CI green.

## Configuration in use

- LLM: Google Gemini on the free tier (`LLM_ANSWER_MODEL=gemini-3.5-flash-lite` in `.env`;
  `gemini-3.8-flash` is better but allows only 20 requests a day per model on the free tier).
  The free tier lets Google use submitted content; use a paid tier for real users.
- CAPTCHA: not configured (Turnstile keys empty); honeypot + form token + rate limits active.
- Contact email on legal pages: placeholder `privacy@notemind.example`
  (`NEXT_PUBLIC_CONTACT_EMAIL`), to be replaced before launch.

## Things that surprised us

- The Next.js server gzips proxied responses, which buffered the answer stream; fixed with
  `Cache-Control: no-transform` on the stream.
- Behind the proxy, every visitor had the proxy's IP in rate limits. Trusting
  `X-Forwarded-For` from the frontend fixed that but let clients fake it, because Next.js
  rewrites pass the client's header through untouched; `frontend/client-ip.mjs` now replaces it
  with the real peer address before Next.js sees the request (verified: a spoofed 6.6.6.6 is ignored).
- RLS + `INSERT … RETURNING`: the returned row must pass the SELECT policy, and the policy's
  helper can't see the row being inserted. Owners and self-memberships match directly; the
  write-only tables use `implicit_returning=False`.
- pymupdf 2.x pulls an ONNX layout model that crashed on Windows; excluded via uv overrides.

## Open items

See [TASKS.md](TASKS.md) → Next.
