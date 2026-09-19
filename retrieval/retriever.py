"""retriever.py — Stage 5 module.

Mode-aware retrieval per TDR Section 4:
  - single_doc: filter by one doc_id
  - multi_doc: retrieve across all doc_ids in the session, group by source
  - legal: filter doc_type == "legal", boost section-tagged chunks,
    smaller top-k for precision

This module handles the FILTERING/candidate-generation step (vector
similarity + metadata filters). Precision re-ranking of the resulting
candidates is a separate step, handled by reranker.py — retriever.py
intentionally over-fetches (larger top-k than what's finally needed)
so reranker.py has enough candidates to re-score meaningfully.
"""

from __future__ import annotations

from typing import List, Literal, Optional, TypedDict

from embedding.embed_chunks import embed_query
from embedding.vector_store import search

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

    if mode == "legal":
        hits = _apply_legal_section_boost(hits)

    return hits  # type: ignore[return-value]


def _apply_legal_section_boost(hits: List[dict]) -> List[dict]:
    """Boosts chunks with a non-null section label, then re-sorts."""
    boosted = []
    for hit in hits:
        boosted_hit = dict(hit)
        if hit.get("section"):
            boosted_hit["score"] = hit["score"] * LEGAL_SECTION_BOOST
        boosted.append(boosted_hit)

    return sorted(boosted, key=lambda h: h["score"], reverse=True)
