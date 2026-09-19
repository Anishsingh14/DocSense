"""ocr_fallback.py — Stage 1 module.

Runs Tesseract OCR on pages where text_parser.py returned near-empty
text (i.e., likely scanned/image-only pages).

Contract (per TDR Section 4):
    Given a PDF path and a page number, renders that page to an image
    and runs OCR, returning the extracted text plus a confidence flag.

Notes on TDR Section 7 ("Scanned PDF with poor OCR quality"):
    The caller (pipeline.py) is responsible for tagging the resulting
    page with `low_text_confidence: true` in metadata when OCR
    confidence is low, per the error-handling table. This module
    exposes the raw Tesseract confidence score so the caller can make
    that decision.
"""

from __future__ import annotations

from typing import TypedDict

import pytesseract
from pdf2image import convert_from_path

# A page is considered "near-empty" (needs OCR) if it has fewer than
# this many non-whitespace characters extracted by text_parser.py.
NEAR_EMPTY_CHAR_THRESHOLD = 20

# Below this average Tesseract word-confidence (0-100), the page is
# flagged as low_text_confidence per TDR Section 7.
LOW_CONFIDENCE_THRESHOLD = 60.0

# DPI used when rasterizing PDF pages for OCR. Higher DPI improves
# accuracy at the cost of speed; 300 is the common OCR sweet spot.
OCR_DPI = 300


class OcrResult(TypedDict):
    text: str
    confidence: float
    low_text_confidence: bool


def needs_ocr(page_text: str) -> bool:
    """Returns True if the given extracted text is near-empty."""
    stripped = "".join(page_text.split())
    return len(stripped) < NEAR_EMPTY_CHAR_THRESHOLD


def ocr_page(file_path: str, page_num: int) -> OcrResult:
    """Runs OCR on a single page of a PDF (1-indexed page_num).

    Returns:
        OcrResult with the OCR'd text, average confidence (0-100),
        and a low_text_confidence flag per TDR Section 7.

    On any OCR failure, returns empty text with confidence 0.0 and
    low_text_confidence=True rather than raising — a failed OCR pass
    should not crash the whole ingestion pipeline (consistent with
    the "log and skip" spirit of TDR Section 7's error table).
    """
    try:
        images = convert_from_path(
            file_path, dpi=OCR_DPI, first_page=page_num, last_page=page_num
        )
        if not images:
            return {"text": "", "confidence": 0.0, "low_text_confidence": True}

        page_image = images[0]
        ocr_data = pytesseract.image_to_data(
            page_image, output_type=pytesseract.Output.DICT
        )

        words = []
        confidences = []
        for word, conf in zip(ocr_data["text"], ocr_data["conf"]):
            if word.strip():
                words.append(word)
                conf_val = float(conf)
                if conf_val >= 0:  # Tesseract uses -1 for non-text regions
                    confidences.append(conf_val)

        text = " ".join(words).strip()
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        return {
            "text": text,
            "confidence": avg_confidence,
            "low_text_confidence": avg_confidence < LOW_CONFIDENCE_THRESHOLD,
        }
    except Exception:
        return {"text": "", "confidence": 0.0, "low_text_confidence": True}
