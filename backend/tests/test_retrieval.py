import logging
import uuid

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.models import Collection
from app.rag.retriever import reciprocal_rank_fusion, retrieve
from tests.conftest import signup
from tests.files import make_pdf

NORMALIZATION = "3.1 Normalization\nThird normal form removes transitive dependencies."
TRANSACTIONS = "3.2 Transactions\nA transaction is atomic: it commits fully or rolls back."
LOCKING = "4 Concurrency\nTwo-phase locking prevents lost updates but can deadlock."
PRIVATE_QUESTION = "what does third normal form remove zebra"


@pytest.fixture
def alice(make_client):
    client = make_client()
    signup(client, "alice@x.com")
    return client


@pytest.fixture
def bob(make_client):
    client = make_client()
    signup(client, "bob@x.com")
    return client


def make_collection(client, pages, name="DBMS", filename="notes.pdf"):
    cid = client.post("/collections", json={"name": name}).json()["id"]
    response = client.post(
        f"/collections/{cid}/documents", params={"filename": filename}, content=make_pdf(pages)
    )
    assert response.status_code == 202, response.text
    return cid, response.json()["id"]


def search(client, cid, query):
    return client.post(f"/collections/{cid}/search", json={"query": query})


# --- results ----------------------------------------------------------------------------------


def test_search_returns_best_chunk_with_citation_fields(alice):
    cid, doc_id = make_collection(alice, [NORMALIZATION, TRANSACTIONS, LOCKING])
    response = search(alice, cid, "what does third normal form remove?")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["low_confidence"] is False
    best = body["chunks"][0]
    assert best["heading"] == "3.1 Normalization"
    assert best["page"] == 1
    assert best["document_id"] == doc_id
    assert best["document_title"] == "notes.pdf"
    assert best["text"] == "Third normal form removes transitive dependencies."
    scores = [c["score"] for c in body["chunks"]]
    assert scores == sorted(scores, reverse=True)


def test_reranker_sees_heading_with_chunk_text(alice, reranker):
    cid, _ = make_collection(alice, [NORMALIZATION])
    search(alice, cid, "normalization")
    _, passages = reranker.calls[-1]
    assert passages == ["3.1 Normalization\nThird normal form removes transitive dependencies."]


def test_keeps_only_top_k(alice, monkeypatch):
    monkeypatch.setattr(get_settings(), "retrieval_top_k", 2)
    cid, _ = make_collection(alice, [NORMALIZATION, TRANSACTIONS, LOCKING])
    assert len(search(alice, cid, "normal form transaction locking").json()["chunks"]) == 2


def test_unrelated_question_is_low_confidence(alice):
    cid, _ = make_collection(alice, [NORMALIZATION, TRANSACTIONS])
    body = search(alice, cid, "who won the football world cup").json()
    assert body["low_confidence"] is True


def test_empty_collection_is_low_confidence(alice):
    cid = alice.post("/collections", json={"name": "Empty"}).json()["id"]
    assert search(alice, cid, "anything").json() == {"low_confidence": True, "chunks": []}


def test_keyword_search_matches_any_word_not_all(alice, embedder, monkeypatch):
    # Disable the vector side so only full-text search can find the chunk. A question with
    # extra words ("explain", "please") must still match: words are ORed, not ANDed.
    monkeypatch.setattr(embedder, "embed_query", lambda q: embedder._embed("zzzz"))
    cid, _ = make_collection(alice, [LOCKING])
    body = search(alice, cid, "please explain deadlock").json()
    assert [c["heading"] for c in body["chunks"]] == ["4 Concurrency"]


def test_question_of_only_stopwords_does_not_error(alice):
    cid, _ = make_collection(alice, [NORMALIZATION])
    assert search(alice, cid, "what is the").status_code == 200


# --- tenant isolation (threat T1) ---------------------------------------------------------------


def test_identical_notes_and_question_never_cross_users(alice, bob):
    alice_cid, alice_doc = make_collection(alice, [NORMALIZATION, TRANSACTIONS])
    bob_cid, bob_doc = make_collection(bob, [NORMALIZATION, TRANSACTIONS])

    for client, cid, own, other in (
        (alice, alice_cid, alice_doc, bob_doc),
        (bob, bob_cid, bob_doc, alice_doc),
    ):
        chunks = search(client, cid, "third normal form transaction").json()["chunks"]
        assert chunks
        assert {c["document_id"] for c in chunks} == {own}
        assert other not in str(chunks)


def test_other_tenants_cannot_crowd_out_your_chunks(alice, bob, monkeypatch):
    # If results were fetched globally and filtered afterwards, Bob's 8 closer matches would
    # fill the 3 candidate slots and Alice would get nothing.
    monkeypatch.setattr(get_settings(), "retrieval_candidates", 3)
    question = "normal form removes dependencies"
    # Distinct pages: identical lines on every page would be stripped as a running header.
    bob_cid, _ = make_collection(
        bob, [f"{i} Normalization\nNormal form {i} removes dependencies." for i in range(1, 9)]
    )
    alice_cid, alice_doc = make_collection(alice, ["Notes\nnormal form trivia and other things."])
    assert len(search(bob, bob_cid, question).json()["chunks"]) == 3  # Bob's matches exist

    chunks = search(alice, alice_cid, question).json()["chunks"]
    assert [c["document_id"] for c in chunks] == [alice_doc]


def test_owner_and_collection_must_both_match(alice, bob, db, embedder, reranker):
    alice_cid, _ = make_collection(alice, [NORMALIZATION])
    bob_cid, _ = make_collection(bob, [NORMALIZATION])
    with db() as session:
        alice_id = session.scalar(
            select(Collection.owner_id).where(Collection.id == uuid.UUID(alice_cid))
        )
        # Alice's user_id with Bob's collection: nothing, even if the API layer were bypassed.
        result = retrieve(
            session,
            embedder,
            reranker,
            owner_id=alice_id,
            collection_id=uuid.UUID(bob_cid),
            question="third normal form",
        )
    assert result.chunks == []
    assert result.low_confidence is True


def test_search_is_scoped_to_one_collection(alice):
    dbms_cid, dbms_doc = make_collection(alice, [NORMALIZATION], name="DBMS")
    os_cid, _ = make_collection(
        alice, ["Scheduling\nRound robin normal form."], name="OS", filename="os.pdf"
    )
    chunks = search(alice, dbms_cid, "normal form").json()["chunks"]
    assert {c["document_id"] for c in chunks} == {dbms_doc}


def test_stranger_gets_404(alice, bob):
    cid, _ = make_collection(alice, [NORMALIZATION])
    assert search(bob, cid, "normal form").status_code == 404


def test_requires_login(alice, make_client):
    cid, _ = make_collection(alice, [NORMALIZATION])
    assert search(make_client(), cid, "normal form").status_code == 401


def test_viewer_can_search_shared_collection(alice, bob):
    cid, doc_id = make_collection(alice, [NORMALIZATION])
    token = alice.post(f"/collections/{cid}/invites", json={}).json()["token"]
    assert bob.post("/invites/accept", json={"token": token}).status_code == 200

    chunks = search(bob, cid, "third normal form").json()["chunks"]
    assert [c["document_id"] for c in chunks] == [doc_id]


# --- input limits and logging -------------------------------------------------------------------


@pytest.mark.parametrize("query", ["", "   ", "x" * 501])
def test_rejects_empty_or_huge_queries(alice, query):
    cid, _ = make_collection(alice, [NORMALIZATION])
    assert search(alice, cid, query).status_code == 422


def test_search_is_rate_limited(alice):
    cid, _ = make_collection(alice, [NORMALIZATION])
    codes = [search(alice, cid, "normal form").status_code for _ in range(61)]
    assert codes[:60] == [200] * 60
    assert codes[60] == 429


def test_logs_counts_but_never_question_or_notes(alice, caplog):
    cid, _ = make_collection(alice, [NORMALIZATION])
    with caplog.at_level(logging.INFO, logger="app.rag.retriever"):
        search(alice, cid, PRIVATE_QUESTION)
    assert f"collection_id={cid}" in caplog.text
    assert "zebra" not in caplog.text
    assert "transitive" not in caplog.text


# --- fusion -------------------------------------------------------------------------------------


def test_rrf_rewards_items_found_by_both_searches():
    vector = ["a", "b", "c"]
    keyword = ["c", "d"]
    # c is in both lists; b and d tie (both rank 2) and keep first-seen order.
    assert reciprocal_rank_fusion([vector, keyword]) == ["c", "a", "b", "d"]


def test_rrf_handles_empty_rankings():
    assert reciprocal_rank_fusion([[], []]) == []
    assert reciprocal_rank_fusion([["a"], []]) == ["a"]
