import pytest
from sqlalchemy import select

from app.config import get_settings
from app.models import Document, DocumentPage
from tests.conftest import GOOD_PASSWORD, signup
from tests.files import make_docx_zip_bomb, make_pdf, make_pptx


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


@pytest.fixture
def cid(alice):
    return alice.post("/collections", json={"name": "DBMS"}).json()["id"]


def upload(client, cid, data, filename="notes.pdf"):
    return client.post(f"/collections/{cid}/documents", params={"filename": filename}, content=data)


def _files_on_disk(storage):
    return [p for p in storage.root.iterdir() if p.is_file()]


# --- happy path ---------------------------------------------------------------------------------


def test_upload_pdf_is_processed_into_pages(alice, cid, db, storage):
    response = upload(alice, cid, make_pdf(["Normalization reduces redundancy", "Joins"]))
    assert response.status_code == 202, response.text
    doc_id = response.json()["id"]

    document = alice.get(f"/collections/{cid}/documents/{doc_id}").json()
    assert document["status"] == "ready"
    assert document["page_count"] == 2
    assert document["kind"] == "pdf"
    assert document["filename"] == "notes.pdf"

    with db() as session:
        pages = session.scalars(select(DocumentPage).order_by(DocumentPage.page_number)).all()
    assert [p.page_number for p in pages] == [1, 2]
    assert "redundancy" in pages[0].text
    assert len(_files_on_disk(storage)) == 1


def test_upload_pptx(alice, cid):
    data = make_pptx([{"title": "ER Model", "notes": "Weak entities"}])
    doc = upload(alice, cid, data, "lecture.pptx").json()
    assert alice.get(f"/collections/{cid}/documents/{doc['id']}").json()["status"] == "ready"


def test_list_documents(alice, cid):
    upload(alice, cid, make_pdf(["one"]), "a.pdf")
    upload(alice, cid, make_pdf(["two"]), "b.pdf")
    names = [d["filename"] for d in alice.get(f"/collections/{cid}/documents").json()]
    assert sorted(names) == ["a.pdf", "b.pdf"]


def test_download_has_safe_headers(alice, cid):
    data = make_pdf(["hello"])
    doc_id = upload(alice, cid, data).json()["id"]
    response = alice.get(f"/collections/{cid}/documents/{doc_id}/file")
    assert response.status_code == 200
    assert response.content == data
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith("attachment")
    assert response.headers["content-security-policy"] == "sandbox"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_filename_is_sanitized(alice, cid):
    doc = upload(alice, cid, make_pdf(["x"]), "../../etc/passwd.pdf").json()
    assert doc["filename"] == "passwd.pdf"


# --- processing failures are reported, not crashes ---------------------------------------------


def test_pdf_without_text_fails_with_ocr_message(alice, cid):
    doc_id = upload(alice, cid, make_pdf([""])).json()["id"]
    doc = alice.get(f"/collections/{cid}/documents/{doc_id}").json()
    assert doc["status"] == "failed"
    assert "OCR" in doc["error"]


def test_corrupted_pdf_fails_gracefully(alice, cid):
    doc_id = upload(alice, cid, b"%PDF-1.7\nthis is not really a pdf").json()["id"]
    doc = alice.get(f"/collections/{cid}/documents/{doc_id}").json()
    assert doc["status"] == "failed"
    assert "Traceback" not in doc["error"]


# --- upload validation ---------------------------------------------------------------------------


def test_rejects_empty_upload(alice, cid):
    assert upload(alice, cid, b"").status_code == 400


def test_rejects_spoofed_extension(alice, cid, storage):
    response = upload(alice, cid, b"MZ\x90\x00 an exe", "notes.pdf")
    assert response.status_code == 415
    assert _files_on_disk(storage) == []  # nothing left behind


def test_rejects_zip_bomb(alice, cid, storage):
    response = upload(alice, cid, make_docx_zip_bomb(), "bomb.docx")
    assert response.status_code == 422
    assert _files_on_disk(storage) == []


def test_rejects_oversized_file_while_streaming(alice, cid, storage, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_upload_bytes", 1000)
    response = upload(alice, cid, b"%PDF-" + b"x" * 5000)
    assert response.status_code == 413
    assert _files_on_disk(storage) == []
    assert list((storage.root / ".tmp").iterdir()) == []  # temp file cleaned up


def test_enforces_storage_quota(alice, cid, monkeypatch):
    first = make_pdf(["first"])
    monkeypatch.setattr(get_settings(), "user_storage_quota_bytes", len(first) + 10)
    assert upload(alice, cid, first, "a.pdf").status_code == 202
    response = upload(alice, cid, make_pdf(["second document"]), "b.pdf")
    assert response.status_code == 413
    assert "storage limit" in response.json()["detail"]


def test_duplicate_upload_rejected(alice, cid):
    data = make_pdf(["same"])
    assert upload(alice, cid, data, "a.pdf").status_code == 202
    assert upload(alice, cid, data, "copy.pdf").status_code == 409


def test_upload_is_rate_limited(alice, cid):
    codes = [upload(alice, cid, make_pdf([f"doc {i}"]), f"{i}.pdf").status_code for i in range(31)]
    assert codes[:30] == [202] * 30
    assert codes[30] == 429


# --- authorization -------------------------------------------------------------------------------


def test_stranger_gets_404_everywhere(alice, bob, cid):
    doc_id = upload(alice, cid, make_pdf(["private"])).json()["id"]
    base = f"/collections/{cid}/documents"
    assert bob.get(base).status_code == 404
    assert bob.get(f"{base}/{doc_id}").status_code == 404
    assert bob.get(f"{base}/{doc_id}/file").status_code == 404
    assert bob.delete(f"{base}/{doc_id}").status_code == 404
    assert upload(bob, cid, make_pdf(["sneaky"])).status_code == 404


def test_viewer_can_read_but_not_upload_or_delete(alice, bob, cid):
    doc_id = upload(alice, cid, make_pdf(["shared notes"])).json()["id"]
    token = alice.post(f"/collections/{cid}/invites", json={}).json()["token"]
    bob.post("/invites/accept", json={"token": token})

    base = f"/collections/{cid}/documents"
    assert bob.get(base).status_code == 200
    assert bob.get(f"{base}/{doc_id}/file").status_code == 200
    assert upload(bob, cid, make_pdf(["mine"])).status_code == 403
    assert bob.delete(f"{base}/{doc_id}").status_code == 403


def test_document_id_from_another_collection_does_not_resolve(alice, cid):
    other = alice.post("/collections", json={"name": "OS"}).json()["id"]
    doc_id = upload(alice, cid, make_pdf(["x"])).json()["id"]
    assert alice.get(f"/collections/{other}/documents/{doc_id}").status_code == 404
    assert alice.delete(f"/collections/{other}/documents/{doc_id}").status_code == 404


# --- deletion removes files, not just rows ----------------------------------------------------


def test_delete_document_removes_file_and_pages(alice, cid, db, storage):
    doc_id = upload(alice, cid, make_pdf(["bye"])).json()["id"]
    assert alice.delete(f"/collections/{cid}/documents/{doc_id}").status_code == 204
    assert _files_on_disk(storage) == []
    with db() as session:
        assert session.scalars(select(DocumentPage)).all() == []


def test_delete_collection_removes_files(alice, cid, storage):
    upload(alice, cid, make_pdf(["a"]), "a.pdf")
    upload(alice, cid, make_pdf(["b"]), "b.pdf")
    assert len(_files_on_disk(storage)) == 2
    assert alice.delete(f"/collections/{cid}").status_code == 204
    assert _files_on_disk(storage) == []


def test_delete_account_removes_files(alice, cid, db, storage):
    upload(alice, cid, make_pdf(["mine"]))
    response = alice.request("DELETE", "/me", json={"password": GOOD_PASSWORD})
    assert response.status_code == 204
    assert _files_on_disk(storage) == []
    with db() as session:
        assert session.scalars(select(Document)).all() == []
