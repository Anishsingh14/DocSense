"""answer_with_citations.py — Stage 6 module.

Assembles labeled context from Stage 5's reranked chunks, calls the
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
module uses Google Gemini instead, consistently across all modes (no
Sonnet/Haiku-style two-tier model split — see GENERATION_MODEL below).
The Gemini API call is isolated in `_call_llm`, so swapping back to
Claude (and reintroducing a two-tier model choice, if desired) is a
contained change to this one function.

MODEL CHANGE (see TDR.md Section 2e): originally gemini-2.5-flash;
switched to gemini-3.6-flash because the newer keys added for Section
2d's multi-key rotation could not access gemini-2.5-flash at all (a
404 "no longer available to new users" error), which defeated the
purpose of having multiple keys. gemini-3.6-flash was verified
(a) Stable (not preview/experimental) via Google's own model docs and
(b) actually callable on a newly-created key via a direct live test,
before being adopted here.
"""

from __future__ import annotations

import os
import re
from typing import List, Literal, Optional, TypedDict

from dotenv import load_dotenv

from generation.confidence_check import build_warning, score_chunk_confidence
from generation.gemini_key_rotation import (
    build_http_options,
    call_with_model_and_key_rotation,
)
from generation.prompt_templates import AnswerStyle, Mode, build_prompt

load_dotenv()

# Model priority chain, highest preference first. Each is tried on
# the CURRENT key before rotating keys at all — see
# gemini_key_rotation.call_with_model_and_key_rotation for why that
# ordering matters (a 503 is per-model and globally shared, so
# switching model beats sweeping keys).
#
# Verified reachable on our keys 2026-09-25 via one minimal call each:
#   gemini-3.8-flash  OK   4.31s                      <- primary
#   gemini-3.7-flash  503 high demand (exists, was congested)  <- fallback
#   gemini-3.6-flash  OK   1.91s                      <- DELIBERATELY EXCLUDED
#
# DELIBERATE EXCLUSION of gemini-3.6-flash (user decision, and the
# correct one): 3.6 was the previous primary and is the specific
# model whose multi-hour 503 congestion on 2026-09-24/25 blocked
# every attempted Stage 7 eval run — it is the reason this fallback
# mechanism exists at all. Including it as a last-resort tier is
# circular: if 3.8 and 3.7 both fail we would fall straight back onto
# the known-unreliable model that caused the outage, converting a
# clear, informative "all allowed models are down" signal into a
# silent retry against the worst option. It was briefly added here as
# a third tier on the reasoning that 3.7 was measurably 503 at
# verification time and the chain would otherwise have no
# verified-healthy fallback; that reasoning was wrong, because an
# honest hard failure is more useful than a fallback onto the model
# we are specifically trying to stop depending on. Total exhaustion
# of this 2-tier chain now fails loudly and distinctly instead — see
# gemini_key_rotation.AllModelsAndKeysExhaustedError.
#
# CAVEAT WORTH REMEMBERING (user observation): 3.8, 3.7 and 3.6 are
# all Google Flash-tier models and may share underlying capacity, so
# these two tiers are NOT guaranteed to fail independently. The
# 2026-09-25 sample (3.7 down while 3.8 and 3.6 were up) is a single
# data point. If the live run shows 3.8 and 3.7 degrading together,
# treat model fallback as insufficient on its own rather than
# assuming the chain is simply too short.
#
# Override with GEMINI_GENERATION_MODELS as a comma-separated list.
GENERATION_MODELS = [
    m.strip()
    for m in os.getenv(
        "GEMINI_GENERATION_MODELS",
        "gemini-3.8-flash,gemini-3.7-flash",
    ).split(",")
    if m.strip()
]

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
    model_used: Optional[str]  # which model in GENERATION_MODELS
    # actually produced this answer, or None when no LLM call was made
    # (the empty-chunks short-circuit below). Recorded so a fallback
    # chain is auditable: a result is not interpretable without
    # knowing which tier served it.


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
            "model_used": None,
        }

    prompt = build_prompt(question, chunks, mode, answer_style)
    raw_answer, model_used = _call_llm(prompt)

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
    """Sends the assembled prompt to Gemini.

    Returns:
        (answer_text, model_used) — model_used names the model that
        actually served the request, so the caller can record it (a
        fallback chain is only auditable if the result says which
        tier produced it).

    Tries every model in GENERATION_MODELS on the current key before
    rotating keys (TDR Section 2d for key rotation; see
    call_with_model_and_key_rotation for why model-before-key).
    """
    from google import genai

    def _make_call(api_key: str, model: str) -> str:
        client = genai.Client(api_key=api_key, http_options=build_http_options())
        response = client.models.generate_content(model=model, contents=prompt)
        return response.text or ""

    return call_with_model_and_key_rotation(_make_call, GENERATION_MODELS)
