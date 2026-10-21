# Product requirements: NoteMind

What we are building and why. The full design, threat model and decision record are in
[SYSTEM_DESIGN.md](SYSTEM_DESIGN.md); this page is the short version a new contributor reads first.

## Problem

Students revise from their own notes and slides, but searching hundreds of pages before an
exam is slow, and general chatbots answer from the internet instead of what *their* course
teaches, sometimes confidently wrong.

## Target user

A college or university student (India first) revising for exams from PDF notes, lecture
slides (PPTX with speaker notes) and Word documents. Uses a laptop at home and a phone on
the go. Often shares material with a study group.

## Main outcome

A student uploads a course's material and, within a minute, can ask questions in plain
English and get answers **only from that material**, each claim **cited to a page**, and
practice with **quizzes** generated from it.

## MVP scope (v1): all done

| # | User story | Status |
|---|---|---|
| U1 | Sign up and log in securely | Done (Argon2id, rotating refresh cookies, bot checks) |
| U2 | One collection per course | Done |
| U3 | Upload PDF / PPTX / DOCX (≤ 200 MB, ≤ 2,000 pages) | Done |
| U4 | Ask a question, get a streamed answer with page citations | Done |
| U5 | Be told "not found in your notes" when it isn't there | Done |
| U6 | Generate an MCQ quiz from a collection or topic | Done |
| U7 | Export my data / delete my account | Done |
| — | Share a collection read-only via revocable invite link | Done (was "Later") |
| — | Public site: landing, features, privacy, terms, cookie consent | Done |

## Not in v1

- OCR for scanned or handwritten notes (scanned PDFs are rejected with a clear message)
- Google / college single sign-on, email verification
- Spaced repetition and a "weak topics" dashboard
- Public or cross-user search; grading or exam proctoring; general chat without sources

## Success measures

| Measure | Target | Where measured |
|---|---|---|
| Retrieval Recall@6 | ≥ 0.85 | `ml/eval/REPORT.md` (seed set: 1.00) |
| Correct refusal on unanswerable questions | ≥ 0.85 | `ml/eval/REPORT.md` |
| Time to first answer token | < 2 s p95 | smoke test, eval |
| 200 MB PDF ready to query | < 60 s | `scripts/smoke_test.py` (42 s for 1,500 pages) |
| Lighthouse (mobile) | ≥ 90 in every category | [TEST_PLAN.md](TEST_PLAN.md) |
