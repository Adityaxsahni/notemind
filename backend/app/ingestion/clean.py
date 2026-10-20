"""Normalize extracted text so retrieval sees content, not layout noise."""

import re
import unicodedata
from collections import Counter

from app.ingestion.extract import Page

_EDGE_LINES = 2  # header/footer candidates: first and last N lines of each page
_PAGE_NUMBER = re.compile(r"^(page\s*)?\d{1,4}(\s*(/|of)\s*\d{1,4})?$", re.IGNORECASE)


def normalize_text(text: str) -> str:
    text = text.replace("\x00", "")  # Postgres text columns reject NUL bytes
    text = unicodedata.normalize("NFKC", text)  # ligatures (ﬁ → fi), full-width chars
    text = re.sub(r"([a-z])-\n([a-z])", r"\1\2", text)  # re-join words hyphenated at line ends
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_pages(pages: list[Page]) -> list[Page]:
    texts = [normalize_text(p.text) for p in pages]
    repeated = _repeated_edge_lines(texts)
    return [
        Page(number=p.number, text=_strip_edges(t, repeated))
        for p, t in zip(pages, texts, strict=True)
    ]


def _repeated_edge_lines(texts: list[str]) -> set[str]:
    """Lines at the top/bottom of at least half the pages: course headers, footers, logos."""
    if len(texts) < 4:
        return set()
    counts: Counter[str] = Counter()
    for text in texts:
        lines = text.split("\n")
        counts.update({line for line in lines[:_EDGE_LINES] + lines[-_EDGE_LINES:] if line})
    threshold = max(3, len(texts) // 2)
    return {line for line, count in counts.items() if count >= threshold}


def _is_noise(line: str, repeated: set[str]) -> bool:
    return line in repeated or bool(_PAGE_NUMBER.fullmatch(line))


def _strip_edges(text: str, repeated: set[str]) -> str:
    lines = text.split("\n")
    start, end = 0, len(lines)
    while start < end and start < _EDGE_LINES and _is_noise(lines[start], repeated):
        start += 1
    while end > start and len(lines) - end < _EDGE_LINES and _is_noise(lines[end - 1], repeated):
        end -= 1
    return "\n".join(lines[start:end]).strip()
