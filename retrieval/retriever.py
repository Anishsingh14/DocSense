"""retriever.py — Stage 5 module.

Mode-aware retrieval per TDR Section 4:
  - single_doc: filter by one doc_id
  - multi_doc: retrieve across all doc_ids in the session, group by source
  - legal: filter doc_type == "legal", boost section-tagged chunks,
    smaller top-k for precision

This module handles the FILTERING/candidate-generation step (vector
similarity + metadata filters). Precision re-ranking of the resulting
candidates is a separate step, which is handled by reranker.py — retriever.py
intentionally over-fetches (larger top-k than what's finally needed)
so reranker.py has enough candidates to re-score meaningfully.
"""

from __future__ import annotations

import re
from typing import List, Literal, Optional, TypedDict

from embedding.embed_chunks import embed_query
from embedding.vector_store import count_points, search

Mode = Literal["single_doc", "multi_doc", "legal"]

# How many candidates to pull from the vector store before reranking.
# Legal mode uses a smaller candidate pool per TDR ("smaller top-k for
# precision") since clause-level chunks are already narrowly scoped by
# legal_chunker.py, so a large candidate pool adds noise rather than
# recall.
CANDIDATE_POOL_SIZE = {
    "single_doc": 20,
    "multi_doc": 30,
    "legal": 10,
}

# Multiplier applied to a legal-mode chunk's score when it has a
# non-null `section` label — per TDR's "boost section-tagged chunks".
# A chunk with a detected clause heading is more likely to be exactly
# on-topic than a chunk that fell back to unlabeled structure-aware
# splitting (see chunking/legal_chunker.py's fallback behavior).
LEGAL_SECTION_BOOST = 1.15

# ADDED (TDR Section 2k): extra per-document candidates for multi_doc.
# The global pool above is ranked across ALL requested documents, so one
# document whose chunks all score lower can be under-represented in it.
# Pulling each document's own top candidates guarantees the reranker
# always has material from every requested document to choose from.
MULTI_DOC_CANDIDATES_PER_DOC = 5

# chunk_id formats: "{doc_id}_p{page}_c{i}" (text) and
# "{doc_id}_p{page}_img{i}" (image) — see chunking/text_chunker.py,
# chunking/legal_chunker.py and ingestion/image_analyzer.py.
_CHUNK_INDEX_PATTERN = re.compile(r"_(?:c|img)(\d+)$")


class RetrievedChunk(TypedDict):
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
    score: float


def retrieve(
    question: str,
    mode: Mode,
    doc_ids: List[str],
) -> List[RetrievedChunk]:
    """Retrieves candidate chunks for a question, mode-aware.

    Args:
        question: the user's natural-language question.
        mode: "single_doc", "multi_doc", or "legal".
        doc_ids: the doc_id(s) in scope for this query. For
            single_doc, this must contain exactly one doc_id. For
            multi_doc, all doc_ids in the current session. For legal,
            the doc_id(s) to search within (legal mode still scopes to
            specific documents — it additionally filters by
            doc_type == "legal" on top of that).

    Returns:
        List of RetrievedChunk, ordered by descending score (after
        the legal-mode section boost, if applicable). This is the
        candidate pool for reranker.py, not the final answer set.
    """
    if not doc_ids:
        return []

    query_vector = embed_query(question)
    limit = CANDIDATE_POOL_SIZE[mode]

    doc_type_filter = "legal" if mode == "legal" else None
    hits = search(query_vector, limit=limit, doc_ids=doc_ids, doc_type=doc_type_filter)

    # ADDED (TDR Section 2k). For legal and multi_doc, guarantee the
    # candidate pool contains each requested document's OPENING chunk
    # (title, parties and dates live there, and those questions failed
    # when it was missing), and for multi_doc, each document's own top
    # candidates. These are local Qdrant reads reusing the single
    # query vector above — no additional embedding call is made.
    # single_doc is deliberately untouched.
    if mode in ("multi_doc", "legal"):
        extra: List[dict] = []
        for doc_id in doc_ids:
            doc_hits = _scan_document(query_vector, doc_id, doc_type_filter)
            if mode == "multi_doc":
                extra.extend(doc_hits[:MULTI_DOC_CANDIDATES_PER_DOC])
            opening = find_opening_chunk(doc_hits)
            if opening is not None:
                extra.append(opening)
        hits = _merge_unique(hits, extra)

    if mode == "legal":
        hits = _apply_legal_section_boost(hits)
    elif mode == "multi_doc":
        hits = sorted(hits, key=lambda h: h["score"], reverse=True)

    return hits  # type: ignore[return-value]


def find_opening_chunk(chunks: List[dict]) -> Optional[dict]:
    """Returns the opening chunk among one document's chunks: lowest
    page, text before image on that page, then lowest chunk index.

    Used by retrieval.pipeline too. It only finds the TRUE opening chunk
    if that chunk is in `chunks`, which retrieve() guarantees for legal
    and multi_doc candidate pools.
    """
    if not chunks:
        return None
    return min(chunks, key=_opening_sort_key)


def _opening_sort_key(chunk: dict) -> tuple:
    match = _CHUNK_INDEX_PATTERN.search(chunk.get("chunk_id", ""))
    index = int(match.group(1)) if match else 10**9
    is_image = 0 if chunk.get("type") == "text" else 1
    return (chunk.get("page_num", 10**9), is_image, index)


def _scan_document(
    query_vector: List[float], doc_id: str, doc_type_filter: Optional[str]
) -> List[dict]:
    """Every chunk of one document, ordered by similarity.

    Uses only the existing public vector_store functions, sized by
    count_points() so the whole document comes back. That is a full
    per-document scan — cheap at V1 scale (5-19 chunks per sample
    document), and worth revisiting for documents with hundreds of
    chunks.
    """
    n = count_points(doc_id)
    if n == 0:
        return []
    return search(query_vector, limit=n, doc_ids=[doc_id], doc_type=doc_type_filter)


def _merge_unique(primary: List[dict], extra: List[dict]) -> List[dict]:
    """primary followed by any extra chunks not already present."""
    seen = {h["chunk_id"] for h in primary}
    merged = list(primary)
    for hit in extra:
        if hit["chunk_id"] not in seen:
            seen.add(hit["chunk_id"])
            merged.append(hit)
    return merged


def _apply_legal_section_boost(hits: List[dict]) -> List[dict]:
    """Boosts chunks with a non-null section label, then re-sorts."""
    boosted = []
    for hit in hits:
        boosted_hit = dict(hit)
        if hit.get("section"):
            boosted_hit["score"] = hit["score"] * LEGAL_SECTION_BOOST
        boosted.append(boosted_hit)

    return sorted(boosted, key=lambda h: h["score"], reverse=True)
