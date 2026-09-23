"""confidence_check.py — Stage 6 module.

Flags low-confidence answers, per TDR Section 4: "e.g., low similarity
score on retrieved chunks, or LLM stating 'not found'".

DEVIATION FROM TDR: TDR requires a per-source confidence level
("high | medium | low" — Section 3's API response schema) but doesn't
specify how to compute it. This module fills that gap with thresholds
on the reranker's cross-encoder score (retrieval/reranker.py's
rerank_score), since that's already the most reliable per-chunk
relevance signal available in this pipeline (a cross-encoder jointly
attending over the question+chunk pair is generally more informative
than the raw vector-similarity score alone — see reranker.py's
docstring). Thresholds are heuristic starting points, not derived from
labeled data; TUNABLE — revisit during Stage 7 evaluation if the
labels don't match human judgment on the eval set.
"""

from __future__ import annotations

from typing import List, Literal, Optional

ConfidenceLevel = Literal["high", "medium", "low"]

# rerank_score is a raw (unbounded, not probability-like) cross-encoder
# logit — see retrieval/reranker.py. These thresholds were picked by
# eyeballing the Stage 5 test run's score distributions (e.g., correct
# top hits scored 0.4-0.99, low-relevance tail hits scored <0.01).
HIGH_CONFIDENCE_THRESHOLD = 0.3
MEDIUM_CONFIDENCE_THRESHOLD = 0.05

# Phrases that indicate the LLM itself is signaling "not found" in its
# generated answer text — checked case-insensitively as a substring.
# Kept intentionally short/generic since these are meant to catch the
# LLM's own admission, not to parse arbitrary answer content.
#
# WIDENED (found via manual Stage 6 test run, case 7's actual not-found
# answer: "The provided sources do not contain information about the
# CEO's name or salary."): none of the phrases below matched this
# verbatim — "sources above do not contain" assumed a specific lead-in
# word ("above") the model didn't actually use here. It was the
# generic, unqualified "does not contain" entry that was catching this
# case in practice, but that same generic entry is also what caused
# the false positive fixed above (matching a short, unrelated aside
# inside a long, complete answer). Rather than rely on an overly broad
# generic phrase to cover a specific real phrasing, added the model's
# actual wording directly.
_NOT_FOUND_PHRASES = [
    "not found in the provided document",
    "not found in the document",
    "does not contain",
    "sources above do not contain",
    "provided sources do not contain",
    "no information about this",
]

# See answer_indicates_not_found's "FIXED BUG" note: a genuine
# not-found answer is short (the LLM's own real examples are one
# sentence, well under 200 characters); a not-found phrase appearing
# only past this point in the text is far more likely to be a
# localized aside inside an otherwise complete answer than the
# answer itself being a non-answer.
_NOT_FOUND_PHRASE_MAX_ANSWER_LEN = 200


def score_chunk_confidence(rerank_score: float) -> ConfidenceLevel:
    """Maps a single chunk's rerank_score to a confidence level."""
    if rerank_score >= HIGH_CONFIDENCE_THRESHOLD:
        return "high"
    if rerank_score >= MEDIUM_CONFIDENCE_THRESHOLD:
        return "medium"
    return "low"


def answer_indicates_not_found(answer_text: str) -> bool:
    """Returns True if the LLM's answer text ITSELF IS an admission
    that the information wasn't found in the retrieved sources — as
    opposed to a long, otherwise-complete answer that merely mentions
    one of these phrases somewhere in passing.

    FIXED BUG (found via manual Stage 6 multi_doc test run): this
    originally searched for any _NOT_FOUND_PHRASES substring ANYWHERE
    in the answer text, with no regard for how much of the text that
    covered. A real multi_doc comparison answer — five sources cited,
    several full clauses quoted, clearly a complete and useful answer
    — included one honest, LOCALIZED aside near the end: "(Source 1
    does not contain a provision regarding the post-termination
    survival of obligations in its text)". That aside is accurate and
    worth keeping (it correctly notes a real per-source gap on one
    sub-point), but the old substring-anywhere check matched
    "does not contain" and flagged the ENTIRE five-source, correctly-
    cited answer as "Not found in the provided document(s)" — a
    seriously misleading warning on a good answer.

    A genuine not-found answer (see generate_answer's empty-chunks
    case, and the LLM's own not-found answers in practice, e.g.
    "The provided sources do not contain information about the CEO's
    name or salary.") is short: the not-found admission more or less
    IS the whole answer, not one aside buried inside a much longer
    one. So this now requires the matched phrase to appear within the
    answer's first _NOT_FOUND_PHRASE_MAX_ANSWER_LEN characters — long
    enough to comfortably cover a real one-or-two-sentence not-found
    answer, short enough that a phrase appearing only deep into a
    long, multi-paragraph answer (like the aside above) does not
    trigger this. This is a heuristic, like the confidence thresholds
    above — not a semantic "is this actually a complete non-answer"
    judgment — but it fixes the specific, confirmed failure mode
    above without weakening genuine not-found detection (case 7's
    style of answer is far under this length).
    """
    prefix = answer_text[:_NOT_FOUND_PHRASE_MAX_ANSWER_LEN].lower()
    return any(phrase in prefix for phrase in _NOT_FOUND_PHRASES)


def build_warning(
    answer_text: str,
    used_chunks: List[dict],
    discarded_citation_count: int,
) -> Optional[str]:
    """Builds the `warning` field for the API response schema
    (TDR Section 3): "null or a string if confidence is low / info
    not found".

    Args:
        answer_text: the LLM's generated answer.
        used_chunks: the chunks actually cited in the final answer
            (after answer_with_citations.py's cross-check discards any
            hallucinated citation — see that module).
        discarded_citation_count: how many citations the LLM produced
            that did NOT match any retrieved chunk and were discarded
            (TDR Section 6's "discard/flag any mismatch").

    Returns:
        A warning string, or None if nothing warrants one.
    """
    if answer_indicates_not_found(answer_text):
        return "Not found in the provided document(s)."

    if not used_chunks:
        return (
            "No sources could be verified for this answer. The answer "
            "may not be grounded in the retrieved document content."
        )

    if discarded_citation_count > 0:
        return (
            f"{discarded_citation_count} citation(s) in the generated "
            f"answer did not match any retrieved source and were "
            f"discarded. The answer may be incomplete."
        )

    confidences = [score_chunk_confidence(c["rerank_score"]) for c in used_chunks]
    if all(c == "low" for c in confidences):
        return (
            "Low confidence: the best-matching sources had low "
            "relevance scores. Consider verifying this answer manually."
        )

    return None
