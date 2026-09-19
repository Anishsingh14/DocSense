"""image_pipeline.py — Stage 3 orchestrator.

Takes a Stage 1 IngestedDocument (from ingestion/pipeline.py) plus its
detected doc_type (from chunking/doc_type_classifier.py) and produces
schema-conformant image chunks via image_analyzer.py.

Kept separate from chunking/pipeline.py (Stage 2) since Stage 3 is a
distinct pipeline stage per TDR — a caller assembling a document's
full chunk set combines chunking.pipeline.chunk_ingested_document()
(text chunks) with this module's output (image chunks).
"""

from __future__ import annotations

from typing import List

from chunking.doc_type_classifier import classify_doc_type
from chunking.text_chunker import Chunk
from ingestion.image_analyzer import analyze_images


def analyze_ingested_document_images(ingested_doc: dict) -> List[Chunk]:
    """Analyzes a Stage 1 IngestedDocument's images into image chunks.

    Args:
        ingested_doc: the dict returned by
            ingestion.pipeline.ingest_document(), i.e.
            {"doc_id", "doc_name", "file_hash", "pages", "images"}.

    Returns:
        List of Chunk dicts (image chunks only; type == "image").
        Returns an empty list if the document has no extracted images.
    """
    if not ingested_doc["images"]:
        return []

    doc_id = ingested_doc["doc_id"]
    doc_name = ingested_doc["doc_name"]
    doc_type = classify_doc_type(doc_id, doc_name, ingested_doc["pages"])

    return analyze_images(doc_id, doc_name, doc_type, ingested_doc["images"])
