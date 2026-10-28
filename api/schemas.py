"""Request/response models for the Stage 8 API.

The response models mirror the existing pipeline result types rather
than inventing a parallel vocabulary: `Citation` and `EvidenceSource`
are projections of retrieval.reranker.RankedChunk, and `QueryMeta`
carries generation.answer_with_citations.AnswerResult's own
provider_used / model_used / warning.

Deliberately absent: any request flag that trims the response. The
full response is always returned and the UI decides what to show.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

Mode = Literal["single_doc", "multi_doc", "legal"]
AnswerStyle = Literal["full", "summary"]
JobStatus = Literal["queued", "running", "done", "failed"]


# --------------------------------------------------------------- health
class HealthResponse(BaseModel):
    status: Literal["ok"]
    collection: str
    embedding_backend: str
    # Provider ENV VAR NAMES only — never values. Names are not secret;
    # key material must never reach a response body.
    providers_enabled: List[str]


# ------------------------------------------------------------ documents
class DocumentSummary(BaseModel):
    doc_id: str
    doc_name: str
    doc_type: str
    chunk_count: int
    pages: int


class DocumentListResponse(BaseModel):
    documents: List[DocumentSummary]


class UploadAcceptedResponse(BaseModel):
    job_id: str
    doc_id: str
    status: JobStatus


class JobStatusResponse(BaseModel):
    job_id: str
    doc_id: str
    status: JobStatus
    chunks_stored: Optional[int] = None
    error: Optional[str] = None


class DeleteResponse(BaseModel):
    doc_id: str
    chunks_deleted: int


# ---------------------------------------------------------------- query
class QueryRequest(BaseModel):
    question: str = Field(min_length=1)
    mode: Mode
    # min_length=1 so an empty list is a 422 rather than a retrieval
    # against the whole collection.
    doc_ids: List[str] = Field(min_length=1)
    answer_style: AnswerStyle = "full"


class Citation(BaseModel):
    source_number: int
    doc_name: str
    page_num: int


class EvidenceSource(BaseModel):
    source_number: int
    doc_name: str
    page_num: int
    section: Optional[str] = None
    text: str


class CitationCheck(BaseModel):
    """Stage 6's own cross-check of the model's citations against what
    was actually retrieved — counts plus AnswerResult.warning verbatim.
    """

    valid_citations: int
    discarded_citations: int
    warning: Optional[str] = None


class QueryCore(BaseModel):
    answer: str
    citations: List[Citation]


class QueryEvidence(BaseModel):
    # Every retrieved chunk, cited or not. The UI highlights the cited
    # ones by matching source_number against core.citations.
    sources: List[EvidenceSource]


class QueryMeta(BaseModel):
    provider_used: Optional[str] = None
    model_used: Optional[str] = None
    citation_check: CitationCheck


class QueryResponse(BaseModel):
    question: str
    mode: Mode
    core: QueryCore
    evidence: QueryEvidence
    meta: QueryMeta


class ErrorResponse(BaseModel):
    detail: str
