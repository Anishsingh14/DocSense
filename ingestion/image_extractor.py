"""image_extractor.py — Stage 1 module.

Extracts embedded images per page from PDF files using PyMuPDF, and
filters out decorative images below a size threshold before they are
passed downstream (to Stage 3's vision analysis).

Contract (per TDR Section 4 & Section 6 "Cost control on vision calls"):
    Returns a list of dicts:
    [{"page_num": int, "image_path": str, "width": int, "height": int,
      "image_hash": str}, ...]

Notes:
- DOCX/TXT are out of scope for image extraction in V1. TDR Section 4
  only specifies PyMuPDF-based extraction (PDF). DOCX embedded images
  are not mentioned in TDR module breakdown, so we do not extract them
  here — flagged as a deviation in the Stage 1 summary.
  TODO(V2+): add DOCX embedded-image extraction (via python-docx's
  document part relationships) if a future version requires analyzing
  charts/images embedded in Word documents. Not needed for current
  V1 sample docs.
- Decorative-image filtering (TDR Section 6): images smaller than
  100x100px are dropped before being written to disk or considered
  for Stage 3 vision analysis.
- Repeated-image hashing (TDR Section 6, "likely a logo"): each saved
  image's content hash (MD5) is included in the output so a later
  stage can deduplicate repeated images across pages/documents before
  calling the vision API. Deduplication logic itself belongs to
  Stage 3 (image_analyzer.py), not here — this module only computes
  and exposes the hash.
"""

from __future__ import annotations

import hashlib
import os
from typing import List, TypedDict

import pymupdf  # PyMuPDF (the `fitz` alias is deprecated upstream)

MIN_IMAGE_DIMENSION_PX = 100


class ExtractedImage(TypedDict):
    page_num: int
    image_path: str
    width: int
    height: int
    image_hash: str


def extract_images(file_path: str, output_dir: str) -> List[ExtractedImage]:
    """Extracts embedded images from a PDF, filtering decorative ones.

    Args:
        file_path: path to the source PDF.
        output_dir: directory where extracted images are saved. Will
            be created if it doesn't exist.

    Returns:
        A list of ExtractedImage dicts, one per non-decorative image,
        in page order. Returns an empty list for non-PDF files (DOCX/
        TXT have no embedded-image extraction in V1).
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext != ".pdf":
        return []

    os.makedirs(output_dir, exist_ok=True)

    doc = pymupdf.open(file_path)
    doc_stem = os.path.splitext(os.path.basename(file_path))[0]
    results: List[ExtractedImage] = []

    try:
        for page_index, page in enumerate(doc):
            page_num = page_index + 1
            image_list = page.get_images(full=True)

            for img_seq, img_info in enumerate(image_list):
                xref = img_info[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                width = base_image.get("width", 0)
                height = base_image.get("height", 0)
                ext_out = base_image.get("ext", "png")

                # Decorative-image filter (TDR Section 6).
                if width < MIN_IMAGE_DIMENSION_PX or height < MIN_IMAGE_DIMENSION_PX:
                    continue

                image_hash = hashlib.md5(image_bytes).hexdigest()
                image_filename = f"{doc_stem}_p{page_num}_img{img_seq}.{ext_out}"
                image_path = os.path.join(output_dir, image_filename)

                with open(image_path, "wb") as f:
                    f.write(image_bytes)

                results.append({
                    "page_num": page_num,
                    "image_path": image_path,
                    "width": width,
                    "height": height,
                    "image_hash": image_hash,
                })
    finally:
        doc.close()

    return results
