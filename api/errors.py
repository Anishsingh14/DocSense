"""Exception -> HTTP mapping for the Stage 8 API.

All mapping lives here so no route handler builds its own error
response. Three rules hold for every handler below:
  1. No stack traces, ever.
  2. No server filesystem paths. Ingestion exceptions embed the
     absolute upload path in their message, so messages are passed
     through sanitize_message() before being returned.
  3. No key material. Nothing here reads or formats a key.
"""

from __future__ import annotations

import os
import re

from fastapi import Request
from fastapi.responses import JSONResponse

from api.service import (
    DocumentNotFoundError,
    JobNotFoundError,
    UploadTooLargeError,
)
from embedding.embed_chunks import EmbeddingUnavailableError
from generation.gemini_key_rotation import AllModelsAndKeysExhaustedError
from ingestion.text_parser import DocumentParsingError, UnsupportedFileTypeError

# How long a client should wait before retrying an exhausted provider
# pool. 60s matches the short transient cooldown in
# generation.provider_rotation, so a retry has a realistic chance of
# landing on a provider that has come back.
RETRY_AFTER_SECONDS = 60

_PATH_PATTERN = re.compile(r"[A-Za-z]:\\[^\s'\"]+|/(?:[\w.-]+/)+[\w.-]+")


def sanitize_message(message: str) -> str:
    """Strips anything path-like out of an exception message.

    Ingestion raises e.g. "Failed to open PDF 'C:\\...\\data\\uploads\\
    x.pdf': ..." — the filename is useful to the caller but the server
    path is not, and leaking directory layout is needless exposure.
    """
    cleaned = _PATH_PATTERN.sub(
        lambda m: os.path.basename(m.group(0).replace("\\", "/")), message
    )
    return cleaned.strip()


def _json(status: int, detail: str, headers: dict | None = None) -> JSONResponse:
    return JSONResponse(status_code=status, content={"detail": detail}, headers=headers)


async def handle_providers_exhausted(
    request: Request, exc: AllModelsAndKeysExhaustedError
) -> JSONResponse:
    """503 + Retry-After.

    Catches AllProvidersExhaustedError too, since that is a subclass.
    This is explicitly NOT a server fault: every configured provider
    returned a retryable error (429/503/504/timeout), so the honest
    answer is "unavailable, try again" rather than a 500.
    """
    return _json(
        503,
        "All configured answer providers are currently unavailable "
        "(rate-limited or overloaded). This is a temporary upstream "
        "condition, not a problem with the request. Please retry.",
        headers={"Retry-After": str(RETRY_AFTER_SECONDS)},
    )


async def handle_embedding_unavailable(
    request: Request, exc: EmbeddingUnavailableError
) -> JSONResponse:
    """503 with a message distinct from provider exhaustion.

    Kept separate on purpose: this one means retrieval could not run at
    all because no query vector could be produced, which is a different
    operational problem (the Gemini embedding key pool) from the answer
    providers being busy.
    """
    return _json(
        503,
        "The embedding service is currently unavailable, so document "
        "retrieval cannot run. No local fallback is used, because local "
        "embeddings are not compatible with the stored vectors. Please "
        "retry.",
        headers={"Retry-After": str(RETRY_AFTER_SECONDS)},
    )


async def handle_unsupported_file_type(
    request: Request, exc: UnsupportedFileTypeError
) -> JSONResponse:
    return _json(415, "Unsupported file type. Supported types are PDF, DOCX and TXT.")


async def handle_upload_too_large(
    request: Request, exc: UploadTooLargeError
) -> JSONResponse:
    return _json(413, sanitize_message(str(exc)))


async def handle_not_found(request: Request, exc: KeyError) -> JSONResponse:
    identifier = sanitize_message(str(exc).strip("'\""))
    return _json(404, f"Not found: {identifier}")


async def handle_parse_error(
    request: Request, exc: DocumentParsingError
) -> JSONResponse:
    """422 — the upload was accepted but could not be read.

    Not 500: nothing is wrong with the server, the submitted document
    is empty or corrupted.
    """
    return _json(422, sanitize_message(str(exc)))


async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all 500 with a fixed, generic message.

    Deliberately reveals nothing about the exception: no type, no
    message, no traceback, no path. Anything genuinely unexpected is a
    defect to be read from the server log, not from a client response.
    """
    return _json(500, "An internal error occurred while processing the request.")


def register_exception_handlers(app) -> None:
    """Wires every handler above onto the app.

    Ordering note: FastAPI resolves handlers by exact exception class,
    walking the MRO, so AllModelsAndKeysExhaustedError also catches its
    AllProvidersExhaustedError subclass, and the specific KeyError
    subclasses below are matched before the bare Exception catch-all.
    """
    app.add_exception_handler(AllModelsAndKeysExhaustedError, handle_providers_exhausted)
    app.add_exception_handler(EmbeddingUnavailableError, handle_embedding_unavailable)
    app.add_exception_handler(UnsupportedFileTypeError, handle_unsupported_file_type)
    app.add_exception_handler(DocumentParsingError, handle_parse_error)
    app.add_exception_handler(UploadTooLargeError, handle_upload_too_large)
    app.add_exception_handler(DocumentNotFoundError, handle_not_found)
    app.add_exception_handler(JobNotFoundError, handle_not_found)
    app.add_exception_handler(Exception, handle_unexpected)
