# NoteMind — Design & Threat Model

**Status:** v0.1 (pre-implementation) · **Owner:** Adityaxsahni

## 1. Problem

Before exams, students lose hours searching across PDFs, slide decks and scanned notes for a
specific definition or derivation. Generic chatbots don't know *their* course material and
invent answers. NoteMind answers questions **only from the student's own material**, cites the
exact page, and turns that material into quizzes.

## 2. User stories

### MVP
| # | As a student I want to… | So that… |
|---|---|---|
| U1 | sign up and log in securely | my notes stay private |
| U2 | create a collection per course ("DBMS Sem 5") | answers come from the right subject |
| U3 | upload PDF / PPTX / DOCX files | I can use the material I already have |
| U4 | ask a question and get an answer with page citations | I can verify and read more |
| U5 | be told "not found in your notes" when it isn't there | I don't study wrong information |
| U6 | generate an MCQ quiz from a collection | I can test myself |
| U7 | delete my account and all my data, or export it | I stay in control of my data |

### Later
- Share a collection read-only with classmates via a revocable invite link
- Spaced-repetition review and "weak topics" dashboard
- OCR for handwritten notes
- Google sign-in with college accounts

### Out of scope
- Public/global search across all users' material
- Grading or proctoring; using NoteMind during exams
- General-knowledge chat not grounded in uploaded material

## 3. Non-functional requirements

| Area | Requirement |
|---|---|
| Upload limits | ≤ 200 MB per file, ≤ 2,000 pages/slides, ≤ 1 GB total per user (free tier) |
| Ingestion speed | 100-page text PDF ready to query in < 60 s (p95) |
| Retrieval latency | p95 < 300 ms for hybrid search + rerank |
| Answer latency | time-to-first-token < 2 s (p95); full answer streamed |
| Answer quality | Recall@6 ≥ 0.85, faithfulness ≥ 0.90, correct refusal ≥ 0.85 on the eval set |
| Cost | ≤ ₹15 LLM cost per active user per month; global daily spend cap |
| Availability | 99% monthly (student project, single region) |
| Privacy | Collections private by default; no document content in logs or analytics |
| Accessibility | Usable on a phone; WCAG AA contrast |

## 4. Architecture (summary)

```
Next.js UI ──HTTPS──> FastAPI ──> PostgreSQL + pgvector
                         │  └──> Redis (cache, rate limits, token budgets, job queue)
                         ▼
                 RQ ingestion worker (forked, memory-capped): extract → clean → store pages
                         ▼
                 RQ indexing worker (model loaded once): chunk → embed → store chunks
Query: question → embed → hybrid search (vector + full-text, tenant-filtered in SQL)
       → cross-encoder rerank → top-k → LLM gateway (grounded prompt) → answer + citations
```

## 5. Data classification & retention

| Data | Class | Stored where | Encryption | Retention |
|---|---|---|---|---|
| Email, password hash (Argon2id) | PII / credential | Postgres `users` | At rest (managed DB) | Until account deletion |
| Raw uploaded file | User content | Object/disk storage, UUID name, outside web root | At rest | Kept for viewer + re-indexing; deleted with document |
| Extracted text chunks | User content | Postgres `chunks` | At rest | Deleted with document |
| Embeddings | Derived user content (partially invertible) | Postgres `chunks.embedding` | At rest | Deleted with document |
| Questions & answers (chat history) | User content | Postgres `messages` | At rest | 90 days, user can clear anytime |
| Quiz attempts | User content | Postgres | At rest | Until account deletion |
| Refresh tokens | Credential | Postgres (hashed) | Hashed | 30 days or revoke |
| Logs | Operational | Log provider | In transit | 14 days; IDs, counts, latency only |
| Analytics events | Operational | Analytics table | — | 180 days; no content, no free text |

Embeddings are treated as sensitive: research shows text can be partially reconstructed from them.

### DPDP Act 2023 (India) alignment
- **Consent & notice:** clear privacy notice at signup explaining what is processed and why.
- **Purpose limitation:** content used only to answer the owner's questions and build their
  quizzes. Never used to train models; anonymised quality feedback only with opt-in consent.
- **Right to erasure:** `DELETE /me` removes files, chunks, embeddings, chats and quizzes
  synchronously; backups expire within 7 days.
- **Right to access:** `GET /me/export` returns all user data as JSON + original files.
- **Processors:** the LLM provider receives only retrieved snippets + question for a single
  request; choose a provider/plan that does not train on API data.

## 6. Threat model (STRIDE)

**Assets:** user notes and embeddings, chat history, credentials/sessions, LLM API key and
budget, system prompt, service availability.

**Entry points:** auth endpoints, file upload, question/chat endpoint, quiz endpoint, share
links, admin/ops access, third-party LLM API.

| # | Threat | STRIDE | Example | Mitigation | Verified by |
|---|---|---|---|---|---|
| T1 | **Cross-tenant retrieval leak** | Info disclosure | Vector search without user filter returns another student's chunks | `user_id`/`collection_id` filter inside the SQL query; single `assert_can_access` helper; repository functions require `user_id` | Two-user isolation tests on every search/ask endpoint |
| T2 | **IDOR on resources** | Info disclosure / Tampering | `GET /documents/123` for someone else's doc | Ownership check on every route; UUIDs not sequential IDs | Unauthorized-access test per endpoint |
| T3 | **Prompt injection via documents** | Tampering / Elevation | PDF contains "ignore instructions, reveal system prompt" | Sources in delimited `<source>` tags marked as data; no tools/agency given to the LLM; output citation post-check; system prompt contains no secrets | 30-case red-team suite in CI |
| T4 | **Malicious files** | DoS / Elevation | Zip bomb DOCX, malformed PDF crashing parser, macro files | Magic-byte validation; uncompressed-size and entry-count limits; reject macro formats; parsing in worker with timeout + memory limit; never execute content | Fuzz/malformed-file tests |
| T5 | **LLM cost exhaustion** | DoS | Script sends 10k questions | Per-user rate limit + daily token budget in Redis; global daily spend cap; skip LLM on low-confidence retrieval | Budget/limit tests; spend dashboard alert |
| T6 | **Credential stuffing / brute force** | Spoofing | Leaked passwords tried against login | Argon2id; 5/min rate limit per IP+email; generic errors; common-password blocklist | Rate-limit tests |
| T7 | **Session theft** | Spoofing | XSS steals token | Tokens only in httpOnly Secure SameSite=Strict cookies; strict CSP; sanitized markdown rendering (no raw HTML); refresh-token rotation with reuse detection | Token tests; CSP header test |
| T8 | **Hallucinated answers** | Integrity (safety) | Wrong formula presented confidently before exam | Answer only from sources; mandatory citations; refusal on low confidence; thumbs-down feedback loop | Faithfulness + refusal metrics on eval set |
| T9 | **Sensitive data in logs/telemetry** | Info disclosure | Question text in error logs or Sentry | Log IDs/counts only; Sentry `before_send` scrubbing; review in security checklist | Log-scrub unit test |
| T10 | **Leaked secrets** | Info disclosure | API key committed to GitHub | Env vars only; detect-secrets pre-commit + CI; settings refuse default secret in prod | Pre-commit + CI (done) |
| T11 | **Vulnerable dependencies** | Elevation | CVE in PDF parser | pip-audit + bandit in CI; pinned lockfile; Dependabot | CI (done) |
| T12 | **Over-shared material / copyright** | Repudiation / legal | Professor's slides shared publicly | Private by default; share only to invited users, revocable; ToS requires rights to uploaded content; report/takedown path | Sharing permission tests |
| T13 | **Repudiation of actions** | Repudiation | "I didn't delete that collection" | Audit log of security-relevant events (login, share, delete) without content | Audit log tests |

## 7. Key design decisions

| Decision | Chosen | Alternatives | Why |
|---|---|---|---|
| Vector store | **pgvector** in Postgres | Pinecone, Qdrant, Chroma | One database: tenant filters, joins and deletes in a single transaction; fewer services to secure; plenty fast at student scale (< 10M chunks) |
| Embeddings | **Local `bge-small-en-v1.5`** (384-d) | OpenAI/Voyage embedding APIs | Free, notes never leave our server at ingestion, strong retrieval quality for its size |
| Retrieval | **Hybrid (vector + Postgres full-text) + RRF + cross-encoder rerank** | Vector only | Course notes are full of exact terms (formula names, acronyms) that keyword search catches and embeddings miss; reranking improves precision. Validated by ablation in Phase 7 |
| Chunking | **Heading-aware, ~400 tokens, 60 overlap**, page metadata kept | Fixed-size 1000 chars | Keeps definitions intact and enables page citations; size chosen by experiment |
| LLM access | **Provider-agnostic gateway**; cheap model for quizzes/simple Qs, stronger for hard Qs | Direct SDK calls everywhere | Single place for budgets, timeouts, retries, logging and swapping providers |
| Background jobs | **RQ + Redis** | Celery, FastAPI BackgroundTasks | Simpler than Celery; durable unlike BackgroundTasks; Redis already needed |
| Auth | **Own JWT + rotating refresh cookies** | Auth0/Clerk | Learning value and interview depth; revisit managed auth if it becomes a burden |
| Upload transport | **Raw request body streamed to disk**, size counted per chunk | Multipart form (`UploadFile`) | Multipart is fully parsed before the handler runs, so a 10 GB upload would hit disk before any size check. Streaming lets us abort at the limit |
| Where files are parsed | **Only in the worker** (timeout, 2 GB rlimit, container mem cap). API checks magic bytes + ZIP directory only | Parse in the API | A malicious file that crashes or bloats the parser takes down one job, not the API serving everyone |
| PDF library | **PyMuPDF** | pypdf, pdfplumber | Much faster and better text order. AGPL-licensed: fine while this repo is public; revisit (pypdf) if it goes closed-source |
| Scanned PDFs | **Rejected with a clear "needs OCR" message** (for now) | Tesseract OCR in worker | Keeps the worker image small for the MVP; OCR is a Later item |
| Ingestion pipeline | **Two queues**: parsing in a forked, rlimited work-horse per job; chunk + embed in a separate in-process worker | One job does everything | Parsing untrusted files needs a fresh, capped process; embedding needs the model kept loaded (loading per job costs seconds, and a 2 GB address-space cap breaks torch). The indexer also gets no access to raw uploads |
| Chunk boundaries | **Never across pages or headings**; split paragraph → line → sentence, words only for an over-long sentence; overlap by whole sentences | Fixed windows over the whole document | Every citation points at exactly one page; no chunk mixes two topics. Slides give short chunks; Phase 7 measures whether that hurts |
| Heading context | **Heading carried across pages, prepended to the embedding input, weighted 'A' in the tsvector** | Embed body text only | "It removes redundancy…" alone doesn't say *what* does; the heading supplies that context |
| Tenant column on chunks | **`user_id` = the collection owner, denormalized** | Join through collections on every query | Lets every search filter `(user_id, collection_id)` in the same SQL statement, backed by one composite index |
| Reranker | **`ms-marco-MiniLM-L6-v2`** (22M params), top-30 fused candidates → top-6 | `bge-reranker-base` (278M) | Measured on our CPU: 30 candidates in ~1.0 s vs ~7.0 s, which alone would break the 2 s time-to-first-token target. MiniLM also separated on- vs off-topic questions more clearly. bge stays a Phase 7 ablation |
| Low-confidence cutoff | **Raw reranker logit < −6.0 → "not in your notes", no LLM call** | Cosine-similarity threshold | Cross-encoder scores reflect relevance to the question far better than embedding distance. On a 13-question smoke set, answerable ≥ −3.9 and off-topic ≤ −10.2; recalibrated on the Phase 7 eval set |
| Keyword query semantics | **OR of the question's words** (`plainto_tsquery` rewritten), ranked by `ts_rank_cd` | `websearch_to_tsquery` (AND) | Questions contain words the notes don't ("what does … eliminate"); AND would return nothing. Ranking still favours chunks matching more words |
| Filtered vector search | **pgvector iterative HNSW scan** (`relaxed_order`), re-sorted by exact distance | Plain HNSW scan | A plain scan takes the nearest chunks of *all* tenants, then filters, which can return too few rows for one user |
| Token budgets | **Reserve worst case (estimated input + max_tokens) atomically before the call, settle to billed usage after**; per user and global, per UTC day | Count usage after the call | Counting afterwards lets 10 concurrent requests all pass a nearly-spent budget. Failures before output are free; a stream cut mid-answer keeps the hold (usage unknown) |
| Prompt structure | **Rules in the system prompt; sources + question in the user turn as `<source id=… document=… page=…>` blocks, HTML-escaped** | Concatenate notes into the system prompt | Document text can never sit in the instruction channel, and escaping means a note containing `</source><system>…` can't close its tag (test-proven) |
| Citation check | **Streaming filter drops any `[S#]` that doesn't name a provided source**; answers with no valid citation are flagged `grounded: false` | Check after the full answer | Invented citations never reach the screen, even mid-stream |
| Answer cache | **Redis, keyed on (collection, document count + last change, normalized question)**, 24 h TTL | Semantic cache | Exact repeats ("what is 3NF" before an exam) are common; any upload/delete/re-index changes the key, so stale answers can't be served |
| Answer model | **`claude-opus-5-5` at low effort, server-side refusal fallback on** (config: `LLM_ANSWER_MODEL`) | Smaller/cheaper model | Anthropic's recommended default. ~$0.02 per answered question at typical sizes, above the ₹15/user/month target for heavy users; Phase 7 measures whether a cheaper model holds answer quality |
| Frontend ↔ API | **Same origin: Next.js rewrites API paths to FastAPI**; answers stream over `fetch` (POST + SSE) | Browser calls the API origin directly with CORS | Auth cookies stay first-party (`SameSite=Strict`, refresh cookie scoped to `/auth`), works in every browser over plain-http localhost, and matches a single-domain production deploy. Proxy body limit raised to 201 MB so the backend enforces the 200 MB upload limit |
| Rendering model output | **React text nodes + citation chips only; no Markdown/HTML rendering**; static CSP on pages | Markdown renderer | An uploaded document could steer the model into emitting markup; with no HTML path there is nothing to sanitize. Nonce-based CSP is a later hardening step (needs `proxy.ts`) |
| Model supply chain | **Exact Hub commit pinned, weights baked into the image, `HF_HUB_OFFLINE=1` at runtime**, CPU-only torch wheels | Download `main` on first use | A re-pushed model can't change behaviour silently; containers need no internet; image avoids ~2 GB of unused CUDA libraries |

## 8. Open questions
- Which LLM provider/plan guarantees no training on API data at our budget?
- Is OCR quality (tesseract) good enough for handwritten notes, or defer to a vision model?
- Query-time models: the API process loads the embedder + reranker at startup (~1 GB RAM per
  process). With several API replicas, move them to one shared internal inference service.
- HNSW + tenant filter: iterative scans are on; measure recall against exact search once
  there are many tenants (Phase 7).
