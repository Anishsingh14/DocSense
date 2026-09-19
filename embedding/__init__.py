"""Stage 4 — Embedding & Vector Storage.

Converts schema-conformant chunks (text and image-derived, from
Stages 2 and 3) into embeddings and stores them in a vector database
with full metadata (doc_id, doc_name, page_num, type, doc_type),
enabling mode-aware filtering in Stage 5.
"""
