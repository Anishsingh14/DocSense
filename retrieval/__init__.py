"""Stage 5 — Retrieval & Re-ranking.

Given a user question, retrieves the most relevant chunks (with
mode-aware filtering: single-doc / multi-doc / legal) and re-ranks
for precision before handing off to Stage 6 (Answer Generation).
"""
