"""Splits parsed sections into overlapping chunks.

Token counts are approximated as len(text) / 4 (a common rule of thumb for English),
which avoids an extra API call per chunk. Chunks never cross a page/section boundary,
so every chunk keeps an accurate page_number and section_title for citations.
"""

import re
from dataclasses import dataclass

from app.parsers import Section

CHARS_PER_TOKEN = 4


@dataclass
class Chunk:
    index: int
    content: str
    page_number: int | None
    section_title: str | None


def _split_units(text: str) -> list[str]:
    """Paragraphs, then sentences for paragraphs that are too long on their own."""
    units: list[str] = []
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if para:
            units.extend(s.strip() for s in re.split(r"(?<=[.!?。！？])\s+", para) if s.strip())
    return units


def _hard_wrap(unit: str, size: int) -> list[str]:
    return [unit[i : i + size] for i in range(0, len(unit), size)]


def chunk_sections(sections: list[Section], chunk_tokens: int, overlap_tokens: int) -> list[Chunk]:
    size = chunk_tokens * CHARS_PER_TOKEN
    overlap = min(overlap_tokens * CHARS_PER_TOKEN, size // 2)
    chunks: list[Chunk] = []

    for section in sections:
        units: list[str] = []
        for u in _split_units(section.text):
            units.extend(_hard_wrap(u, size) if len(u) > size else [u])
        current = ""
        for unit in units:
            candidate = f"{current} {unit}".strip()
            if len(candidate) <= size:
                current = candidate
                continue
            chunks.append(Chunk(len(chunks), current, section.page_number, section.section_title))
            tail = current[-overlap:] if overlap else ""
            # start the overlap at a word boundary
            if " " in tail:
                tail = tail[tail.index(" ") + 1 :]
            current = f"{tail} {unit}".strip()
        if current:
            chunks.append(Chunk(len(chunks), current, section.page_number, section.section_title))
    return chunks
