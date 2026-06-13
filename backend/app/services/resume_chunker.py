"""Section + size hybrid chunking for resumes.

Strategy:
  1. Detect section headers (Experience, Projects, Education, Skills, …) and
     group lines under their section.
  2. Sub-split any section whose body exceeds _MAX_CHARS into overlapping
     windows, breaking on sentence/line/word boundaries to preserve meaning.

Pure module — no DB, no embeddings. Returns plain dicts.
"""
from __future__ import annotations

# Common resume section headers (lowercased, matched against short heading lines)
_SECTION_PATTERNS: tuple[str, ...] = (
    "work experience", "professional experience", "experience", "employment",
    "education", "academic background",
    "personal projects", "projects", "selected projects",
    "technical skills", "skills", "core competencies",
    "certifications", "certificates",
    "achievements", "awards", "honors", "honours",
    "publications", "research", "research experience",
    "summary", "professional summary", "objective", "about",
    "contact", "interests", "hobbies",
    "volunteer", "leadership", "positions of responsibility",
    "coursework", "relevant coursework",
)

_MAX_CHARS = 500
_OVERLAP = 80
_MAX_HEADER_LEN = 45


def _detect_section(line: str) -> str | None:
    """If a line looks like a section header, return its normalised title."""
    s = line.strip().rstrip(":").strip()
    low = s.lower()
    if not (0 < len(s) <= _MAX_HEADER_LEN):
        return None
    for pat in _SECTION_PATTERNS:
        if low == pat or low.startswith(pat + " ") or low == pat + "s":
            return s.title()
    return None


def _split_by_size(text: str, max_chars: int = _MAX_CHARS, overlap: int = _OVERLAP) -> list[str]:
    """Split text into overlapping windows on natural boundaries."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = start + max_chars
        if end >= n:
            tail = text[start:].strip()
            if tail:
                chunks.append(tail)
            break

        window = text[start:end]
        # Prefer sentence end, then newline, then semicolon, then last space
        break_at = max(window.rfind(". "), window.rfind("\n"), window.rfind("; "))
        if break_at < int(max_chars * 0.5):
            break_at = window.rfind(" ")
        if break_at <= 0:
            break_at = max_chars - 1

        piece = text[start:start + break_at + 1].strip()
        if piece:
            chunks.append(piece)

        next_start = start + break_at + 1 - overlap
        start = next_start if next_start > start else start + max_chars

    return chunks


def chunk_resume(text: str) -> list[dict]:
    """Chunk resume text via section + size hybrid.

    Returns: [{"content": str, "section": str, "chunk_index": int}]
    """
    lines = (text or "").splitlines()
    sections: list[tuple[str, list[str]]] = [("General", [])]

    for line in lines:
        sec = _detect_section(line)
        if sec:
            sections.append((sec, []))
        else:
            sections[-1][1].append(line)

    chunks: list[dict] = []
    idx = 0
    for section_name, body_lines in sections:
        body = "\n".join(body_lines).strip()
        if not body:
            continue
        for piece in _split_by_size(body):
            chunks.append({"content": piece, "section": section_name, "chunk_index": idx})
            idx += 1

    # Fallback: text without recognisable sections
    if not chunks and (text or "").strip():
        for piece in _split_by_size(text):
            chunks.append({"content": piece, "section": "General", "chunk_index": idx})
            idx += 1

    return chunks
