# Technical Design Report (TDR)
## Project: DocSense — Unified Document Intelligence & Q&A Platform

**Version:** 1.0 (V1 Scope)
**Companion document to:** PRD.md
**Status:** Draft for Agentic Build (Kiro)
**Last Updated:** 2026-09-22 (Section 2e added — Gemini model change from gemini-2.5-flash to gemini-3.6-flash for Stages 3 and 6 documented)

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
| Embeddings | ~~`voyage-3` (Voyage AI)~~ → **Google Gemini embedding API (free tier)** — see Section 2a. Fallback: `BAAI/bge-large-en-v1.5` (local, free) remains available | Keeps embeddings on the same free provider as vision/generation; local fallback avoids any API dependency if preferred |
| Vector database | `Qdrant` (self-hosted via Docker) | Strong metadata filtering (doc_id, page_num, type) needed for multi-mode retrieval |
| Re-ranking | `bge-reranker-v2-m3` (local, free) | Improves precision of top-k retrieved chunks before generation |
| Vision analysis | ~~Claude (Sonnet) vision API~~ → **Google Gemini API (free tier)** — see Section 2a | Free-tier alternative with no billing setup required; Claude remains the documented target for a future upgrade |
| LLM (generation) | ~~Claude (Sonnet/Haiku)~~ → **Google Gemini API (free tier)** — see Section 2a | Same free-tier substitution as above, applied consistently across all LLM-calling stages |
| Orchestration | `LlamaIndex` (`CitationQueryEngine` as base, customized) | Built specifically for citation-grounded Q&A |
| Backend API | `FastAPI` | Async support, clean OpenAPI docs, easy to wire to a future frontend |
| Evaluation | `RAGAS` (open-source) + custom scoring script | Automates retrieval/answer accuracy scoring |
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

### Stage 7 — Evaluation (`evaluation/`)
- `eval_dataset.json`: the labeled test Q&A set (see Section 9 below)
- `run_eval.py`: runs each test question through the full pipeline, compares retrieved page vs. expected page, and answer correctness (via RAGAS metrics: faithfulness, answer relevancy, context precision)
- Outputs a simple accuracy report (percentage correct, per-mode breakdown)

### Stage 8 — API (`api/`)
- `main.py` (FastAPI): 
  - `POST /upload` — accepts file(s), runs Stages 1–4, returns `doc_id(s)`
  - `POST /query` — accepts `{question, doc_ids, mode, answer_style}`, runs Stages 5–6, returns the answer schema from Section 3
  - `GET /health` — basic status check

### Stage 9 — Frontend (`frontend/`) — built last
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
