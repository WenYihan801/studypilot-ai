"""File type detection and text extraction for PDF, DOCX, TXT and Markdown."""

import io
import re
import zipfile
from dataclasses import dataclass, field

from app.core.errors import ValidationFailedError


class ParseError(Exception):
    """Raised when a valid file contains no usable text (e.g. a scanned PDF)."""


@dataclass
class Section:
    text: str
    page_number: int | None = None
    section_title: str | None = None


@dataclass
class ParsedDocument:
    sections: list[Section] = field(default_factory=list)
    page_count: int | None = None


EXTENSION_MIME = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": "text/plain",
    "md": "text/markdown",
    "markdown": "text/markdown",
}
# Browsers report Markdown inconsistently; accept these declared types per extension.
ACCEPTED_DECLARED = {
    "pdf": {"application/pdf"},
    "docx": {EXTENSION_MIME["docx"], "application/octet-stream", "application/zip"},
    "txt": {"text/plain", "application/octet-stream", ""},
    "md": {"text/markdown", "text/x-markdown", "text/plain", "application/octet-stream", ""},
    "markdown": {"text/markdown", "text/x-markdown", "text/plain", "application/octet-stream", ""},
}
EXECUTABLE_MAGIC = (b"MZ", b"\x7fELF", b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"#!")


def extension_of(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def detect_file_type(filename: str, data: bytes, declared_mime: str | None) -> tuple[str, str]:
    """Validates extension, declared MIME and the file's actual bytes. Returns (kind, mime)."""
    ext = extension_of(filename)
    if ext not in EXTENSION_MIME:
        raise ValidationFailedError("Unsupported file type. Upload PDF, DOCX, TXT or Markdown.", code="unsupported_type")
    if any(data.startswith(m) for m in EXECUTABLE_MAGIC):
        raise ValidationFailedError("Executable files are not allowed.", code="executable_rejected")
    declared = (declared_mime or "").split(";")[0].strip().lower()
    if declared not in ACCEPTED_DECLARED[ext]:
        raise ValidationFailedError(f"File content type '{declared}' does not match .{ext}.", code="mime_mismatch")

    if ext == "pdf":
        if not data.startswith(b"%PDF-"):
            raise ValidationFailedError("This file is not a valid PDF.", code="mime_mismatch")
        return "pdf", EXTENSION_MIME["pdf"]
    if ext == "docx":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                if "word/document.xml" not in zf.namelist():
                    raise ValidationFailedError("This file is not a valid DOCX document.", code="mime_mismatch")
        except zipfile.BadZipFile as exc:
            raise ValidationFailedError("This file is not a valid DOCX document.", code="mime_mismatch") from exc
        return "docx", EXTENSION_MIME["docx"]
    # text formats
    if b"\x00" in data[:8192]:
        raise ValidationFailedError("Text files must not contain binary data.", code="mime_mismatch")
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationFailedError("Text files must be UTF-8 encoded.", code="mime_mismatch") from exc
    kind = "markdown" if ext in ("md", "markdown") else "txt"
    return kind, EXTENSION_MIME[ext]


def _clean(text: str) -> str:
    text = text.replace("\x00", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_pdf(data: bytes) -> ParsedDocument:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ParseError("Password-protected PDFs are not supported.")
        sections = []
        for i, page in enumerate(reader.pages, start=1):
            text = _clean(page.extract_text() or "")
            if text:
                sections.append(Section(text=text, page_number=i))
        page_count = len(reader.pages)
    except PdfReadError as exc:
        raise ParseError("The PDF file is damaged or cannot be read.") from exc
    if not sections:
        raise ParseError("No extractable text found. Scanned/image-only PDFs need OCR, which V1 does not support.")
    return ParsedDocument(sections=sections, page_count=page_count)


def parse_docx(data: bytes) -> ParsedDocument:
    import docx

    document = docx.Document(io.BytesIO(data))
    sections: list[Section] = []
    title: str | None = None
    buf: list[str] = []

    def flush() -> None:
        text = _clean("\n".join(buf))
        if text:
            sections.append(Section(text=text, section_title=title))
        buf.clear()

    for para in document.paragraphs:
        style = (para.style.name if para.style is not None else "") or ""
        text = para.text.strip()
        if not text:
            continue
        if style.lower().startswith(("heading", "title")):
            flush()
            title = text[:200]
        else:
            buf.append(text)
    for table in document.tables:
        for row in table.rows:
            buf.append(" | ".join(cell.text.strip() for cell in row.cells))
    flush()
    if not sections:
        raise ParseError("The DOCX file contains no text.")
    return ParsedDocument(sections=sections, page_count=None)


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


def parse_markdown(data: bytes) -> ParsedDocument:
    text = data.decode("utf-8")
    sections: list[Section] = []
    title: str | None = None
    buf: list[str] = []
    in_code = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
        m = None if in_code else HEADING_RE.match(line)
        if m:
            if _clean("\n".join(buf)):
                sections.append(Section(text=_clean("\n".join(buf)), section_title=title))
            buf = []
            title = m.group(2)[:200]
        else:
            buf.append(line)
    if _clean("\n".join(buf)):
        sections.append(Section(text=_clean("\n".join(buf)), section_title=title))
    if not sections:
        raise ParseError("The Markdown file contains no text.")
    return ParsedDocument(sections=sections)


def parse_txt(data: bytes) -> ParsedDocument:
    text = _clean(data.decode("utf-8"))
    if not text:
        raise ParseError("The text file is empty.")
    return ParsedDocument(sections=[Section(text=text)])


def parse_document(kind: str, data: bytes) -> ParsedDocument:
    parsers = {"pdf": parse_pdf, "docx": parse_docx, "markdown": parse_markdown, "txt": parse_txt}
    return parsers[kind](data)


def kind_from_mime(mime: str) -> str:
    return {
        "application/pdf": "pdf",
        EXTENSION_MIME["docx"]: "docx",
        "text/markdown": "markdown",
        "text/plain": "txt",
    }[mime]
