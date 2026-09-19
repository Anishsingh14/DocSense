"""pipeline.py — Stage 2 orchestrator.

Takes a Stage 1 IngestedDocument (from ingestion/pipeline.py) and
produces a list of schema-conformant text chunks (TDR Section 3),
by:
  1. Classifying doc_type (doc_type_classifier.py)
  2. Routing to legal_chunker.py if doc_type == "legal",
     otherwise text_chunker.py

Image-derived chunks are NOT produced here — that's Stage 3's job
(ingestion/image_analyzer.py), which will use the same schema but
type == "image".
"""

from __future__ import annotations

from typing import List

from chunking.doc_type_classifier import classify_doc_type
from chunking.legal_chunker import chunk_legal_document
from chunking.text_chunker import Chunk, chunk_document


def chunk_ingested_document(ingested_doc: dict) -> List[Chunk]:
    """Chunks a Stage 1 IngestedDocument into schema-conformant chunks.

    Args:
        ingested_doc: the dict returned by
            ingestion.pipeline.ingest_document(), i.e.
            {"doc_id", "doc_name", "file_hash", "pages", "images"}.

    Returns:
        List of Chunk dicts (text chunks only; see module docstring).
    """
    doc_id = ingested_doc["doc_id"]
    doc_name = ingested_doc["doc_name"]
    pages = ingested_doc["pages"]

    doc_type = classify_doc_type(doc_id, doc_name, pages)

    if doc_type == "legal":
        return chunk_legal_document(doc_id, doc_name, doc_type, pages)

    return chunk_document(doc_id, doc_name, doc_type, pages)
