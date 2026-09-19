"""reranker.py — Stage 5 module.

Re-scores retrieved chunks with `bge-reranker-v2-m3` (local, free —
no provider substitution needed here, unlike Stages 3/4/6), returning
the top 3-5 per TDR Section 4.

A cross-encoder reranker jointly attends over the (query, chunk_text)
pair to produce a relevance score, which is generally more accurate
for final ranking than the cosine-similarity score from vector search
alone — that's the entire reason this is a separate step from
retriever.py rather than just trusting the vector store's ranking.
"""

from __future__ import annotations

import os
from typing import List, Optional, TypedDict

# Default final result count. TDR Section 4 specifies "top 3-5";
# 5 is used as the default to give Stage 6 slightly more context to
# work with, while still being tunable per call.
DEFAULT_TOP_K = 5

RERANKER_MODEL = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")

_reranker_cache = {}


class RankedChunk(TypedDict):
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
    rerank_score: float


def rerank(question: str, candidates: List[dict], top_k: int = DEFAULT_TOP_K) -> List[RankedChunk]:
    """Re-scores candidate chunks against the question, returns top_k.

    Args:
        question: the user's natural-language question.
        candidates: chunks from retriever.py (each must have a "text"
            field; the "score" field from vector search is preserved
            but not used for final ordering — rerank_score decides
            the final order).
        top_k: how many chunks to return after reranking.

    Returns:
        List of RankedChunk (candidates, unchanged except for an
        added "rerank_score" field), sorted by descending
        rerank_score, truncated to top_k. Returns an empty list if
        candidates is empty.
    """
    if not candidates:
        return []

    model = _get_reranker_model()
    pairs = [(question, chunk["text"]) for chunk in candidates]
    rerank_scores = model.predict(pairs)

    ranked = []
    for chunk, rerank_score in zip(candidates, rerank_scores):
        ranked_chunk = dict(chunk)
        ranked_chunk["rerank_score"] = float(rerank_score)
        ranked.append(ranked_chunk)

    ranked.sort(key=lambda c: c["rerank_score"], reverse=True)
    return ranked[:top_k]  # type: ignore[return-value]


def _get_reranker_model():
    if "model" not in _reranker_cache:
        from sentence_transformers import CrossEncoder

        _reranker_cache["model"] = CrossEncoder(RERANKER_MODEL)
    return _reranker_cache["model"]
