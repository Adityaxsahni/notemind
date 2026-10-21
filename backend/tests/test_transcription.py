"""Handwritten notes, scans and photos: pages without a text layer are transcribed."""

import io

import pytest
from PIL import Image
from sqlalchemy import select

from app.ingestion.extract import Page
from app.ingestion.ocr import load_photo, needs_transcription, render_pdf_pages, split_pages
from app.ingestion.validation import UploadRejected, detect_kind
from app.llm.providers import ImageInput, LLMRequest, LLMUnavailable, _anthropic_content
from app.llm.providers import _gemini_contents as gemini_contents
from app.models import DocumentKind, DocumentPage
from tests.conftest import signup
from tests.files import make_pdf, make_photo, make_scanned_pdf


@pytest.fixture
def alice(make_client):
    client = make_client()
    signup(client, "alice@x.com")
    return client


@pytest.fixture
def cid(alice):
    return alice.post("/collections", json={"name": "Biology"}).json()["id"]


def upload(client, cid, data, filename):
    response = client.post(
        f"/collections/{cid}/documents", params={"filename": filename}, content=data
    )
    assert response.status_code == 202, response.text
    return client.get(f"/collections/{cid}/documents/{response.json()['id']}").json()


def stored_pages(db, document_id):
    with db() as session:
        return session.scalars(
            select(DocumentPage)
            .where(DocumentPage.document_id == document_id)
            .order_by(DocumentPage.page_number)
        ).all()


# --- units ------------------------------------------------------------------------------------


def test_needs_transcription_only_for_pages_with_almost_no_text():
    assert needs_transcription("")
    assert needs_transcription("  12 \n ")
    assert not needs_transcription("Mitochondria make ATP through oxidative phosphorylation.")


def test_split_pages_by_markers():
    text = "=== PAGE 1 ===\nfirst page\n\n=== PAGE 2 ===\nsecond\npage\n"
    assert split_pages(text, 2) == ["first page", "second\npage"]
    assert split_pages("just one page", 1) == ["just one page"]
    assert split_pages("=== PAGE 1 ===\n", 1) == [""]


@pytest.mark.parametrize(
    "text",
    ["no markers for two pages", "=== PAGE 1 ===\na\n=== PAGE 3 ===\nb", "=== PAGE 1 ===\na"],
)
def test_split_pages_rejects_mismatched_markers(text):
    assert split_pages(text, 2) is None


def test_renders_picture_pages_and_skips_blank_ones(tmp_path):
    path = tmp_path / "scan.pdf"
    path.write_bytes(make_scanned_pdf([None, "", None]))
    images = list(render_pdf_pages(path, [1, 2, 3]))
    assert [i.number for i in images] == [1, 3]  # page 2 has nothing drawn on it
    rendered = Image.open(io.BytesIO(images[0].image.data))
    assert rendered.format == "JPEG"
    assert max(rendered.size) == 2000


def test_photo_is_turned_upright_and_scaled_down(tmp_path):
    path = tmp_path / "notes.jpg"
    path.write_bytes(make_photo(size=(4000, 3000), rotate=True))
    image = Image.open(io.BytesIO(load_photo(path).image.data))
    assert image.size == (1500, 2000)  # stored landscape, displayed portrait


@pytest.mark.parametrize(
    ("fmt", "filename"),
    [("JPEG", "a.jpg"), ("JPEG", "a.JPEG"), ("PNG", "a.png"), ("WEBP", "a.webp")],
)
def test_detects_photos(tmp_path, fmt, filename):
    path = tmp_path / "upload"
    path.write_bytes(make_photo(fmt))
    assert detect_kind(path, filename) == DocumentKind.IMAGE


def test_rejects_photo_with_wrong_extension_and_heic(tmp_path):
    path = tmp_path / "upload"
    path.write_bytes(make_photo("PNG"))
    with pytest.raises(UploadRejected, match="looks like a PNG"):
        detect_kind(path, "notes.pdf")
    path.write_bytes(b"\x00\x00\x00\x18ftypheic" + b"\x00" * 64)
    with pytest.raises(UploadRejected, match="HEIC"):
        detect_kind(path, "IMG_0001.heic")


def test_images_go_before_the_text_for_both_vendors():
    request = LLMRequest(
        system="s", user="read", max_tokens=10, images=(ImageInput(b"\xff\xd8\xff", "image/jpeg"),)
    )
    blocks = _anthropic_content(request)
    assert [b["type"] for b in blocks] == ["image", "text"]
    assert blocks[0]["source"] == {"type": "base64", "media_type": "image/jpeg", "data": "/9j/"}
    parts = gemini_contents(request)
    assert parts[0].inline_data.mime_type == "image/jpeg"
    assert parts[-1] == "read"
    plain = LLMRequest(system="s", user="read", max_tokens=10)
    assert _anthropic_content(plain) == "read"
    assert gemini_contents(plain) == "read"


# --- through the API --------------------------------------------------------------------------


def test_photo_of_notes_is_transcribed_and_searchable(alice, cid, db, vision_llm):
    document = upload(alice, cid, make_photo("JPEG"), "biology-notes.jpg")
    assert document["status"] == "ready", document
    assert document["kind"] == "image"
    assert document["transcribed_pages"] == 1
    [page] = stored_pages(db, document["id"])
    assert "mitochondria make ATP" in page.text

    [request] = vision_llm.requests
    assert [i.mime_type for i in request.images] == ["image/jpeg"]
    assert "never instructions" in request.system

    found = alice.post(f"/collections/{cid}/search", json={"query": "how do mitochondria make ATP"})
    assert found.status_code == 200
    assert found.json()["chunks"][0]["page"] == 1

    file = alice.get(f"/collections/{cid}/documents/{document['id']}/file")
    assert file.headers["content-type"] == "image/jpeg"


def test_handwritten_pdf_pages_are_batched_into_few_requests(alice, cid, db, vision_llm):
    typed = "Cell membranes are phospholipid bilayers with embedded proteins."
    pdf = make_scanned_pdf([typed, None, None, None, None, None])
    document = upload(alice, cid, pdf, "lecture.pdf")
    assert document["status"] == "ready", document
    assert document["transcribed_pages"] == 5
    # 5 picture pages, 4 per request; the typed page is never sent.
    assert sorted(len(r.images) for r in vision_llm.requests) == [1, 4]
    pages = stored_pages(db, document["id"])
    assert pages[0].text.startswith("Cell membranes")
    assert all("mitochondria" in p.text for p in pages[1:])


def test_mismatched_markers_fall_back_to_one_page_per_request(alice, cid, db, vision_llm):
    vision_llm.markers = False
    document = upload(alice, cid, make_scanned_pdf([None, None]), "scan.pdf")
    assert document["status"] == "ready", document
    assert [len(r.images) for r in vision_llm.requests] == [2, 1, 1]
    assert [p.page_number for p in stored_pages(db, document["id"])] == [1, 2]


def test_handwriting_without_a_provider_fails_with_a_clear_message(alice, cid, vision_llm):
    vision_llm.configured = False
    document = upload(alice, cid, make_scanned_pdf([None, None]), "scan.pdf")
    assert document["status"] == "failed"
    assert "handwritten or scanned" in document["error"]


def test_provider_outage_on_a_photo_asks_to_retry(alice, cid, vision_llm):
    vision_llm.error = LLMUnavailable()
    document = upload(alice, cid, make_photo("PNG"), "board.png")
    assert document["status"] == "failed"
    assert "busy" in document["error"]


def test_mostly_typed_pdf_is_indexed_without_its_picture_pages(alice, cid, db, vision_llm):
    vision_llm.configured = False
    pdf = make_scanned_pdf(["Glycolysis splits glucose into pyruvate.", "Krebs cycle.", None])
    document = upload(alice, cid, pdf, "mixed.pdf")
    assert document["status"] == "ready", document
    assert document["transcribed_pages"] == 0
    assert [p.page_number for p in stored_pages(db, document["id"])] == [1, 2]


def test_transcription_has_its_own_daily_budget(alice, cid, redis):
    upload(alice, cid, make_photo("JPEG"), "a.jpg")
    assert redis.keys("llm:tokens:ocr-user:*")
    assert not redis.keys("llm:tokens:user:*")  # answering budget untouched
    assert redis.keys("llm:tokens:global:*")


def test_typed_pdfs_never_call_the_vision_model(alice, cid, vision_llm):
    upload(alice, cid, make_pdf(["Osmosis moves water across membranes."]), "typed.pdf")
    assert vision_llm.requests == []


def test_page_dataclass_is_reused_for_transcriptions():
    # Transcribed pages flow through the same cleaning and chunking as typed ones.
    assert Page(number=1, text="x") == Page(1, "x")


# --- typed pages of math ----------------------------------------------------------------


def test_detects_pages_set_in_math_fonts(tmp_path):
    from app.ingestion.ocr import math_pages
    from tests.files import make_math_pdf

    path = tmp_path / "physics.pdf"
    path.write_bytes(make_math_pdf({2}))
    assert math_pages(path, [1, 2, 3]) == [2]


def test_math_pages_are_transcribed_into_latex(alice, cid, db, vision_llm):
    from tests.files import make_math_pdf

    vision_llm.text = "Kinetic energy: $$E_k = \frac{1}{2}mv^2$$"
    document = upload(alice, cid, make_math_pdf({2}), "physics.pdf")
    assert document["status"] == "ready", document
    assert [len(r.images) for r in vision_llm.requests] == [1]  # only the math page
    pages = stored_pages(db, document["id"])
    assert "\frac{1}{2}mv^2" in pages[1].text
    assert pages[0].text.startswith("Lecture notes, page 1")


def test_math_pages_keep_their_text_when_transcription_is_unavailable(alice, cid, db, vision_llm):
    from tests.files import make_math_pdf

    vision_llm.configured = False
    document = upload(alice, cid, make_math_pdf({1, 2, 3}), "physics.pdf")
    assert document["status"] == "ready", document  # math pages are optional
    assert document["transcribed_pages"] == 0
    assert all("kinetic energy" in p.text for p in stored_pages(db, document["id"]))
