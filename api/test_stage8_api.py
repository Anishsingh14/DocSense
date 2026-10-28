"""Stage 8 API verification — ZERO live API calls.

Run from the project root:

    python -m api.test_stage8_api

Uses FastAPI's TestClient with every pipeline function mocked, so no
Gemini/provider call and no Qdrant write happens. Written as a plain
self-checking script rather than pytest tests because pytest is not a
project dependency and this stage does not justify adding one.

Note that _extract_valid_citations is deliberately NOT mocked: the
citation numbering and citation_check parity checks below only mean
something if they exercise Stage 6's real parser.
"""

from __future__ import annotations

import sys
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app
from api.service import MAX_UPLOAD_BYTES
from embedding.embed_chunks import EmbeddingUnavailableError
from generation.provider_rotation import AllProvidersExhaustedError

client = TestClient(app)

# TestClient re-raises unhandled server exceptions by default, which is
# useful for most tests but hides the catch-all 500 handler. This second
# client lets that handler's actual response be inspected, which is the
# only way to assert it leaks nothing. Under uvicorn the handler always
# runs; this flag only affects the test transport.
safe_client = TestClient(app, raise_server_exceptions=False)

passes = failures = 0


def check(label, actual, expected):
    global passes, failures
    if actual == expected:
        passes += 1
        print(f"  PASS  {label}")
    else:
        failures += 1
        print(f"  FAIL  {label}")
        print(f"          expected: {expected!r}")
        print(f"          actual:   {actual!r}")


def check_true(label, condition, detail=""):
    check(label + (f" ({detail})" if detail else ""), bool(condition), True)


def banner(text):
    print(f"\n--- {text} ---")


# Two chunks shaped like retrieval.reranker.RankedChunk.
CHUNKS = [
    {
        "chunk_id": "DocA_p3_c1", "doc_id": "DocA", "doc_name": "DocA",
        "doc_type": "legal", "page_num": 3, "section": "4.2 Termination",
        "type": "text", "image_type": None, "text": "Either party may terminate...",
        "source_image_path": None, "score": 0.81, "rerank_score": 7.2,
    },
    {
        "chunk_id": "DocA_p5_c2", "doc_id": "DocA", "doc_name": "DocA",
        "doc_type": "legal", "page_num": 5, "section": "9.1 Notices",
        "type": "text", "image_type": None, "text": "Notices shall be sent...",
        "source_image_path": None, "score": 0.44, "rerank_score": 2.1,
    },
]


def answer_result(answer, warning=None, provider="RAG_Groq", model="openai/gpt-oss-20b"):
    return {
        "answer": answer, "mode": "single_doc", "answer_style": "full",
        "sources": [], "warning": warning,
        "provider_used": provider, "model_used": model,
    }


# ------------------------------------------------------------- health
banner("GET /health — no lock, no provider call, no key values")
with patch("api.service.vector_store.count_points") as counted, \
     patch("api.service.vector_store.list_documents") as listed:
    r = client.get("/health")
    check("status 200", r.status_code, 200)
    body = r.json()
    check("status field", body["status"], "ok")
    check_true("providers_enabled present", len(body["providers_enabled"]) > 0)
    check("made no Qdrant count call", counted.called, False)
    check("made no Qdrant list call", listed.called, False)
    # providers_enabled must be env var NAMES, not values. Real keys in
    # this project are 53 chars; a name is short and starts with RAG_.
    check_true(
        "providers_enabled are names, not key values",
        all(p.startswith("RAG_") and len(p) < 30 for p in body["providers_enabled"]),
    )

# ---------------------------------------------------------- documents
banner("GET /documents")
with patch("api.service.vector_store.list_documents", return_value=[
    {"doc_id": "DocA", "doc_name": "DocA", "doc_type": "legal",
     "chunk_count": 9, "pages": 5}
]):
    r = client.get("/documents")
    check("status 200", r.status_code, 200)
    check("one document returned", len(r.json()["documents"]), 1)
    check("chunk_count passed through", r.json()["documents"][0]["chunk_count"], 9)

banner("POST /documents — 202 accepted, ingestion queued")
with patch("api.service.save_upload", return_value="data/uploads/tiny.txt"), \
     patch("api.service.start_ingestion", return_value={
         "job_id": "job123", "doc_id": "tiny", "status": "queued",
         "chunks_stored": None, "error": None}):
    r = client.post("/documents", files={"file": ("tiny.txt", b"hello", "text/plain")})
    check("status 202", r.status_code, 202)
    check("job_id returned", r.json()["job_id"], "job123")
    check("status queued", r.json()["status"], "queued")

banner("POST /documents — 415 unsupported file type")
r = client.post("/documents", files={"file": ("notes.md", b"# nope", "text/markdown")})
check("status 415", r.status_code, 415)
check_true("mentions supported types", "PDF" in r.json()["detail"])

banner("POST /documents — 413 oversized upload")
big = b"x" * (MAX_UPLOAD_BYTES + 1)
r = client.post("/documents", files={"file": ("big.txt", big, "text/plain")})
check("status 413", r.status_code, 413)

banner("GET /documents/jobs/{job_id}")
with patch("api.service.get_job", return_value={
        "job_id": "job123", "doc_id": "tiny", "status": "done",
        "chunks_stored": 2, "error": None}):
    r = client.get("/documents/jobs/job123")
    check("status 200", r.status_code, 200)
    check("chunks_stored", r.json()["chunks_stored"], 2)

banner("GET /documents/jobs/{job_id} — 404 unknown job")
r = client.get("/documents/jobs/does-not-exist")
check("status 404", r.status_code, 404)

banner("DELETE /documents/{doc_id}")
with patch("api.service.vector_store.count_points", return_value=9), \
     patch("api.service.vector_store.delete_document", return_value=1):
    r = client.delete("/documents/DocA")
    check("status 200", r.status_code, 200)
    check("chunks_deleted", r.json()["chunks_deleted"], 9)

banner("DELETE /documents/{doc_id} — 404 unknown doc_id")
with patch("api.service.vector_store.count_points", return_value=0):
    r = client.delete("/documents/NopeDoc")
    check("status 404", r.status_code, 404)

# -------------------------------------------------------------- query
banner("POST /query — full response shape, real citation parsing")
with patch("api.service.vector_store.count_points", return_value=9), \
     patch("api.service.retrieve_and_rerank", return_value=CHUNKS), \
     patch("api.service.generate_answer", return_value=answer_result(
         "Thirty (30) days written notice. (Source 1)")):
    r = client.post("/query", json={
        "question": "What is the termination notice period?",
        "mode": "single_doc", "doc_ids": ["DocA"]})
    check("status 200", r.status_code, 200)
    body = r.json()
    check("top-level question", body["question"], "What is the termination notice period?")
    check("top-level mode", body["mode"], "single_doc")
    check("exactly three groups + question + mode",
          sorted(body.keys()), ["core", "evidence", "meta", "mode", "question"])
    check("core.citations count", len(body["core"]["citations"]), 1)
    check("citation source_number", body["core"]["citations"][0]["source_number"], 1)
    check("citation page_num", body["core"]["citations"][0]["page_num"], 3)
    check("evidence lists ALL retrieved chunks", len(body["evidence"]["sources"]), 2)
    check("evidence source_numbers are 1-based",
          [s["source_number"] for s in body["evidence"]["sources"]], [1, 2])
    check("evidence keeps section", body["evidence"]["sources"][0]["section"], "4.2 Termination")
    check("meta.provider_used", body["meta"]["provider_used"], "RAG_Groq")
    check("meta.model_used", body["meta"]["model_used"], "openai/gpt-oss-20b")
    check("citation_check.valid", body["meta"]["citation_check"]["valid_citations"], 1)
    check("citation_check.discarded", body["meta"]["citation_check"]["discarded_citations"], 0)

banner("POST /query — citation_check PARITY: out-of-range marker discarded")
with patch("api.service.vector_store.count_points", return_value=9), \
     patch("api.service.retrieve_and_rerank", return_value=CHUNKS), \
     patch("api.service.generate_answer", return_value=answer_result(
         "See (Source 1) and (Source 7).", warning="1 citation was discarded.")):
    r = client.post("/query", json={
        "question": "q", "mode": "legal", "doc_ids": ["DocA"]})
    body = r.json()
    # Source 7 does not exist among 2 chunks, so Stage 6's own parser
    # must discard it. This is the parity guarantee: the API reports
    # exactly what Stage 6 computed, not its own recount.
    check("only in-range citation kept", len(body["core"]["citations"]), 1)
    check("valid_citations", body["meta"]["citation_check"]["valid_citations"], 1)
    check("discarded_citations", body["meta"]["citation_check"]["discarded_citations"], 1)
    check("warning passed through verbatim",
          body["meta"]["citation_check"]["warning"], "1 citation was discarded.")

banner("POST /query — EMPTY retrieval does not crash")
with patch("api.service.vector_store.count_points", return_value=9), \
     patch("api.service.retrieve_and_rerank", return_value=[]), \
     patch("api.service.generate_answer", return_value=answer_result(
         "Not found in the provided document(s).",
         warning="No relevant chunks were retrieved for this question.",
         provider=None, model=None)):
    r = client.post("/query", json={
        "question": "unanswerable", "mode": "single_doc", "doc_ids": ["DocA"]})
    check("status 200 (not 500)", r.status_code, 200)
    body = r.json()
    check("no citations", body["core"]["citations"], [])
    check("no evidence sources", body["evidence"]["sources"], [])
    check("provider_used is null", body["meta"]["provider_used"], None)
    check("model_used is null", body["meta"]["model_used"], None)
    check("valid_citations 0", body["meta"]["citation_check"]["valid_citations"], 0)
    check_true("warning surfaced", body["meta"]["citation_check"]["warning"] is not None)

banner("POST /query — 404 unknown doc_id, before any provider call")
with patch("api.service.vector_store.count_points", return_value=0), \
     patch("api.service.retrieve_and_rerank") as retrieved:
    r = client.post("/query", json={
        "question": "q", "mode": "single_doc", "doc_ids": ["GhostDoc"]})
    check("status 404", r.status_code, 404)
    check("no retrieval attempted", retrieved.called, False)

banner("POST /query — 422 invalid input")
r = client.post("/query", json={"question": "q", "mode": "sideways", "doc_ids": ["DocA"]})
check("bad mode -> 422", r.status_code, 422)
r = client.post("/query", json={"question": "q", "mode": "legal", "doc_ids": []})
check("empty doc_ids -> 422", r.status_code, 422)
r = client.post("/query", json={"question": "", "mode": "legal", "doc_ids": ["DocA"]})
check("empty question -> 422", r.status_code, 422)
r = client.post("/query", json={"mode": "legal", "doc_ids": ["DocA"]})
check("missing question -> 422", r.status_code, 422)

banner("POST /query — 503 all providers exhausted, with Retry-After")
exhausted = AllProvidersExhaustedError(
    ["RAG_Groq:openai/gpt-oss-20b"], RuntimeError("503 UNAVAILABLE"))
with patch("api.service.vector_store.count_points", return_value=9), \
     patch("api.service.retrieve_and_rerank", return_value=CHUNKS), \
     patch("api.service.generate_answer", side_effect=exhausted):
    r = client.post("/query", json={
        "question": "q", "mode": "single_doc", "doc_ids": ["DocA"]}, )
    check("status 503", r.status_code, 503)
    check("Retry-After header present", "retry-after" in {k.lower() for k in r.headers}, True)
    check("Retry-After value", r.headers["retry-after"], "60")
    detail = r.json()["detail"]
    check_true("message names the condition", "unavailable" in detail.lower())
    check_true("no traceback leaked", "Traceback" not in detail)

banner("POST /query — 503 embedding unavailable, DISTINCT message")
with patch("api.service.vector_store.count_points", return_value=9), \
     patch("api.service.retrieve_and_rerank",
           side_effect=EmbeddingUnavailableError("Gemini embedding call failed")):
    r = client.post("/query", json={
        "question": "q", "mode": "single_doc", "doc_ids": ["DocA"]})
    check("status 503", r.status_code, 503)
    detail = r.json()["detail"]
    check_true("mentions embedding", "embedding" in detail.lower())
    check_true("distinct from provider-exhaustion message",
               "answer providers" not in detail.lower())

banner("Leak checks — no server paths, no tracebacks, no key material")
with patch("api.service.vector_store.count_points", return_value=9), \
     patch("api.service.retrieve_and_rerank",
           side_effect=RuntimeError("boom at C:\\Users\\secret\\data\\uploads\\x.pdf")):
    r = safe_client.post("/query", json={
        "question": "q", "mode": "single_doc", "doc_ids": ["DocA"]})
    check("unexpected error -> 500", r.status_code, 500)
    detail = r.json()["detail"]
    check_true("no server path in body", "uploads" not in detail and "C:\\" not in detail)
    check_true("no traceback in body", "Traceback" not in detail)
    check_true("no raw exception text", "boom" not in detail)

# sanitize_message is what strips paths out of the messages that DO
# get surfaced (413 / 422 / job errors).
from api.errors import sanitize_message  # noqa: E402

check("sanitize strips a Windows path",
      sanitize_message("Failed to open PDF 'C:\\Users\\me\\data\\uploads\\a.pdf': bad"),
      "Failed to open PDF 'a.pdf': bad")
check("sanitize strips a POSIX path",
      sanitize_message("No content extracted from '/home/me/data/uploads/b.txt'."),
      "No content extracted from 'b.txt'.")

print("\n" + "=" * 70)
print(f"RESULT: {passes} passed, {failures} failed")
print("=" * 70)
sys.exit(1 if failures else 0)
