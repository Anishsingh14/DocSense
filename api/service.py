"""Stage 8 service layer — the ONLY module in api/ that imports Stages 1-6.

Keeping every pipeline and key/provider touchpoint here means the route
handlers stay transport-only, and the planned per-user-key work later
has one place to change rather than five endpoints to audit.

KEY HANDLING: this module never reads an API key. Keys stay inside
generation.gemini_key_rotation (embeddings, vision) and
generation.provider_rotation (generation, grading), exactly as the
pipeline reads them today.
"""

from __future__ import annotations

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple

from chunking.pipeline import chunk_ingested_document
from embedding import vector_store
from embedding.pipeline import embed_and_store_chunks
from generation.answer_with_citations import generate_answer
from generation.provider_rotation import PROVIDERS
from ingestion.image_pipeline import analyze_ingested_document_images
from ingestion.pipeline import compute_doc_id, ingest_document
from retrieval.pipeline import retrieve_and_rerank

# APPROVED PRIVATE IMPORT (user decision, Stage 8 plan):
# AnswerResult.sources is the CITED SUBSET and carries no source
# number, but the "(Source N)" markers in the answer text refer to a
# chunk's 1-based position in the list handed to the prompt. Recovering
# N therefore needs the same parser Stage 6 uses. Importing Stage 6's
# own _extract_valid_citations guarantees the API's numbering can never
# drift from the numbering Stage 6 validated against; re-implementing
# the regex here would be a second source of truth. Stage 6 is
# unchanged — see TDR Section 2j.
from generation.answer_with_citations import _extract_valid_citations

RETRIEVAL_TOP_K = 5  # matches retrieval.reranker.DEFAULT_TOP_K

UPLOAD_DIR = os.path.join("data", "uploads")

# 25 MB. Chosen because the sample corpus's largest document is far
# below it while a cap this size still refuses anything that would make
# ingestion (one vision call per unique image) run unboundedly long.
MAX_UPLOAD_BYTES = 25 * 1024 * 1024

# Ingestion runs on a single worker. Two reasons, both load-bearing:
# the local Qdrant store is a single in-process writer, and ingestion
# is the long operation (vision + embedding calls), so serialising it
# keeps memory and provider usage predictable.
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="docsense-ingest")

# In-memory job registry. Jobs do not survive a restart — acceptable
# for V1 (see TDR Section 2j limitations), and deliberately not
# persisted into Qdrant, which stores chunks rather than job state.
_jobs: Dict[str, dict] = {}
_jobs_lock = threading.Lock()


class DocumentNotFoundError(KeyError):
    """Raised when a doc_id has no chunks stored. Maps to 404."""


class JobNotFoundError(KeyError):
    """Raised when a job_id is unknown. Maps to 404."""


class UploadTooLargeError(ValueError):
    """Raised when an upload exceeds MAX_UPLOAD_BYTES. Maps to 413."""


# ------------------------------------------------------------- health
def health_snapshot() -> dict:
    """Static health info.

    Deliberately takes NO lock and makes NO provider or Qdrant call
    (user requirement): health must stay answerable while a slow
    ingestion or query is in flight, so it reports only configuration
    that is knowable without I/O. Provider ENV VAR NAMES are returned,
    never key values.
    """
    return {
        "status": "ok",
        "collection": vector_store.COLLECTION_NAME,
        "embedding_backend": os.getenv("DOCSENSE_EMBEDDING_BACKEND", "gemini"),
        "providers_enabled": [p.env_var for p in PROVIDERS if p.enabled],
    }


# ---------------------------------------------------------- documents
def list_documents() -> List[dict]:
    return vector_store.list_documents()


def document_exists(doc_id: str) -> bool:
    return vector_store.count_points(doc_id) > 0


def delete_document(doc_id: str) -> int:
    """Deletes a document's chunks. Raises DocumentNotFoundError if it
    isn't stored, so the route can return 404 rather than a misleading
    200-with-zero.
    """
    chunk_count = vector_store.count_points(doc_id)
    if chunk_count == 0:
        raise DocumentNotFoundError(doc_id)
    vector_store.delete_document(doc_id)
    return chunk_count


def save_upload(filename: str, data: bytes) -> str:
    """Writes an upload to UPLOAD_DIR and returns the saved path.

    The returned path is for internal use only and must never appear
    in a response body.
    """
    if len(data) > MAX_UPLOAD_BYTES:
        raise UploadTooLargeError(
            f"File is {len(data)} bytes; the limit is {MAX_UPLOAD_BYTES} bytes."
        )
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    # Basename only — a client-supplied name must not be able to
    # traverse out of the upload directory.
    safe_name = os.path.basename(filename)
    path = os.path.join(UPLOAD_DIR, safe_name)
    with open(path, "wb") as f:
        f.write(data)
    return path


def start_ingestion(file_path: str) -> dict:
    """Queues ingestion and returns the job record immediately.

    Synchronous ingestion was rejected: a document's cost is one vision
    call per unique image plus embedding calls, and a single provider
    call has been measured at ~40s under congestion, so the request
    would outlive normal client timeouts with no progress signal.
    """
    doc_id = compute_doc_id(file_path)
    job_id = uuid.uuid4().hex
    job = {
        "job_id": job_id,
        "doc_id": doc_id,
        "status": "queued",
        "chunks_stored": None,
        "error": None,
    }
    with _jobs_lock:
        _jobs[job_id] = job
    _executor.submit(_run_ingestion, job_id, file_path)
    return dict(job)


def get_job(job_id: str) -> dict:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None:
            raise JobNotFoundError(job_id)
        return dict(job)


def _set_job(job_id: str, **fields) -> None:
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id].update(fields)


def _run_ingestion(job_id: str, file_path: str) -> None:
    """Stages 1 -> 2/3 -> 4. Runs on the single ingest worker."""
    _set_job(job_id, status="running")
    try:
        ingested = ingest_document(file_path)
        text_chunks = chunk_ingested_document(ingested)
        image_chunks = analyze_ingested_document_images(ingested)
        stored = embed_and_store_chunks(text_chunks + image_chunks)
        _set_job(job_id, status="done", chunks_stored=stored)
    except Exception as exc:  # noqa: BLE001 - recorded, never re-raised
        # Only the exception TYPE and a sanitised message are kept. No
        # traceback, and no server path: ingestion errors embed the
        # absolute file path in their message, which must not be
        # exposed.
        from api.errors import sanitize_message

        _set_job(
            job_id,
            status="failed",
            error=f"{type(exc).__name__}: {sanitize_message(str(exc))}",
        )


# -------------------------------------------------------------- query
def run_query(
    question: str,
    mode: str,
    doc_ids: List[str],
    answer_style: str = "full",
) -> dict:
    """Stages 5-6 for one question, shaped into the API response.

    PARITY WITH answer_question(): generation.pipeline.answer_question
    is exactly retrieve_and_rerank() followed by generate_answer(). This
    performs the same two calls in the same order with the same
    arguments, so the answer and every AnswerResult field are identical.
    The reason for not calling answer_question() is that it returns only
    the AnswerResult and discards the chunk list, which the evidence
    group needs. Retrieving here also means generate_answer() receives
    the chunks directly, so retrieval is not run twice.

    NO LOCK IS HELD HERE. Qdrant access is locked inside
    embedding.vector_store around the client calls themselves, so the
    embedding, rerank and generation work in this path never blocks
    another request.
    """
    chunks = retrieve_and_rerank(question, mode, doc_ids, top_k=RETRIEVAL_TOP_K)
    result = generate_answer(question, chunks, mode, answer_style=answer_style)

    cited_indices, discarded_count = _extract_valid_citations(
        result["answer"], len(chunks)
    )

    # Empty retrieval is a supported outcome, not an error:
    # generate_answer() short-circuits to a "Not found" answer with
    # provider_used/model_used None, and _extract_valid_citations finds
    # no markers against 0 chunks, so both lists below come out empty.
    citations = [
        {
            "source_number": i + 1,
            "doc_name": chunks[i]["doc_name"],
            "page_num": chunks[i]["page_num"],
        }
        for i in cited_indices
    ]

    sources = [
        {
            "source_number": i + 1,
            "doc_name": chunk["doc_name"],
            "page_num": chunk["page_num"],
            "section": chunk.get("section"),
            "text": chunk["text"],
        }
        for i, chunk in enumerate(chunks)
    ]

    return {
        "question": question,
        "mode": result["mode"],
        "core": {"answer": result["answer"], "citations": citations},
        "evidence": {"sources": sources},
        "meta": {
            "provider_used": result.get("provider_used"),
            "model_used": result.get("model_used"),
            "citation_check": {
                "valid_citations": len(cited_indices),
                "discarded_citations": discarded_count,
                "warning": result.get("warning"),
            },
        },
    }


def missing_doc_ids(doc_ids: List[str]) -> List[str]:
    """Returns the subset of doc_ids with no stored chunks."""
    return [d for d in doc_ids if vector_store.count_points(d) == 0]
