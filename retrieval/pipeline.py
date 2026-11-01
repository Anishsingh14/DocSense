"""pipeline.py — Stage 5 orchestrator.

This module combines retriever.py (mode-aware candidate retrieval) and
reranker.py (precision re-scoring) into a single call, producing the
final chunk set that Stage 6 will use to generate a cited answer.
"""

from __future__ import annotations

from typing import List

from retrieval.reranker import DEFAULT_TOP_K, RankedChunk, rerank
from retrieval.retriever import Mode, find_opening_chunk, retrieve

# ADDED (TDR Section 2k). Hard cap on the context handed to Stage 6 in
# legal and multi_doc mode. Every extra chunk lengthens the prompt, and
# longer prompts exhaust per-minute token limits (Groq's in particular)
# sooner, so the guarantees below are bounded rather than open-ended.
MAX_CONTEXT_CHUNKS = 8

# multi_doc: every requested document contributes at least this many
# chunks (its opening chunk counts toward it).
MIN_CHUNKS_PER_DOC = 2


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
        top_k: how many chunks to take from the global ranking. In
            single_doc mode this is the whole result, exactly as
            before. In legal and multi_doc mode the per-document
            guarantees are added on top, capped at MAX_CONTEXT_CHUNKS.

    Returns:
        List of RankedChunk, the final set to hand to Stage 6, ordered
        by descending rerank_score. Stage 6 numbers sources by position
        in this list, so the order returned here IS the source order.
    """
    candidates = retrieve(question, mode, doc_ids)
    if mode == "single_doc":
        return rerank(question, candidates, top_k=top_k)  # unchanged path

    # Score the whole pool so every per-document pick has a real
    # rerank_score — confidence_check reads that score downstream.
    ranked = rerank(question, candidates, top_k=len(candidates))
    return _select_context(ranked, mode, doc_ids, top_k)


def _select_context(
    ranked: List[RankedChunk], mode: Mode, doc_ids: List[str], top_k: int
) -> List[RankedChunk]:
    """Global top_k plus per-document guarantees, deduped and capped.

    ADDED (TDR Section 2k). The first full Stage 7 run showed a single
    global top-5 dropping whole documents (5/12 multi_doc coverage
    queries had full coverage) and missing opening-page facts such as
    titles and parties. Picks are taken in priority order, so if the
    guarantees alone exceed the cap, lower tiers are dropped first:

      1. multi_doc: each document's best chunk
      2. legal + multi_doc: each document's opening chunk
      3. multi_doc: each document's next-best chunks, until it has
         MIN_CHUNKS_PER_DOC
      4. the global ranking (top_k), as before

    The result is re-sorted by rerank_score so the strongest evidence
    still comes first in the prompt.
    """
    by_doc = {d: [c for c in ranked if c["doc_id"] == d] for d in doc_ids}
    chosen: dict = {}

    def take(chunk) -> None:
        if len(chosen) < MAX_CONTEXT_CHUNKS:
            chosen.setdefault(chunk["chunk_id"], chunk)

    if mode == "multi_doc":
        for doc_chunks in by_doc.values():
            if doc_chunks:
                take(doc_chunks[0])
    for doc_chunks in by_doc.values():
        opening = find_opening_chunk(doc_chunks)
        if opening is not None:
            take(opening)
    if mode == "multi_doc":
        for doc_id, doc_chunks in by_doc.items():
            for chunk in doc_chunks:
                have = sum(1 for c in chosen.values() if c["doc_id"] == doc_id)
                if have >= MIN_CHUNKS_PER_DOC:
                    break
                take(chunk)
    for chunk in ranked[:top_k]:
        take(chunk)

    return sorted(chosen.values(), key=lambda c: c["rerank_score"], reverse=True)
