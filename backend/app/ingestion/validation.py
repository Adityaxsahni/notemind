"""Cheap, safe checks run in the API process before a file is accepted (threat T4).

Nothing here parses document content. Full parsing of untrusted files happens only in the
worker, under a timeout and memory limit. Here we only read magic bytes and the ZIP central
directory, both bounded and fast.
"""

import unicodedata
import zipfile
from pathlib import Path, PurePosixPath

from app.models import DocumentKind

MAX_ZIP_ENTRIES = 5_000
MAX_ZIP_TOTAL_UNCOMPRESSED = 300 * 1024 * 1024
MAX_ZIP_ENTRY_RATIO = 100  # real XML/images compress ~5-20x; zip bombs reach 1000x+
RATIO_CHECK_MIN_SIZE = 5 * 1024 * 1024
MAX_CONTENT_TYPES_XML = 1024 * 1024

_PDF_MAGIC = b"%PDF-"
_ZIP_MAGIC = b"PK\x03\x04"
_OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # legacy .doc/.ppt and encrypted Office files
_JPEG_MAGIC = b"\xff\xd8\xff"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_HEIF_BRANDS = (b"heic", b"heix", b"hevc", b"mif1", b"msf1", b"avif")

# Photos of notes: detected image format -> (media type, extensions that may carry it).
IMAGE_FORMATS = {
    "jpeg": ("image/jpeg", {".jpg", ".jpeg"}),
    "png": ("image/png", {".png"}),
    "webp": ("image/webp", {".webp"}),
}
UNSUPPORTED = "Unsupported file type. Upload a PDF, DOCX, PPTX, or a photo (JPG, PNG, WebP)."


class UploadRejected(Exception):
    def __init__(self, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def safe_display_name(raw: str) -> str:
    """Filename for display only: basename, printable characters, bounded length."""
    name = raw.replace("\\", "/").rsplit("/", 1)[-1]
    name = unicodedata.normalize("NFC", name)
    name = "".join(ch for ch in name if ch.isprintable()).strip()
    if len(name) > 200:
        stem, dot, ext = name.rpartition(".")
        name = (stem[: 200 - len(ext) - 1] + dot + ext) if dot and len(ext) <= 10 else name[:200]
    return name or "document"


def image_format(head: bytes) -> str | None:
    """The image format (jpeg, png or webp) from a file's first 12 bytes, else None."""
    if head.startswith(_JPEG_MAGIC):
        return "jpeg"
    if head.startswith(_PNG_MAGIC):
        return "png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    return None


def image_media_type(path: Path) -> str:
    with path.open("rb") as f:
        return IMAGE_FORMATS[image_format(f.read(12)) or "jpeg"][0]


def detect_kind(path: Path, filename: str) -> DocumentKind:
    with path.open("rb") as f:
        head = f.read(12)
    suffix = PurePosixPath(filename.lower()).suffix

    if (image := image_format(head)) is not None:
        if suffix not in IMAGE_FORMATS[image][1]:
            raise UploadRejected(
                f"The file extension doesn't match its contents (looks like a {image.upper()}).",
                status_code=415,
            )
        return DocumentKind.IMAGE
    if head[4:8] == b"ftyp" and head[8:12] in _HEIF_BRANDS:
        raise UploadRejected(
            "HEIC photos aren't supported yet. Export the photo as JPEG, or set your camera "
            "to “Most Compatible”.",
            status_code=415,
        )

    if head.startswith(_PDF_MAGIC):
        kind = DocumentKind.PDF
    elif head.startswith(_ZIP_MAGIC):
        kind = _inspect_ooxml(path)
    elif head.startswith(_OLE_MAGIC):
        raise UploadRejected(
            "Old Office formats (.doc, .ppt) and password-protected Office files aren't "
            "supported. Please save as PDF, DOCX or PPTX.",
            status_code=415,
        )
    else:
        raise UploadRejected(UNSUPPORTED, 415)

    # The extension must agree with the actual content: a ".pdf" that is really a ZIP
    # is either a mistake or an attempt to confuse something downstream.
    if suffix != f".{kind.value}":
        raise UploadRejected(
            f"The file extension doesn't match its contents (looks like a {kind.value.upper()}).",
            status_code=415,
        )
    return kind


def _inspect_ooxml(path: Path) -> DocumentKind:
    try:
        archive = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError):
        raise UploadRejected("This file is damaged or isn't a valid Office document.") from None

    with archive:
        entries = archive.infolist()
        if len(entries) > MAX_ZIP_ENTRIES:
            raise UploadRejected("This document has too many internal parts to process safely.")

        names: set[str] = set()
        total_uncompressed = 0
        for entry in entries:
            name = entry.filename
            if name.startswith("/") or ".." in PurePosixPath(name).parts:
                raise UploadRejected("This document contains unsafe internal paths.")
            if entry.flag_bits & 0x1:
                raise UploadRejected("Encrypted documents aren't supported.")
            if name.lower().endswith("vbaproject.bin"):
                raise UploadRejected("Documents containing macros aren't allowed.")
            total_uncompressed += entry.file_size
            if (
                entry.file_size > RATIO_CHECK_MIN_SIZE
                and entry.file_size > entry.compress_size * MAX_ZIP_ENTRY_RATIO
            ):
                raise UploadRejected("This document expands to an unsafe size.")
            names.add(name)

        # Python's zipfile never inflates past an entry's declared size, so these totals are
        # real upper bounds even if an attacker crafted the headers.
        if total_uncompressed > MAX_ZIP_TOTAL_UNCOMPRESSED:
            raise UploadRejected("This document expands to an unsafe size.")

        if "[Content_Types].xml" not in names:
            raise UploadRejected("This file isn't a valid Office document.")
        content_types = archive.getinfo("[Content_Types].xml")
        if content_types.file_size > MAX_CONTENT_TYPES_XML:
            raise UploadRejected("This file isn't a valid Office document.")
        if b"macroEnabled" in archive.read(content_types):
            raise UploadRejected("Documents containing macros aren't allowed.")

        if "word/document.xml" in names:
            return DocumentKind.DOCX
        if "ppt/presentation.xml" in names:
            return DocumentKind.PPTX
    raise UploadRejected(UNSUPPORTED, 415)
