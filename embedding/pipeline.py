"""pipeline.py — Stage 4 orchestrator.

Takes schema-conformant chunks (text chunks from Stage 2, image
chunks from Stage 3) and runs them through embedding + vector storage.
"""

from __future__ import annotations

from typing import List

from embedding.embed_chunks import embed_chunks
from embedding.vector_store import upsert_chunks


def embed_and_store_chunks(chunks: List[dict]) -> int:
    """Embeds and upserts a list of schema-conformant chunks.

    Args:
        chunks: chunk dicts from chunking.pipeline.chunk_ingested_document()
            and/or ingestion.image_pipeline (Stage 3 image chunks).

    Returns:
        The number of chunks upserted into the vector store.
    """
    if not chunks:
        return 0

    embedded = embed_chunks(chunks)
    return upsert_chunks(embedded)
