"""main.py — Stage 8 FastAPI application (TDR Section 2j).

RUN AS A SINGLE PROCESS:

    uvicorn api.main:app --port 8000

Do NOT pass --reload and do NOT pass --workers > 1. The local embedded
Qdrant store takes an exclusive file lock, so a second process dies
with "Storage folder data/vector_store is already accessed by another
instance". --reload spawns a reloader process plus a worker, which is
enough to trigger it. For the same reason, do not run this alongside
evaluation/run_eval.py.

Route handlers are plain `def`, not `async def`, on purpose: every
pipeline call is blocking, so Starlette runs these in its threadpool
and the event loop stays free. Qdrant access is serialised inside
embedding.vector_store, around the client calls only.
"""

from __future__ import annotations

import os

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from api import service
from api.errors import register_exception_handlers
from api.schemas import (
    DeleteResponse,
    DocumentListResponse,
    ErrorResponse,
    HealthResponse,
    JobStatusResponse,
    QueryRequest,
    QueryResponse,
    UploadAcceptedResponse,
)
from ingestion.text_parser import SUPPORTED_EXTENSIONS, UnsupportedFileTypeError

app = FastAPI(
    title="DocSense API",
    description=(
        "Stage 8 API over the DocSense RAG pipeline. Answers always "
        "carry page citations cross-checked against the chunks that "
        "were actually retrieved."
    ),
    version="1.0.0",
)

# Stage 9's Streamlit UI will call this from the browser. Localhost
# origins only — this API has no auth yet, so it must not be reachable
# from arbitrary origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8501",  # Streamlit default
        "http://127.0.0.1:8501",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

register_exception_handlers(app)


@app.get("/health", response_model=HealthResponse, tags=["health"])
def health() -> dict:
    """Liveness + configuration snapshot.

    Takes no lock and makes no Qdrant or provider call, so it stays
    answerable while a slow ingestion or query is in flight. It
    reports provider env var NAMES, never key values.
    """
    return service.health_snapshot()


@app.post(
    "/documents",
    response_model=UploadAcceptedResponse,
    status_code=202,
    tags=["documents"],
    responses={413: {"model": ErrorResponse}, 415: {"model": ErrorResponse}},
)
def upload_document(file: UploadFile = File(...)) -> dict:
    """Accepts a PDF/DOCX/TXT upload and queues ingestion.

    Returns 202 rather than blocking: ingestion runs Stages 1-4,
    including one vision call per unique image plus embedding calls,
    which can far exceed a normal client timeout. Poll
    /documents/jobs/{job_id} for completion.
    """
    filename = os.path.basename(file.filename or "")
    ext = os.path.splitext(filename)[1].lower()
    # Checked up front so an unsupported type costs nothing — no file
    # written, no pipeline work started.
    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileTypeError(f"Unsupported file type '{ext}'.")

    data = file.file.read()
    path = service.save_upload(filename, data)
    return service.start_ingestion(path)


@app.get(
    "/documents/jobs/{job_id}",
    response_model=JobStatusResponse,
    tags=["documents"],
    responses={404: {"model": ErrorResponse}},
)
def job_status(job_id: str) -> dict:
    """Ingestion job status: queued | running | done | failed."""
    return service.get_job(job_id)


@app.get("/documents", response_model=DocumentListResponse, tags=["documents"])
def list_documents() -> dict:
    """Lists every document currently stored in the vector collection."""
    return {"documents": service.list_documents()}


@app.delete(
    "/documents/{doc_id}",
    response_model=DeleteResponse,
    tags=["documents"],
    responses={404: {"model": ErrorResponse}},
)
def delete_document(doc_id: str) -> dict:
    """Deletes every chunk belonging to a doc_id."""
    chunks_deleted = service.delete_document(doc_id)
    return {"doc_id": doc_id, "chunks_deleted": chunks_deleted}


@app.post(
    "/query",
    response_model=QueryResponse,
    tags=["query"],
    responses={
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def query(request: QueryRequest) -> dict:
    """Answers a question in single_doc, multi_doc or legal mode.

    Always returns the full response — core, evidence and meta. There
    is no flag to trim it; the UI decides what to display.
    """
    missing = service.missing_doc_ids(request.doc_ids)
    if missing:
        # 404 before any provider call, so an unknown doc_id costs
        # nothing rather than burning an embedding call first.
        raise service.DocumentNotFoundError(", ".join(missing))

    return service.run_query(
        question=request.question,
        mode=request.mode,
        doc_ids=request.doc_ids,
        answer_style=request.answer_style,
    )
