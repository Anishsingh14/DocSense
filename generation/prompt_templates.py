"""prompt_templates.py — Stage 6 module.

Holds the mode-specific (single_doc/multi_doc/legal) and style-specific
(full/summary) prompt templates described in TDR Section 5 and PRD
Section 9.

Each retrieved chunk is labeled as [Source N | ...] in the assembled
context, where N is the chunk's position in the (already reranked)
list — this label is the ONLY thing the LLM is asked to cite by. The
actual page_num/doc_name/section for each Source N come from the
chunk's own metadata (known to us already, from Stage 5), not from
anything the LLM has to remember or infer. answer_with_citations.py
maps the LLM's "[Source N]" references back to real metadata after
generation — see that module for why this matters (TDR Section 6:
"never trust the LLM's own page-number memory").

FIXED BUG (found via manual Stage 6 legal-mode test run — see
answer_with_citations.py's "FIXED BUGS" #3): the legal and multi_doc
mode instructions told the model to separately "cite the page and
section number" / "cite the source document and page number" for
every point, while the citation instructions elsewhere said to cite
using only the "(Source N)" label. Those two instructions conflicted
in legal mode specifically, and the model resolved the conflict by
inventing a hybrid format ("From **Source 1** (Page 4, Section 9
INDEMNITY):") that the citation parser did not recognize. Fixed by
making every mode instruction point back at the Source label instead
of asking the model to restate page/section/document itself — that
metadata is already attached to the label and looked up from the
real chunk data after generation, so the model was never being asked
to know it accurately in the first place.
"""

from __future__ import annotations

from typing import List, Literal

Mode = Literal["single_doc", "multi_doc", "legal"]
AnswerStyle = Literal["full", "summary"]

# Appended to every prompt regardless of mode, to enforce PRD Section
# 7's "no hallucinated citations" / "never force an answer" rules
# directly in the generation instructions (in addition to the
# code-level cross-check in answer_with_citations.py — belt and
# suspenders, since an instructed-but-unenforced rule is not a
# guarantee).
_CITATION_INSTRUCTIONS = (
    "Cite sources using the exact label shown, e.g. \"(Source 1)\", "
    "immediately after the text it supports. The Source label alone "
    "is always sufficient — do not also restate the page or section "
    "number yourself next to it, even if asked to reference the page "
    "or section elsewhere in these instructions; that information is "
    "already tied to the Source label and will be looked up "
    "separately. Do not invent a page number or section, and do not "
    "reference anything other than the Source labels given above. If "
    "the sources above do not contain the answer, say so explicitly: "
    "do not guess or make up an answer."
)

_STYLE_INSTRUCTIONS = {
    "full": (
        "Answer style: FULL. Quote the relevant text precisely and "
        "completely — do not paraphrase or shorten it."
    ),
    "summary": (
        "Answer style: SUMMARY. Synthesize the relevant information "
        "into a concise summary in your own words, while still citing "
        "every source you draw from."
    ),
}


def build_prompt(
    question: str,
    chunks: List[dict],
    mode: Mode,
    answer_style: AnswerStyle,
) -> str:
    """Builds the full prompt for a given mode and answer style.

    Args:
        question: the user's natural-language question.
        chunks: reranked chunks from retrieval.reranker.rerank(), in
            final order (Source 1 = chunks[0], Source 2 = chunks[1], ...).
        mode: "single_doc", "multi_doc", or "legal".
        answer_style: "full" or "summary".

    Returns:
        The complete prompt string to send to the LLM.
    """
    context = _build_context_block(chunks, mode)
    instructions = _MODE_INSTRUCTIONS[mode]
    style = _STYLE_INSTRUCTIONS[answer_style]

    return (
        f"{instructions}\n\n"
        f"Context:\n{context}\n\n"
        f"{style}\n"
        f"{_CITATION_INSTRUCTIONS}\n\n"
        f"Question: {question}"
    )


def _build_context_block(chunks: List[dict], mode: Mode) -> str:
    """Formats retrieved chunks into labeled [Source N | ...] blocks.

    Per TDR Section 5's three reference templates:
      - single_doc: "[Source N | Page X]"
      - multi_doc: "[Source N | doc_name | Page X]" (doc name shown
        since multiple documents are in play)
      - legal: "[Source N | Page X | Section Y]" (section shown when
        available, since legal mode's whole point is clause precision)
    """
    lines = []
    for i, chunk in enumerate(chunks, start=1):
        page = chunk["page_num"]
        section = chunk.get("section")

        if mode == "multi_doc":
            label = f"[Source {i} | {chunk['doc_name']} | Page {page}]"
        elif mode == "legal" and section:
            label = f"[Source {i} | Page {page} | Section {section}]"
        else:
            label = f"[Source {i} | Page {page}]"

        # Image-derived chunks get an extra tag so the LLM knows this
        # text is a description of a visual element, not prose from
        # the document body (helps it phrase the answer appropriately,
        # e.g. "the chart shows..." rather than quoting it as text).
        if chunk["type"] == "image":
            image_type = chunk.get("image_type") or "image"
            label = label[:-1] + f" | {image_type.capitalize()}]"

        lines.append(f'{label}: "{chunk["text"]}"')

    return "\n".join(lines)


_MODE_INSTRUCTIONS = {
    "single_doc": (
        "Answer the question using only the sources above, from a "
        "single document."
    ),
    "multi_doc": (
        "The sources above come from multiple documents. Compare them "
        "and note where they agree and where they differ. Cite the "
        "Source label for every point (see citation instructions "
        "below) — the source document and page are already attached "
        "to that label."
    ),
    "legal": (
        "You are in legal/clause precision mode. Quote the exact "
        "relevant clause verbatim — do not paraphrase legal language. "
        "Cite the Source label for every quote (see citation "
        "instructions below) — the page and section are already "
        "attached to that label, so you do not need to state them "
        "yourself."
    ),
}
