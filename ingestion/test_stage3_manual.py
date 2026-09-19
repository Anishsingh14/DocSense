"""Manual test script for Stage 3 — Image Analysis.

Run from the project root:
    python -m ingestion.test_stage3_manual

Or target a single file:
    python -m ingestion.test_stage3_manual data/sample_docs/Acme_Corp_Annual_Report.pdf

Requires GEMINI_API_KEY to be set in a .env file in the project root
(see env.example) — this script makes real API calls.

For each document: runs Stage 1 ingestion, then Stage 3 image
analysis, and prints the resulting image chunks (page_num, image_type,
description, source_image_path) plus a schema-conformance check.
Documents with no extracted images are skipped with a note.
"""

from __future__ import annotations

import os
import sys

from ingestion.image_pipeline import analyze_ingested_document_images
from ingestion.pipeline import ingest_document

SAMPLE_DOCS_DIR = os.path.join("data", "sample_docs")

REQUIRED_KEYS = {
    "chunk_id", "doc_id", "doc_name", "doc_type", "page_num",
    "section", "type", "image_type", "text", "source_image_path",
}


def summarize(file_path: str) -> None:
    print("=" * 80)
    print(f"FILE: {file_path}")
    try:
        ingested = ingest_document(file_path)
    except Exception as exc:
        print(f"  ERROR during ingestion: {type(exc).__name__}: {exc}")
        return

    if not ingested["images"]:
        print("  No embedded images found — skipping (nothing to analyze).")
        return

    print(f"  images extracted: {len(ingested['images'])}")

    try:
        image_chunks = analyze_ingested_document_images(ingested)
    except Exception as exc:
        print(f"  ERROR during vision analysis: {type(exc).__name__}: {exc}")
        return

    print(f"  image chunks produced: {len(image_chunks)}")
    for chunk in image_chunks:
        missing = REQUIRED_KEYS - chunk.keys()
        if missing:
            print(f"  SCHEMA ERROR in {chunk.get('chunk_id')}: missing {missing}")

        print(
            f"    - {chunk['chunk_id']} | page {chunk['page_num']} | "
            f"image_type: {chunk['image_type']} | source: {chunk['source_image_path']}"
        )
        print(f"      description: \"{chunk['text']}\"")


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
        summarize(file_path)

    print("=" * 80)
    print(f"Done. Processed {len(targets)} document(s).")


if __name__ == "__main__":
    main()
