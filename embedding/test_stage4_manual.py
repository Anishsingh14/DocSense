"""Manual test script for Stage 4 — Embedding & Vector Storage.

Run from the project root:
    python -m embedding.test_stage4_manual

Or target a single file:
    python -m embedding.test_stage4_manual data/sample_docs/SampleServices_MSA_Contract.pdf

For each document: runs Stages 1-3 (ingestion, chunking, image
analysis), then Stage 4 (embed + store in Qdrant), and reports how
many chunks were embedded and stored, plus a verification count
pulled back from Qdrant by doc_id filter.

NOTE: if GEMINI_API_KEY is not set (or the Gemini API call fails for
any reason), embed_chunks.py automatically falls back to a local
BGE model — this script will still run and report results either way,
just flagging which embedding path was used per embed_chunks.py's
own printed warnings.
"""

from __future__ import annotations

import os
import sys

from chunking.pipeline import chunk_ingested_document
from embedding.pipeline import embed_and_store_chunks
from embedding.vector_store import count_points
from ingestion.image_pipeline import analyze_ingested_document_images
from ingestion.pipeline import ingest_document

SAMPLE_DOCS_DIR = os.path.join("data", "sample_docs")


def process(file_path: str) -> None:
    print("=" * 80)
    print(f"FILE: {file_path}")
    try:
        ingested = ingest_document(file_path)
        text_chunks = chunk_ingested_document(ingested)
        image_chunks = analyze_ingested_document_images(ingested)
        all_chunks = text_chunks + image_chunks
    except Exception as exc:
        print(f"  ERROR during ingestion/chunking: {type(exc).__name__}: {exc}")
        return

    print(f"  doc_id: {ingested['doc_id']}")
    print(f"  text chunks: {len(text_chunks)} | image chunks: {len(image_chunks)}")

    try:
        upserted = embed_and_store_chunks(all_chunks)
    except Exception as exc:
        print(f"  ERROR during embedding/storage: {type(exc).__name__}: {exc}")
        return

    stored_count = count_points(doc_id=ingested["doc_id"])
    print(f"  chunks upserted this run: {upserted}")
    print(f"  chunks now in Qdrant for this doc_id: {stored_count}")

    if stored_count != len(all_chunks):
        print(
            f"  NOTE: stored count ({stored_count}) != total chunks produced "
            f"({len(all_chunks)}) — expected if re-running on an already-"
            f"processed doc (idempotent upsert overwrites, doesn't duplicate)."
        )


def main() -> None:
    if len(sys.argv) > 1:
        targets = sys.argv[1:]
    else:
        if not os.path.isdir(SAMPLE_DOCS_DIR):
            print(f"No sample docs directory found at {SAMPLE_DOCS_DIR}")
            return
        targets = [
            os.path.join(SAMPLE_DOCS_DIR, name)
            for name in sorted(os.listdir(SAMPLE_DOCS_DIR))
            if os.path.splitext(name)[1].lower() in {".pdf", ".docx", ".txt"}
        ]

    if not targets:
        print("No documents found to test.")
        return

    for file_path in targets:
        process(file_path)

    total_in_store = count_points()
    print("=" * 80)
    print(f"Done. Processed {len(targets)} document(s).")
    print(f"Total points currently in the vector store (all docs): {total_in_store}")


if __name__ == "__main__":
    main()
