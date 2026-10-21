"""Heading-aware chunking of cleaned pages into retrievable passages.

- A chunk never spans two pages (a citation points at exactly one page) or two headings.
- Text is split at the coarsest boundary that fits the target: paragraph, then line, then
  sentence. Only a single sentence longer than the target is split between words.
- Consecutive chunks of a section overlap by whole trailing sentences, up to `overlap_tokens`.
- The latest heading carries over page breaks, so page 5 of a section still knows its heading.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

from app.ingestion.extract import Page
from app.models import DocumentKind

CountTokens = Callable[[str], int]

MAX_HEADING_CHARS = 100
# Slides and DOCX sections usually start with their title.
_TITLED_KINDS = (DocumentKind.PPTX, DocumentKind.DOCX)

# "3.2 Normalization", "4 Transactions", "Unit 3: Joins". Not "1. Insert the row" (list item).
_NUMBERED_HEADING = re.compile(
    r"^(\d+\.\d+(\.\d+)*\.?|\d+|(chapter|unit|module|lecture|section|part)\s+[\dIVX]+[:.]?)"
    r"\s+[A-Z(]",
    re.IGNORECASE,
)
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[\"'(\[]?[A-Z0-9])")
# Coarsest first: paragraphs, lines, sentences. Joiners restore the separator we split on.
_SPLITTERS = (re.compile(r"\n\s*\n"), re.compile(r"\n"), _SENTENCE_BOUNDARY)
_JOINERS = ("\n\n", "\n", " ")
_OVERLAP_UNITS = re.compile(r"(?<=[.!?])\s+|\n+")


@dataclass(frozen=True)
class ChunkDraft:
    page: int
    heading: str | None
    text: str
    token_count: int


def chunk_pages(
    pages: list[Page],
    kind: DocumentKind,
    count_tokens: CountTokens,
    target_tokens: int,
    overlap_tokens: int,
) -> list[ChunkDraft]:
    chunks: list[ChunkDraft] = []
    heading: str | None = None
    for page in pages:
        sections, heading = _sections(page.text, heading, titled=kind in _TITLED_KINDS)
        for section_heading, body in sections:
            for text in _split_section(body, count_tokens, target_tokens, overlap_tokens):
                chunks.append(ChunkDraft(page.number, section_heading, text, count_tokens(text)))
    return chunks


def with_heading(heading: str | None, text: str) -> str:
    """What models see for a chunk: the heading gives "It removes redundancy..." its subject."""
    return f"{heading}\n{text}" if heading else text


def is_heading(line: str, *, title_position: bool = False) -> bool:
    line = line.strip()
    if not line or len(line) > MAX_HEADING_CHARS or line[-1] in ".,;:?!":
        return False
    if title_position or _NUMBERED_HEADING.match(line):
        return True
    letters = [c for c in line if c.isalpha()]
    # ALL-CAPS lines like "TRANSACTION ISOLATION"; 4+ letters so "SQL" or "E = MC2" don't count.
    return len(letters) >= 4 and line.isupper() and len(line.split()) <= 8


def _sections(
    text: str, heading: str | None, *, titled: bool
) -> tuple[list[tuple[str | None, str]], str | None]:
    """Split one page at heading lines. Returns (heading, body) pairs and the last heading."""
    sections: list[tuple[str | None, str]] = []
    body: list[str] = []
    for i, line in enumerate(text.split("\n")):
        if is_heading(line, title_position=titled and i == 0):
            if "".join(body).strip():
                sections.append((heading, "\n".join(body).strip()))
            heading, body = line.strip(), []
        else:
            body.append(line)
    if "".join(body).strip():
        sections.append((heading, "\n".join(body).strip()))
    return sections, heading


def _split_section(body: str, count_tokens: CountTokens, target: int, overlap: int) -> list[str]:
    """Greedily pack pieces into chunks of at most `target` tokens, overlapping by sentences."""
    chunks: list[str] = []
    parts: list[str] = []
    size = 0
    for joiner, piece in _pieces(body, count_tokens, target):
        n = count_tokens(piece)
        if parts and size + n > target:
            chunks.append("".join(parts))
            tail = _overlap_tail(chunks[-1], count_tokens, min(overlap, target - n))
            parts, size = ([tail], count_tokens(tail)) if tail else ([], 0)
        parts.append(joiner + piece if parts else piece)
        size += n
    if parts:
        chunks.append("".join(parts))
    return chunks


def _pieces(
    text: str, count_tokens: CountTokens, target: int, level: int = 0
) -> list[tuple[str, str]]:
    """(joiner, piece) pairs, each piece at most `target` tokens, split as coarsely as possible."""
    if count_tokens(text) <= target:
        return [("", text)]
    for lvl in range(level, len(_SPLITTERS)):
        parts = [p.strip() for p in _SPLITTERS[lvl].split(text) if p.strip()]
        if len(parts) > 1:
            pieces: list[tuple[str, str]] = []
            for part in parts:
                sub = _pieces(part, count_tokens, target, lvl + 1)
                pieces.append((_JOINERS[lvl], sub[0][1]))
                pieces.extend(sub[1:])
            return pieces
    return [(" ", window) for window in _word_windows(text, count_tokens, target)]


def _word_windows(text: str, count_tokens: CountTokens, target: int) -> list[str]:
    """Last resort for a single sentence longer than the target: split between words."""
    windows: list[str] = []
    words: list[str] = []
    size = 0
    for word in text.split():
        n = count_tokens(word)
        if words and size + n > target:
            windows.append(" ".join(words))
            words, size = [], 0
        words.append(word)
        size += n
    if words:
        windows.append(" ".join(words))
    return windows


def _overlap_tail(text: str, count_tokens: CountTokens, budget: int) -> str:
    """Whole trailing sentences/lines of `text` within `budget` tokens; never all of `text`."""
    units = [u for u in _OVERLAP_UNITS.split(text) if u.strip()]
    taken: list[str] = []
    used = 0
    for unit in reversed(units[1:]):
        n = count_tokens(unit)
        if used + n > budget:
            break
        taken.append(unit.strip())
        used += n
    return " ".join(reversed(taken))
