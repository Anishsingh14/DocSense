"""Stage 6 — Answer Generation with Mandatory Citation.

Takes Stage 5's reranked chunks, assembles them into a labeled prompt
context, calls the LLM to generate an answer, and cross-checks every
citation the LLM produces against the actual retrieved chunk metadata
— never trusting the LLM's own memory of page numbers (TDR Section 6).
"""
