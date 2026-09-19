"""legal_chunker.py — Stage 2 module.

Regex/heading-based clause splitting for legal mode. Detects section
and article headings (e.g., "Section 4.2", "Article 9", "4.2
Termination") and uses them as chunk boundaries, tagging each
resulting chunk with the detected `section` label. This gives legal
mode exact, citable clause boundaries instead of size-based chunks.

Falls back to text_chunker.py's structure-aware splitting for any
stretch of text with no detected heading (e.g., a preamble before the
first numbered section) and for documents where no headings are found
at all, so legal_chunker.py never produces zero chunks.

Output: list of chunk dicts conforming to the TDR Section 3 schema.
"""

from __future__ import annotations

import re
from typing import List, Optional

from chunking.text_chunker import Chunk, _split_page_into_chunks

# Matches headings at the START of a line, e.g.:
#   "Section 4.2 Termination"          "Section 4.2. Termination"
#   "4.2 Termination"                   "4.2. TERMINATION"
#   "Article 9: Indemnification"        "ARTICLE 9 - INDEMNIFICATION"
#   "1.2 Reimbursement and Allocation. The Operating Company shall..."
#
# NOTE: unlike a heading-only-line match, this deliberately does NOT
# anchor to end-of-line ($). Real-world PDF text extraction (e.g. from
# CUAD contracts) frequently puts the heading and the clause body's
# first sentence on the same physical line — there is no line break
# after "1.2 Reimbursement and Allocation." before the clause text
# continues. The heading title is captured up to the first sentence-
# ending period, and everything after that period (on the same line
# or subsequent lines, until the next detected heading) is treated as
# the clause body.
_HEADING_RE = re.compile(
    r"^\s*"
    r"(?:(?P<label>Section|Article|Clause)\s+)?"
    r"(?P<number>\d{1,2}(?:\.\d{1,2}){0,2})"
    r"\s*[.:\-]?\s*"
    r"(?P<title>[A-Z][A-Za-z0-9 ,/&'()-]{2,80}?)?"
    r"(?=\.\s|\.$|:|\s-\s|\s{2,}|$)",
    re.MULTILINE,
)

# A heading candidate line must be reasonably short before the title
# capture kicks in — this bounds how far we scan for a heading pattern
# at the start of a line without requiring the whole line to be short
# (since the clause body may continue on the same line).
_MAX_HEADING_PREFIX_LENGTH = 100


def chunk_legal_document(
    doc_id: str,
    doc_name: str,
    doc_type: str,
    pages: List[dict],
) -> List[Chunk]:
    """Chunks a legal document's pages by detected clause/section headings.

    Args:
        doc_id: the document's doc_id.
        doc_name: original filename.
        doc_type: expected to be "legal", but passed through as given
            rather than hardcoded, in case a document is legal-shaped
            but classified otherwise.
        pages: Stage 1 output, list of
            {"page_num": int, "text": str, ...}.

    Returns:
        List of Chunk dicts, one per detected clause/section per page
        (falling back to structure-aware sub-chunking for any
        oversized clause, and to full structure-aware chunking for
        pages with no detected headings at all).
    """
    chunks: List[Chunk] = []

    for page in pages:
        page_num = page["page_num"]
        text = (page.get("text") or "").strip()
        if not text:
            continue

        clauses = _split_by_headings(text)

        if len(clauses) == 1 and clauses[0][0] is None:
            # No headings detected on this page — fall back to
            # structure-aware chunking so this page still yields
            # retrievable chunks.
            for i, chunk_text in enumerate(_split_page_into_chunks(text)):
                chunks.append(_make_chunk(
                    doc_id, doc_name, doc_type, page_num, i, None, chunk_text
                ))
            continue

        chunk_index = 0
        for section_label, clause_text in clauses:
            if not clause_text.strip():
                continue
            # A single clause can still be long; sub-split it with the
            # same structure-aware packer used for general text so no
            # chunk blows past the target size, while keeping the
            # section label attached to every resulting piece.
            for sub_text in _split_page_into_chunks(clause_text):
                chunks.append(_make_chunk(
                    doc_id, doc_name, doc_type, page_num,
                    chunk_index, section_label, sub_text,
                ))
                chunk_index += 1

    return chunks


def _split_by_headings(text: str) -> List[tuple]:
    """Splits text into (section_label_or_None, clause_text) pairs.

    Headings are detected at the start of a line, but the clause body
    may begin on that SAME line (common in PDF-extracted text — see
    _HEADING_RE's docstring note). To handle this, each line is split
    into a "heading prefix" (if any) and a "rest of line", and clause
    text is reassembled from the rest-of-line pieces plus all
    subsequent lines up to the next detected heading.

    Any text before the first detected heading is returned with a
    None section label (typically a preamble/title block). If no
    heading is found at all, returns a single (None, full_text) pair.
    """
    lines = text.split("\n")
    matches = []  # (line_index, section_label)

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        prefix = stripped[:_MAX_HEADING_PREFIX_LENGTH]
        m = _HEADING_RE.match(prefix)
        if m and (m.group("label") or m.group("title")) and _looks_like_heading_title(m):
            label = _format_section_label(m)
            matches.append((i, label))

    if not matches:
        return [(None, text)]

    clauses = []
    if matches[0][0] > 0:
        preamble = "\n".join(lines[: matches[0][0]]).strip()
        if preamble:
            clauses.append((None, preamble))

    for idx, (line_index, label) in enumerate(matches):
        end = matches[idx + 1][0] if idx + 1 < len(matches) else len(lines)
        # Keep the full heading line verbatim (label + title + any
        # inline clause text that followed it on the same line), then
        # append any remaining lines up to the next heading.
        heading_line = lines[line_index].strip()
        following_lines = lines[line_index + 1:end]
        clause_text = "\n".join([heading_line] + following_lines).strip()
        clauses.append((label, clause_text))

    return clauses


# Common corporate-entity suffixes that can trigger a false heading
# match when a numbered clause's first sentence starts with a company
# name (e.g., "2.1 SampleServices Inc. agrees to..." is a numbered
# clause, NOT a heading titled "SampleServices Inc").
_ENTITY_SUFFIX_RE = re.compile(
    r"\b(Inc|LLC|Corp|Ltd|Co|LLP|LP)\.?$", re.IGNORECASE
)


def _looks_like_heading_title(m: re.Match) -> bool:
    """Filters out numbered-clause false positives.

    A real heading title is a short noun phrase describing the
    clause's subject (e.g., "Term and Termination", "Reimbursement
    and Allocation"). A numbered clause with no real heading instead
    starts directly with a sentence subject, which regularly happens
    to be a capitalized party name — the giveaway is that the
    "title" capture ends in a corporate-entity suffix (Inc., LLC,
    Corp., etc.), which is never how a real section heading ends.

    A bare numeric label with no title at all (e.g., a Section/Article
    label group present) is still accepted, since that's the label
    doing the identifying work, not the title text.
    """
    title = m.group("title")
    if not title:
        return True  # Section/Article N with no title — still valid.
    return not _ENTITY_SUFFIX_RE.search(title)


def _format_section_label(m: re.Match) -> str:
    label = m.group("label")
    number = m.group("number")
    title = (m.group("title") or "").strip()

    prefix = f"{label} {number}" if label else number
    return f"{prefix} {title}".strip() if title else prefix


def _make_chunk(
    doc_id: str,
    doc_name: str,
    doc_type: str,
    page_num: int,
    chunk_index: int,
    section_label: Optional[str],
    text: str,
) -> Chunk:
    return {
        "chunk_id": f"{doc_id}_p{page_num}_c{chunk_index}",
        "doc_id": doc_id,
        "doc_name": doc_name,
        "doc_type": doc_type,
        "page_num": page_num,
        "section": section_label,
        "type": "text",
        "image_type": None,
        "text": text,
        "source_image_path": None,
    }
