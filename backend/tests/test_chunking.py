import pytest

from app.ingestion.chunking import chunk_pages, is_heading
from app.ingestion.extract import Page
from app.models import DocumentKind


def words(text: str) -> int:
    return len(text.split())


def sentence(i: int, n_words: int = 10) -> str:
    return " ".join([f"S{i}"] + [f"w{i}x{j}" for j in range(n_words - 2)] + [f"end{i}."])


def chunk(pages, kind=DocumentKind.PDF, target=40, overlap=0):
    pages = [Page(number=i, text=t) for i, t in enumerate(pages, start=1)]
    return chunk_pages(pages, kind, words, target, overlap)


def test_short_page_is_one_chunk_with_its_page_number():
    chunks = chunk(["Normalization reduces redundancy.", "Joins combine tables."])
    assert [(c.page, c.text) for c in chunks] == [
        (1, "Normalization reduces redundancy."),
        (2, "Joins combine tables."),
    ]
    assert chunks[0].token_count == 3


def test_chunks_fit_the_target_and_never_split_a_sentence():
    sentences = [sentence(i) for i in range(30)]
    chunks = chunk([" ".join(sentences)], target=40, overlap=12)

    assert len(chunks) > 1
    for c in chunks:
        assert c.token_count <= 40
        assert c.text.startswith("S") and c.text.endswith(".")
    covered = " ".join(c.text for c in chunks)
    assert all(s in covered for s in sentences)


def test_consecutive_chunks_overlap_by_whole_sentences():
    chunks = chunk([" ".join(sentence(i) for i in range(12))], target=40, overlap=12)
    for previous, current in zip(chunks, chunks[1:], strict=False):
        last_sentence = previous.text.rsplit(". ", 1)[-1]
        assert current.text.startswith(last_sentence.removesuffix("."))


def test_no_overlap_when_disabled():
    chunks = chunk([" ".join(sentence(i) for i in range(12))], target=40, overlap=0)
    assert sum(c.token_count for c in chunks) == 120


def test_paragraph_boundaries_are_preferred_over_packing_sentences():
    first = " ".join(sentence(i) for i in range(3))  # 30 words
    second = " ".join(sentence(i) for i in range(3, 6))
    chunks = chunk([f"{first}\n\n{second}"], target=40)
    assert [c.text for c in chunks] == [first, second]


def test_sentence_longer_than_target_is_split_between_words_only():
    long = " ".join(f"t{i}" for i in range(100)) + "."
    chunks = chunk([long], target=40)
    assert [c.token_count for c in chunks] == [40, 40, 20]
    assert " ".join(c.text for c in chunks) == long


@pytest.mark.parametrize(
    "line",
    ["3.2 Normalization", "4 Transactions", "Unit 3: Joins", "TRANSACTION ISOLATION LEVELS"],
)
def test_detects_headings(line):
    assert is_heading(line)


@pytest.mark.parametrize(
    "line",
    [
        "1. Insert the row into the table",  # numbered list item
        "Normalization reduces redundancy.",  # sentence
        "SQL",  # acronym
        "E = MC2",  # formula
        "3.2 normalization is the process of " + "x " * 60,  # too long
        "",
    ],
)
def test_ignores_non_headings(line):
    assert not is_heading(line)


def test_headings_split_sections_and_carry_over_page_breaks():
    chunks = chunk(
        [
            "3.1 Normalization\nRemoves redundancy.\n3.2 Transactions\nACID properties hold.",
            "Isolation prevents dirty reads.",
            "4 Indexing\nB-trees keep keys sorted.",
        ]
    )
    assert [(c.page, c.heading, c.text) for c in chunks] == [
        (1, "3.1 Normalization", "Removes redundancy."),
        (1, "3.2 Transactions", "ACID properties hold."),
        (2, "3.2 Transactions", "Isolation prevents dirty reads."),
        (3, "4 Indexing", "B-trees keep keys sorted."),
    ]


def test_heading_on_a_page_without_body_still_applies_to_the_next_page():
    chunks = chunk(["5 Concurrency", "Locks serialize access."])
    assert [(c.page, c.heading) for c in chunks] == [(2, "5 Concurrency")]


def test_first_line_of_a_slide_is_its_title():
    slides = ["Weak Entities\nThey depend on an owner entity.", "Keys\nA key identifies a row."]
    chunks = chunk(slides, kind=DocumentKind.PPTX)
    assert [(c.heading, c.text) for c in chunks] == [
        ("Weak Entities", "They depend on an owner entity."),
        ("Keys", "A key identifies a row."),
    ]


def test_first_line_of_a_pdf_page_is_not_assumed_to_be_a_title():
    chunks = chunk(["Weak entities\nThey depend on an owner entity."])
    assert chunks[0].heading is None
    assert chunks[0].text.startswith("Weak entities")


def test_chunks_never_span_pages():
    pages = [" ".join(sentence(i + 10 * p) for i in range(3)) for p in range(3)]  # 30 words each
    chunks = chunk(pages, target=100)
    assert [c.page for c in chunks] == [1, 2, 3]


def test_empty_pages_produce_no_chunks():
    assert chunk(["", "   \n  "]) == []
