"""Manual test script for Stage 2 — Chunking.

Run from the project root:
    python -m chunking.test_stage2_manual

Or target a single file:
    python -m chunking.test_stage2_manual data/sample_docs/SampleServices_MSA_Contract.pdf

For each document: runs Stage 1 ingestion, then Stage 2 chunking, and
prints the detected doc_type, chunk count, and a preview of each
chunk (chunk_id, page_num, section, text preview) so you can verify
chunk boundaries and section labels look right.
"""

from __future__ import annotations

import os
import sys

from chunking.pipeline import chunk_ingested_document
from ingestion.pipeline import ingest_document

SAMPLE_DOCS_DIR = os.path.join("data", "sample_docs")


def summarize(file_path: str) -> None:
    print("=" * 80)
    print(f"FILE: {file_path}")
    try:
        ingested = ingest_document(file_path)
        chunks = chunk_ingested_document(ingested)
    except Exception as exc:
        print(f"  ERROR: {type(exc).__name__}: {exc}")
        return

    doc_type = chunks[0]["doc_type"] if chunks else "N/A (no chunks)"
    print(f"  doc_id: {ingested['doc_id']}")
    print(f"  doc_type detected: {doc_type}")
    print(f"  total chunks: {len(chunks)}")

    for chunk in chunks:
        preview = chunk["text"][:90].replace("\n", " ")
        section = chunk["section"] or "-"
        print(
            f"    - {chunk['chunk_id']} | page {chunk['page_num']} | "
            f"section: {section} | \"{preview}\""
        )

    # Schema conformance check (TDR Section 3).
    required_keys = {
        "chunk_id", "doc_id", "doc_name", "doc_type", "page_num",
        "section", "type", "image_type", "text", "source_image_path",
    }
    for chunk in chunks:
        missing = required_keys - chunk.keys()
        if missing:
            print(f"  SCHEMA ERROR in {chunk.get('chunk_id')}: missing {missing}")


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
