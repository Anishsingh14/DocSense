"""embed_chunks.py — Stage 4 module.

Batches all chunks (text + image-derived, both share the same schema
per TDR Section 3) through an embedding model, attaching a numeric
vector to each chunk.

DEVIATION FROM TDR (see TDR.md Section 2a): TDR originally specified
`voyage-3` (Voyage AI) with a local BGE fallback. Per the user's
documented provider substitution, this module uses Google Gemini's
embedding API (`gemini-embedding-001`) instead, consistent with
Stages 3 and 6 also using Gemini. `gemini-embedding-001` was chosen
over the newer `gemini-embedding-2` because it supports per-call
`task_type` (RETRIEVAL_DOCUMENT vs RETRIEVAL_QUERY) — the asymmetric
embedding setup recommended for retrieval — and because our inputs
are always text by the time they reach this module (Stage 3 already
converts images to text descriptions), so gemini-embedding-2's
native multimodal (raw image/video) input support isn't needed here.

A local, free fallback (`sentence-transformers` / BGE) remains
available and is used automatically if the Gemini API is unavailable
(e.g., missing API key, network/quota error) — this keeps the module
usable without any API key for local testing, consistent with TDR's
original intent for the fallback.

NOTE — UNEXERCISED PATH: as of the Stage 4 build/test pass, the
Gemini API was available throughout, so `_embed_with_local_model`
(the fallback branch below) has NOT been exercised against the real
sample documents. It's implemented and importable, but not yet
verified end-to-end. If Gemini's API key/quota becomes unavailable,
this is the first place to check and test before trusting its output.
"""

from __future__ import annotations

import os
from typing import List, Literal, Optional, TypedDict

from dotenv import load_dotenv

load_dotenv()

GEMINI_EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")

# Local fallback model — small, fast, well-regarded for retrieval.
# Matches the TDR-specified fallback family (BGE).
LOCAL_FALLBACK_MODEL = "BAAI/bge-small-en-v1.5"

# gemini-embedding-001 defaults to 3072 dimensions; truncating to 768
# is explicitly recommended by Google as retaining most of the
# quality while reducing storage — see Section 3 of TDR for chunk
# volume expectations (V1 caps documents at 50 pages).
EMBEDDING_OUTPUT_DIMENSIONALITY = 768

TaskType = Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"]


class EmbeddedChunk(TypedDict):
    chunk_id: str
    doc_id: str
    doc_name: str
    doc_type: str
    page_num: int
    section: Optional[str]
    type: str
    image_type: Optional[str]
    text: str
    source_image_path: Optional[str]
    embedding: List[float]


_local_model_cache = {}


def embed_chunks(chunks: List[dict]) -> List[EmbeddedChunk]:
    """Embeds a list of schema-conformant chunks for document storage.

    Uses RETRIEVAL_DOCUMENT task type (chunks are the documents being
    indexed, not the queries searching them — see embed_query below
    for the query-side counterpart used at retrieval time in Stage 5).

    Args:
        chunks: list of chunk dicts conforming to TDR Section 3
            schema (as produced by chunking.pipeline / Stage 3).

    Returns:
        The same chunks, each with an added "embedding" field
        (list of floats).
    """
    if not chunks:
        return []

    texts = [chunk["text"] for chunk in chunks]
    vectors = _embed_texts(texts, task_type="RETRIEVAL_DOCUMENT")

    embedded: List[EmbeddedChunk] = []
    for chunk, vector in zip(chunks, vectors):
        embedded_chunk = dict(chunk)
        embedded_chunk["embedding"] = vector
        embedded.append(embedded_chunk)  # type: ignore[arg-type]

    return embedded


def embed_query(query_text: str) -> List[float]:
    """Embeds a single user query for retrieval (Stage 5).

    Uses RETRIEVAL_QUERY task type, which per Gemini's docs optimizes
    the embedding differently than RETRIEVAL_DOCUMENT — queries and
    documents must use matching task types on each side for the
    asymmetric retrieval setup to work as intended.
    """
    vectors = _embed_texts([query_text], task_type="RETRIEVAL_QUERY")
    return vectors[0]


def _embed_texts(texts: List[str], task_type: TaskType) -> List[List[float]]:
    """Embeds a batch of texts, trying Gemini (rotating across all
    configured keys — TDR Section 2d) first, then falling back to a
    local model only if every configured key is exhausted/unavailable
    (missing key entirely, network error, or all keys 429'd).
    """
    try:
        return _embed_with_gemini(texts, task_type)
    except Exception as exc:
        print(
            f"WARNING: Gemini embedding call failed on all configured "
            f"keys ({type(exc).__name__}: {exc}). Falling back to local "
            f"embedding model ({LOCAL_FALLBACK_MODEL})."
        )
        return _embed_with_local_model(texts)


def _embed_with_gemini(texts: List[str], task_type: TaskType) -> List[List[float]]:
    from google import genai
    from google.genai import types as genai_types

    from generation.gemini_key_rotation import call_with_key_rotation

    def _make_call(api_key: str) -> List[List[float]]:
        client = genai.Client(api_key=api_key)
        result = client.models.embed_content(
            model=GEMINI_EMBEDDING_MODEL,
            contents=texts,
            config=genai_types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=EMBEDDING_OUTPUT_DIMENSIONALITY,
            ),
        )
        # gemini-embedding-001 returns one embedding per input string
        # (unlike gemini-embedding-2, which aggregates multi-part
        # input — see this module's docstring for why -001 was chosen).
        return [list(e.values) for e in result.embeddings]

    return call_with_key_rotation(_make_call)


def _embed_with_local_model(texts: List[str]) -> List[List[float]]:
    # UNEXERCISED PATH — see module docstring. Not yet run against
    # real sample documents; only exercised via Gemini so far.
    if "model" not in _local_model_cache:
        from sentence_transformers import SentenceTransformer

        _local_model_cache["model"] = SentenceTransformer(LOCAL_FALLBACK_MODEL)

    model = _local_model_cache["model"]
    vectors = model.encode(texts, normalize_embeddings=True)
    return [vector.tolist() for vector in vectors]
