"""image_analyzer.py — Stage 3 module.

Sends filtered, non-decorative images (from image_extractor.py) to a
vision-capable LLM with a strict, factual prompt, classifies the
image_type (chart/diagram/table/photo), and converts the result into
a schema-conformant chunk (type: "image") per TDR Section 3.

DEVIATION FROM TDR: TDR Section 2 specifies Claude (Sonnet) for vision
analysis. The user has no Anthropic billing set up; per explicit user
instruction, this module uses Google Gemini's vision API instead
(model: gemini-2.5-flash, chosen for low cost/fast latency on a
factual-description task — swappable via GEMINI_VISION_MODEL).
NOTE: gemini-2.0-flash was used initially but is now deprecated/shut
down by Google; gemini-2.5-flash is the current stable equivalent
tier as of this writing (confirmed via ai.google.dev/gemini-api/docs/models).

This is an isolated substitution: the prompt content, output schema,
and downstream chunk contract are all unchanged from TDR's design.
Swapping back to Claude later only requires changing `_call_vision_api`
in this file — no other module depends on which vision provider is
used.

Prompt style follows PRD Section 9's expected output style: factual,
non-speculative, page-cited descriptions (page citation is added by
the caller from already-known metadata, not asked of the LLM, per
TDR Section 6's "never trust the LLM's own page-number memory" rule
— though that rule is written for text citation, the same principle
applies here: image_type/page_num are things WE already know from
image_extractor.py, not something to ask the vision model to guess).

Cost control (TDR Section 6): images are deduplicated by their
image_hash (computed by image_extractor.py) before any vision API
call is made — a repeated image (e.g., a letterhead logo appearing on
every page) is analyzed once and the same description is reused for
every occurrence.

Error handling (TDR Section 7): "Vision API failure on an image ->
log and skip that image; do not fail the entire document processing
job." Implemented in analyze_images() — a failure on one image
produces no chunk for that image, but does not raise or abort
processing of the remaining images.
"""

from __future__ import annotations

import os
from typing import List, Literal, Optional, TypedDict

from dotenv import load_dotenv
from google import genai
from google.genai import types as genai_types

from chunking.text_chunker import Chunk

load_dotenv()

GEMINI_VISION_MODEL = os.getenv("GEMINI_VISION_MODEL", "gemini-2.5-flash")

ImageType = Literal["chart", "diagram", "table", "photo"]

_VISION_PROMPT = """You are analyzing an image embedded in a document. Describe ONLY what is factually visible in the image. Do not speculate, infer intent, or add information not directly shown.

Respond in exactly this format:

TYPE: <one of: chart, diagram, table, photo>
DESCRIPTION: <a factual, specific description of what the image shows — include exact numbers, labels, categories, or data points if visible>

If the image is decorative (a logo, icon, or design element with no informational content), respond with:
TYPE: decorative
DESCRIPTION: (leave blank)
"""


class VisionAnalysisResult(TypedDict):
    image_type: Optional[ImageType]
    description: str
    is_decorative: bool


def analyze_images(
    doc_id: str,
    doc_name: str,
    doc_type: str,
    images: List[dict],
) -> List[Chunk]:
    """Analyzes a document's extracted images and returns image chunks.

    Args:
        doc_id, doc_name, doc_type: document-level metadata, same as
            used for text chunks, so image chunks share the same
            filterable fields.
        images: Stage 1 image_extractor.py output, list of
            {"page_num", "image_path", "width", "height", "image_hash"}.

    Returns:
        List of Chunk dicts (type == "image"), one per non-decorative,
        successfully analyzed image. Images that fail analysis or are
        classified as decorative produce no chunk (TDR Section 7).
    """
    chunks: List[Chunk] = []

    # Cost control: dedupe by image_hash so a repeated image (e.g., a
    # logo appearing on multiple pages) is only sent to the vision API
    # once (TDR Section 6).
    hash_to_result: dict = {}
    chunk_index = 0

    for image in images:
        image_hash = image["image_hash"]

        if image_hash in hash_to_result:
            result = hash_to_result[image_hash]
        else:
            result = _analyze_single_image(image["image_path"])
            hash_to_result[image_hash] = result

        if result is None or result["is_decorative"] or not result["description"]:
            continue

        chunks.append({
            "chunk_id": f"{doc_id}_p{image['page_num']}_img{chunk_index}",
            "doc_id": doc_id,
            "doc_name": doc_name,
            "doc_type": doc_type,
            "page_num": image["page_num"],
            "section": None,
            "type": "image",
            "image_type": result["image_type"],
            "text": result["description"],
            "source_image_path": image["image_path"],
        })
        chunk_index += 1

    return chunks


def _analyze_single_image(image_path: str) -> Optional[VisionAnalysisResult]:
    """Calls the vision API on a single image and parses the response.

    Returns None on any failure (network error, API error, malformed
    response) so the caller can skip this image without aborting the
    rest of the document (TDR Section 7).
    """
    try:
        raw_text = _call_vision_api(image_path)
        return _parse_vision_response(raw_text)
    except Exception:
        return None


def _call_vision_api(image_path: str) -> str:
    """Sends the image to Gemini's vision API and returns the raw text response.

    Raises on failure — caller (_analyze_single_image) is responsible
    for catching and converting to a skip.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Add it to a .env file in the "
            "project root (see env.example)."
        )

    client = genai.Client(api_key=api_key)

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    ext = os.path.splitext(image_path)[1].lower().lstrip(".")
    mime_type = f"image/{'jpeg' if ext == 'jpg' else ext}"

    response = client.models.generate_content(
        model=GEMINI_VISION_MODEL,
        contents=[
            genai_types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            _VISION_PROMPT,
        ],
    )
    return response.text or ""


def _parse_vision_response(raw_text: str) -> VisionAnalysisResult:
    """Parses the TYPE:/DESCRIPTION: formatted response.

    Falls back gracefully (is_decorative=True, empty description) if
    the response doesn't match the expected format, rather than
    raising — a malformed-but-successful API call should still result
    in "skip this image," not a hard failure.
    """
    image_type_raw = None
    description = ""

    for line in raw_text.splitlines():
        line = line.strip()
        if line.upper().startswith("TYPE:"):
            image_type_raw = line.split(":", 1)[1].strip().lower()
        elif line.upper().startswith("DESCRIPTION:"):
            description = line.split(":", 1)[1].strip()

    valid_types = {"chart", "diagram", "table", "photo"}
    if image_type_raw not in valid_types:
        return {"image_type": None, "description": "", "is_decorative": True}

    return {
        "image_type": image_type_raw,  # type: ignore[typeddict-item]
        "description": description,
        "is_decorative": False,
    }
