# NoteMind frontend

Next.js 16 + Tailwind 4. See the [root README](../README.md) for how to run it with the
backend, and `AGENTS.md` before changing Next.js code (APIs differ from older versions).

- `src/lib/api.ts` — typed API client (same-origin; `next.config.ts` proxies to FastAPI)
- `src/lib/sse.ts` — parser for the streamed `/ask` answers
- `src/components/` — UI; model output is rendered as text only, never HTML
