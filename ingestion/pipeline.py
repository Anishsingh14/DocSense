"""pipeline.py — Stage 1 orchestrator.

Combines text_parser.py, image_extractor.py, and ocr_fallback.py into
a single per-document ingestion result.

This module defines the Stage 1 OUTPUT CONTRACT. It is intentionally
NOT the final chunk schema from TDR Section 3 — that schema applies to
retrievable chunks, which are only produced starting in Stage 2
(text chunks) and Stage 3 (image-derived chunks). Stage 1's job is
purely extraction: raw per-page text + raw extracted images, with
enough metadata for Stage 2/3 to build schema-conformant chunks from.

Output contract (IngestedDocument):
{
  "doc_id": "Acme_Corp_Annual_Report",         # filename stem, used
                                                 # consistently across
                                                 # all stages
  "doc_name": "Acme_Corp_Annual_Report.pdf",   # original filename
  "file_hash": "<sha256 of file bytes>",       # for idempotency
                                                 # (TDR Section 6)
  "pages": [
    {
      "page_num": 1,
      "text": "...",
      "low_text_confidence": false             # true only if OCR
                                                 # fallback ran and
                                                 # was low-confidence
    },
    ...
  ],
  "images": [
    {
      "page_num": 3,
      "image_path": "data/processed/images/Acme_..._p3_img0.png",
      "width": 640,
      "height": 480,
      "image_hash": "<md5 of image bytes>"
    },
    ...
  ]
}
"""

from __future__ import annotations

import hashlib
import os
from typing import List, TypedDict

from ingestion.image_extractor import ExtractedImage, extract_images
from ingestion.ocr_fallback import needs_ocr, ocr_page
from ingestion.text_parser import PageText, parse_document

DEFAULT_IMAGE_OUTPUT_DIR = os.path.join("data", "processed", "images")


class IngestedPage(TypedDict):
    page_num: int
    text: str
    low_text_confidence: bool


class IngestedDocument(TypedDict):
    doc_id: str
    doc_name: str
    file_hash: str
    pages: List[IngestedPage]
    images: List[ExtractedImage]


def compute_file_hash(file_path: str) -> str:
    """Computes a SHA-256 hash of the file's bytes (TDR Section 6:
    idempotent processing — re-uploading the same document should not
    reprocess/re-embed it).
    """
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_doc_id(file_path: str) -> str:
    """Derives doc_id from the filename stem (no extension).

    This matches the convention already used in
    data/eval/cuad_sample_eval.json, e.g.
    'CUAD_XLITECHNOLOGIES_INC_12_02_2015-EX-10_02-STRATEGIC_ALLIANCE_A'.
    """
    return os.path.splitext(os.path.basename(file_path))[0]


def ingest_document(
    file_path: str,
    image_output_dir: str = DEFAULT_IMAGE_OUTPUT_DIR,
) -> IngestedDocument:
    """Runs the full Stage 1 pipeline on a single document.

    Steps:
      1. Parse text per page (text_parser.py).
      2. For any page with near-empty text, run OCR fallback and
         replace/flag that page's text (ocr_fallback.py). Only
         applies to PDFs — DOCX/TXT already reflect the document's
         actual native text.
      3. Extract embedded images per page, filtered by size
         (image_extractor.py). Only applies to PDFs.

    Raises:
        UnsupportedFileTypeError, DocumentParsingError — propagated
        from text_parser.py (see TDR Section 7 error table).
    """
    doc_id = compute_doc_id(file_path)
    doc_name = os.path.basename(file_path)
    file_hash = compute_file_hash(file_path)
    ext = os.path.splitext(file_path)[1].lower()

    raw_pages: List[PageText] = parse_document(file_path)

    ingested_pages: List[IngestedPage] = []
    for page in raw_pages:
        page_num = page["page_num"]
        text = page["text"]
        low_confidence = False

        if ext == ".pdf" and needs_ocr(text):
            ocr_result = ocr_page(file_path, page_num)
            if len(ocr_result["text"]) > len(text):
                text = ocr_result["text"]
            low_confidence = ocr_result["low_text_confidence"]

        ingested_pages.append({
            "page_num": page_num,
            "text": text,
            "low_text_confidence": low_confidence,
        })

    doc_image_dir = os.path.join(image_output_dir, doc_id)
    images: List[ExtractedImage] = extract_images(file_path, doc_image_dir)

    return {
        "doc_id": doc_id,
        "doc_name": doc_name,
        "file_hash": file_hash,
        "pages": ingested_pages,
        "images": images,
    }
