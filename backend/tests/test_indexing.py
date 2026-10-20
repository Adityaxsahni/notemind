import logging
import uuid

import numpy as np
import pytest
from sqlalchemy import func, select, text

from app.config import get_settings
from app.ingestion.tasks import INDEXING_FAILURE, index_document
from app.models import EMBEDDING_DIM, Chunk, Collection, Document, DocumentStatus
from tests.conftest import GOOD_PASSWORD, signup
from tests.files import make_pdf, make_pptx

NORMALIZATION = "3.1 Normalization\nThird normal form removes transitive dependencies."
TRANSACTIONS = "3.2 Transactions\nA transaction is atomic: all of it happens or none of it."
PRIVATE_NOTE_TEXT = "the-private-exam-answer"


@pytest.fixture
def alice(make_client):
    client = make_client()
    signup(client, "alice@x.com")
    return client


@pytest.fixture
def cid(alice):
    return alice.post("/collections", json={"name": "DBMS"}).json()["id"]


def upload(client, cid, data, filename="notes.pdf"):
    response = client.post(
        f"/collections/{cid}/documents", params={"filename": filename}, content=data
    )
    assert response.status_code == 202, response.text
    return response.json()["id"]


def chunks_of(db, doc_id):
    with db() as session:
        return session.scalars(
            select(Chunk).where(Chunk.document_id == uuid.UUID(doc_id)).order_by(Chunk.position)
        ).all()


def test_upload_is_chunked_embedded_and_ready(alice, cid, db):
    doc_id = upload(alice, cid, make_pdf([NORMALIZATION, TRANSACTIONS]))

    document = alice.get(f"/collections/{cid}/documents/{doc_id}").json()
    assert document["status"] == "ready"
    assert document["progress"] == 100

    chunks = chunks_of(db, doc_id)
    assert [(c.position, c.page, c.heading) for c in chunks] == [
        (0, 1, "3.1 Normalization"),
        (1, 2, "3.2 Transactions"),
    ]
    assert chunks[0].text == "Third normal form removes transitive dependencies."
    assert chunks[0].token_count == 6
    for c in chunks:
        assert len(c.embedding) == EMBEDDING_DIM
        assert np.linalg.norm(c.embedding) == pytest.approx(1.0, abs=1e-5)


def test_chunks_carry_the_collection_owner_and_collection_ids(alice, cid, db):
    doc_id = upload(alice, cid, make_pdf([NORMALIZATION]))
    with db() as session:
        owner_id = session.scalar(
            select(Collection.owner_id).where(Collection.id == uuid.UUID(cid))
        )
    for c in chunks_of(db, doc_id):
        assert c.user_id == owner_id
        assert str(c.collection_id) == cid


def test_heading_is_part_of_the_embedded_text(alice, cid, embedder):
    upload(
        alice, cid, make_pptx([{"title": "Weak Entities", "body": "Depend on an owner."}]), "l.pptx"
    )
    assert embedder.calls == [["Weak Entities\nDepend on an owner."]]


def test_embeds_in_batches_of_the_configured_size(alice, cid, embedder, monkeypatch):
    monkeypatch.setattr(get_settings(), "embedding_batch_size", 2)
    pages = [f"{i} Topic\nBody of page {i}." for i in range(1, 6)]
    upload(alice, cid, make_pdf(pages))
    assert [len(batch) for batch in embedder.calls] == [2, 2, 1]


def test_vector_and_keyword_search_find_the_right_chunk(alice, cid, db, embedder):
    upload(alice, cid, make_pdf([NORMALIZATION, TRANSACTIONS]))
    with db() as session:
        owner_id = session.scalar(select(Collection.owner_id))
        tenant = (Chunk.user_id == owner_id, Chunk.collection_id == uuid.UUID(cid))

        query = embedder.embed_query("what does third normal form remove")
        nearest = session.scalar(
            select(Chunk.heading).where(*tenant).order_by(Chunk.embedding.cosine_distance(query))
        )
        assert nearest == "3.1 Normalization"

        keyword = func.websearch_to_tsquery("english", "atomic transaction")
        hits = session.scalars(select(Chunk.heading).where(*tenant, Chunk.tsv.op("@@")(keyword)))
        assert list(hits) == ["3.2 Transactions"]


def test_index_matches_headings_through_the_tsvector(alice, cid, db):
    upload(alice, cid, make_pdf([NORMALIZATION]))
    with db() as session:
        hit = session.scalar(
            select(func.count())
            .select_from(Chunk)
            .where(Chunk.tsv.op("@@")(func.to_tsquery("english", "normalization")))
        )
    assert hit == 1  # "Normalization" only appears in the heading


def test_rerunning_indexing_replaces_chunks_instead_of_duplicating(alice, cid, db, embedder):
    doc_id = upload(alice, cid, make_pdf([NORMALIZATION, TRANSACTIONS]))
    with db() as session:
        document = session.get(Document, uuid.UUID(doc_id))
        document.status = DocumentStatus.PROCESSING  # as if the job were retried
        session.commit()
        index_document(session, embedder, document.id)
    assert [c.position for c in chunks_of(db, doc_id)] == [0, 1]


def test_indexing_skips_documents_that_are_not_processing(alice, cid, db, embedder):
    doc_id = upload(alice, cid, make_pdf([NORMALIZATION]))
    embedder.calls.clear()
    with db() as session:
        index_document(session, embedder, uuid.UUID(doc_id))  # already ready
        index_document(session, embedder, uuid.uuid4())  # deleted
    assert embedder.calls == []


def test_embedding_failure_marks_document_failed_without_logging_content(
    alice, cid, db, embedder, monkeypatch, caplog
):
    def boom(texts):
        raise RuntimeError("model crashed")

    monkeypatch.setattr(embedder, "embed_documents", boom)
    with caplog.at_level(logging.INFO):
        doc_id = upload(alice, cid, make_pdf([f"Topic\n{PRIVATE_NOTE_TEXT} is here."]))

    document = alice.get(f"/collections/{cid}/documents/{doc_id}").json()
    assert document["status"] == "failed"
    assert document["error"] == INDEXING_FAILURE
    assert chunks_of(db, doc_id) == []
    assert doc_id in caplog.text
    assert PRIVATE_NOTE_TEXT not in caplog.text


def test_deleting_a_document_deletes_its_chunks(alice, cid, db):
    doc_id = upload(alice, cid, make_pdf([NORMALIZATION]))
    assert alice.delete(f"/collections/{cid}/documents/{doc_id}").status_code == 204
    assert chunks_of(db, doc_id) == []


def test_deleting_the_account_deletes_all_chunks(alice, cid, db):
    upload(alice, cid, make_pdf([NORMALIZATION]))
    assert alice.request("DELETE", "/me", json={"password": GOOD_PASSWORD}).status_code == 204
    with db() as session:
        assert session.scalar(select(func.count()).select_from(Chunk)) == 0


def test_embedding_column_has_hnsw_cosine_index(db):
    with db() as session:
        indexdef = session.scalar(
            text("SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_chunks_embedding_hnsw'")
        )
    assert "USING hnsw" in indexdef
    assert "vector_cosine_ops" in indexdef
