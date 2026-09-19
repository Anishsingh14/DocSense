"""text_chunker.py — Stage 2 module.

Structure-aware chunking for general/multi-doc/financial/research
mode (i.e., anything not routed to legal_chunker.py).

DEVIATION FROM TDR: TDR Section 2 specifies LlamaIndex's
`SemanticSplitterNodeParser` for this module. That splitter determines
chunk boundaries by embedding sentences and cutting where embedding
distance jumps — which requires an embedding model at chunk time.
Stage 4 (Embedding & Vector Storage) is where the embedding model is
actually introduced; depending on it here would create a backwards
dependency (Stage 2 -> Stage 4) and add embedding-API cost/latency to
a purely structural step.

Per user decision, this module instead uses a dependency-free,
structure-aware splitter: it splits on paragraph boundaries first,
then greedily packs paragraphs into chunks up to a target character
size, falling back to sentence-level splitting for any single
paragraph that exceeds the target size on its own. Adjacent chunks
overlap by a small amount to preserve context across chunk
boundaries, which is the main retrieval-quality benefit semantic
chunking would otherwise provide.

REVISIT: once Stage 4's embedding model exists, consider swapping this
for true semantic chunking (e.g., LlamaIndex's SemanticSplitterNodeParser)
if retrieval accuracy in Stage 7 evaluation shows it's needed.

Output: list of chunk dicts conforming to the TDR Section 3 schema.
"""

from __future__ import annotations

import re
from typing import List, Optional, TypedDict

TARGET_CHUNK_SIZE_CHARS = 1000
CHUNK_OVERLAP_CHARS = 150

# A paragraph is anything separated by one or more blank lines, or a
# single newline if no blank-line breaks exist in the source text.
_PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


class Chunk(TypedDict):
    chunk_id: str
    doc_id: str
    doc_name: str
    doc_type: str
    page_num: int
    section: Optional[str]
    type: str
    image_type: Optional[str]
    text: str
    source_image_path: Optional[str]


def chunk_document(
    doc_id: str,
    doc_name: str,
    doc_type: str,
    pages: List[dict],
) -> List[Chunk]:
    """Chunks a document's pages into schema-conformant text chunks.

    Args:
        doc_id: the document's doc_id.
        doc_name: original filename.
        doc_type: one of legal | financial | research | general
            (from doc_type_classifier.py). Included on every chunk.
        pages: Stage 1 output, list of
            {"page_num": int, "text": str, ...}.

    Returns:
        List of Chunk dicts. Chunks never span multiple pages — each
        page is chunked independently, so page_num attribution stays
        exact (a hard requirement given mandatory page citations).
    """
    chunks: List[Chunk] = []

    for page in pages:
        page_num = page["page_num"]
        text = (page.get("text") or "").strip()
        if not text:
            continue

        page_chunks_text = _split_page_into_chunks(text)

        for i, chunk_text in enumerate(page_chunks_text):
            chunks.append({
                "chunk_id": f"{doc_id}_p{page_num}_c{i}",
                "doc_id": doc_id,
                "doc_name": doc_name,
                "doc_type": doc_type,
                "page_num": page_num,
                "section": None,
                "type": "text",
                "image_type": None,
                "text": chunk_text,
                "source_image_path": None,
            })

    return chunks


def _split_page_into_chunks(text: str) -> List[str]:
    """Splits a single page's text into overlapping, size-bounded chunks."""
    paragraphs = [p.strip() for p in _PARAGRAPH_SPLIT_RE.split(text) if p.strip()]
    if not paragraphs:
        paragraphs = [text]

    # Break any oversized paragraph into sentence-level pieces so no
    # single unit is larger than the target size before packing.
    units: List[str] = []
    for para in paragraphs:
        if len(para) <= TARGET_CHUNK_SIZE_CHARS:
            units.append(para)
        else:
            units.extend(_split_long_paragraph(para))

    # Greedily pack units into chunks up to the target size.
    raw_chunks: List[str] = []
    current = ""
    for unit in units:
        candidate = f"{current}\n\n{unit}".strip() if current else unit
        if len(candidate) <= TARGET_CHUNK_SIZE_CHARS or not current:
            current = candidate
        else:
            raw_chunks.append(current)
            current = unit
    if current:
        raw_chunks.append(current)

    return _apply_overlap(raw_chunks)


def _split_long_paragraph(paragraph: str) -> List[str]:
    """Splits an oversized paragraph into sentence-packed pieces."""
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(paragraph) if s.strip()]
    if not sentences:
        return [paragraph]

    pieces: List[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) <= TARGET_CHUNK_SIZE_CHARS or not current:
            current = candidate
        else:
            pieces.append(current)
            current = sentence
    if current:
        pieces.append(current)

    return pieces


def _apply_overlap(raw_chunks: List[str]) -> List[str]:
    """Prepends a trailing slice of the previous chunk to each chunk
    (except the first) to preserve cross-boundary context.
    """
    if len(raw_chunks) <= 1:
        return raw_chunks

    overlapped: List[str] = [raw_chunks[0]]
    for i in range(1, len(raw_chunks)):
        prev_tail = raw_chunks[i - 1][-CHUNK_OVERLAP_CHARS:]
        overlapped.append(f"{prev_tail}\n\n{raw_chunks[i]}")

    return overlapped
