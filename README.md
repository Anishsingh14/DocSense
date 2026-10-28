<div align="center">

# DocSense

**Unified document intelligence — upload any document, ask questions, get page-cited answers.**

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Gemini](https://img.shields.io/badge/Google_Gemini-Vision_%7C_Embeddings-4285F4?style=flat&logo=googlegemini&logoColor=white)](https://ai.google.dev/)
[![Providers](https://img.shields.io/badge/Answer_LLMs-7_provider_rotation-6E40C9?style=flat)](./TDR.md)
[![Qdrant](https://img.shields.io/badge/Qdrant-Vector_DB-DC244C?style=flat&logo=qdrant&logoColor=white)](https://qdrant.tech/)
[![Streamlit](https://img.shields.io/badge/Streamlit-Frontend-FF4B4B?style=flat&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat)](LICENSE)

**Build status:** Stages 1–6 complete and independently verified · Stage 7 evaluation framework built · Stage 8 API layer built · Stage 9 not started

</div>

---

## Overview

DocSense is a Retrieval-Augmented Generation (RAG) system that answers questions from uploaded documents — PDF, DOCX, or TXT — and always cites the **exact page number** the answer came from. It also analyzes **images embedded in documents** (charts, diagrams, tables-as-images) so visual content is just as answerable as text.

No model training is required. DocSense orchestrates pre-trained LLM, embedding, and vision models through a retrieval pipeline — it does not fine-tune anything.

## Features

- **Page-cited answers** — every response is grounded in the source document, with the page number attached
- **Three Q&A modes** from one unified pipeline:
  - **General** — single-document question answering
  - **Multi-document** — cross-document comparison and synthesis
  - **Legal** — exact clause retrieval with clause-level chunking, no paraphrasing
- **Image understanding** — charts, diagrams, and tables embedded in documents are analyzed and become searchable, with values verified accurate to the source
- **Precision re-ranking** — a cross-encoder reranker (`bge-reranker-v2-m3`) re-scores retrieved candidates before generation
- **Two answer styles** — full/verbatim or summarized
- **Built-in evaluation framework** — retrieval accuracy and answer correctness are measured separately against a labeled Q&A set, not eyeballed
- **Provider rotation** — answer generation and grading rotate across 7 OpenAI-compatible providers, so one vendor's outage does not stop a run

## Build Progress

| Stage | Status | What it does |
|---|---|---|
| 1 — Ingestion & Parsing | ✅ Complete | Extracts text + images per page from PDF/DOCX/TXT, with OCR fallback for scanned pages |
| 2 — Chunking | ✅ Complete | Splits text into retrievable chunks; clause-aware for legal documents |
| 3 — Image Analysis | ✅ Complete | Vision model analyzes embedded charts/diagrams into searchable descriptions |
| 4 — Embedding & Vector Storage | ✅ Complete | Converts chunks into vectors, stored in Qdrant with full metadata |
| 5 — Retrieval & Re-ranking | ✅ Complete | Mode-aware candidate retrieval, re-ranked for precision |
| 6 — Answer Generation | ✅ Complete | Generates the final cited answer from retrieved context |
| 7 — Evaluation Framework | ✅ Built | Two separately-reported metrics — a deterministic retrieved-page check and LLM-graded answer correctness on a fixed verdict scale — plus a multi-document coverage check |
| 8 — API Layer | ✅ Built | FastAPI endpoints for health, upload/ingest, list, delete and query |
| 9 — Frontend UI | ⏳ Not started | Streamlit interface, built last (`frontend/` does not exist yet) |

Every completed stage has been manually tested against 6 real sample documents (including real-world legal contracts from the [CUAD dataset](https://www.atticusprojectai.org/cuad)) and independently verified — not just accepted on the agent's word.

## Architecture

```
Document Upload
      │
      ▼
Ingestion (text + image extraction, per page)
      │
      ├──► Text Chunking (structure-aware / legal-clause aware)
      └──► Image Analysis (vision model → text description)
      │
      ▼
Embedding + Vector Storage (Qdrant, tagged by doc_id / page_num / type)
      │
      ▼
Retrieval + Re-ranking (mode-aware: single-doc / multi-doc / legal)
      │                    [query embedding → Gemini key pool]
      ▼
Answer Generation (mandatory page citation)
      │                    [7-provider rotation, sticky + cooldowns]
      ▼
Evaluation (retrieval accuracy + LLM-graded correctness)   ← Stage 7, built
      │
      ▼
FastAPI Layer (single process, one shared Qdrant client)   ← Stage 8, built
      │
      ▼
Streamlit UI                                               ← Stage 9, not started
```

Full architectural detail, module responsibilities, and data schemas are documented in [`TDR.md`](./TDR.md). Product scope and build stages are documented in [`PRD.md`](./PRD.md).

## Tech Stack

| Layer | Technology |
|---|---|
| PDF / DOCX parsing | PyMuPDF, python-docx |
| OCR (scanned documents) | Tesseract |
| Chunking | Custom structure-aware splitter + clause-aware legal chunker (documented deviation, TDR Section 2c) |
| Document-type classification | Lightweight heuristic classifier (filename + keyword + structural signals) |
| Image analysis (Stage 3) | **Google Gemini API** — model set by `GEMINI_VISION_MODEL`, default `gemini-3.6-flash` (documented substitution from Claude, TDR Section 2a) |
| Embeddings (Stage 4) | **Google Gemini API** — `gemini-embedding-001` at 768 dimensions. A local `BGE` backend exists but is **opt-in only** via `DOCSENSE_EMBEDDING_BACKEND=local`, never an automatic fallback (TDR Section 2h) |
| Answer generation + grading (Stages 6–7) | **Rotation across 7 OpenAI-compatible providers** via `generation/provider_rotation.py` (TDR Section 2i) — see the table below |
| Vector database | Qdrant, local embedded mode (documented deviation from Docker, TDR Section 2b) |
| Re-ranking | `bge-reranker-v2-m3`, loaded locally through `sentence-transformers`' `CrossEncoder` |
| HTTP client | `httpx` — all 7 answer providers speak the OpenAI-compatible `/chat/completions` REST API, so no per-vendor SDK is required |
| Backend API | FastAPI — single process, one shared Qdrant client (TDR Section 2j) |
| Evaluation | Custom scoring script — `evaluation/run_eval.py` + `evaluation/llm_judge.py`. **RAGAS is not called by the code**; it remains in `requirements.txt` as a candidate for continuous scoring later |
| Frontend | Streamlit *(Stage 9, not started)* |

### Answer providers (generation + grading)

Rotation is **sticky**: one provider serves every question until it fails, then the next provider re-answers that same question from scratch using the already-retrieved chunks. Failures put a provider on a cooldown whose length depends on the error class, and a `401`/`402`/`403` removes it for the rest of the session. Every result records both `provider_used` and `model_used`.

| Order | Env variable | Pinned model | Enabled |
|---|---|---|---|
| 1 | `RAG_Groq` | `openai/gpt-oss-20b` | yes |
| 2 | `RAG_NVIDIA` | `minimaxai/minimax-m3.1-flash` | yes |
| 3 | `RAG_Cohere` | `command-r-08-2024` | yes |
| 4 | `RAG_OpenRouter` | `openrouter/free` (alias — the model that actually served the request is recorded) | yes |
| 5 | `RAG_Gemini` | `gemini-3.8-flash` | yes |
| — | `RAG_SiliconFlow` | `Qwen/Qwen2.5-7B-Instruct` | no |
| — | `RAG_OpenCode_Console` | `deepseek-v4.1-flash` | no |

The two disabled providers are configured but never called, each logging one line explaining why. Flip `enabled=True` on their entry in `generation/provider_rotation.py` to bring them back in.

**Embeddings and image analysis deliberately stay on the Gemini key pool** and are not part of this rotation.

> **Note:** TDR.md originally specified Claude (vision + generation), Voyage AI (embeddings), Dockerized Qdrant, and RAGAS. Each was deliberately substituted during the V1 build, and every substitution is documented with its reasoning, what stays unchanged, and a trigger for reconsidering it. See [`TDR.md`](./TDR.md) Sections 2a–2i for the full decision log.

## Project Structure

Directories that exist today:

```
DocSense/
├── ingestion/                      # Stage 1 — text + image extraction, OCR fallback
│   ├── text_parser.py              #   PDF/DOCX/TXT parsing, page numbers preserved
│   ├── image_extractor.py          #   pulls embedded images out per page
│   ├── image_analyzer.py           #   Stage 3 — Gemini vision -> text description
│   ├── image_pipeline.py
│   ├── ocr_fallback.py             #   Tesseract, for near-empty (scanned) pages
│   └── pipeline.py
├── chunking/                       # Stage 2 — structure-aware + legal-clause chunking
│   ├── text_chunker.py
│   ├── legal_chunker.py
│   ├── doc_type_classifier.py      #   legal | financial | research | general
│   └── pipeline.py
├── embedding/                      # Stage 4 — embeddings + vector storage
│   ├── embed_chunks.py             #   Gemini embeddings; opt-in local BGE backend
│   ├── vector_store.py             #   Qdrant collection, metadata filtering
│   └── pipeline.py
├── retrieval/                      # Stage 5 — mode-aware retrieval + re-ranking
│   ├── retriever.py
│   ├── reranker.py
│   └── pipeline.py
├── generation/                     # Stage 6 — citation-grounded answer generation
│   ├── prompt_templates.py
│   ├── answer_with_citations.py    #   parses citations back against real metadata
│   ├── confidence_check.py
│   ├── provider_rotation.py        #   7-provider rotation for answer calls (TDR 2i)
│   ├── gemini_key_rotation.py      #   Gemini key pool for embeddings + vision
│   └── pipeline.py
├── evaluation/                     # Stage 7 — evaluation framework
│   ├── run_eval.py                 #   orchestrator; supports --estimate-only
│   ├── llm_judge.py                #   fixed-scale LLM-as-judge grading
│   ├── eval_dataset_supplement.json#   single_doc + multi_doc questions
│   └── multi_doc_queries.json      #   12 multi-document coverage queries
├── api/                            # Stage 8 — FastAPI layer
│   ├── main.py                     #   app, CORS, routes
│   ├── schemas.py                  #   request/response models
│   ├── service.py                  #   only module importing Stages 1-6
│   ├── errors.py                   #   exception -> HTTP mapping
│   └── test_stage8_api.py          #   mocked tests, zero API calls
├── data/
│   ├── sample_docs/                # 6 test documents (synthetic + real CUAD contracts)
│   ├── eval/                       # cuad_sample_eval.json — labeled Q&A set
│   ├── processed/                  # extracted images (gitignored)
│   ├── vector_store/               # local Qdrant storage (gitignored)
│   └── README_datasets.md
├── .env                            # Local keys — gitignored, never committed
├── .env.example                    # Template with empty values, safe to commit
├── PRD.md                          # Product Requirements Document
├── TDR.md                          # Technical Design Report (incl. deviations 2a–2i)
├── requirements.txt
└── README.md
```

Not created yet: `api/` (Stage 8) and `frontend/` (Stage 9). `evaluation/results/` is created on the first completed evaluation run and is gitignored.

## Getting Started

```bash
# Clone the repository
git clone https://github.com/<your-username>/docsense.git
cd docsense

# Install dependencies
pip install -r requirements.txt

# Create your local env file from the template, then fill in the keys you have
cp .env.example .env
```

### API keys

There are **two independent key groups**, and they are not interchangeable. Variable names are **case-sensitive** — copy them exactly. Windows environment variables happen to be case-insensitive, so a wrong case can appear to work locally and then break on Linux/macOS.

**1. Gemini key pool — embeddings (Stage 4) and image analysis (Stage 3)**

```
GEMINI_API_KEY
GEMINI_API_KEY_2 ... GEMINI_API_KEY_7
```

Each should belong to a **different Google Cloud project**, since Gemini's free-tier limits apply per project rather than per key — multiple keys from the same project add no headroom. `GEMINI_API_KEY` alone is enough to start. Retrieval depends on this group: every query needs one embedding call.

**2. Answer providers — generation (Stage 6) and grading (Stage 7)**

```
RAG_Gemini
RAG_Groq
RAG_NVIDIA
RAG_OpenRouter
RAG_SiliconFlow
RAG_Cohere
RAG_OpenCode_Console
```

One working key is enough to run; the rotation skips any provider whose key is missing. See the provider table above for which are enabled by default.

Optional variables, all with working defaults: `GEMINI_VISION_MODEL`, `DOCSENSE_EMBEDDING_BACKEND`, `QDRANT_COLLECTION`, `QDRANT_URL`, `QDRANT_API_KEY`.

Never commit `.env` — it is gitignored. Do not paste key values into issues, screenshots, or commit messages.

### Running it

```bash
# Per-stage manual test scripts
python -m ingestion.test_stage1_manual
python -m chunking.test_stage2_manual
python -m ingestion.test_stage3_manual
python -m embedding.test_stage4_manual
python -m retrieval.test_stage5_manual
python -m generation.test_stage6_manual

# Stage 8 — run the API (see the warning below about --reload)
uvicorn api.main:app --port 8000

# Stage 8 mocked tests (no API calls)
python -m api.test_stage8_api

# Stage 9 is not built yet:
#   streamlit run frontend/app.py     # frontend/ does not exist
```

Qdrant runs in local embedded mode by default — no separate database server needed. Note that it takes an exclusive lock on its storage directory, so only one process can use the vector store at a time.

## Verified Results So Far

A few concrete, independently-checked results from testing:

- **Chart understanding:** every value read off an embedded revenue chart (title, axis labels, all four data points) matched the source chart exactly
- **Legal clause precision:** exact clauses (e.g., "Termination for Convenience," "Indemnity") correctly isolated to their own chunk, with the correct page number, across both synthetic and real-world contracts
- **Retrieval confidence:** for an image-based question, the correct chart chunk was ranked ~160× higher than the next-best text chunk
- **Multi-document mode:** correctly surfaced relevant clauses from 3 different contracts in a single ranked list
- **Citation grounding:** generated answers were checked against the real page/section metadata of every source they cite, and the exact quoted text was cross-checked against the original source PDFs — no hallucinated pages, no dropped or fabricated citations

## API (Stage 8)

```bash
uvicorn api.main:app --port 8000
```

Interactive docs at `http://127.0.0.1:8000/docs`.

> **Run it as a single process.** Do not pass `--workers`, and do not pass `--reload`. The local embedded Qdrant store holds an exclusive file lock, and `--reload` spawns a second process which then fails with *"Storage folder data/vector_store is already accessed by another instance"*. For the same reason, don't run the API at the same time as `evaluation/run_eval.py`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness and configuration. Takes no lock, makes no Qdrant or provider call |
| POST | `/documents` | Upload a PDF/DOCX/TXT. Returns **202** with a `job_id`; ingestion runs in the background |
| GET | `/documents/jobs/{job_id}` | Ingestion status: `queued` / `running` / `done` / `failed` |
| GET | `/documents` | List stored documents with chunk and page counts |
| DELETE | `/documents/{doc_id}` | Delete a document's chunks |
| POST | `/query` | Ask a question in `single_doc`, `multi_doc` or `legal` mode |

Upload cap is 25 MB; uploads land in `data/uploads/` (gitignored). CORS is restricted to localhost origins. Errors map to 415 (unsupported type), 413 (too large), 404 (unknown `doc_id`/`job_id`), 422 (invalid input or unreadable document) and 503 (providers exhausted, or embeddings unavailable — with `Retry-After`). No response ever contains a stack trace, a server path, or key material.

**Query request**

```json
{ "question": "What is the termination notice period?",
  "mode": "single_doc",
  "doc_ids": ["SampleServices_MSA_Contract"],
  "answer_style": "full" }
```

**Query response** — the full response is always returned; the UI decides what to show. Below is a real response from a live call, with the evidence list truncated to 2 of the 5 chunks it returned:

```json
{
  "question": "What is the termination notice period?",
  "mode": "single_doc",
  "core": {
    "answer": "\"Either party may terminate this Agreement with thirty (30) days written notice to the other party.\" (Source 1)",
    "citations": [
      { "source_number": 1, "doc_name": "SampleServices_MSA_Contract.pdf", "page_num": 3 }
    ]
  },
  "evidence": {
    "sources": [
      { "source_number": 1, "doc_name": "SampleServices_MSA_Contract.pdf", "page_num": 3,
        "section": "4.2 Termination for Convenience",
        "text": "4.2 Termination for Convenience. Either party may terminate this Agreement with thirty (30) days\nwritten notice to the other party." },
      { "source_number": 2, "doc_name": "SampleServices_MSA_Contract.pdf", "page_num": 3,
        "section": "4.3 Termination for Cause",
        "text": "4.3 Termination for Cause. Either party may terminate this Agreement immediately upon written notice\nif the other party materially breaches this Agreement and fails to cure such breach within fifteen (15)\ndays of receiving written notice describing the breach." }
    ]
  },
  "meta": {
    "provider_used": "RAG_Groq",
    "model_used": "openai/gpt-oss-20b",
    "citation_check": { "valid_citations": 1, "discarded_citations": 0, "warning": null }
  }
}
```

`evidence.sources` carries **every** retrieved chunk with its `source_number`, cited or not — match `source_number` against `core.citations` to highlight the ones the answer actually used. `meta.citation_check` is Stage 6's own cross-check of the model's citations against what was really retrieved.

## Evaluation

Accuracy is measured, not assumed. The framework runs a labeled question set — including real, expert-annotated clause data from CUAD — through the full pipeline.

**Preview the API cost first.** `--estimate-only` prints the call breakdown and exits **without making a single API call**:

```bash
python -m evaluation.run_eval --estimate-only
```

For the current dataset that reports **81** calls as a floor: **35** against the Gemini key pool (query embeddings for 23 questions plus 12 coverage queries) and **46** against the answer providers (23 generation plus 23 grading). It is a floor rather than a ceiling, because every retry is an additional real request.

```bash
python -m evaluation.run_eval
```

Run it as a module (`-m`), not as a file path — it relies on package-relative imports.

**What gets reported**, as two separate metrics so a fault in one is never blamed on the other:

- **Retrieval accuracy** — deterministic, no LLM involved. For each requested document, did *that document's own* expected page appear among the chunks retrieved for it? Multi-document questions use a per-document `expected_pages_by_doc` mapping, because the same clause can sit on a different page in each contract, and a question only counts as correct if **every** requested document's page was found.
- **Answer correctness** — LLM-as-judge on a fixed scale of `correct` / `partially_correct` / `incorrect`, never free text, so verdicts stay comparable.

A question that could not be graded at all is recorded as **`not_measured`** with an `error_kind`, and is **excluded from every accuracy rate**. That outcome sits deliberately outside the three-value grading scale: counting a provider outage as a wrong answer would make the headline numbers reflect vendor capacity rather than pipeline quality.

Output is a full per-question transcript — expected versus generated answer, retrieved pages per document, verdict, reason, raw grader response, and the `provider_used` / `model_used` that served it — written to a timestamped JSON under `evaluation/results/`, alongside a readable console summary broken down by mode.

A separate set of **12 multi-document coverage queries** checks how often a requested document is left out of the retrieved context entirely, which is the known limitation recorded in TDR Section 2f.

## Roadmap

| Version | Scope |
|---|---|
| **V1** (in progress — Stages 1–8 built, UI remaining) | PDF, DOCX, TXT + embedded image analysis, 3 Q&A modes |
| V2 | PPTX, XLSX/CSV support |
| V3 | Password-protected PDFs, legacy `.DOC`, handwriting OCR |
| V4 | Multi-user support, persistent history, confidence scoring UI |

## Reliability

Free-tier APIs fail in ways that are easy to mistake for bugs, so a few things are deliberate:

- **Every API call has an explicit 45-second timeout.** The Google SDK applies no timeout by default, which meant a single stalled request could hang a whole run indefinitely with nothing raised to catch.
- **Narrowed exception handling.** Only genuine "the API did not serve this request" failures trigger fallback behaviour. A `TypeError` or `KeyError` in our own code propagates intact instead of being misreported as a provider outage.
- **`504 DEADLINE_EXCEEDED` is treated as transient**, alongside `503`, so it rotates to the next provider instead of failing the question outright.
- **Timestamped logs with a heartbeat during backoff waits**, so a run that is deliberately waiting looks clearly different from one that has frozen.
- **No duplicate retrieval.** Retrieved chunks are passed straight into `generate_answer()` rather than being retrieved a second time, which removes one embedding call per question.
- **The embedding fallback fails cleanly.** If Gemini embeddings are unavailable it raises `EmbeddingUnavailableError` rather than silently switching to the local model. The local backend produces vectors of different dimensionality *and* in a different vector space, so an automatic switch would write quietly-wrong vectors into the collection. It is opt-in only via `DOCSENSE_EMBEDDING_BACKEND=local`, and a dimension check guards both backends.

## Known Limitations

Documented honestly rather than hidden. Full reasoning for each is in [`TDR.md`](./TDR.md):

- **A requested document can be missing from a multi-document answer** — retrieval returns one global top-k across all requested documents, with no guarantee each contributes a chunk. Flagged, not yet fixed; the 12 coverage queries exist to measure it. *(TDR 2f)*
- **"Not found" behaviour is not covered by a correctness eval entry yet** — no labeled question currently tests whether the system correctly reports that information is absent. *(TDR 2g)*
- **Embeddings and image analysis are still single-vendor.** They remain on the Gemini key pool, so a Gemini-wide outage still blocks retrieval even when several answer providers are healthy. This is the largest remaining shared-fate risk. *(TDR 2i)*
- **Citation formats differ by model.** The parser accepts any provider that emits `(Source N)`, but adherence is per-model behaviour, not a guarantee — which is why `provider_used` is recorded on every result. Verdicts are not strictly comparable across providers. *(TDR 2i)*
- **Documents pass through several third-party providers.** Retrieved text is sent to whichever vendor is active. Fine for the public sample documents used here; review before using it on anything confidential. *(TDR 2i)*
- **Free-tier terms and limits apply.** Some providers' free tiers carry usage caps and non-commercial restrictions, and running an evaluation suite repeatedly can exhaust them. Several providers' current quotas and context windows could **not** be verified from official documentation and are deliberately not quoted here. *(TDR 2i)*
- **Multi-key rotation is a development-volume workaround**, not a production rate-limiting strategy. *(TDR 2d)*

## Documentation

- [`PRD.md`](./PRD.md) — Product requirements, scope, and build stages
- [`TDR.md`](./TDR.md) — Technical architecture, schemas, module design, and the full log of documented deviations from the original spec (Sections 2a–2i)

## License

Released under the [MIT License](LICENSE).
