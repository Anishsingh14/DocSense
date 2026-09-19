"""Manual test script for Stage 1 — Ingestion & Parsing.

Run from the project root:
    python -m ingestion.test_stage1_manual

Or target a single file:
    python -m ingestion.test_stage1_manual data/sample_docs/SampleServices_MSA_Contract.pdf

Prints a summary of what was extracted per document: doc_id, file
hash, page count, per-page text preview + low-confidence flags, and
any extracted images.
"""

from __future__ import annotations

import os
import sys

from ingestion.pipeline import ingest_document

SAMPLE_DOCS_DIR = os.path.join("data", "sample_docs")


def summarize(file_path: str) -> None:
    print("=" * 80)
    print(f"FILE: {file_path}")
    try:
        result = ingest_document(file_path)
    except Exception as exc:
        print(f"  ERROR: {type(exc).__name__}: {exc}")
        return

    print(f"  doc_id: {result['doc_id']}")
    print(f"  doc_name: {result['doc_name']}")
    print(f"  file_hash: {result['file_hash'][:16]}...")
    print(f"  pages: {len(result['pages'])}")

    for page in result["pages"]:
        preview = page["text"][:100].replace("\n", " ")
        flag = " [LOW TEXT CONFIDENCE]" if page["low_text_confidence"] else ""
        print(f"    - page {page['page_num']}: \"{preview}\"{flag}")

    print(f"  images extracted: {len(result['images'])}")
    for img in result["images"]:
        print(
            f"    - page {img['page_num']}: {img['image_path']} "
            f"({img['width']}x{img['height']}, hash={img['image_hash'][:8]}...)"
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
        summarize(file_path)

    print("=" * 80)
    print(f"Done. Processed {len(targets)} document(s).")


if __name__ == "__main__":
    main()
