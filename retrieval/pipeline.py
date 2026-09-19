"""pipeline.py — Stage 5 orchestrator.

Combines retriever.py (mode-aware candidate retrieval) and
reranker.py (precision re-scoring) into a single call, producing the
final chunk set that Stage 6 will use to generate a cited answer.
"""

from __future__ import annotations

from typing import List

from retrieval.reranker import DEFAULT_TOP_K, RankedChunk, rerank
from retrieval.retriever import Mode, retrieve


def retrieve_and_rerank(
    question: str,
    mode: Mode,
    doc_ids: List[str],
    top_k: int = DEFAULT_TOP_K,
) -> List[RankedChunk]:
    """Retrieves candidates, then reranks them, for a single question.

    Args:
        question: the user's natural-language question.
        mode: "single_doc", "multi_doc", or "legal".
        doc_ids: the doc_id(s) in scope for this query.
        top_k: how many final chunks to return after reranking.

    Returns:
        List of RankedChunk, the final set to hand to Stage 6.
    """
    candidates = retrieve(question, mode, doc_ids)
    return rerank(question, candidates, top_k=top_k)
