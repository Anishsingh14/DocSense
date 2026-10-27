"""answer_with_citations.py — Stage 6 module.

This model assembles labeled context from Stage 5's reranked chunks, calls the
LLM to generate an answer, and parses citations back against the
ACTUAL retrieved chunk metadata — never trusting the LLM's own memory
of page numbers (TDR Section 6: "the generation layer must cross-check
every page number the LLM cites against the actual metadata of
retrieved chunks; discard/flag any mismatch").

HOW THE CROSS-CHECK WORKS: the LLM is instructed (prompt_templates.py)
to cite only using "Source N" labels, where N is a chunk's position
in the already-known, already-retrieved chunk list — never asked to
state a page number itself. After generation, this module finds every
"Source N" occurrence anywhere in the answer text (see
_extract_valid_citations — not anchored to appearing inside parens,
since the model wraps the label in several different ways in
practice), then for each one found, looks up chunk N's REAL metadata
(page_num, doc_name, section) from the chunk list we already have —
not from anything the LLM wrote. Any "Source N" reference where N is
out of range (i.e., the LLM invented a source number that doesn't
exist) is discarded rather than surfaced, per TDR's "discard/flag any
mismatch" rule. This structurally prevents the failure mode TDR is
worried about: the LLM cannot cite a page number that wasn't actually
retrieved, because the citation mechanism never lets it name a page
number directly at all (any page/section text the LLM writes near
"Source N", e.g. "(Source 1 | Page 4 | Section 9)", is ignored by the
parser and by _chunk_to_source_info — the REAL page_num/section always
come from chunk N's own metadata, never parsed out of the LLM's text).

FIXED BUGS (found via manual Stage 6 test runs — three rounds):
1. The citation regex originally required the closing paren
   immediately after the digit, i.e. it only matched a bare
   "(Source N)". The model frequently echoes the context block's own
   "[Source N | Page X | Section Y]" label format back in its
   citations, e.g. "(Source 1 | Page 4 | Section 9 INDEMNITY)", which
   the original regex did not match — silently discarding a VALID
   citation (the opposite failure mode from a hallucinated citation).
2. The first fix only added support for a pipe separator, but the
   model also produces a COMMA-separated variant of the same pattern,
   e.g. "(Source 1, Page 4, Section 9 INDEMNITY)" — still not matched
   — and combines MULTIPLE source numbers in one parenthetical, e.g.
   "(Source 1, Source 2, Source 4)", which neither prior version
   could parse at all (not even the first number), because the
   comma immediately after "Source 1" matched neither ")" nor "|".
3. In legal mode specifically, the model sometimes drops the
   surrounding parens entirely and instead bolds the label as a
   lead-in, e.g. "From **Source 1** (Page 4, Section 9 INDEMNITY):",
   with the page/section parenthetical that follows containing no
   "Source" word at all. A paren-anchored search finds no "Source N"
   inside any "(...)" span in that sentence at all — SOURCES (0),
   even though the citation is clearly present and unambiguous to a
   human reader. Root cause: prompt_templates.py's legal-mode
   instructions ask the model to both cite "(Source N)" AND state the
   page/section per quote, without saying the Source label alone
   already suffices — the model reasonably improvised a hybrid
   format to satisfy both. Fixed prompt_templates.py to remove that
   ambiguity (see its module docstring), but this parser is also
   loosened as a safety net: TDR Section 6 wants the extraction to be
   robust to reasonable format drift, not just to whatever a single
   prompt revision currently instructs.

FIX: rather than trying to enumerate every separator variant, or every
markdown wrapper, the approach now works in two passes:
  (a) find every "Source N" occurrence anywhere in the answer text —
      not anchored to being inside parens — regardless of surrounding
      punctuation (bare parens, pipe/comma-separated parens, bold
      markdown asterisks, or nothing at all)
  (b) de-duplicate and validate each N against the actual chunk count,
      exactly as before
This handles bare, pipe-separated, comma-separated, combined
multi-source, and bold-lead-in citations uniformly, without depending
on which punctuation or markdown the model happens to wrap the label
in. The only remaining anchor is the literal word "Source" followed
by a number — the same anchor the original design always relied on —
so this is strictly a widening of where that anchor is allowed to
appear, not a change to what counts as a citation.

DEVIATION FROM TDR (see TDR.md Section 2a): TDR specifies Claude
(Sonnet for legal/precision mode, Haiku for general/summary mode) for
generation. Per the user's documented provider substitution, this
module does not use Claude, and applies ONE model per request across
all modes rather than a Sonnet/Haiku-style two-tier split. The LLM
call is isolated in `_call_llm`, so changing provider strategy stays
a contained change to that one function.

PROVIDER CHANGE (see TDR.md Section 2i, which supersedes Section 2e
for answer calls): generation no longer targets a Gemini model
directly. `_call_llm` delegates to
generation.provider_rotation.call_with_provider_rotation, which
rotates across 7 independent OpenAI-compatible providers and pins one
model per provider. The earlier Gemini-only chain
(gemini-3.8-flash -> gemini-3.7-flash) was removed because both tiers
share Google's Flash-tier capacity and were observed failing together,
so model fallback within one vendor could not absorb a vendor-wide
capacity event. Gemini remains one of the 7 providers (RAG_Gemini).

Section 2e's history is still relevant background: gemini-2.5-flash is
not available to newly-created API keys (404 "no longer available to
new users"), which is why the pinned Gemini model is a 3.x Flash
model rather than 2.5.

NOTE: embeddings (Stage 4) and image analysis (Stage 3) are NOT
affected by the above — they still use the GEMINI_API_KEY..._7 pool
via generation.gemini_key_rotation.
"""

from __future__ import annotations

import os
import re
from typing import List, Literal, Optional, TypedDict

from dotenv import load_dotenv

from generation.confidence_check import build_warning, score_chunk_confidence
from generation.provider_rotation import call_with_provider_rotation
from generation.prompt_templates import AnswerStyle, Mode, build_prompt

load_dotenv()

# REMOVED (TDR Section 2i): GENERATION_MODELS, the Gemini-only
# 2-tier model chain (gemini-3.8-flash -> gemini-3.7-flash), together
# with its GEMINI_GENERATION_MODELS override. Answer generation now
# rotates across independent vendors via generation/
# provider_rotation.py, which pins one model per provider, so a
# Gemini-specific model list here would be dead configuration that
# looks live.
#
# The history is kept because it explains the current design:
#   - gemini-3.6-flash was deliberately EXCLUDED from that chain (its
#     multi-hour 503 congestion on 2026-09-24/25 blocked every
#     attempted Stage 7 run, so falling back onto it was circular).
#   - 3.8 and 3.7 then degraded TOGETHER during the 2026-10-06 run,
#     503-ing within seconds of each other on the same key. That
#     confirmed the shared-capacity caveat recorded at the time:
#     sibling Flash-tier models are not independent failure domains,
#     so model fallback within one vendor cannot fix a vendor-wide
#     capacity event. Cross-vendor rotation is the response to that
#     finding.
# Gemini remains available as one of the seven answer providers
# (RAG_Gemini, pinned to gemini-3.8-flash).

# Finds every "Source N" occurrence anywhere in the answer text —
# NOT anchored to appearing inside a "(...)" parenthetical, since the
# model has been observed to wrap the label in several different ways
# (see module docstring "FIXED BUGS" #1-3): bare parens, pipe- or
# comma-separated parens with trailing page/section text, multiple
# source numbers combined in one parenthetical, or a bold markdown
# lead-in with no surrounding parens at all, e.g. "**Source 1**".
# Covers: "(Source 1)", "(Source 1 | Page 4 | Section 9)",
# "(Source 1, Page 4, Section 9)", "(Source 1, Source 2, Source 4)",
# and "**Source 1**". The word boundary before "Source" avoids
# matching it as a suffix of some other word (e.g. "Resource 1").
_SOURCE_NUM_RE = re.compile(r"\bSource\s+(\d+)")


class SourceInfo(TypedDict):
    doc_name: str
    page_num: int
    section: Optional[str]
    type: str
    confidence: Literal["high", "medium", "low"]


class AnswerResult(TypedDict):
    answer: str
    mode: Mode
    answer_style: AnswerStyle
    sources: List[SourceInfo]
    warning: Optional[str]
    provider_used: Optional[str]  # which answer provider (env var
    # name, e.g. "RAG_Groq") served this answer, or None when no LLM
    # call was made (the empty-chunks short-circuit below). Added with
    # TDR Section 2i's multi-provider rotation: with 7 vendors in play,
    # "which model" is no longer enough to interpret a result — two
    # providers can serve the same model id, and provider is the unit
    # that cooldowns and session-removal act on.
    model_used: Optional[str]  # which model actually served it, as
    # reported by the provider's own response rather than the
    # configured id — these differ for the openrouter/free alias,
    # which routes to an arbitrary free model per request.


def generate_answer(
    question: str,
    chunks: List[dict],
    mode: Mode,
    answer_style: AnswerStyle = "full",
) -> AnswerResult:
    """Generates a cited answer from retrieved chunks.

    Args:
        question: the user's natural-language question.
        chunks: reranked chunks from retrieval.reranker.rerank()
            (or retrieval.pipeline.retrieve_and_rerank()). Empty list
            is handled explicitly (TDR Section 7: "No relevant chunks
            found for a question -> return 'Not found...'").
        mode: "single_doc", "multi_doc", or "legal".
        answer_style: "full" or "summary" (PRD FR-5).

    Returns:
        AnswerResult conforming to TDR Section 3's API response
        schema (fields: answer, mode, answer_style, sources, warning).
    """
    if not chunks:
        return {
            "answer": "Not found in the provided document(s).",
            "mode": mode,
            "answer_style": answer_style,
            "sources": [],
            "warning": "No relevant chunks were retrieved for this question.",
            "provider_used": None,
            "model_used": None,
        }

    prompt = build_prompt(question, chunks, mode, answer_style)
    raw_answer, provider_used, model_used = _call_llm(prompt)

    cited_indices, discarded_count = _extract_valid_citations(raw_answer, len(chunks))
    used_chunks = [chunks[i] for i in cited_indices]

    sources = [_chunk_to_source_info(chunk) for chunk in used_chunks]
    warning = build_warning(raw_answer, used_chunks, discarded_count)

    return {
        "answer": raw_answer,
        "mode": mode,
        "answer_style": answer_style,
        "sources": sources,
        "warning": warning,
        "provider_used": provider_used,
        "model_used": model_used,
    }


def _extract_valid_citations(answer_text: str, num_chunks: int) -> tuple:
    """Finds every "Source N" reference anywhere in the answer text,
    and validates each N against the actual number of retrieved
    chunks.

    Not anchored to appearing inside a "(...)" parenthetical (see
    module docstring "FIXED BUGS" note for why) — this handles a bare
    citation, a pipe- or comma-separated citation with trailing
    page/section text, multiple source numbers combined in one
    parenthetical, and a bold-markdown lead-in with no parens at all,
    all uniformly.

    Returns:
        (valid_zero_based_indices, discarded_count) — valid_indices is
        a de-duplicated, order-preserving list of 0-based chunk
        indices that were validly cited; discarded_count is how many
        citations referenced an out-of-range N (TDR's "hallucinated
        citation" case this whole module exists to catch).
    """
    seen = set()
    valid_indices = []
    discarded_count = 0

    for source_match in _SOURCE_NUM_RE.finditer(answer_text):
        source_num = int(source_match.group(1))  # 1-based, as written by the LLM
        zero_based = source_num - 1

        if 0 <= zero_based < num_chunks:
            if zero_based not in seen:
                seen.add(zero_based)
                valid_indices.append(zero_based)
        else:
            # The LLM cited a source number that doesn't correspond
            # to any chunk we actually retrieved — exactly the
            # hallucinated-citation case TDR Section 6 requires us
            # to catch and discard.
            discarded_count += 1

    return valid_indices, discarded_count


def _chunk_to_source_info(chunk: dict) -> SourceInfo:
    return {
        "doc_name": chunk["doc_name"],
        "page_num": chunk["page_num"],
        "section": chunk.get("section"),
        "type": chunk["type"],
        "confidence": score_chunk_confidence(chunk["rerank_score"]),
    }


def _call_llm(prompt: str) -> tuple:
    """Sends the assembled prompt to the current answer provider.

    Returns:
        (answer_text, provider_used, model_used) — so the caller can
        record BOTH which vendor served the request and which model
        that vendor actually used. A rotation chain is only auditable
        if the result says what produced it, and for the
        openrouter/free alias the served model is not knowable from
        the configured id alone.

    CHANGED (TDR Section 2i): previously this tried every model in
    GENERATION_MODELS against each Gemini key in turn. That chain
    shared Google's Flash-tier capacity, so a congestion event took
    out every tier at once (Stage 7 run of 2026-10-06: 5 of 11
    questions unmeasured). Answer calls now rotate across independent
    vendors instead — see generation/provider_rotation.py. Embeddings
    and image reading deliberately stay on the Gemini key pool.
    """
    return call_with_provider_rotation(
        [{"role": "user", "content": prompt}]
    )
