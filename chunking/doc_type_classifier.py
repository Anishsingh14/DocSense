"""doc_type_classifier.py — Stage 2 support module.

Assigns a `doc_type` (legal | financial | research | general) to a
document, which determines which chunker (text_chunker.py vs
legal_chunker.py) is used and is stored on every resulting chunk per
the TDR Section 3 schema.

DEVIATION FROM TDR: neither PRD.md nor TDR.md specifies how `doc_type`
should be determined — it's referenced only as a schema field and as
a retrieval filter (TDR Section 4, Stage 5 "legal: filter
doc_type == legal"). This module fills that gap with a lightweight,
dependency-free heuristic (filename hints + keyword scoring over the
first few pages of extracted text). It intentionally does NOT call
any LLM/embedding model, to keep Stage 2 self-contained.

If classification accuracy turns out to matter more than expected
(e.g., misrouting a legal doc to the general chunker), this is the
one place to upgrade later — e.g., to an LLM-based classifier — without
touching the chunkers themselves.
"""

from __future__ import annotations

import re
from typing import Literal

DocType = Literal["legal", "financial", "research", "general"]

# Keyword sets are intentionally simple and case-insensitive. Order of
# checks below (legal -> financial -> research -> general) acts as the
# tie-break priority when a document scores for multiple types.
_LEGAL_KEYWORDS = [
    r"\bagreement\b", r"\bcontract\b", r"\bwhereas\b", r"\bindemnif",
    r"\btermination\b", r"\bgoverning law\b", r"\bconfidentiality\b",
    r"\bclause\b", r"\bcovenant", r"\bparty\b", r"\bparties\b",
    r"\bexecuted\b", r"\bhereinafter\b",
]
_FINANCIAL_KEYWORDS = [
    r"\brevenue\b", r"\bfiscal year\b", r"\bbalance sheet\b",
    r"\bincome statement\b", r"\b10-k\b", r"\bearnings\b",
    r"\bshareholders?\b", r"\bnet income\b", r"\bcash flow\b",
    r"\bannual report\b",
]
_RESEARCH_KEYWORDS = [
    r"\bmethodology\b", r"\bhypothesis\b", r"\bdataset\b",
    r"\bexperiment", r"\bfigure \d", r"\brelated work\b",
]

# Strong structural signals for academic papers: these patterns are
# far less ambiguous than general keywords (a legal contract will
# never open with "Abstract" as a standalone heading, or cite sources
# as "et al."), so they're weighted heavily to break ties against
# keyword overlap from a paper's subject matter (e.g., a RAG paper
# that discusses "contracts" and "clauses" as example use cases should
# still classify as research, not legal).
_RESEARCH_STRUCTURAL_SIGNALS = [
    r"^\s*abstract\s*$", r"^\s*references\s*$", r"^\s*conclusion\s*$",
    r"\bet al\.", r"\barxiv\b", r"^\s*\d\.\s+introduction\s*$",
]
_RESEARCH_STRUCTURAL_WEIGHT = 3

_FILENAME_HINTS = {
    "legal": [r"cuad", r"contract", r"agreement", r"msa"],
    "financial": [r"10-?k", r"annual_report", r"financial"],
    "research": [r"arxiv", r"paper", r"study"],
}

# Only score against the first N pages — enough signal, keeps this
# cheap even for the 50-page V1 document size cap.
_MAX_PAGES_TO_SCAN = 3


def classify_doc_type(doc_id: str, doc_name: str, pages: list) -> DocType:
    """Classifies a document into one of the four doc_type values.

    Args:
        doc_id: the document's doc_id (used for filename-hint matching
            alongside doc_name, since doc_id is the filename stem).
        doc_name: original filename, e.g. "Contract_A.pdf".
        pages: Stage 1 output pages, i.e. list of
            {"page_num": int, "text": str, ...}.

    Returns:
        One of "legal", "financial", "research", "general". Defaults
        to "general" when no strong signal is found.
    """
    filename_signal = f"{doc_id} {doc_name}".lower()

    for doc_type, patterns in _FILENAME_HINTS.items():
        if any(re.search(p, filename_signal) for p in patterns):
            return doc_type  # type: ignore[return-value]

    sample_text = " ".join(
        p.get("text", "") for p in pages[:_MAX_PAGES_TO_SCAN]
    ).lower()

    research_structural_score = (
        _score(sample_text, _RESEARCH_STRUCTURAL_SIGNALS) * _RESEARCH_STRUCTURAL_WEIGHT
    )

    scores = {
        "legal": _score(sample_text, _LEGAL_KEYWORDS),
        "financial": _score(sample_text, _FINANCIAL_KEYWORDS),
        "research": _score(sample_text, _RESEARCH_KEYWORDS) + research_structural_score,
    }

    best_type = max(scores, key=lambda k: (scores[k], k == "research"))
    if scores[best_type] == 0:
        return "general"

    return best_type  # type: ignore[return-value]


def _score(text: str, patterns: list) -> int:
    return sum(len(re.findall(p, text, re.MULTILINE)) for p in patterns)
