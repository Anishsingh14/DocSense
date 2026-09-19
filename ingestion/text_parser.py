"""text_parser.py — Stage 1 module.

Extracts text per page from PDF, DOCX, and TXT files.

Contract (per TDR Section 4):
    Returns a list of dicts: [{"page_num": int, "text": str}, ...]

Notes:
- Page numbers are 1-indexed to match how humans reference pages
  (and to match the eval dataset's `expected_page` convention).
- DOCX has no native concept of "pages" (page breaks are a rendering
  detail, not a stored property). We treat each page-break-delimited
  section as a page, falling back to treating the whole document as
  a single page 1 if no explicit page breaks are found. This is a
  documented deviation — see the Stage 1 summary for details.
- TXT has no page concept at all; the entire file is returned as page 1.
"""

from __future__ import annotations

import os
from typing import List, TypedDict

import pymupdf  # PyMuPDF (the `fitz` alias is deprecated upstream)
from docx import Document
from docx.oxml.ns import qn


class PageText(TypedDict):
    page_num: int
    text: str


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}


class UnsupportedFileTypeError(ValueError):
    """Raised when a file extension is not supported (TDR Section 7)."""


class DocumentParsingError(ValueError):
    """Raised when a document is empty or corrupted (TDR Section 7)."""


def parse_document(file_path: str) -> List[PageText]:
    """Dispatches to the correct parser based on file extension.

    Raises:
        UnsupportedFileTypeError: if the extension isn't PDF/DOCX/TXT.
        DocumentParsingError: if the document is empty or corrupted.
    """
    ext = os.path.splitext(file_path)[1].lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileTypeError(
            f"Unsupported file type '{ext}'. Supported types for V1: "
            f"PDF, DOCX, TXT."
        )

    if ext == ".pdf":
        pages = _parse_pdf(file_path)
    elif ext == ".docx":
        pages = _parse_docx(file_path)
    else:  # .txt
        pages = _parse_txt(file_path)

    if not pages:
        raise DocumentParsingError(
            f"No content could be extracted from '{file_path}'. "
            f"The file may be empty or corrupted."
        )

    return pages


def _parse_pdf(file_path: str) -> List[PageText]:
    """Extracts text per page from a PDF using PyMuPDF.

    Pages with near-empty text (< 20 non-whitespace chars) are still
    included here with whatever text was found — the OCR fallback
    decision is made by the pipeline layer (ocr_fallback.py), not here.
    """
    try:
        doc = pymupdf.open(file_path)
    except Exception as exc:
        raise DocumentParsingError(
            f"Failed to open PDF '{file_path}': {exc}"
        ) from exc

    pages: List[PageText] = []
    try:
        for i, page in enumerate(doc):
            text = page.get_text("text") or ""
            pages.append({"page_num": i + 1, "text": text.strip()})
    finally:
        doc.close()

    return pages


def _parse_docx(file_path: str) -> List[PageText]:
    """Extracts text per page from a DOCX file.

    DOCX does not store page numbers — pagination is computed at
    render time by the consuming application (e.g., Word), not stored
    in the XML. We approximate pages by splitting on explicit manual
    page-break runs (<w:br w:type="page"/>) and section breaks.

    If no page breaks are found, the entire document is returned as
    a single page (page_num=1). This is the documented deviation
    referenced in the Stage 1 summary.
    """
    try:
        doc = Document(file_path)
    except Exception as exc:
        raise DocumentParsingError(
            f"Failed to open DOCX '{file_path}': {exc}"
        ) from exc

    pages: List[PageText] = []
    current_page_num = 1
    current_lines: List[str] = []

    def _paragraph_has_page_break(paragraph) -> bool:
        for run in paragraph.runs:
            brs = run._element.findall(qn("w:br"))
            for br in brs:
                if br.get(qn("w:type")) == "page":
                    return True
        return False

    for paragraph in doc.paragraphs:
        if _paragraph_has_page_break(paragraph):
            pages.append({
                "page_num": current_page_num,
                "text": "\n".join(current_lines).strip(),
            })
            current_page_num += 1
            current_lines = []
            # Text in the same paragraph as the break still belongs
            # to the new page.
            if paragraph.text.strip():
                current_lines.append(paragraph.text)
            continue

        if paragraph.text.strip():
            current_lines.append(paragraph.text)

    # Flush the final (or only) page.
    pages.append({
        "page_num": current_page_num,
        "text": "\n".join(current_lines).strip(),
    })

    # Also pull table text (python-docx does not include tables in
    # doc.paragraphs) and append it to the last page, since tables are
    # not reliably attributable to a specific page without a break.
    table_lines = []
    for table in doc.tables:
        for row in table.rows:
            row_text = " | ".join(cell.text.strip() for cell in row.cells)
            if row_text.strip(" |"):
                table_lines.append(row_text)
    if table_lines:
        pages[-1]["text"] = (pages[-1]["text"] + "\n" + "\n".join(table_lines)).strip()

    return pages


def _parse_txt(file_path: str) -> List[PageText]:
    """Reads a TXT file as a single page (page_num=1)."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    except Exception as exc:
        raise DocumentParsingError(
            f"Failed to read TXT '{file_path}': {exc}"
        ) from exc

    return [{"page_num": 1, "text": text.strip()}]
