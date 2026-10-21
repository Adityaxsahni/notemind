"""End-to-end check of the running stack through the frontend proxy, like the browser does.

Signs up throwaway users, uploads a PDF, waits for indexing, then checks search, cited
answers, refusals, quizzes, the 200 MB limit, sharing, export and account deletion. Uses a
few LLM calls. Deletes its main account at the end.

    docker compose up -d --build
    uv run --project backend python scripts/make_big_pdf.py course-pack.pdf
    uv run --project backend python scripts/smoke_test.py course-pack.pdf
"""

import json
import os
import sys
import time
import uuid

import httpx

BASE = "http://localhost:3000"
PASSWORD = "correct-horse-battery-staple-42"  # noqa: S105  # pragma: allowlist secret
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""), flush=True)
    return ok


def client() -> httpx.Client:
    return httpx.Client(base_url=BASE, timeout=httpx.Timeout(60, read=900, write=900))


def signup(c: httpx.Client, tag: str) -> str:
    email = f"{tag}-{uuid.uuid4().hex[:8]}@example.com"
    # Like the real form: load the bot-check token, take a human amount of time, leave the
    # honeypot empty. (With Turnstile enabled, sign-up needs a real browser instead.)
    token = c.get("/auth/form-token").json()["token"]
    time.sleep(2.2)
    r = c.post(
        "/auth/signup",
        json={"email": email, "password": PASSWORD, "form_token": token, "website": ""},
    )
    if r.status_code == 202:
        # Two-step sign-in. Locally without SMTP the code comes back in the response.
        challenge = r.json()
        check(f"sign-in code issued {tag}", bool(challenge.get("dev_code")), r.text[:120])
        r = c.post(
            "/auth/otp/verify",
            json={"challenge_id": challenge["challenge_id"], "code": challenge["dev_code"]},
        )
        check(f"sign up {tag} (password + code)", r.status_code == 200, f"{r.status_code}")
    else:
        check(f"sign up {tag}", r.status_code == 201, f"{r.status_code} {r.text[:120]}")
    # Browsers treat http://localhost as secure and send Secure cookies to it; httpx doesn't,
    # so re-add them without the flag.
    for cookie in list(c.cookies.jar):
        c.cookies.set(cookie.name, cookie.value, domain=cookie.domain, path=cookie.path)
    return email


def ask(c: httpx.Client, cid: str, question: str) -> dict:
    started = time.perf_counter()
    first = None
    done, error = None, None
    with c.stream("POST", f"/collections/{cid}/ask", json={"question": question}) as r:
        if r.status_code != 200:
            return {"status": r.status_code, "error": r.read().decode()[:200]}
        buffer = ""
        for text in r.iter_text():
            first = first or time.perf_counter() - started
            buffer += text
        for block in buffer.strip().split("\n\n"):
            name, data = block.split("\n", 1)
            payload = json.loads(data.removeprefix("data: "))
            if name == "event: done":
                done = payload
            elif name == "event: error":
                error = payload["message"]
    return {
        "status": 200,
        "done": done,
        "error": error,
        "ttft_s": round(first or 0, 2),
        "total_s": round(time.perf_counter() - started, 2),
    }


def main(pdf_path: str) -> int:
    size_mb = os.path.getsize(pdf_path) / 1024 / 1024
    alice = client()

    r = alice.get("/health")
    check("health", r.status_code == 200, r.text[:80])
    signup(alice, "alice")
    r = alice.get("/me")
    check("session cookie works (/me)", r.status_code == 200, f"{r.status_code}")

    cid = alice.post("/collections", json={"name": "OS + DBMS course pack"}).json()["id"]
    check("create collection", bool(cid), cid)

    # --- 200 MB upload ------------------------------------------------------------------
    started = time.perf_counter()
    with open(pdf_path, "rb") as f:
        r = alice.post(
            f"/collections/{cid}/documents",
            params={"filename": "course-pack.pdf"},
            content=f,
            headers={"Content-Length": str(os.path.getsize(pdf_path))},
        )
    upload_s = time.perf_counter() - started
    if not check(
        f"upload {size_mb:.0f} MB PDF",
        r.status_code == 202,
        f"{r.status_code} in {upload_s:.1f}s {r.text[:150]}",
    ):
        return report()
    doc_id = r.json()["id"]

    started, last = time.perf_counter(), None
    while True:
        d = alice.get(f"/collections/{cid}/documents/{doc_id}").json()
        state = (d["status"], d["progress"])
        if state != last:
            print(
                f"    {time.perf_counter() - started:6.1f}s  {d['status']:<10} {d['progress']:>3}%  pages={d['page_count']}",
                flush=True,
            )
            last = state
        if d["status"] in ("ready", "failed") or time.perf_counter() - started > 2400:
            break
        time.sleep(3)
    ingest_s = time.perf_counter() - started
    if not check(
        "document processed",
        d["status"] == "ready",
        f"{d['status']} pages={d['page_count']} in {ingest_s:.0f}s error={d['error']}",
    ):
        return report()

    # --- over the limit ------------------------------------------------------------------
    too_big = b"%PDF-1.7\n" + os.urandom(201 * 1024 * 1024)
    r = alice.post(
        f"/collections/{cid}/documents", params={"filename": "huge.pdf"}, content=too_big
    )
    check("201 MB upload rejected", r.status_code == 413, f"{r.status_code} {r.text[:100]}")

    # --- search & answers ------------------------------------------------------------------
    for question, page in [
        ("How does the Banker's algorithm avoid deadlock?", 417),
        ("Why are B+ tree leaves linked together?", 902),
        ("What is Belady's anomaly?", 1377),
    ]:
        r = alice.post(f"/collections/{cid}/search", json={"query": question}).json()
        pages = [h["page"] for h in r["chunks"]]
        check(f"search finds page {page}", page in pages[:3], f"top pages {pages[:3]}")
        a = ask(alice, cid, question)
        done = a.get("done") or {}
        cited = [c["page"] for c in done.get("citations", [])]
        check(
            f"answer cites page {page}",
            page in cited,
            f"cited={cited} ttft={a.get('ttft_s')}s total={a.get('total_s')}s error={a.get('error') or a.get('status')}",
        )
        if done:
            print(f"      answer: {done['answer'][:220]!r}")

    a = ask(alice, cid, "Who won the 2022 football world cup?")
    done = a.get("done") or {}
    check(
        "off-topic question refused",
        done.get("answer", "").startswith("I couldn't find"),
        f"{done.get('answer', a)!r:.120}",
    )

    # --- quizzes ----------------------------------------------------------------------------
    for body in ({"topic": "deadlock avoidance banker", "num_questions": 3}, {"num_questions": 3}):
        started = time.perf_counter()
        r = alice.post(f"/collections/{cid}/quiz", json=body)
        took = time.perf_counter() - started
        ok = r.status_code == 200 and len(r.json().get("questions", [])) > 0
        check(f"quiz {body}", ok, f"{r.status_code} in {took:.1f}s {'' if ok else r.text[:200]}")
        if ok:
            q = r.json()["questions"][0]
            print(
                f"      Q: {q['question']}  A: {q['options'][q['answer']]}  (page {q['citation']['page']})"
            )
    r = alice.post(f"/collections/{cid}/quiz", json={"topic": "football world cup"})
    check(
        "quiz on uncovered topic says not found",
        r.status_code == 200 and r.json()["found"] is False,
        r.text[:100],
    )

    # --- sharing --------------------------------------------------------------------------
    token = alice.post(f"/collections/{cid}/invites", json={}).json()["token"]
    bob = client()
    signup(bob, "bob")
    r = bob.post("/invites/accept", json={"token": token})
    check("classmate joins via invite", r.status_code == 200, f"{r.status_code}")
    r = bob.post(f"/collections/{cid}/documents", params={"filename": "x.pdf"}, content=b"%PDF-1.7")
    check("classmate can't upload (read-only)", r.status_code in (403, 404), f"{r.status_code}")
    stranger = client()
    signup(stranger, "eve")
    r = stranger.get(f"/collections/{cid}")
    check("stranger can't see the collection", r.status_code == 404, f"{r.status_code}")

    # --- security & website -------------------------------------------------------------------
    bot = client()
    r = bot.post("/auth/signup", json={"email": "bot@example.com", "password": PASSWORD})
    check("bot sign-up without form token refused", r.status_code == 400, f"{r.status_code}")
    r = stranger.get("/admin/audit-log")
    check("admin pages closed to normal users", r.status_code == 403, f"{r.status_code}")
    for path in (
        "/",
        "/features",
        "/privacy",
        "/terms",
        "/robots.txt",
        "/sitemap.xml",
        "/opengraph-image",
    ):
        r = bot.get(path)
        check(f"page {path}", r.status_code == 200, f"{r.status_code} {len(r.content)} bytes")
    r = bot.get("/no-such-page")
    check("custom 404 page", r.status_code == 404 and "our notes" in r.text, f"{r.status_code}")
    headers = bot.get("/").headers
    check(
        "security headers on pages",
        "frame-ancestors 'none'" in headers.get("content-security-policy", "")
        and headers.get("x-frame-options") == "DENY",
        headers.get("content-security-policy", "")[:60],
    )

    # --- data rights --------------------------------------------------------------------------
    r = alice.get("/me/export")
    check(
        "export my data",
        r.status_code == 200 and "collections" in r.text,
        f"{r.status_code} {len(r.content)} bytes",
    )
    r = alice.request("DELETE", "/me", json={"password": PASSWORD})
    check("delete account", r.status_code == 204, f"{r.status_code}")
    r = bob.get(f"/collections/{cid}")
    check(
        "deleted owner's collection is gone for classmate", r.status_code == 404, f"{r.status_code}"
    )
    for throwaway in (bob, stranger):  # leave no test accounts behind
        throwaway.request("DELETE", "/me", json={"password": PASSWORD})
    return report()


def report() -> int:
    failed = [name for name, ok, _ in results if not ok]
    print(
        f"\n{len(results) - len(failed)}/{len(results)} checks passed"
        + (f"; failed: {failed}" if failed else "")
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
