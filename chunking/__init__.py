"""Stage 2 — Chunking.

Splits Stage 1's per-page text output into retrievable chunks that
conform to the TDR Section 3 chunk schema. Chunking strategy is
selected per `doc_type`: legal documents use clause-aware splitting
(legal_chunker.py); everything else uses structure-aware splitting
(text_chunker.py).
"""
