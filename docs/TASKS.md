# Tasks

Small, verifiable slices. Done items stay listed so the history of the build is visible.

## Done

- [x] Phase 0–1: design doc, threat model, repo tooling, CI, secret scanning
- [x] Phase 2: auth (Argon2id, JWT + rotating refresh cookies), collections, sharing
- [x] Phase 3: secure upload (streamed, size-limited) and parsing in isolated workers
- [x] Phase 4: heading-aware chunking and local embeddings
- [x] Phase 5–6: hybrid retrieval, reranking, grounded cited answers, token budgets
- [x] Frontend: Next.js app linked to the API
- [x] Phase 7: evaluation framework, ablations, CI retrieval gate
- [x] Gemini provider; quizzes (U6); 200 MB uploads; streaming fix; smoke test
- [x] Website: landing, features, privacy, terms, cookie consent, metadata, social image,
      favicon, 404, sitemap/robots, analytics, error monitoring, mobile layout
- [x] Security: row-level security, auth-on-every-route test, global rate limit, CORS off,
      HTTPS enforcement, bot checks + CAPTCHA, audit log + admin view, input hygiene
- [x] Project docs per the vibe-coding guide; Playwright browser tests in CI
- [x] Handwriting: scanned/handwritten PDFs and photos transcribed by the vision model
- [x] CD: images to GHCR, release load test, SSH deploy job; nginx edge; 10,000-user load test
- [x] Paper-and-ink redesign (city-explorer handoff)

## Next

- [ ] Real-notes evaluation set (150 questions over 3 real courses) and answer-quality run
- [ ] Email verification on sign-up; password reset
- [ ] Nonce-based CSP (remove `'unsafe-inline'` for scripts)
- [ ] Deploy: provision a server, set the CD variables (docs/CI_CD.md), TLS, backups
- [ ] HEIC photos (iPhone default) for handwriting uploads
- [ ] Load test on separate generator hardware; Postgres connection pooler (PgBouncer) beyond ~4 API processes
- [ ] Scheduled `python -m app.admin prune` job in production
