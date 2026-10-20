"""Validation, extraction and cleaning, tested directly without the API."""

import pytest

from app.ingestion.clean import clean_pages, normalize_text
from app.ingestion.extract import ExtractionError, Page, extract_pages
from app.ingestion.validation import UploadRejected, detect_kind, safe_display_name
from app.models import DocumentKind
from tests.files import (
    make_docm_with_macro,
    make_docx,
    make_docx_zip_bomb,
    make_pdf,
    make_pptx,
    make_zip,
)


@pytest.fixture
def write(tmp_path):
    def _write(data: bytes):
        path = tmp_path / "upload.bin"
        path.write_bytes(data)
        return path

    return _write


# --- detect_kind: magic bytes, extension agreement, ZIP safety ------------------------------


def test_detects_real_formats(write):
    assert detect_kind(write(make_pdf(["hi"])), "a.pdf") == DocumentKind.PDF
    assert detect_kind(write(make_docx([("hi", None)])), "a.docx") == DocumentKind.DOCX
    assert detect_kind(write(make_pptx([{"title": "hi"}])), "a.PPTX") == DocumentKind.PPTX


@pytest.mark.parametrize(
    ("data", "filename"),
    [
        (make_pdf(["hi"]), "notes.docx"),  # extension lies about content
        (make_docx([("hi", None)]), "notes.pdf"),
        (b"MZ\x90\x00 this is a windows exe", "notes.pdf"),
        (b"<html><script>alert(1)</script></html>", "notes.pdf"),
        (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1legacy-ole", "notes.doc"),
        (b"PK\x03\x04 truncated zip", "notes.docx"),
    ],
    ids=["pdf-as-docx", "docx-as-pdf", "exe", "html", "legacy-ole", "broken-zip"],
)
def test_rejects_spoofed_and_unsupported_files(write, data, filename):
    with pytest.raises(UploadRejected):
        detect_kind(write(data), filename)


def test_rejects_zip_bomb(write):
    with pytest.raises(UploadRejected, match="unsafe size"):
        detect_kind(write(make_docx_zip_bomb()), "bomb.docx")


def test_rejects_macros(write):
    with pytest.raises(UploadRejected, match="macros"):
        detect_kind(write(make_docm_with_macro()), "evil.docx")


def test_rejects_path_traversal_entries(write):
    data = make_zip(
        {
            "[Content_Types].xml": b"<Types/>",
            "word/document.xml": b"<w:document/>",
            "../../evil.sh": b"rm -rf /",
        }
    )
    with pytest.raises(UploadRejected, match="unsafe internal paths"):
        detect_kind(write(data), "x.docx")


def test_rejects_zip_that_is_not_office(write):
    with pytest.raises(UploadRejected):
        detect_kind(write(make_zip({"readme.txt": b"hello"})), "x.docx")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("../../etc/passwd.pdf", "passwd.pdf"),
        ("C:\\Users\\me\\DBMS Unit 1.pdf", "DBMS Unit 1.pdf"),
        ("evil\x00name\n.pdf", "evilname.pdf"),
        ("", "document"),
    ],
)
def test_safe_display_name(raw, expected):
    assert safe_display_name(raw) == expected


def test_safe_display_name_keeps_extension_when_truncating():
    name = safe_display_name("a" * 300 + ".pdf")
    assert len(name) == 200 and name.endswith(".pdf")


# --- extraction --------------------------------------------------------------------------------


def test_pdf_extraction_keeps_page_numbers(write):
    pages = extract_pages(write(make_pdf(["First page", "Second page"])), DocumentKind.PDF)
    assert [p.number for p in pages] == [1, 2]
    assert "Second page" in pages[1].text


def test_corrupted_pdf_raises_user_safe_error(write):
    with pytest.raises(ExtractionError):
        extract_pages(write(b"%PDF-1.7\n garbage garbage"), DocumentKind.PDF)


def test_password_protected_pdf_rejected(write, tmp_path):
    import pymupdf

    document = pymupdf.open()
    document.new_page().insert_text((72, 72), "secret")
    out = tmp_path / "locked.pdf"
    document.save(out, encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="u-pass", owner_pw="o-pass")
    document.close()
    with pytest.raises(ExtractionError, match="Password-protected"):
        extract_pages(out, DocumentKind.PDF)


def test_pptx_extracts_titles_text_tables_and_notes(write):
    data = make_pptx(
        [
            {
                "title": "Normal Forms",
                "body": "2NF removes partial dependencies",
                "table": [["Form", "Rule"], ["3NF", "No transitive deps"]],
                "notes": "Mention BCNF in class",
            },
            {"title": "Indexing"},
        ]
    )
    pages = extract_pages(write(data), DocumentKind.PPTX)
    assert [p.number for p in pages] == [1, 2]
    first = pages[0].text
    for expected in ("Normal Forms", "partial dependencies", "3NF | No transitive deps", "BCNF"):
        assert expected in first


def test_docx_splits_sections_at_heading_1(write):
    data = make_docx(
        [
            ("Unit 1", "Heading 1"),
            ("Relational model basics.", None),
            ("Unit 2", "Heading 1"),
            ("SQL joins.", None),
        ]
    )
    pages = extract_pages(write(data), DocumentKind.DOCX)
    assert len(pages) == 2
    assert "Relational model" in pages[0].text and "SQL joins" in pages[1].text


# --- cleaning ----------------------------------------------------------------------------------


def test_normalize_text():
    raw = "nor-\nmalization  of\x00 data\n\n\n\nthe ﬁrst\u00a0form"
    assert normalize_text(raw) == "normalization of data\n\nthe first form"


def test_removes_repeated_headers_footers_and_page_numbers():
    pages = [
        Page(n, f"CS301 DBMS - Prof. Rao\nContent of page {n}\nPage {n} of 6") for n in range(1, 7)
    ]
    cleaned = clean_pages(pages)
    assert [p.text for p in cleaned] == [f"Content of page {n}" for n in range(1, 7)]


def test_does_not_strip_repeated_lines_on_short_documents():
    pages = [Page(1, "Header\nA"), Page(2, "Header\nB")]
    assert [p.text for p in clean_pages(pages)] == ["Header\nA", "Header\nB"]
