# Coding rules

Rules for anyone (person or AI assistant) changing this codebase. The non-negotiable
security rules are repeated in [../CLAUDE.md](../CLAUDE.md), which AI tools read automatically.

## Before writing code

1. Read [PRD.md](PRD.md), [ARCHITECTURE.md](ARCHITECTURE.md) and the relevant module.
2. Plan the change as one vertical slice (API + UI + tests) small enough to review.
3. Check [DECISIONS.md](DECISIONS.md): don't silently reverse a recorded decision.

## Security (never break these)

1. Every search filters by `user_id` and `collection_id` inside the SQL query.
2. New tenant tables get row-level-security policies in `backend/app/rls.py` and a new
   migration that re-applies them.
3. Uploaded text is untrusted: it reaches the LLM only inside escaped `<source>` tags.
4. Never log document content, questions or answers.
5. Every LLM call goes through `app/llm/gateway.py` (budgets).
6. Every route requires login unless added to `PUBLIC_ROUTES` in `tests/test_hardening.py`
   with a reason. Public routes need rate limits.
7. Authorization through `assert_can_access`; resource lookups filter on the parent id too.
8. Secrets only in environment variables; the browser bundle gets `NEXT_PUBLIC_*` values only,
   and none of them may be secret.
9. Validate every input on the server with Pydantic, even if the frontend already checks it.

## Style

- Python: type hints, ruff (lint + format), config only via `get_settings()`.
- TypeScript: strict, ESLint (React Compiler rules), no `any`; use `useSyncExternalStore`
  for browser state (localStorage, cookies), not `setState` in effects.
- Comments explain *why*, not what. Match the surrounding code.

## Definition of done

- [ ] Unit/integration tests, including an unauthorized-access test for new endpoints
- [ ] `uv run pytest`, `ruff`, `npm run lint`, `npm run typecheck`, `npm test` pass
- [ ] `npm run build`, `npm run check:bundle` and `npm run test:e2e` pass for UI changes
- [ ] Docs updated (this folder, README) if behaviour or setup changed
- [ ] Small commit with a message saying why
