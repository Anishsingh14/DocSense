"""pipeline.py — Stage 6 orchestrator.

Combines retrieval.pipeline.retrieve_and_rerank() (Stage 5) with
answer_with_citations.generate_answer() (Stage 6) into a single call:
question -> final cited answer.
"""

from __future__ import annotations

from generation.answer_with_citations import AnswerResult, generate_answer
from generation.prompt_templates import AnswerStyle, Mode
from retrieval.pipeline import retrieve_and_rerank


def answer_question(
    question: str,
    mode: Mode,
    doc_ids: list,
    answer_style: AnswerStyle = "full",
) -> AnswerResult:
    """Runs Stages 5-6 end-to-end for a single question.

    Args:
        question: the user's natural-language question.
        mode: "single_doc", "multi_doc", or "legal".
        doc_ids: the doc_id(s) in scope for this query.
        answer_style: "full" or "summary".

    Returns:
        AnswerResult conforming to TDR Section 3's API response schema.
    """
    chunks = retrieve_and_rerank(question, mode, doc_ids)
    return generate_answer(question, chunks, mode, answer_style)
