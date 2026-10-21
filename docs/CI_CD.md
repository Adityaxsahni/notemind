# CI/CD

Two GitHub Actions workflows. CI checks every push and pull request; CD runs only after CI
passes on `main`.

```
push / PR ──► CI ──(main, green)──► CD: publish ──► verify (load test) ──► deploy
```

## CI ([ci.yml](../.github/workflows/ci.yml))

| Job | What it checks |
|---|---|
| pre-commit | formatting, secret scan (detect-secrets), whitespace, YAML |
| backend | ruff; migrations apply, roll back, re-apply and match the models; 250+ tests on real Postgres + pgvector; bandit; pip-audit |
| frontend | ESLint, TypeScript, unit tests, production build, no secrets in browser JavaScript, Playwright (desktop + mobile), npm audit |
| eval-regression | retrieval quality on the seed question set must not regress (Recall@6, MRR, refusal) |
| load-test-script | the k6 script compiles and its options are valid |

## CD ([cd.yml](../.github/workflows/cd.yml))

1. **publish**: builds the backend and frontend images from the commit CI tested and
   pushes them to GitHub Container Registry as `ghcr.io/adityaxsahni/notemind-backend` and
   `…/notemind-frontend`, tagged `sha-<7 chars>` and `latest`.
2. **verify**: starts the published images as a complete stack (Postgres, Redis, API,
   workers, frontend) with throwaway secrets, then runs the k6 load test
   ([loadtest/notemind.js](../loadtest/notemind.js)) at 300 concurrent users. The release
   fails if any performance objective is missed (error rate under 1%, p95 under 800 ms for
   pages and API calls, under 3 s for sign-in and search). The k6 HTML report is attached
   to the run as the `load-test-report` artifact.
3. **deploy**: skipped until a server is configured (below). It checks out the commit on
   the server, pulls the exact images that passed `verify`, restarts the stack, and checks
   the site responds.

Run CD by hand from the Actions tab (**CD → Run workflow**) to choose a bigger load test,
for example 2,000 users with the `full` profile.

### Turning on deployment

On a Linux server with Docker, clone the repository to `/opt/notemind`, create `.env` from
`.env.example` (`ENVIRONMENT=production`, a random `SECRET_KEY`, a database password, the
LLM key), and put a TLS reverse proxy (Caddy, nginx) in front of port 3000. Then add to the
GitHub repository (Settings → Secrets and variables → Actions):

| Name | Kind | Value |
|---|---|---|
| `DEPLOY_HOST` | variable | server hostname; setting it turns the deploy job on |
| `DEPLOY_USER` | variable | SSH user with permission to run Docker |
| `DEPLOY_PATH` | variable | optional, default `/opt/notemind` |
| `SITE_URL` | variable | public URL, e.g. `https://notemind.example.com` (also baked into the frontend) |
| `CONTACT_EMAIL` | variable | contact address shown on the legal pages |
| `FORCE_HTTPS` | variable | `true` in production |
| `TURNSTILE_SITE_KEY` | variable | optional CAPTCHA site key |
| `DEPLOY_SSH_KEY` | secret | private key for `DEPLOY_USER` |
| `DEPLOY_KNOWN_HOSTS` | secret | output of `ssh-keyscan <host>`, so the server's identity is pinned |

The `production` environment can require a manual approval before each deploy
(Settings → Environments → production → Required reviewers).

### Rolling back

Every published image is kept under its commit tag, so on the server:

```
NOTEMIND_TAG=sha-<previous> docker compose -f docker-compose.yml -f docker-compose.release.yml up -d --no-build
```

Database migrations are additive; `alembic downgrade -1` reverses the latest one if needed.
