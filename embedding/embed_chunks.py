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

A local, free alternative (`sentence-transformers` / BGE) remains
available, but is OPT-IN ONLY via DOCSENSE_EMBEDDING_BACKEND=local —
it is deliberately NOT used as an automatic runtime fallback. It
previously was, via a bare `except Exception`, which was unsafe: the
local model's vectors differ from Gemini's in both dimensionality
(384 vs 768) and vector space, so an automatic mid-run switch
produced vectors that either couldn't be stored/searched at all, or —
worse — could be compared arithmetically while being semantically
meaningless. See the _EMBEDDING_BACKEND constant below for the full
reasoning. If Gemini embeddings are unavailable, this module now
raises EmbeddingUnavailableError instead of silently degrading.

NOTE — UNEXERCISED PATH: `_embed_with_local_model` has still not been
exercised against the real sample documents (the Gemini API was
available throughout the Stage 4 build/test pass). It is implemented
and importable, and its output dimensionality is now validated at the
call site, but using it requires re-embedding the entire corpus into
a collection created at its own dimensionality.
"""

from __future__ import annotations

import os
from typing import List, Literal, Optional, TypedDict

import httpx
from dotenv import load_dotenv
from google.genai import errors as genai_errors

load_dotenv()

GEMINI_EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")

# Local embedding model — small, fast, well-regarded for retrieval.
# Matches the TDR-specified fallback family (BGE).
#
# NOTE: this is 384-dimensional, NOT 768 — see
# EMBEDDING_OUTPUT_DIMENSIONALITY below and
# _assert_dimensionality_matches() for why that matters and why this
# can no longer be used as an automatic runtime fallback.
LOCAL_FALLBACK_MODEL = os.getenv("DOCSENSE_LOCAL_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")

# gemini-embedding-001 defaults to 3072 dimensions; truncating to 768
# is explicitly recommended by Google as retaining most of the
# quality while reducing storage — see Section 3 of TDR for chunk
# volume expectations (V1 caps documents at 50 pages).
#
# MUST stay in sync with embedding/vector_store.py's VECTOR_SIZE,
# which is the dimensionality the Qdrant collection was actually
# created with. Any vector produced at a different dimensionality
# cannot be stored in or searched against that collection.
EMBEDDING_OUTPUT_DIMENSIONALITY = 768

# Opt-in switch for using the local model instead of Gemini.
#
# FIXED BUG (found during a Stage 7 call-count audit; previously
# recorded in TDR.md as a documented-but-unfixed known limitation):
# _embed_texts() used to wrap the Gemini call in a bare
# `except Exception` and, on ANY failure, silently fall back to
# LOCAL_FALLBACK_MODEL. That was unsafe in two independent ways:
#
#   1. DIMENSION MISMATCH. The local model emits 384-dim vectors while
#      the Qdrant collection is built at 768 (VECTOR_SIZE). A silent
#      fallback therefore produced vectors that physically cannot be
#      upserted into or searched against the existing collection —
#      surfacing later as a confusing Qdrant dimension error far from
#      the actual cause, rather than as "Gemini was unavailable."
#
#   2. VECTOR-SPACE MISMATCH, which is the deeper problem and is NOT
#      fixed by padding/projecting to 768 or by picking a natively
#      768-dim local model. Embeddings are only comparable within the
#      same model's vector space. A query embedded by BGE, searched
#      against chunks embedded by Gemini, yields cosine scores that
#      are arithmetically valid but semantically meaningless — i.e.
#      silently wrong retrieval results, which is strictly worse than
#      a loud failure. Mixing embedding models within one collection
#      is incoherent regardless of dimensionality.
#
# Because a coherent local-embedding setup requires the WHOLE corpus
# (and every subsequent query) to use that same model, it is a
# deliberate, corpus-wide configuration decision — not something to
# switch to automatically mid-run. It is therefore opt-in only:
# set DOCSENSE_EMBEDDING_BACKEND=local and re-embed every document
# from scratch into a collection created at the local model's own
# dimensionality.
_EMBEDDING_BACKEND = os.getenv("DOCSENSE_EMBEDDING_BACKEND", "gemini").strip().lower()

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


class EmbeddingUnavailableError(RuntimeError):
    """Raised when the configured embedding backend could not produce
    embeddings. Deliberately a distinct type so callers can tell
    "the embedding provider is down" apart from a programming error
    elsewhere in the pipeline — see _embed_texts for why that
    distinction was previously impossible.
    """


def _embed_texts(texts: List[str], task_type: TaskType) -> List[List[float]]:
    """Embeds a batch of texts using the configured backend.

    Default backend is Gemini, rotating across all configured keys
    (TDR Section 2d). If every key is exhausted/unavailable, this
    raises EmbeddingUnavailableError rather than silently switching
    to the local model — see _EMBEDDING_BACKEND above for the full
    reasoning (dimension mismatch AND vector-space mismatch make an
    automatic mid-run switch produce silently-wrong retrieval).

    To use local embeddings, set DOCSENSE_EMBEDDING_BACKEND=local and
    re-embed the whole corpus into a matching collection.

    Raises:
        EmbeddingUnavailableError: if the configured backend could not
            produce embeddings (all Gemini keys exhausted/unavailable,
            no keys configured, or a local-model dimensionality
            mismatch).
    """
    if _EMBEDDING_BACKEND == "local":
        vectors = _embed_with_local_model(texts)
        _assert_dimensionality_matches(vectors, source=f"local model {LOCAL_FALLBACK_MODEL}")
        return vectors

    try:
        vectors = _embed_with_gemini(texts, task_type)
    except (genai_errors.APIError, httpx.TimeoutException, httpx.ConnectError) as exc:
        # NARROWED (was a bare `except Exception`): only genuine
        # "the Gemini API did not serve this request" failures are
        # caught here — HTTP errors from the SDK (genai_errors.APIError
        # is the parent of both ClientError/4xx and ServerError/5xx)
        # and network-level timeout/connection failures. A TypeError,
        # KeyError, AttributeError, ImportError or similar from our own
        # code now propagates normally instead of being swallowed and
        # misreported as "Gemini unavailable, falling back", which
        # previously could hide a real bug indefinitely.
        raise EmbeddingUnavailableError(
            f"Gemini embedding call failed on all configured keys "
            f"({type(exc).__name__}: {exc}). Not falling back to the local "
            f"model automatically: {LOCAL_FALLBACK_MODEL} produces vectors in a "
            f"different vector space (and a different dimensionality) than the "
            f"existing {EMBEDDING_OUTPUT_DIMENSIONALITY}-dim Gemini-built "
            f"collection, so mixing them would yield silently-wrong retrieval "
            f"rather than a visible error. Either retry once Gemini is "
            f"available, or set DOCSENSE_EMBEDDING_BACKEND=local AND re-embed "
            f"the entire corpus into a collection created at the local model's "
            f"own dimensionality."
        ) from exc
    except RuntimeError as exc:
        # call_with_key_rotation raises a plain RuntimeError when no
        # API keys are configured at all. Surfaced with the same
        # explicit guidance rather than silently going local.
        raise EmbeddingUnavailableError(
            f"Gemini embedding backend is not usable: {exc} "
            f"Set GEMINI_API_KEY (see .env.example), or set "
            f"DOCSENSE_EMBEDDING_BACKEND=local AND re-embed the entire corpus "
            f"into a collection matching the local model's dimensionality."
        ) from exc

    _assert_dimensionality_matches(vectors, source=f"Gemini model {GEMINI_EMBEDDING_MODEL}")
    return vectors


def _assert_dimensionality_matches(vectors: List[List[float]], source: str) -> None:
    """Fails fast if produced vectors don't match the dimensionality
    the Qdrant collection was built at.

    Catches the mismatch HERE, where the cause is obvious and the
    error message can name the offending model, instead of letting it
    surface later as an opaque Qdrant dimension error during upsert or
    search (see _EMBEDDING_BACKEND's note for the original bug).
    """
    if not vectors:
        return

    actual_dim = len(vectors[0])
    if actual_dim != EMBEDDING_OUTPUT_DIMENSIONALITY:
        raise EmbeddingUnavailableError(
            f"Embedding dimensionality mismatch: {source} produced "
            f"{actual_dim}-dim vectors, but this pipeline's Qdrant collection is "
            f"built for {EMBEDDING_OUTPUT_DIMENSIONALITY}-dim vectors "
            f"(embedding/vector_store.py VECTOR_SIZE). These vectors cannot be "
            f"stored in or searched against that collection. Use an embedding "
            f"model whose output dimensionality is "
            f"{EMBEDDING_OUTPUT_DIMENSIONALITY}, or recreate the collection at "
            f"{actual_dim} dimensions and re-embed every document."
        )


def _embed_with_gemini(texts: List[str], task_type: TaskType) -> List[List[float]]:
    from google import genai
    from google.genai import types as genai_types

    from generation.gemini_key_rotation import build_http_options, call_with_key_rotation

    def _make_call(api_key: str) -> List[List[float]]:
        client = genai.Client(api_key=api_key, http_options=build_http_options())
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
    # OPT-IN ONLY — reachable solely via
    # DOCSENSE_EMBEDDING_BACKEND=local, never as an automatic runtime
    # fallback (see _EMBEDDING_BACKEND for why). Still unexercised
    # against the real sample documents; its output dimensionality is
    # checked by _assert_dimensionality_matches() at the call site, so
    # a mismatch now fails immediately with a clear message instead of
    # producing unusable vectors.
    if "model" not in _local_model_cache:
        from sentence_transformers import SentenceTransformer

        _local_model_cache["model"] = SentenceTransformer(LOCAL_FALLBACK_MODEL)

    model = _local_model_cache["model"]
    vectors = model.encode(texts, normalize_embeddings=True)
    return [vector.tolist() for vector in vectors]
