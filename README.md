<div align="center">

# DocSense

**Unified document intelligence — upload any document, ask questions, get page-cited answers.**

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Gemini](https://img.shields.io/badge/Google_Gemini-Vision_%7C_Embeddings-4285F4?style=flat&logo=googlegemini&logoColor=white)](https://ai.google.dev/)
[![Providers](https://img.shields.io/badge/Answer_LLMs-7_provider_rotation-6E40C9?style=flat)](./TDR.md)
[![Qdrant](https://img.shields.io/badge/Qdrant-Vector_DB-DC244C?style=flat&logo=qdrant&logoColor=white)](https://qdrant.tech/)
[![React](https://img.shields.io/badge/React_%2B_Vite-Frontend-61DAFB?style=flat&logo=react&logoColor=black)](https://react.dev/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat)](LICENSE)

**Build status:** Stages 1–6 complete and independently verified · Stage 7 evaluation framework built · Stage 8 API layer complete · Stage 9 web UI built

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
| 8 — API Layer | ✅ Complete | FastAPI endpoints for health, upload/ingest, list, delete and query |
| 9 — Web UI | ✅ Built | React + Vite site in `DocSense-UI/`: PDF upload, the three Q&A modes, Summary or Exact-quote answers with clickable page citations, connected to the API |

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
FastAPI Layer (single process, one shared Qdrant client)   ← Stage 8, complete
      │
      ▼
Web UI (React + Vite, DocSense-UI/)                        ← Stage 9, built
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
| Frontend (Stage 9) | React 18 + Vite 5, React Router and Tailwind CSS, in `DocSense-UI/`. Streamlit was the original plan (TDR Section 2l) |

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

**Rotation order since 2026-11-13:** Groq, Cohere, OpenRouter, NVIDIA, Gemini. NVIDIA times out often, so it is tried only after the other three.

The two disabled providers are configured but never called, each logging one line explaining why. Flip `enabled=True` on their entry in `generation/provider_rotation.py` to bring them back in.

**Embeddings and image analysis deliberately stay on the Gemini key pool** and are not part of this rotation.

> **Note:** TDR.md originally specified Claude (vision + generation), Voyage AI (embeddings), Dockerized Qdrant, and RAGAS. Each was deliberately substituted during the V1 build, and every substitution is documented with its reasoning, what stays unchanged, and a trigger for reconsidering it. See [`TDR.md`](./TDR.md) Sections 2a–2l for the full decision log.

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
├── DocSense-UI/                    # Stage 9 — web UI (React + Vite)
│   ├── src/pages/                  #   Home, GetStarted, Chat, Terms
│   ├── src/lib/                    #   api.js (API client), chatConfig.js, modes.js
│   ├── public/                     #   logos and the home-page video
│   └── vite.config.js              #   forwards /api/... to the API on port 8000
├── data/
│   ├── sample_docs/                # 6 test documents (synthetic + real CUAD contracts)
│   ├── eval/                       # cuad_sample_eval.json — labeled Q&A set
│   ├── processed/                  # extracted images (gitignored)
│   ├── vector_store/               # local Qdrant storage (gitignored)
│   └── README_datasets.md
├── .env                            # Local keys — gitignored, never committed
├── .env.example                    # Template with empty values, safe to commit
├── PRD.md                          # Product Requirements Document
├── TDR.md                          # Technical Design Report (incl. deviations 2a–2l)
├── requirements.txt
└── README.md
```

`evaluation/results/` is created on the first completed evaluation run and is gitignored.

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

# Stage 9 — the web UI, in a second terminal while the API runs (see "Web UI (Stage 9)" below)
cd DocSense-UI && npm install && npm run dev
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

## Web UI (Stage 9)

A React + Vite site in `DocSense-UI/`, connected to the API above (TDR Section 2l).

```bash
# Terminal 1, from the project root: the API
uvicorn api.main:app --port 8000

# Terminal 2: the UI (needs Node.js 18 or newer)
cd DocSense-UI
npm install
npm run dev
```

Open `http://localhost:5173`. Use `localhost`, because the dev server may not answer on `127.0.0.1`. The dev server forwards `/api/...` requests to the API on port 8000, so the API's CORS settings need no change; set `DOCSENSE_API_URL` to use another address.

- **Get Started:** choose General Q&A, Multi-Doc or Legal Precision, then add PDFs (up to 25 MB each, the API's limit).
- **Chat:** the files are sent to the API when the page opens, unless a document with the same file name is already stored. Answers show clickable `[n]` citations, the cited passages with links to their pages in the PDF preview, and the provider and model that answered. The API's warnings appear under the answer as a note.
- **Summary | Exact quotes:** a header toggle that sets `answer_style` for each question. General Q&A and Multi-Doc start on Summary. Legal Precision always uses Exact quotes, because its prompt asks for the exact clause text.

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

**Final Stage 7 run** (2026-11-03, HEAD 3b9c014, results file `eval_results_20261103T180353Z.json`). This is the headline result. It replaces the 2026-11-02 run, which ran on commit 1e463c7 before the truncation fix.

- Retrieval 23/23. Coverage 12/12 queries and 32/32 documents.
- Judge verdicts: 18 correct, 4 partially_correct (Q5, Q8, Q18, Q21), 1 incorrect (Q1), 0 not_measured.
- Manual review (by hand, not by the judge): 20 correct, 2 partially_correct (Q8, Q18), 1 incorrect (Q1). The judge marked Q5 down for extra detail and Q21 for wording, which its own rules allow.
- 81 calls, 0 failures, 8 min 8 s. Groq wrote all 23 answers and Cohere graded all 23. NVIDIA was skipped in memory only, with no repo change.

TDR Section 2k has the details, including an aborted first attempt and the first live truncation warning (Q7).

## Roadmap

| Version | Scope |
|---|---|
| **V1** (Stages 1–9 built; minor fixes and speed work pending) | PDF, DOCX, TXT + embedded image analysis, 3 Q&A modes |
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

- **Multi-document coverage is guaranteed at retrieval, within a cap.** Retrieval used to return one global top-k across all requested documents, so a requested document could be left out entirely. It now reserves chunks for every requested document, within an 8-chunk context cap: at least two each for up to 4 documents, at least one each for up to 8. On the 12 coverage queries this gave full coverage on 12 of 12, against 5 of 12 before. The final Stage 7 run (2026-11-03, HEAD 3b9c014) also had full coverage on all 12, with 32 of 32 documents; it supersedes the 2026-11-02 run at commit 1e463c7. *(TDR 2f, 2k)*
- **Answer writers sometimes quote selectively or answer "no such clause" wrongly.** In the 11-question re-check, one answer quoted the "executed this Agreement as of the date below" line and stopped before the signature dates it introduces (Q8). Another said the contract gives no expiration date, although the retrieved context contained "This Agreement shall remain in effect until terminated by the Parties" (Q16). In both cases the text had been retrieved, so these are generation behaviours, not retrieval misses. In the final run, Groq said a contract has no document name although retrieval was correct (Q1), a false "not found"; the app's own "No sources could be verified" warning fired. *(TDR 2k)*
- **"Not found" behaviour is not covered by a correctness eval entry yet** — no labeled question currently tests whether the system correctly reports that information is absent. *(TDR 2g)*
- **Embeddings and image analysis are still single-vendor.** They remain on the Gemini key pool, so a Gemini-wide outage still blocks retrieval even when several answer providers are healthy. This is the largest remaining shared-fate risk. *(TDR 2i)*
- **Citation formats differ by model.** The parser accepts any provider that emits `(Source N)`, but adherence is per-model behaviour, not a guarantee — which is why `provider_used` is recorded on every result. Verdicts are not strictly comparable across providers. *(TDR 2i)*
- **Documents pass through several third-party providers.** Retrieved text is sent to whichever vendor is active. Fine for the public sample documents used here; review before using it on anything confidential. *(TDR 2i)*
- **NVIDIA's free endpoint times out intermittently.** On 2026-11-01 it graded answers in about 2.5 s in the afternoon, then gave no response to six requests in a row that evening. Rotation absorbs this with a 60-second cooldown while the next provider answers, but each timeout adds about 45 s to that question. *(TDR 2k)*
- **Groq's reasoning length varies, and can use up the whole output limit.** On the same multi-document question it spent 764, about 1,900 (inferred) and then 3,998 output tokens on reasoning. At 3,998 of 4,000 it returned an empty answer and another provider wrote it instead. In the final run it finished that question normally at 1,097 output tokens. A lower reasoning effort for Groq is the candidate fix; it is deferred. *(TDR 2k)*
- **Legal and single-document answers keep a 1,024-token output limit, and Groq can truncate legal answers.** Reasoning counts inside the limit. In the final run, Groq's Q7 answer used all 1,024 output tokens, 797 of them reasoning, and stops mid-sentence at "…or if". The app showed the warning "This answer was cut off at the output limit and may be incomplete.", the first time it fired live. *(TDR 2k)*
- **The grader does not see truncation.** It still marked the cut-off Q7 answer correct, because the parties quote is complete. *(TDR 2k)*
- **The grader can be strict on extra detail and wording.** In the final run it marked Q5 down for extra detail and Q21 for wording, both of which its own rules allow. In the 2026-11-02 run it marked Q5 and Q7 down for extra, accurate detail, and Q11 for omitting a requirement that the quoted clause does contain. *(TDR 2k)*
- **Answer writers can misspell file names.** In both the 2026-11-02 run and the final run, one answer's heading spelled a contract file as `..._SERVICES_AGEM.pdf` instead of `..._SERVICES_AGREEM.pdf` (Q22). *(TDR 2k)*
- **The low-confidence warning is noisy.** It fired on 11 of the 23 answers in the final run. *(TDR 2k)*
- **An empty OpenRouter reply has no logged `finish_reason`.** In the final run's first attempt, OpenRouter returned HTTP 200 with empty content while grading. That path does not log `finish_reason`, so the cause is unproven. *(TDR 2k)*
- **Answers through the UI take about 15–60 s.** In a five-question test, questions took 16–57 s. The reranker runs on the CPU, at about 11–12 s per question and about 48 s on the first question after the API starts, and slow or failing providers added up to about 44 s. Speed fixes are planned. *(TDR 2l)*
- **The web UI reuses stored documents by file name.** The API names a document after its file, so a changed file with the same name is answered from the old copy until you delete it (`DELETE /documents/{doc_id}`) or rename the file. *(TDR 2l)*
- **The web UI has no chat memory.** Each question is answered on its own. *(TDR 2l)*
- **Summary answers are not covered by the Stage 7 results**, which used Exact quotes (`answer_style: "full"`). *(TDR 2l)*
- **The UI's `/api` forwarding exists only in `npm run dev` and `npm run preview`.** Hosting the built site needs `/api` routed to the API, or `VITE_API_BASE_URL` plus a CORS change on the API. *(TDR 2l)*
- **Free-tier terms and limits apply.** Some providers' free tiers carry usage caps and non-commercial restrictions, and running an evaluation suite repeatedly can exhaust them. Several providers' current quotas and context windows could **not** be verified from official documentation and are deliberately not quoted here. *(TDR 2i)*
- **Multi-key rotation is a development-volume workaround**, not a production rate-limiting strategy. *(TDR 2d)*

## Documentation

- [`PRD.md`](./PRD.md) — Product requirements, scope, and build stages
- [`TDR.md`](./TDR.md) — Technical architecture, schemas, module design, and the full log of documented deviations from the original spec (Sections 2a–2l)

## License

Released under the [MIT License](LICENSE).
