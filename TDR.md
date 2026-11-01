# Technical Design Report (TDR)
## Project: DocSense — Unified Document Intelligence & Q&A Platform

**Version:** 1.0 (V1 Scope)
**Companion document to:** PRD.md
**Status:** Stages 1–6 built and verified; Stage 7 (evaluation framework) built; Stage 8 (API layer) complete; Stage 9 not started
**Last Updated:** 2026-11-01 (Section 2k extended: the authorised multi_doc Stage 6 exception and its live check, the judge-only re-grade and its caveat, and NVIDIA's intermittent timeouts. Earlier the same day: Section 2k added — Stage 7 follow-up: per-document retrieval guarantee and opening chunk for legal/multi_doc, three judge rules, grader independence, and the measured before/after results; Section 2f's status now points to 2k. Previously 2026-10-28: Section 2j added — Stage 8 FastAPI layer: endpoint shapes, single-process/narrow-lock concurrency model, asynchronous ingestion, error mapping, and the two approved exceptions to "no changes in earlier stages". Previously 2026-10-27: documentation synced to the code as built: Stage 7 module list corrected to the three real dataset files and the actual verdict scale, Evaluation tech-stack row corrected — RAGAS is not called, Stage 8/9 marked not started. Section 2i, added 2026-10-26, documents the move of answer generation and grading from the Gemini-only model chain to rotation across 7 independent providers; embeddings and image reading stay on Gemini)

---

## 1. Architecture Overview

```
                    ┌─────────────────────┐
                    │   Uploaded Document  │
                    │   (PDF / DOCX / TXT) │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │   Stage 1: Ingestion  │
                    │   (text + image       │
                    │    extraction, per    │
                    │    page)              │
                    └──────────┬───────────┘
                               │
              ┌────────────────┴────────────────┐
              │                                  │
     ┌────────▼─────────┐              ┌─────────▼──────────┐
     │ Stage 2: Text     │              │ Stage 3: Image      │
     │ Chunking          │              │ Analysis Branch     │
     │ (semantic/legal)  │              │ (vision LLM →       │
     │                   │              │  text description)  │
     └────────┬─────────┘              └─────────┬──────────┘
              │                                   │
              └────────────────┬──────────────────┘
                                │
                     ┌──────────▼───────────┐
                     │ Stage 4: Embedding +  │
                     │ Vector Store          │
                     │ (tagged with doc_id,  │
                     │  page_num, type)      │
                     └──────────┬───────────┘
                                │
        User Question ─────────┤
                                │
                     ┌──────────▼───────────┐
                     │ Stage 5: Retrieval +  │
                     │ Re-ranking (mode-     │
                     │ aware: single/multi/  │
                     │ legal)                │
                     └──────────┬───────────┘
                                │
                     ┌──────────▼───────────┐
                     │ Stage 6: Answer       │
                     │ Generation w/         │
                     │ Mandatory Citation    │
                     └──────────┬───────────┘
                                │
                     ┌──────────▼───────────┐
                     │ Stage 8: API Layer    │
                     └──────────┬───────────┘
                                │
                     ┌──────────▼───────────┐
                     │ Stage 9: Frontend UI  │
                     │ (built LAST)          │
                     └───────────────────────┘

Stage 7 (Evaluation Framework) runs parallel to Stages 5–6 during development.
```

---

## 2. Tech Stack (V1)

| Layer | Tool | Justification |
|---|---|---|
| PDF parsing | `PyMuPDF` (fitz) | Reliable per-page text + image extraction |
| Scanned PDF OCR | `Tesseract` (via `pytesseract`) | Free, well-documented, sufficient for V1 |
| DOCX parsing | `python-docx` | Standard, preserves structure |
| TXT parsing | Native Python | No dependency needed |
| Chunking | `LlamaIndex` `SemanticSplitterNodeParser` + custom regex splitter for legal mode | Semantic chunking improves retrieval accuracy over fixed-size chunking |
| Embeddings | ~~`voyage-3` (Voyage AI)~~ → **Google Gemini embedding API (free tier, `gemini-embedding-001` @ 768 dims)** — see Section 2a. Local `BGE` is available but **opt-in only**, not an automatic fallback — see Section 2h | Keeps embeddings on the same free provider as vision/generation. The originally-specified `bge-large-en-v1.5` (1024-dim) and the implemented `bge-small-en-v1.5` (384-dim) both mismatch the 768-dim collection, so switching backends requires a full corpus re-embed (Section 2h) |
| Vector database | `Qdrant` (self-hosted via Docker) | Strong metadata filtering (doc_id, page_num, type) needed for multi-mode retrieval |
| Re-ranking | `bge-reranker-v2-m3` (local, free) | Improves precision of top-k retrieved chunks before generation |
| Vision analysis | ~~Claude (Sonnet) vision API~~ → **Google Gemini API (free tier)** — see Section 2a | Free-tier alternative with no billing setup required; Claude remains the documented target for a future upgrade |
| LLM (generation + grading) | ~~Claude (Sonnet/Haiku)~~ → ~~Google Gemini API only~~ → **rotation across 7 OpenAI-compatible providers** (Groq, NVIDIA, Cohere, OpenRouter, Gemini; SiliconFlow and OpenCode Console configured but disabled) — see Section 2i | Gemini's sibling Flash-tier models share capacity and failed together, leaving 5 of 11 Stage 7 questions unmeasured. Independent vendors remove that shared-fate risk. Embeddings and image reading deliberately stay on Gemini |
| Orchestration | `LlamaIndex` (`CitationQueryEngine` as base, customized) | Built specifically for citation-grounded Q&A |
| Backend API | `FastAPI` | Async support, clean OpenAPI docs, easy to wire to a future frontend |
| Evaluation | ~~`RAGAS`~~ → **custom scoring script** (`evaluation/run_eval.py` + `evaluation/llm_judge.py`) | Two separately-reported metrics: a deterministic per-document retrieved-page check, and LLM-as-judge answer correctness on a fixed verdict scale. RAGAS is **not** called by the code — it stays in `requirements.txt` and remains a candidate for continuous faithfulness/relevancy scoring later. Deviation recorded in `run_eval.py`'s module docstring |
| Frontend (Stage 9 only) | `Streamlit` | Fastest path to a usable demo UI |

---

## 2a. Provider Substitution Decision (Documented Deviation)

**Decision date:** 2026-09-19
**Status:** Active for V1 build

TDR originally specified **Claude (vision + generation)** and **Voyage AI (embeddings)** as paid API providers. Since Anthropic/Voyage billing was not set up at build time, the following substitution was made to keep the build moving without any cost:

| Original (TDR spec) | Substituted with (V1 build) | Applies to |
|---|---|---|
| Claude (Sonnet) vision API | **Google Gemini API** (free tier, no credit card) | Stage 3 — Image Analysis |
| `voyage-3` (Voyage AI) embeddings | **Google Gemini embedding API** (free tier) — local `BGE` remains an acceptable fallback | Stage 4 — Embedding & Storage |
| Claude (Sonnet/Haiku) generation | **Google Gemini API** (free tier) | Stage 6 — Answer Generation |

**Reasoning:** One consistent, free provider across every LLM-calling stage avoids a mid-build billing dependency and keeps the entire V1 pipeline cost-free to build and test.

**What stays unchanged:** the prompt templates (Section 5), the data schema (Section 3), the image-filtering/cost-control logic (Section 6), and every module's responsibilities (Section 4) are identical regardless of provider. Only the actual API call inside each module (`image_analyzer.py`, `embed_chunks.py`, `answer_with_citations.py`) targets Gemini instead of Claude/Voyage.

**Swap-back plan:** because the provider-specific API call is isolated inside each module rather than spread across the codebase, switching back to Claude/Voyage later (if billing is set up) should only require changing the API client and key inside these three files — not a redesign.

**Credentials:** `GEMINI_API_KEY` is stored locally in `.env` (see `.env.example` for the template) and is never committed to GitHub (excluded via `.gitignore`) or shared in chat/agent conversations.

---

## 2b. Qdrant Deployment Substitution (Documented Deviation)

**Decision date:** 2026-09-19 (Stage 4 build)
**Status:** Active for V1 build

TDR originally specified **self-hosted Qdrant via Docker** (Section 2). Docker is not installed in the local build environment, so Qdrant's **local embedded mode** is used instead for V1.

| Original (TDR spec) | Substituted with (V1 build) |
|---|---|
| Qdrant server, self-hosted via Docker (`qdrant/qdrant` container, accessed over HTTP) | Qdrant **embedded/local mode** — the same `qdrant-client` Python package, run in-process with `QdrantClient(path="...")`, persisting to a local folder instead of talking to a server |

**Reasoning:** avoids requiring Docker to be installed just to build and test Stages 4–6 locally. It is still genuinely Qdrant — same client library, same collection/metadata-filtering API (`doc_id`, `page_num`, `type`, `doc_type` remain filterable exactly as specified) — only the deployment target changes.

**What stays unchanged:** the collection schema, metadata filtering behavior, and every module's responsibilities (Section 4) are identical regardless of deployment mode. Retrieval code (Stage 5) is written against the `qdrant-client` API, which behaves the same whether backed by a local path or a remote server.

**Swap-back plan:** the Qdrant client is only constructed in one place (`embedding/vector_store.py`). Switching to a Dockerized or hosted Qdrant server later means changing that one client initialization (`QdrantClient(path=...)` → `QdrantClient(url=..., api_key=...)`) — no other module needs to change.

---

## 2c. Chunking Algorithm & Document-Type Classification (Documented Deviation)

**Decision date:** 2026-09-20 (retroactively documented; decisions made during Stage 2 build)
**Status:** Active for V1 build

### Chunking algorithm substitution

TDR originally specified LlamaIndex's `SemanticSplitterNodeParser` for general/multi-doc chunking (Section 2). That splitter determines chunk boundaries by embedding sentences and cutting where embedding distance jumps — which requires an embedding model at chunk time.

| Original (TDR spec) | Substituted with (V1 build) |
|---|---|
| LlamaIndex `SemanticSplitterNodeParser` (embedding-based semantic chunking) | Custom, dependency-free structure-aware splitter (`chunking/text_chunker.py`): splits on paragraph boundaries, greedily packs paragraphs up to a target character size, falls back to sentence-level splitting for oversized paragraphs, and applies a small overlap between adjacent chunks to preserve cross-boundary context |

**Reasoning:** Stage 4 (Embedding & Vector Storage) is where an embedding model is first introduced in this pipeline. Making Stage 2 (Chunking) depend on Stage 4's embedding model would create a backwards dependency and add embedding-API cost/latency to what should be a purely structural step. A structure-aware splitter keeps Stage 2 self-contained.

**What stays unchanged:** the chunk schema (Section 3), the legal-mode clause-splitting approach (`legal_chunker.py`, unaffected by this decision), and every downstream module's responsibilities are identical regardless of chunking algorithm.

**Revisit trigger:** if Stage 7 evaluation shows retrieval accuracy is weaker than expected on general/financial/research documents, semantic chunking (now feasible since Stage 4's embedding model exists) is the first thing to try as a replacement.

### Document-type classification (undocumented in original TDR)

TDR references `doc_type` (legal | financial | research | general) throughout — as a required chunk schema field (Section 3) and as a retrieval filter (Section 4, Stage 5: "legal: filter doc_type == legal") — but never specifies how a document's `doc_type` should actually be determined.

**V1 build:** `chunking/doc_type_classifier.py` — a lightweight, dependency-free heuristic combining filename hints (e.g., "cuad", "contract", "arxiv") with keyword and structural-signal scoring (e.g., "Abstract"/"References" headings strongly indicate research papers, weighted higher than incidental keyword mentions) over the first few pages of extracted text. Defaults to `general` when no strong signal is found.

**Reasoning:** this is a genuine gap in the original spec, not a substitution of a specified approach — `doc_type` needs to be determined somewhere before chunking/retrieval can use it, so this module fills that gap.

**Revisit trigger:** if a document is ever misclassified during Stage 7 evaluation (e.g., a legal document routed to the general chunker), consider upgrading to an LLM-based classifier — the heuristic is isolated to this one module, so swapping it out doesn't touch the chunkers or any downstream stage.

---

## 2d. Multi-Key Rotation for Free-Tier Quota Management (Documented Deviation)

**Decision date:** 2026-09-20 (Stage 6 build)
**Status:** Active for V1 build/testing only — see "Not a production solution" below

### The problem

Google's Gemini free tier caps `gemini-2.5-flash` at 20 `generate_content` requests per day, and this quota is enforced **per Google Cloud project**, not per API key or per Google account. Stage 6 testing exhausted the single-project quota after only a handful of test cases (each question makes one generation call, on top of the calls already made during Stage 3 image analysis and any repeated Stage 4/6 testing in the same day).

### The substitution

| Original setup | V1 build (testing/dev only) |
|---|---|
| One `GEMINI_API_KEY`, one Google Cloud project, 20 requests/day | Up to 7 independent Google Cloud projects, each with its own API key (`GEMINI_API_KEY` through `GEMINI_API_KEY_7` in `.env`), giving up to 140 requests/day combined |

**Implementation:** `generation/gemini_key_rotation.py` — a single shared helper, `call_with_key_rotation()`, that every Gemini call site (`ingestion/image_analyzer.py` — Stage 3, `embedding/embed_chunks.py` — Stage 4, `generation/answer_with_citations.py` — Stage 6) now routes through. Each call site still constructs its own `genai.Client` and makes its own specific API call (vision, embedding, or generation) — the helper only supplies which key to try next. On a `429 RESOURCE_EXHAUSTED` error, it automatically retries the same call with the next configured key, cycling through all configured keys before giving up. Any non-quota error (e.g., a malformed request) is NOT retried with a different key, since a different key wouldn't fix a bad request — it's raised immediately.

**Reasoning:** keeping the rotation logic in one small, shared file — rather than duplicating retry logic in each of the three call sites — satisfies "small, contained change, not spread across the codebase." Each call site's own code changed only enough to delegate its actual API call through the shared helper.

**What stays unchanged:** every module's responsibilities, prompt content, output schema, and the individual Gemini API calls themselves (vision, embedding, generation) are all unchanged. Only *which key* is used, and the retry-on-429 behavior, are new.

### Not a production solution

This is explicitly a **testing/development-volume workaround**, not a scalable or production-grade rate-limiting strategy. It works because V1's testing volume (a handful of manual test-script runs per day) fits within 140 requests/day. It does NOT address:
- Real production traffic, which would need a paid Gemini tier (or Claude/Voyage, per Sections 2a/2b) with proper rate limits, not multiple free-tier projects
- Concurrent/parallel request handling, load balancing, or per-key usage tracking
- Any guarantee that Google's terms of service permit this pattern at scale (fine for personal development/testing volume; not something to carry into a real deployment)

**Revisit trigger:** before any production deployment, or before Stage 8's API layer is exposed to real (non-test) traffic, replace this with a proper paid-tier plan or the documented Claude/Voyage swap-back (Sections 2a/2b) — key rotation across free-tier projects should not be the production answer key management strategy.

---

## 2e. Gemini Model Change: gemini-2.5-flash → gemini-3.6-flash (Documented Deviation)

**Decision date:** 2026-09-22 (Stage 6 build/testing)
**Status:** Active for V1 build — applies to Stage 3 (vision) and Stage 6 (generation) only. Stage 4 (embeddings, `gemini-embedding-001`) is a separate model family and is explicitly NOT changed by this decision — see "Scope" below.

### The problem

Section 2d's multi-key rotation setup added 6 new Google Cloud projects/API keys specifically to get around `gemini-2.5-flash`'s 20-requests/day free-tier quota. During live Stage 6 testing, calls made with the newer keys failed with:

```
404 NOT_FOUND: This model models/gemini-2.5-flash is no longer available to
new users. Please update your code to use models/gemini-3.6-flash for the
latest features and improvements.
```

This meant rotation had nowhere useful to go on a 429 — the newer keys couldn't serve the request at all, for an unrelated reason (new-project model eligibility, not quota), which defeated the entire point of Section 2d's setup.

### Model history for this project (full log, since this is the second model change)

| Model | Status | Why it stopped being used |
|---|---|---|
| `gemini-2.0-flash` | Shut down by Google | Used initially in Stage 3; deprecated before Stage 3 testing was complete — replaced with `gemini-2.5-flash` |
| `gemini-2.5-flash` | Stable, but not available to new API keys/projects | Used through Stages 3 and 6 build; blocks the 6 newer keys added in Section 2d with a 404, defeating multi-key rotation |
| `gemini-3.6-flash` | **Current — adopted here** | Confirmed Stable (not preview/experimental) via `ai.google.dev/gemini-api/docs/models/gemini-3.6-flash`; confirmed to support both text and image input (`Supported data types: Text, Image, Video, Audio, and PDF`); confirmed actually callable — via a direct live API test, not assumption — on one of the newer keys (`GEMINI_API_KEY_2`/`GEMINI_API_KEY_3`) for both a text-only call and an image+text (vision) call |

### The change

| File | Old default | New default |
|---|---|---|
| `ingestion/image_analyzer.py` (`GEMINI_VISION_MODEL`) | `gemini-2.5-flash` | `gemini-3.6-flash` |
| `generation/answer_with_citations.py` (`GENERATION_MODEL`) | `gemini-2.5-flash` | `gemini-3.6-flash` |

**Scope — what is NOT changed:** `embedding/embed_chunks.py` (Stage 4) continues to use `gemini-embedding-001` unchanged. `gemini-3.6-flash` is a text/vision generation model, not an embedding model, so it is not a substitute for Stage 4's embedding model family — this was a deliberate scope decision (Stage 4 is left as-is until/unless it independently hits an access problem, at which point its embedding model choice would be evaluated on its own terms, not swapped to match Stage 3/6 by default).

**What stays unchanged:** the prompt content, the citation cross-check logic (Section 6, this file), the vision prompt/output-parsing format (Stage 3), the chunk/answer schemas (Section 3), and every module's responsibilities — this is purely a model-string swap inside two `os.getenv(..., default)` calls, both already designed to be overridable via `GEMINI_VISION_MODEL` / `GEMINI_GENERATION_MODEL` env vars without a code change.

**Revisit trigger:** if `gemini-3.6-flash` is ever deprecated or restricted the same way `gemini-2.0-flash` and `gemini-2.5-flash` were, check `ai.google.dev/gemini-api/docs/models` for the current Stable model in the same tier before swapping again — and verify new-key access with a direct live test (not just checking the docs list it) before adopting, per the process followed here.

---

## 2f. Known Limitation: multi_doc Mode Can Exclude a Requested Document Entirely (Addressed in Section 2k)

**Flagged date:** 2026-09-24 (Stage 6 manual test run)
**Status:** Addressed in Section 2k (2026-11-01). With the per-document retrieval guarantee, all 12 coverage queries had full coverage: **12 of 12**, against 5 of 12 before. That is a retrieval-only measurement on those 12 queries; the full suite has not been re-run with the change. The section below is kept as the original record.

### The problem

In `multi_doc` mode, `retrieve_and_rerank()` retrieves candidates across all requested `doc_id`s, then reranks and returns a single global top-k (default 5) across all of them combined (`retrieval/reranker.py`, `retrieval/pipeline.py`). There is no guarantee that every requested document contributes at least one chunk to that top-k — if one document's chunks all score lower than another document's, that document can be completely absent from the final answer, even though the user explicitly asked to compare it.

**Observed:** manually testing the multi_doc case ("What do these contracts say about termination?" across `CUAD_GRIDIRONBIONUTRIENTS_INC...SUPPLY_AGREEMENT`, `CUAD_XLITECHNOLOGIES_INC...STRATEGIC_ALLIANCE_A`, and `SampleServices_MSA_Contract`), all 5 returned sources came from only 2 of the 3 requested documents — `CUAD_XLITECHNOLOGIES_INC...STRATEGIC_ALLIANCE_A` was entirely absent from the answer. The same 3-document query already showed this pattern in Stage 5's own test results, confirming this is a retrieval/ranking behavior, not something introduced by Stage 6's generation or citation logic.

### Why this is deferred, not fixed now

This is a ranking-policy question (should multi_doc guarantee per-document representation, and if so how many chunks minimum per document, at what cost to overall relevance ranking), not a bug with an obvious one-line fix. Stage 7's evaluation framework is the right place to measure how often this actually degrades answer quality across a labeled test set, before choosing a fix.

**Candidate fixes to evaluate during Stage 7** (Section 2k implemented both):
- Widen the multi_doc candidate pool before reranking (retrieve more per-document candidates, so a lower-scoring document still has chunks in play).
- Guarantee at least 1 chunk per requested `doc_id` in the final top-k (e.g., reserve one slot per document, fill remaining slots by global rank).

**Revisit trigger:** during Stage 7 evaluation, specifically test multi_doc queries against documents with uneven chunk-relevance scores (mirroring the case above) and measure how often a requested document is fully excluded from the final answer. If this happens often enough to measurably hurt multi_doc accuracy on the labeled eval set, implement one of the candidate fixes above before Stage 8.

---

## 2g. Known Gap: Generation-Level Absence Detection Is Not Yet Covered By Any Correctness Eval Entry

**Flagged date:** 2026-09-24 (Stage 7 eval dataset construction — user manual review)
**Status:** Known gap — no correctness entry exists yet; candidate for a dedicated eval entry later.

### The gap

Section 2f above measures a RETRIEVAL-level question: does a requested document contribute at least one chunk to the retrieved set at all? A distinct, GENERATION-level question is not yet measured by any answer-correctness entry: when a requested document genuinely has no relevant content for the question asked, does the generation layer correctly say so (e.g., "not found for this document") rather than either (a) hallucinating an answer for that document, or (b) silently omitting any mention of it with no indication that it was checked and found lacking?

**How this surfaced:** while building the multi_doc correctness entry for "What do these contracts say about termination?", `CUAD_XLITECHNOLOGIES_INC...STRATEGIC_ALLIANCE_A` was found to have no termination clause at all (confirmed against the raw PDF — its relevant page contains only an indemnity clause). Including it in that entry would have required the LLM judge to grade a composite 3-part answer (two real clauses plus one correct absence) against a single `correct`/`partially_correct`/`incorrect` verdict — exactly the grading ambiguity the fixed verdict scale (see evaluation/llm_judge.py) is meant to avoid. It was removed from that entry's `doc_ids` for this reason (see evaluation/eval_dataset_supplement.json's `note` field on that entry) and kept only in the separate, ungraded multi-doc coverage stress test (`evaluation/multi_doc_queries.json`'s `md_01`), which checks retrieval-level coverage only, not whether generation correctly reports the absence.

### Why this is a gap, not a bug

No code currently claims to handle this correctly or incorrectly — it is simply unmeasured. `generation/confidence_check.py`'s `answer_indicates_not_found` (see this module) can detect when the LLM says nothing was found, but nothing in the current eval set specifically asks "the answer should mention document X was checked and has no relevant content, while still answering correctly for the other document(s) in the same multi-doc question."

**Candidate for later:** a dedicated eval entry (or a small set of them) using a question deliberately scoped to include one clearly-irrelevant document alongside one or more clearly-relevant ones, with a verdict scale (or a separate boolean check) specifically for "did the answer correctly acknowledge the irrelevant document's absence of content, without hallucinating a false clause for it and without silently pretending it wasn't asked about." This likely needs its own grading rubric rather than reusing the single-clause `correct`/`partially_correct`/`incorrect` scale as-is, since "correctly identifying an absence" is a different judgment than "correctly summarizing present content."

**Revisit trigger:** if multi_doc mode's real-world usage shows the generation layer hallucinating content for a document that has none (as opposed to just under-representing it at retrieval, per Section 2f), build the dedicated eval entry described above rather than continuing to defer it.

---

## 2h. Embedding Fallback Was Unsafe — Dimension & Vector-Space Mismatch (FOUND AND FIXED)

**Found date:** 2026-09-25 (during a Stage 7 API-call-count audit)
**Status:** **FIXED** — not a deferred limitation. See "The fix" below.

### The problem

`embedding/embed_chunks.py`'s `_embed_texts()` wrapped its Gemini call in a bare `except Exception` and, on *any* failure, silently fell back to the local model (`LOCAL_FALLBACK_MODEL`). This was unsafe in three independent ways:

1. **Dimension mismatch.** The implemented local model, `BAAI/bge-small-en-v1.5`, emits **384-dim** vectors. The Qdrant collection is created at **768** (`embedding/vector_store.py`'s `VECTOR_SIZE`, matching `EMBEDDING_OUTPUT_DIMENSIONALITY`). A triggered fallback therefore produced vectors that physically cannot be upserted into or searched against the existing collection — surfacing as an opaque Qdrant dimension error far from the real cause, rather than as "Gemini was unavailable."

2. **Vector-space mismatch** — the deeper issue, and *not* fixable by padding/projecting to 768 or by swapping in a natively-768-dim local model. Embeddings are only comparable within one model's own vector space. A query embedded by BGE, searched against chunks embedded by Gemini, produces cosine scores that are arithmetically valid but semantically meaningless — i.e. **silently wrong retrieval results**, which is strictly worse than a loud failure. Mixing embedding models inside one collection is incoherent regardless of dimensionality.

3. **Bare `except Exception` masked unrelated bugs.** Any `TypeError`, `KeyError`, `ImportError` etc. originating in our own code was swallowed and misreported as "Gemini unavailable, falling back" — meaning a genuine defect could hide indefinitely behind a misleading warning.

**Spec discrepancy also noted:** this file's Tech Stack table (Section 2) originally specified `BAAI/bge-large-en-v1.5` as the fallback, which is **1024-dim** — also not 768. So neither the specified model nor the implemented one matched the collection; the mismatch originated in the spec, not only in the implementation. The table has been corrected.

**Never actually triggered in practice:** across all Stage 4/5/6/7 runs to date the Gemini embedding API remained available, so this path never executed. It came close during the 2026-09-24/25 `gemini-3.6-flash` congestion — generation calls were exhausting all 7 keys while `gemini-embedding-001` kept serving normally. Had the embedding model been congested too, the run would have failed with a confusing dimension error instead of a clear outage message.

### The fix

Chose **fail cleanly over pad/project**, because padding would only hide problem #2 — it converts a storable-but-meaningless vector into exactly the silent-wrongness failure mode this project's citation cross-checking exists to prevent. A coherent local-embedding setup requires the *entire* corpus and every subsequent query to use the same model, which makes it a deliberate corpus-wide configuration decision, not an automatic mid-run switch.

| Before | After |
|---|---|
| Any exception → silent fallback to local model | Gemini-unavailability → raises new `EmbeddingUnavailableError` with explicit guidance; no automatic fallback |
| Bare `except Exception` | Narrowed to `genai_errors.APIError` (parent of ClientError/ServerError), `httpx.TimeoutException`, `httpx.ConnectError`, plus `RuntimeError` for the no-keys-configured case. Everything else propagates untouched |
| Local model reachable implicitly, as a fallback | Opt-in only, via `DOCSENSE_EMBEDDING_BACKEND=local`, documented as requiring a full corpus re-embed into a matching collection |
| Dimensionality never checked | New `_assert_dimensionality_matches()` validates output against `EMBEDDING_OUTPUT_DIMENSIONALITY` on both backends, failing immediately with a message naming the offending model and both dimensions |

**Verified locally** (mocked Gemini call, zero API calls) across 6 cases: 384-dim rejected with both dimensions named; 768-dim accepted; a simulated 503 raises `EmbeddingUnavailableError` *and* provably does not invoke the local model; a network timeout raises the same; and — the key narrowing check — an injected `TypeError` propagates intact rather than being converted into a spurious "Gemini unavailable."

**What stays unchanged:** the embedding model itself (`gemini-embedding-001` at 768 dims), the chunk schema (Section 3), `vector_store.py`'s `VECTOR_SIZE`, and every downstream module's behaviour on the normal (Gemini-available) path.

**Revisit trigger:** if local embeddings are ever genuinely needed (offline development, Gemini permanently unavailable), set `DOCSENSE_EMBEDDING_BACKEND=local`, recreate the Qdrant collection at the local model's own dimensionality, and re-embed every document — do not mix backends within one collection.

---

## 2i. Multi-Provider Rotation for Answer Generation & Grading (Documented Deviation)

**Decision date:** 2026-10-26
**Status:** Active for V1 build/testing. Supersedes Section 2e's model chain **for answer calls only** — Sections 2a/2d still govern embeddings and image reading.

### The problem

Section 2d added 7 Gemini keys to survive per-project quota, and Section 2e pinned a 2-tier model chain (`gemini-3.8-flash` → `gemini-3.7-flash`). Both tiers are Google Flash-tier models and therefore **share capacity**. The live Stage 7 run of 2026-10-06 showed them failing together: 3.8 and 3.7 returned 503 within seconds of each other on the same key, repeatedly, and a single generation call could sweep all 7 keys × 2 models without success. **5 of 11 questions went unmeasured** before the run was stopped. Rotating keys or sibling models within one vendor cannot fix a vendor-wide capacity event — only rotating *vendors* can.

### The substitution

| Call site | Before | After |
|---|---|---|
| Stage 6 generation (`generation/answer_with_citations.py`) | 7 Gemini keys × 2 Gemini models | 7 independent providers, 1 pinned model each |
| Stage 7 grading (`evaluation/llm_judge.py`) | same Gemini chain | same provider rotation |
| Stage 4 embeddings (`embedding/embed_chunks.py`) | `GEMINI_API_KEY..._7` | **unchanged** |
| Stage 3 image reading (`ingestion/image_analyzer.py`) | `GEMINI_API_KEY..._7` | **unchanged** |

New module: `generation/provider_rotation.py`. `GENERATION_MODELS` and `GRADING_MODELS` are removed (they would be dead configuration that looks live).

**All 7 providers are OpenAI-compatible**, verified live: each answered `GET /models` with HTTP 200 and accepts `POST /chat/completions` in OpenAI shape — including Cohere via `/compatibility/v1` and Gemini via `/v1beta/openai`. So one `httpx.post` serves all of them and **Cohere needs no special-case adapter**, which was not obvious beforehand. **No new dependency was added**: `httpx` is already present transitively via `google-genai`; the `openai` and `cohere` SDKs were deliberately not introduced.

### Rotation behaviour

- **Sticky**: a question goes to the current provider and that provider keeps serving every subsequent question until it fails.
- **No partial resume**: on failure the next provider re-answers the *same* question from scratch, reusing the already-retrieved chunks. A half-finished answer is discarded entirely.
- **Cooldown by error class**: 429 → 900s (quota windows do not clear in seconds); 503/504/network timeout/empty response → 60s; **401/402/403 → provider removed for the whole session** with a loud log line (an invalid key or a spent balance does not resolve mid-run); prompt-too-long → skipped for *that question only*, with no cooldown, since the provider is healthy for shorter prompts.
- **An empty response is a failure.** Observed live: `openrouter/free` returned HTTP 200 with 0 characters after 20.9s. Accepting it would feed an empty string to the citation parser and surface as "no valid citations", indistinguishable from a bad answer. **A genuine negative finding is not a failure** — a provider answering "the contract does not state X" is a valid, useful answer and is returned verbatim; the absence-detection concern in Section 2g depends on such answers surviving.
- **Total exhaustion** raises `AllProvidersExhaustedError`, a subclass of `AllModelsAndKeysExhaustedError`, so Stage 7 keeps recording the question as `not_measured` and excluding it from accuracy rates rather than scoring it as wrong. No silent fallback to a disabled or cooled-down provider.
- Results record **both** `provider_used` and `model_used`. For the `openrouter/free` alias the served model is read back out of the response body, because the alias routes to an arbitrary free model per request and recording the alias would say nothing about what produced the answer.

### Provider table (verified 2026-10-26)

| Order | Provider | Model | Enabled | Live result |
|---|---|---|---|---|
| 1 | `RAG_Groq` | `openai/gpt-oss-20b` | yes | OK 0.8s; citations accepted both modes |
| 2 | `RAG_NVIDIA` | `minimaxai/minimax-m3.1-flash` | yes | OK 0.9s; citations accepted both modes |
| 3 | `RAG_Cohere` | `command-r-08-2024` | yes | OK 1.8s; citations accepted single_doc |
| 4 | `RAG_OpenRouter` | `openrouter/free` | yes | OK 1.4s; **empty response** on legal mode |
| 5 | `RAG_Gemini` | `gemini-3.8-flash` (pinned, not the `-latest` alias) | yes | **1 success in 5 attempts**; four 45s timeouts |
| — | `RAG_SiliconFlow` | `Qwen/Qwen2.5-7B-Instruct` | **no** | HTTP 402, signup credit exhausted |
| — | `RAG_OpenCode_Console` | `deepseek-v4.1-flash` | **no** | free models HTTP 403 (client-gated), paid HTTP 402 |

Disabled providers are never called and emit one startup line explaining why, so a short rotation list is never mistaken for a bug.

### Known limitations

1. **Only 2-4 of the 7 providers were dependable at test time.** All 7 keys authenticate, but SiliconFlow and OpenCode Console cannot serve a request at all, and Gemini failed 4 of 5 attempts. The design is sized for 7; the usable pool is currently much smaller, so rotation has less headroom than the provider count suggests.
2. **Embeddings and image reading remain single-vendor.** They stay on the Gemini key pool, so a Gemini-wide outage still blocks retrieval (every query needs one embedding call) even when answer generation has four healthy alternatives. This is the largest remaining shared-fate risk.
3. **Citation formats differ by model.** The parser accepted every provider that emitted `(Source N)` and discarded zero citations, but adherence is a per-model behaviour, not a guarantee. Cohere declined to cite on the legal question and OpenRouter returned nothing at all. Verdicts and citation counts are therefore **not strictly comparable across providers**, which is why `provider_used` is recorded on every result.
4. **Documents pass through several third-party providers.** Retrieved contract text is now sent to whichever vendor is active — Groq, NVIDIA, Cohere, OpenRouter or Google. For the public CUAD/sample documents used here that is acceptable, but it is a real data-handling change: confidential documents would be distributed across five external processors, each with its own retention and training policy. Review before using this on anything non-public.
5. **Free-tier terms of service.** Cohere trial keys are explicitly **non-commercial** and capped at **1,000 calls/month**; OpenRouter free models are limited to roughly **20 requests/minute and 50 requests/day** (1,000/day only after a credit purchase). Running an evaluation suite repeatedly can plausibly exhaust these. Depending on free tiers for anything beyond development volume is not appropriate.
6. **Unverified limits.** Context windows for `openai/gpt-oss-20b`, `minimaxai/minimax-m3.1-flash` and `gemini-3.8-flash` could **not** be confirmed from official documentation. Groq's and NVIDIA's current free-tier quotas are also **unverified** — Groq's official rate-limit page returned no usable content, and third-party sources for NVIDIA actively conflict (1,000 credits / 40 RPM versus "unlimited requests, no daily limits"). Treat all four as unknown rather than assuming a value.

### Not a production solution

Same caveat as Section 2d, now spread across more vendors: this is a development-volume workaround that trades single-vendor fragility for multi-vendor free-tier fragility. It does not provide an SLA, cost control, consistent output quality, or a single data processor.

---

## 2j. Stage 8 API Layer — Shape, Concurrency & Two Approved Exceptions

**Decision date:** 2026-10-28
**Status:** Active for V1 build. Implements Section 4's Stage 8 module; adds no logic to Stages 1–6.

### Scope

`api/` wraps the existing pipeline and contains no pipeline logic of its own. `api/service.py` is the only module that imports Stages 1–6, so the route handlers stay transport-only and the planned per-user-key work has one file to change rather than five endpoints to audit. **No key is read anywhere in `api/`** — keys stay in `generation.gemini_key_rotation` (embeddings, vision) and `generation.provider_rotation` (generation, grading), exactly as the pipeline reads them today. There is no auth and no bring-your-own-key yet.

| File | Responsibility |
|---|---|
| `api/main.py` | app, CORS, routes |
| `api/schemas.py` | pydantic request/response models |
| `api/service.py` | pipeline calls, job registry, upload handling |
| `api/errors.py` | exception → HTTP mapping, message sanitising |
| `api/test_stage8_api.py` | mocked verification, zero API calls |

### Endpoints

`GET /health` · `POST /documents` (202) · `GET /documents/jobs/{job_id}` · `GET /documents` · `DELETE /documents/{doc_id}` · `POST /query`

The query response is always returned in full — `question`, `mode`, and three groups (`core`, `evidence`, `meta`). There is deliberately **no request flag to trim it**; the Stage 9 UI decides what to display. `evidence.sources` lists *every* retrieved chunk with its `source_number`; the UI highlights the cited ones by matching against `core.citations`. Response fields are projections of the existing types — `RankedChunk` for evidence, `AnswerResult` for `provider_used`/`model_used`/`warning`.

### Two approved exceptions to "no changes in earlier stages"

**1. `_extract_valid_citations` is imported from Stage 6 into `api/service.py`.** `AnswerResult.sources` is the *cited subset* and carries no source number, but the `(Source N)` markers in the answer refer to a chunk's 1-based position in the list handed to the prompt. Recovering N requires the same parser Stage 6 validated with. Importing Stage 6's own function guarantees the API's numbering cannot drift from Stage 6's; re-implementing the regex would create a second source of truth. The alternative — adding `source_number` to `SourceInfo` — would have changed Stage 6. Stage 6 is unchanged.

**2. `list_documents()` was added to `embedding/vector_store.py`.** Qdrant has no "distinct values" query and no listing function existed. It lives in `vector_store` rather than `api/` because that module is deliberately the single place the Qdrant client is constructed and touched, and putting the scroll there preserves that property instead of reaching into `_get_client()` from the API layer. It is read-only, scrolls payloads with vectors excluded, and aggregates in Python. **It adds a function and changes no existing behaviour.**

### Concurrency: one process, narrow lock

The local embedded Qdrant store holds an exclusive file lock, so **the API must run as a single process**:

```
uvicorn api.main:app --port 8000
```

No `--workers`, and critically **no `--reload`** — reload spawns a reloader plus a worker, and the second process dies with "Storage folder data/vector_store is already accessed by another instance". For the same reason the API must not run alongside `evaluation/run_eval.py`. The README previously documented `--reload`; that was wrong and has been corrected.

Route handlers are plain `def`, not `async def`: every pipeline call is blocking, so Starlette runs them in its threadpool and the event loop is never blocked.

A `threading.RLock` was added to `vector_store` and wraps **only the Qdrant client calls**. It is never held across an embedding, vision or generation call — one such call was measured at 39.9s under provider congestion, and serialising those would let a single slow request stall every other request. CPU-only work between client calls (filter construction, payload copying) is also outside the lock. RLock rather than Lock because `upsert_chunks()` calls `ensure_collection()`, which takes the same lock. `GET /health` takes no lock and makes no Qdrant or provider call at all, so it stays answerable while a slow request is in flight.

### Ingestion is asynchronous

`POST /documents` returns **202** with a `job_id` and runs Stages 1–4 on a `ThreadPoolExecutor(max_workers=1)`; `GET /documents/jobs/{job_id}` reports `queued`/`running`/`done`/`failed`. Synchronous was rejected: a document costs one vision call per unique image plus embedding calls, and a single provider call has been measured at ~40s, so the request would outlive normal client timeouts with no progress signal. `max_workers=1` also keeps the single-writer property. Stdlib only — no new dependency. **Known limitation:** the job registry is in-memory, so job records are lost on restart (the ingested chunks themselves are durable in Qdrant).

### Error mapping

| Condition | Status |
|---|---|
| `AllModelsAndKeysExhaustedError` (and its `AllProvidersExhaustedError` subclass) | 503 + `Retry-After: 60` |
| `EmbeddingUnavailableError` | 503, deliberately distinct message |
| `UnsupportedFileTypeError` | 415 |
| upload > 25 MB | 413 |
| unknown `doc_id` / `job_id` | 404 |
| invalid input, or `DocumentParsingError` | 422 |
| anything else | 500, fixed generic message |

The 25 MB cap sits far above the sample corpus while still refusing uploads that would make ingestion run unboundedly long. Three rules hold for every handler: no stack traces, no server filesystem paths, no key material. Ingestion exceptions embed the absolute upload path in their message, so messages pass through `sanitize_message()`, which reduces any path to its basename. The catch-all 500 reveals nothing at all — not even the exception type. Uploads are written to `data/uploads/`, already gitignored. CORS is restricted to localhost origins, since the API has no auth.

An unknown `doc_id` on `/query` returns 404 **before** any provider call, so a bad request costs nothing.

### Verification

`api/test_stage8_api.py`: **66 mocked assertions, zero API calls** — every endpoint, every error mapping above, the `Retry-After` header, provider exhaustion, an empty-retrieval query (returns 200 with empty citations and evidence rather than crashing), citation-numbering parity against Stage 6's real parser including an out-of-range marker being discarded, and leak checks asserting no path, traceback or raw exception text reaches a response body.

Live: **3 API calls** — one `POST /query` (1 embedding + 1 generation) and one tiny TXT upload (1 embedding), followed by job polling, list, delete and delete-verification, none of which cost a call.

### Not a production solution

Single process, no auth, no rate limiting, in-memory job state, and one-at-a-time Qdrant access. Correct for V1 and the Stage 9 UI; all four need revisiting before any real deployment, alongside Section 2d's and 2i's existing free-tier caveats.

---

## 2k. Retrieval Guarantees, Judge Rules & Grader Independence (Stage 7 Follow-up)

**Decision date:** 2026-11-01
**Status:** Active for V1 build. Addresses the Section 2f coverage gap for the evaluated set. `single_doc` retrieval, the legal and single_doc prompts, absence detection and citation parsing are unchanged. The multi_doc prompt and output cap changed under an authorised Stage 6 exception (see the end of this section).

### What the first full Stage 7 run showed

The run of 2026-10-31 (`evaluation/results/eval_results_20261031T164332Z.json`) measured all 23 questions: 12 correct, 7 partially_correct, 4 incorrect. Page-level retrieval was 21/23; 5 of the 12 coverage queries had full coverage (25 of 32 requested documents). The transcripts showed three separate problems:

1. **Whole documents dropped (Section 2f).** `multi_doc` took one global top-5 across all requested documents, so a document whose chunks all scored lower got no context at all.
2. **Opening-page facts missing.** Titles, parties and dates sit in a contract's opening chunk, and the global top-5 did not always include it. Q1 (XLI document name) and Q23 (parties across two contracts) both failed page-level retrieval because XLI's page 1 was missing.
3. **Grading.** The judge could mark down an answer that reproduced a blank placeholder (`August __, 2019`) or quoted the expected text after a hedge, and nothing stopped a `multi_doc` answer being graded `correct` while a requested document went unaddressed. Rotation is sticky, so **every one of the 23 questions was graded by the provider that wrote the answer** (Groq for Q1–Q5, Cohere for Q6–Q23).

### Retrieval changes (`retrieval/retriever.py`, `retrieval/pipeline.py`)

**Candidates.** For `legal` and `multi_doc`, `retrieve()` adds each requested document's opening chunk (lowest page, text before image, lowest chunk index; `find_opening_chunk()`), and for `multi_doc` each document's own top 5 candidates (`MULTI_DOC_CANDIDATES_PER_DOC`). These reuse the one query vector with local Qdrant reads through the existing `search()`, sized by `count_points(doc_id)`, so **no extra embedding call is made**. That is a full scan of each requested document: cheap at V1 scale (5–19 chunks per sample document), and worth revisiting for long documents.

**Selection.** The whole pool is reranked, so every pick has a real `rerank_score` for `confidence_check`. `_select_context()` then picks in priority order under a hard cap of **8 chunks** (`MAX_CONTEXT_CHUNKS`):

| Priority | Mode | Pick |
|---|---|---|
| 1 | multi_doc | each document's best chunk |
| 2 | legal, multi_doc | each document's opening chunk |
| 3 | multi_doc | next-best chunks until each document has 2 (`MIN_CHUNKS_PER_DOC`; the opening chunk counts) |
| 4 | legal, multi_doc | the global top-5, as before |

The result is sorted by `rerank_score`, and the source number is still the chunk's position in the prompt list. `single_doc` keeps the old path exactly (`rerank(..., top_k=5)`).

**Rejected:** calling `retrieve()` once per document, which costs one embedding call per document; adding a new `vector_store` function, since `search()` already filters by `doc_id`.

**Trade-offs.** Prompts get longer (up to 8 chunks), so per-minute token limits, Groq's in particular, are reached sooner. A single-document legal question always keeps the old top-5 (5 + 1 opening chunk ≤ 8). With 4 documents, priorities 1–2 alone can fill the cap, so part of the old global top-5 can be dropped (md_10 ends at 2 chunks per document, 8 in total). The guarantee itself is bounded by the cap: every document gets at least two chunks only up to 4 documents, and at least one up to 8. Above 8 requested documents, some get none.

### Judge rules (`evaluation/llm_judge.py`)

The grading prompt gains a `{grading_rules}` block that takes precedence over the general guidance:

1. **Blank placeholders.** If the expected answer contains a blank such as `__` and the answer reproduces it as it appears in the source, that is correct.
2. **Verbatim quotes.** Quoting the expected text verbatim (ignoring case and whitespace) is correct, even after a hedge.
3. **`multi_doc` only.** The answer must address each requested document with clear attribution, otherwise the verdict cannot be `correct`. The judge also gets a source → document map ("Source 1 = …"), because answers cite by `(Source N)` and would otherwise look unattributed.

### Grader independence (`generation/provider_rotation.py`, `evaluation/llm_judge.py`, `evaluation/run_eval.py`)

`call_with_provider_rotation()` takes `avoid_providers`, and `grade_answer()` passes the writer. The grader is the first eligible provider other than the writer. The writer is used only as a last resort, with a log line saying so. Avoid-mode calls never move the sticky index, so grading cannot pull generation off its provider. Cooldowns and session removals stay shared, because they describe provider health. Each record now carries `grader_independent` (`None` for not_measured records). The change is about 20 lines of `provider_rotation.py`.

### Measured results

**Retrieval only: 23 questions and coverage queries md_01–md_10, no generation.** These numbers were **tallied from partial logs**: the script's own summary never flushed before that run was cancelled, so they come from its per-question log lines, not from a saved results file. The "before" figures are from the 2026-10-31 results JSON, not from re-running the old algorithm.

| Metric | Before | After |
|---|---|---|
| Page-level retrieval | 21/23 | **23/23** (Q1 and Q23 now reach page 1) |
| Average context, all 23 questions | 5.00 | 5.61 (legal 5.53, single_doc 5.00, multi_doc 6.67) |

**Coverage, md_01–md_12.** md_01–md_10 come from the cancelled retrieval-only run's logs, md_11–md_12 from the re-check below. Chunks per document are in `doc_ids` order.

| Query | Docs | Before | After | Context | Chunks per doc |
|---|---|---|---|---|---|
| md_01 | 3 | gap | full | 8 | 2 / 2 / 4 |
| md_02 | 2 | full | full | 7 | 2 / 5 |
| md_03 | 3 | gap | full | 7 | 2 / 2 / 3 |
| md_04 | 3 | full | full | 8 | 3 / 3 / 2 |
| md_05 | 2 | full | full | 7 | 3 / 4 |
| md_06 | 3 | gap | full | 8 | 2 / 4 / 2 |
| md_07 | 2 | gap | full | 7 | 2 / 5 |
| md_08 | 2 | full | full | 6 | 4 / 2 |
| md_09 | 2 | gap | full | 7 | 5 / 2 |
| md_10 | 4 | gap | full | 8 | 2 / 2 / 2 / 2 |
| md_11 | 3 | gap | full | 8 | 4 / 2 / 2 |
| md_12 | 3 | full | full | 8 | 2 / 3 / 3 |
| **Total** | 32 | **5/12 full, 25/32 docs** | **12/12 full, 32/32 docs** | avg 7.4 (before 5) | |

**11-question re-check (2026-11-01, 292 s).** The 11 questions that were not `correct` in the 2026-10-31 run (Q1, Q6, Q8, Q10, Q12–Q16, Q21, Q23) ran through `run_question()` with the new retrieval and judge rules. Calls: 13 embeddings (11 questions plus md_11 and md_12) with no failures, and 23 answer-provider attempts, of which one failed (an NVIDIA 429; Cohere graded that question instead). 35 calls were planned.

| Q | Mode | Verdict before → after | Writer before → now | Grader now | Answer contains expected text |
|---|---|---|---|---|---|
| Q1 | legal | incorrect → **correct** | Groq → Groq | NVIDIA | yes |
| Q6 | legal | incorrect → **correct** | Cohere → Groq | NVIDIA | yes |
| Q8 | legal | partially_correct → partially_correct | Cohere → Groq | NVIDIA | no |
| Q10 | legal | partially_correct → **correct** | Cohere → Groq | NVIDIA | yes |
| Q12 | legal | incorrect → **correct** | Cohere → Groq | NVIDIA | yes |
| Q13 | legal | partially_correct → **correct** | Cohere → Groq | NVIDIA | yes |
| Q14 | legal | incorrect → **correct** | Cohere → Groq | NVIDIA | yes |
| Q15 | legal | partially_correct → **correct** | Cohere → Groq | NVIDIA | no (writes `August __ , 2019`, with an extra space) |
| Q16 | legal | partially_correct → partially_correct | Cohere → Groq | Cohere | no |
| Q21 | multi_doc | partially_correct → partially_correct | Cohere → Groq | Cohere | expected answer is a paraphrase; all 3 key facts present |
| Q23 | multi_doc | partially_correct → **correct** | Cohere → Groq | Cohere | expected answer is a paraphrase; all 4 parties named |

For these 11 questions the verdicts went from 0 correct / 7 partially_correct / 4 incorrect to 8 / 3 / 0. `grader_independent` was true for all 11. In the 2026-10-31 run it would have been false for all 23.

What this re-check can and cannot attribute:

- **The writer changed for 10 of the 11 questions** (Cohere → Groq: this process started on Groq and Groq stayed healthy). Most verdict changes therefore mix retrieval, judge-rule, writer and grader effects.
- **Q1** is the cleanest retrieval case: same writer, and the only context change is the added opening chunk, which the answer cites.
- **Q12:** the title appears only in the opening chunk, which the old context lacked. The new answer cites it.
- **Q6 and Q14:** the context was the same as before (the opening chunk was already in the old top-5), so the change came from the writer.
- **Judge rules (Q8, Q10, Q15, Q16):** Q8 and Q16 did not change, and their new answers are weaker. Q8 quotes the "executed this Agreement as of the date below" line and stops before the signature dates; Q16 says no expiration date is given. In both cases the missing text was in the retrieved context (checked against the stored chunks: Gridiron `p5_c0` holds "Date: 1/27/2020", TransMontaigne `p4_c1` holds "This Agreement shall remain in effect until terminated by the Parties"). Q10 became correct, but its new answer does not hedge, so rule 2 was not exercised. Q15 became correct with the same quoted sentence as before, and the grader's reason cites the blank placeholder. That is consistent with rule 1, but the writer and grader also changed. The judge-only re-grade below grades the old answers again with the current judge.
- **Substring-check caveat.** The retrieval-only run's "expected text found in the retrieved context" check (11/11 short expected answers) is weak evidence for the document-name questions. For Q1 and Q6 the title also appears in repeated page headers (`…SUPPLY AGREEMENT (cont'd)`), so the check passes without the opening chunk. Only Q12's title depends on the opening chunk.
- **Q21's cut-off answer:** it stopped mid-table. The live check in the Stage 6 exception at the end of this section points to the 1024-token output cap, and that exception addresses it.
- **Not re-run:** the 12 questions that were already correct, so any regressions among them are unmeasured.

**Judge-only re-grade (2026-11-01).** The 2026-10-31 answers for Q8, Q10, Q15 and Q16 were graded again with the current judge: 4 grading calls, with Groq grading Cohere's answers, so every grade was independent. All four moved from partially_correct to correct. This re-grade changed both the judge prompt (the three rules above) and the grader (Cohere grading its own answers before, Groq now), so the two effects cannot be separated. The four old answers are the cases the rules target: Q15 reproduced the blank date, and Q8, Q10 and Q16 hedged before quoting the expected text verbatim. For Q8 and Q16, the old Cohere answers now grade correct while the re-check's new Groq answers did not, so on those two questions the change of writer made the answers worse.

**Not claimed.** No answer-quality improvement is claimed beyond what the 11-question re-check and the judge-only re-grade above show. The full 23-question suite has not been re-run with the new retrieval and judge rules.

**Mocked verification:** 38/38 checks on the new retrieval, judge-rule and avoid-provider logic (a throwaway script, since deleted), and the Stage 8 suite `api/test_stage8_api.py` still passes 66/66.

### Authorised Stage 6 exception: multi_doc prompt and output cap

**Decision date:** 2026-11-01. **Scope:** multi_doc only, in `generation/prompt_templates.py` and `generation/answer_with_citations.py`.

**Reason.** In the 11-question re-check, Q21's answer called seven sources from two contracts "all four documents" and stopped mid-table. The live check below shows the size involved: Groq counts reasoning inside its output tokens, and Q21's new answer used 1,100 output tokens, 764 of them reasoning, which is more than the old cap of 1,024.

**What changed:**

- **Source headers: unchanged.** They already name the document, as its file name: `[Source N | <file name> | Page X]`.
- **Instruction, appended** to the multi_doc instruction with the original sentence kept: "Several sources can come from the same document, and each Source label names its document. Refer to each document by its name, and never describe or count sources as documents. Give short bullets per document, grouped under that document's name. Do not use tables."
- **Output cap:** `MULTI_DOC_MAX_OUTPUT_TOKENS = 2048`, for multi_doc generation only. legal and single_doc keep the rotation default of 1,024, and grading is unchanged.
- **Not touched:** the legal and single_doc prompts (byte-identical to the previous commit), the "say so explicitly" absence wording (Section 2g), and the citation parser.

**Provider acceptance of 2,048,** checked before the change:

| Provider | Evidence | Status |
|---|---|---|
| Groq `openai/gpt-oss-20b` | Groq model page: max output 65,536; the live Q21 call accepted 2,048 | confirmed |
| Cohere `command-r-08-2024` | Cohere docs: max output 4,000 | docs |
| Gemini `gemini-3.8-flash` | model card: 64K output | docs |
| OpenRouter `openrouter/free` | live probe: HTTP 200, finished normally | confirmed for the model the router picked |
| NVIDIA `minimaxai/minimax-m3.1-flash` | four probes got no response within 45–90 s, one of them at 1,024 | not confirmed |
| SiliconFlow, OpenCode (both disabled) | SiliconFlow docs allow up to the context length; no official OpenCode limit found | never called |

The cap stays at 2,048 by decision: four of the five enabled providers are confirmed, and NVIDIA failed by not responding, not by rejecting the value. If a provider does reject it, the existing rotation rule applies: a 400 that mentions `max_tokens` counts as "prompt too long" and skips that provider for that question only.

**Verification.** Mocked: `api/test_stage8_api.py` 66/66 (it runs the real citation parser), plus 13 throwaway checks: the legal and single_doc prompts are byte-identical to the previous commit, only multi_doc sends 2,048, and the parser reads the new bullet format.

Live, Q21 and Q23 through `run_question()`: 8 attempts against 6 planned and a cap of 14. The 2 extra attempts were NVIDIA grading timeouts that rotation absorbed. Groq wrote both answers and Cohere graded both.

- **Q21:** bullets under each document's file name, no table, and "Both documents" in the comparison, with no wrong document count. It finished normally (`finish_reason: stop`) at 1,100 output tokens, 764 of them reasoning. Verdict correct, up from partially_correct in the re-check. Its comparison bullets shorten the names to "CUAD" and "SampleServices". That is unambiguous here, but "CUAD" is the dataset prefix shared by three of the sample contracts.
- **Q23:** names all four parties under the two documents' file names and finished normally at 697 output tokens, 395 of them reasoning. Verdict correct.

**Known limitation: NVIDIA times out intermittently.** On 2026-11-01 NVIDIA graded the re-check's questions in about 2.5 s each and then returned a 429. That evening it gave no response to six requests in a row: four probes (45–90 s each, one of them at the 1,024 cap) and both grading calls in the live check (45.4 s each). Rotation absorbed every timeout with a 60-second cooldown, and Cohere graded instead, but each timeout added about 45 s to its question.

---

## 3. Data Schema (Core Contract Across All Stages)

Every chunk — whether derived from text or an image — must conform to this schema before being embedded and stored. This is the single most important contract in the system; all modules must read/write it consistently.

```json
{
  "chunk_id": "docA_p4_c2",
  "doc_id": "docA",
  "doc_name": "Contract_A.pdf",
  "doc_type": "legal | financial | research | general",
  "page_num": 4,
  "section": "4.2 Termination",
  "type": "text | image",
  "image_type": "chart | diagram | table | photo | null",
  "text": "The extracted or vision-generated text content of this chunk.",
  "source_image_path": "null or path if type == image"
}
```

### API response schema (answer output)

```json
{
  "answer": "Either party may terminate this agreement with thirty (30) days written notice.",
  "mode": "single_doc | multi_doc | legal",
  "answer_style": "full | summary",
  "sources": [
    {
      "doc_name": "Contract_A.pdf",
      "page_num": 6,
      "section": "4.2 Termination",
      "type": "text",
      "confidence": "high | medium | low"
    }
  ],
  "warning": "null or a string if confidence is low / info not found"
}
```

---

## 4. Module Breakdown

### Stage 1 — Ingestion (`ingestion/`)
- `text_parser.py`: extracts text per page (PDF/DOCX/TXT), returns `[{page_num, text}]`
- `image_extractor.py`: extracts embedded images per page using `PyMuPDF`, filters decorative images by size (<100x100px) before passing downstream
- `ocr_fallback.py`: runs Tesseract on scanned pages when `text_parser.py` returns near-empty text for a page

### Stage 2 — Chunking (`chunking/`)
- `text_chunker.py`: semantic chunking for general/multi-doc mode
- `legal_chunker.py`: regex/heading-based clause splitting (e.g., detects "Section X.X", "Article X") for legal mode
- Output: list of chunk dicts conforming to the schema in Section 3

### Stage 3 — Image Analysis (`ingestion/image_analyzer.py`)
- Sends filtered images to the vision LLM with a strict, factual prompt (see PRD Section 9 for expected style)
- **V1 build uses Google Gemini's vision API (free tier)** — see Section 2a for the documented substitution from Claude
- Classifies image_type (chart/diagram/table/photo) either via prompt output or a lightweight heuristic
- Converts vision output into a schema-conformant chunk (`type: "image"`)
- The Gemini API call is isolated in this file so swapping back to Claude later is a contained change

### Stage 4 — Embedding & Storage (`embedding/`)
- `embed_chunks.py`: batches all chunks (text + image) through the embedding model. **V1 build uses Google Gemini's embedding API (free tier)** — see Section 2a; local `BGE` (`sentence-transformers`) remains an acceptable fallback if preferred
- `vector_store.py`: handles Qdrant collection creation, upsert, and metadata indexing (doc_id, page_num, type, doc_type must be filterable fields)

### Stage 5 — Retrieval (`retrieval/`)
- `retriever.py`: mode-aware retrieval
  - `single_doc`: filter by one `doc_id`
  - `multi_doc`: retrieve across all `doc_id`s in the session, group by source
  - `legal`: filter `doc_type == legal`, boost `section`-tagged chunks, smaller top-k for precision
- `reranker.py`: re-scores retrieved chunks with `bge-reranker-v2-m3`, returns top 3–5

### Stage 6 — Generation (`generation/`)
- `prompt_templates.py`: holds the mode-specific and style-specific (full/summary) prompt templates described in PRD Section 9
- `answer_with_citations.py`: assembles labeled context (`[Source N | Page X]`), calls the LLM, parses citations back against actual retrieved metadata (never trust the LLM's own page-number memory — always cross-check against what was actually retrieved). **V1 build uses Google Gemini's API (free tier)** — see Section 2a for the documented substitution from Claude
- `confidence_check.py`: flags low-confidence answers (e.g., low similarity score on retrieved chunks, or LLM stating "not found")

### Stage 7 — Evaluation (`evaluation/`) — BUILT

Updated to match the code as built. The original entry named a single
`eval_dataset.json` and RAGAS metrics; neither matches the implementation.

- **Datasets** (three, not one):
  - `data/eval/cuad_sample_eval.json` — the original labeled set (Section 9). Every entry is `mode: "legal"`.
  - `evaluation/eval_dataset_supplement.json` — added so the `single_doc` and `multi_doc` rows of the per-mode breakdown are not empty. `multi_doc` entries use **`expected_pages_by_doc`**, a `{doc_id: page}` mapping, because one clause can sit on a different page in each document being compared; a single `expected_page` int could not represent that. Single-doc/legal entries keep `expected_page` and are normalized into the same per-doc shape on load.
  - `evaluation/multi_doc_queries.json` — **12** coverage queries (`query_id`, `question`, `doc_ids`), with no expected answer. Used only for the multi-document coverage check that measures the Section 2f gap.
- `run_eval.py`: runs each question through retrieval and generation and reports **two separate metrics** — a deterministic retrieval check (did each requested `doc_id`'s own expected page appear among the chunks retrieved for that same `doc_id`; scored with `all()`, not `any()`), and LLM-graded answer correctness. Retrieval is measured via `retrieve_and_rerank()` directly, before generation runs, so a generation or citation fault is not blamed on retrieval. The retrieved chunks are then passed straight into `generate_answer()` rather than re-retrieving.
- `llm_judge.py`: LLM-as-judge grading on a **fixed verdict scale** — `correct` / `partially_correct` / `incorrect` — never free text, so verdicts are comparable and summarizable.
- **`not_measured`**: a fourth, deliberately separate outcome for a question that could not be graded at all (infrastructure failure). It sits outside the three-value grading scale and is **excluded from every accuracy rate**, because counting a provider outage as a wrong answer would make the headline numbers depend on vendor capacity. Each carries an `error_kind`: `all_models_and_keys_exhausted`, `embedding_unavailable`, or `other` (a genuine code defect).
- **Output**: a full per-question transcript (question, expected vs. generated answer, retrieved pages per document, verdict, reason, raw grader response, `provider_used`, `model_used`) written to a timestamped JSON under `evaluation/results/`, plus a human-readable console summary broken down by mode.
- **`--estimate-only`**: prints the API-call estimate and exits **without making any API calls**. Current dataset: **81** calls as a floor — **35** on the Gemini key pool (query embeddings for 23 questions + 12 coverage queries) and **46** on the answer providers (23 generation + 23 grading). A floor, not a ceiling: each retry is an additional real request.

### Stage 8 — API (`api/`) — BUILT (see Section 2j for the as-built detail)
- `main.py` (FastAPI): 
  - `POST /upload` — accepts file(s), runs Stages 1–4, returns `doc_id(s)`
  - `POST /query` — accepts `{question, doc_ids, mode, answer_style}`, runs Stages 5–6, returns the answer schema from Section 3
  - `GET /health` — basic status check

**Still under consideration, not implemented and no design decided:** letting users supply their own API keys instead of relying on the server's key pool. The Stage 8 build keeps all key access inside the rotation modules and confines pipeline access to `api/service.py`, so this remains a contained change rather than an endpoint-by-endpoint one — see Section 2j.

### Stage 9 — Frontend (`frontend/`) — built last — NOT STARTED (directory does not exist yet)
- `app.py` (Streamlit): file upload, mode selector, chat interface, citation display with expandable source text, inline image preview when an image-based source is cited

---

## 5. Prompt Templates (Reference)

**General Q&A:**
```
Context:
[Source 1 | Page 4]: "{chunk_text}"
[Source 2 | Page 7]: "{chunk_text}"

Answer the question using only the sources above.
Cite the page number for every claim using this format: (Page X).
If the answer is not in the sources, say so explicitly — do not guess.

Question: {user_question}
```

**Multi-document comparison:**
```
Context (from multiple documents):
[Source 1 | Contract_A.pdf | Page 4]: "{chunk_text}"
[Source 2 | Contract_B.pdf | Page 7]: "{chunk_text}"

Compare the excerpts above. Note where they agree and where they differ.
Cite the source document and page number for every point.

Question: {user_question}
```

**Legal/clause mode:**
```
Context:
[Source 1 | Page 6 | Section 4.2]: "{chunk_text}"

Quote the exact relevant clause verbatim. Do not paraphrase legal language.
Cite the page and section number. If the clause is not present, state that clearly.

Question: {user_question}
```

---

## 6. Non-Functional / Engineering Requirements

- **No hallucinated citations**: the generation layer must cross-check every page number the LLM cites against the actual metadata of retrieved chunks; discard/flag any mismatch.
- **Cost control on vision calls**: images below the size threshold, or matching a repeated-image hash (likely a logo), must be skipped before any vision API call.
- **Idempotent processing**: re-uploading the same document should not reprocess/re-embed it (hash the file, check against existing `doc_id`s).
- **Modular chunking**: chunking logic must be swappable per `doc_type` without touching the embedding/retrieval/generation layers.

---

## 7. Error Handling

| Scenario | Expected Behavior |
|---|---|
| Unsupported file type uploaded | Return a clear error listing supported types (PDF, DOCX, TXT for V1) |
| Scanned PDF with poor OCR quality | Flag the page as "low text confidence" in metadata; still attempt retrieval but surface a warning in the answer |
| No relevant chunks found for a question | Return "Not found in the provided document(s)" — never force an answer |
| Vision API failure on an image | Log and skip that image; do not fail the entire document processing job |
| Empty or corrupted document | Return a clear parsing error before attempting chunking/embedding |

---

## 8. Repository Structure

```
docsense/
├── ingestion/
│   ├── text_parser.py
│   ├── image_extractor.py
│   ├── image_analyzer.py
│   └── ocr_fallback.py
├── chunking/
│   ├── text_chunker.py
│   └── legal_chunker.py
├── embedding/
│   ├── embed_chunks.py
│   └── vector_store.py
├── retrieval/
│   ├── retriever.py
│   └── reranker.py
├── generation/
│   ├── prompt_templates.py
│   ├── answer_with_citations.py
│   └── confidence_check.py
├── evaluation/
│   ├── eval_dataset.json
│   └── run_eval.py
├── api/
│   └── main.py
├── frontend/            # built last (Stage 9)
│   └── app.py
├── data/
│   ├── sample_docs/      # test documents (see Section 9)
│   └── eval/             # evaluation Q&A set
├── .env                  # local secrets (GEMINI_API_KEY) — gitignored, never committed
├── .env.example           # template, safe to commit
├── requirements.txt
└── README.md
```

---

## 9. Datasets & Sample Resources (Testing & Evaluation Only — No Training)

DocSense requires **no training data**, since every model used is pre-trained and accessed via API or run locally as-is. The datasets below are used only for **(a) testing the pipeline during development** and **(b) measuring accuracy** via the Stage 7 evaluation framework.

| Dataset | Source | Used For | Relevant Stage |
|---|---|---|---|
| **CUAD (Contract Understanding Atticus Dataset)** | [atticusprojectai.org/cuad](https://www.atticusprojectai.org/cuad) — 500+ real contracts with expert-labeled clauses (termination, indemnification, etc.) | Test documents + ready-made Q&A pairs for **legal mode** evaluation | Stage 1 (test parsing), Stage 7 (evaluation) |
| **SEC EDGAR 10-K Filings** | [sec.gov/edgar](https://www.sec.gov/edgar/search/) — free public financial reports | Test documents for **general/financial Q&A mode**; realistic long PDFs with tables and charts | Stage 1, Stage 3 (charts), Stage 7 |
| **arXiv papers** | [arxiv.org](https://arxiv.org) (via public API, free to download) | Test documents for **multi-document comparison mode** (e.g., 3 papers on the same topic) | Stage 1, Stage 7 |
| **DocVQA dataset** | [docvqa.org](https://www.docvqa.org) — document images paired with human-written Q&A, includes charts/forms | Evaluation set for **image/chart understanding accuracy** (Stage 3) | Stage 3, Stage 7 |
| **FinQA / TAT-QA** | Public research datasets (financial QA with embedded tables) | Evaluation set for **table-as-image / financial chart precision** | Stage 3, Stage 7 |
| **Manually created eval set** | Built by you: 20–50 hand-written `{document, question, expected_answer, expected_page}` entries covering all 3 modes | Primary accuracy benchmark referenced in `evaluation/eval_dataset.json` | Stage 7 |

### Example `eval_dataset.json` entry format
```json
{
  "doc_id": "cuad_contract_012",
  "mode": "legal",
  "question": "What is the termination notice period?",
  "expected_answer": "30 days written notice",
  "expected_page": 6
}
```

### Notes for the agentic build
- Start with **5–10 documents** from CUAD and SEC EDGAR as the initial `data/sample_docs/` set — enough to build and sanity-check Stages 1–6 without overwhelming development time.
- Build `eval_dataset.json` incrementally: add 3–5 Q&A pairs per document as each stage becomes testable, rather than all at once at the end.
- DocVQA and FinQA are optional for V1 if time-constrained — the manually created eval set is sufficient to satisfy PRD Section 7's accuracy requirement.

---

## 10. Definition of Done (V1)

- [ ] Stages 1–6 run end-to-end via a script (no UI) on at least 5 sample documents
- [ ] All three modes (single-doc, multi-doc, legal) produce correctly cited answers
- [ ] Image-embedded charts/diagrams are detected, analyzed, and answerable
- [ ] `run_eval.py` produces an accuracy report ≥85% on the manual eval set
- [ ] FastAPI endpoints (`/upload`, `/query`) are functional and documented (OpenAPI/Swagger)
- [ ] Streamlit frontend built last, wired to the API, and demoable end-to-end
