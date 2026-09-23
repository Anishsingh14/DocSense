<div align="center">

# DocSense

**Unified document intelligence — upload any document, ask questions, get page-cited answers.**

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Gemini](https://img.shields.io/badge/Google_Gemini-Vision_%7C_Embeddings_%7C_LLM-4285F4?style=flat&logo=googlegemini&logoColor=white)](https://ai.google.dev/)
[![Qdrant](https://img.shields.io/badge/Qdrant-Vector_DB-DC244C?style=flat&logo=qdrant&logoColor=white)](https://qdrant.tech/)
[![Streamlit](https://img.shields.io/badge/Streamlit-Frontend-FF4B4B?style=flat&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat)](LICENSE)

**Build status:** Stages 1–6 complete and independently verified

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
- **Built-in evaluation framework** — accuracy is measured against a labeled Q&A set, not eyeballed

## Build Progress

| Stage | Status | What it does |
|---|---|---|
| 1 — Ingestion & Parsing | ✅ Complete | Extracts text + images per page from PDF/DOCX/TXT, with OCR fallback for scanned pages |
| 2 — Chunking | ✅ Complete | Splits text into retrievable chunks; clause-aware for legal documents |
| 3 — Image Analysis | ✅ Complete | Vision model analyzes embedded charts/diagrams into searchable descriptions |
| 4 — Embedding & Vector Storage | ✅ Complete | Converts chunks into vectors, stored in Qdrant with full metadata |
| 5 — Retrieval & Re-ranking | ✅ Complete | Mode-aware candidate retrieval, re-ranked for precision |
| 6 — Answer Generation | ✅ Complete | Generates the final cited answer from retrieved context |
| 7 — Evaluation Framework | ⏳ Planned | Scores retrieval/answer accuracy against a labeled test set |
| 8 — API Layer | ⏳ Planned | FastAPI endpoints for upload and query |
| 9 — Frontend UI | ⏳ Planned | Streamlit interface, built last |

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
      │
      ▼
Answer Generation (LLM, with mandatory page citation)
      │
      ▼
FastAPI Layer  →  Streamlit UI
```

Full architectural detail, module responsibilities, and data schemas are documented in [`TDR.md`](./TDR.md). Product scope and build stages are documented in [`PRD.md`](./PRD.md).

## Tech Stack

| Layer | Technology |
|---|---|
| PDF / DOCX parsing | PyMuPDF, python-docx |
| OCR (scanned documents) | Tesseract |
| Chunking | Custom structure-aware splitter + clause-aware legal chunker (documented deviation, TDR Section 2c) |
| Document-type classification | Lightweight heuristic classifier (filename + keyword + structural signals) |
| Vision, Embeddings & Generation | **Google Gemini API** (free tier) — documented substitution from Claude/Voyage AI (TDR Section 2a) |
| Vector database | Qdrant, local embedded mode (documented deviation from Docker, TDR Section 2b) |
| Re-ranking | `bge-reranker-v2-m3` (local, free) |
| Backend API | FastAPI *(Stage 8, planned)* |
| Evaluation | RAGAS *(Stage 7, planned)* |
| Frontend | Streamlit *(Stage 9, planned)* |

> **Note:** TDR.md originally specified Claude (vision + generation), Voyage AI (embeddings), and Dockerized Qdrant. These were deliberately substituted with free-tier/local alternatives during the V1 build — every substitution is documented with reasoning, what stays unchanged, and a clear trigger for reconsidering it. See [`TDR.md`](./TDR.md) Sections 2a–2c for the full decision log.

## Project Structure

```
docsense/
├── ingestion/         # Text and image extraction (Stage 1)
├── chunking/           # Structure-aware and legal-clause chunking (Stage 2)
├── embedding/           # Embedding generation and vector storage (Stage 4)
├── retrieval/            # Mode-aware retrieval and re-ranking (Stage 5)
├── generation/           # Citation-grounded answer generation (Stage 6)
├── evaluation/          # Accuracy scoring against a labeled Q&A set (Stage 7)
├── api/                # FastAPI backend (Stage 8)
├── frontend/             # Streamlit UI (Stage 9 — built last)
├── data/
│   ├── sample_docs/      # Test documents (6 docs: synthetic + real CUAD contracts)
│   └── eval/              # Evaluation Q&A set
├── .env                  # Local secrets (GEMINI_API_KEY) — gitignored, never committed
├── .env.example            # Template, safe to commit
├── PRD.md                # Product Requirements Document
├── TDR.md                 # Technical Design Report (incl. all deviation decisions)
├── requirements.txt
└── README.md
```

## Getting Started

```bash
# Clone the repository
git clone https://github.com/<your-username>/docsense.git
cd docsense

# Install dependencies
pip install -r requirements.txt

# Set up your API key
cp .env.example .env
# then edit .env and add your GEMINI_API_KEY

# Run a stage's manual test script, e.g.:
python -m ingestion.test_stage1_manual
python -m chunking.test_stage2_manual
python -m ingestion.test_stage3_manual
python -m embedding.test_stage4_manual
python -m retrieval.test_stage5_manual
python -m generation.test_stage6_manual

# Once complete, run the backend API (Stage 8)
uvicorn api.main:app --reload

# Run the frontend (Stage 9)
streamlit run frontend/app.py
```

Qdrant runs in local embedded mode by default — no separate database server needed.

## Verified Results So Far

A few concrete, independently-checked results from testing:

- **Chart understanding:** every value read off an embedded revenue chart (title, axis labels, all four data points) matched the source chart exactly
- **Legal clause precision:** exact clauses (e.g., "Termination for Convenience," "Indemnity") correctly isolated to their own chunk, with the correct page number, across both synthetic and real-world contracts
- **Retrieval confidence:** for an image-based question, the correct chart chunk was ranked ~160× higher than the next-best text chunk
- **Multi-document mode:** correctly surfaced relevant clauses from 3 different contracts in a single ranked list
- **Citation grounding:** generated answers were checked against the real page/section metadata of every source they cite, and the exact quoted text was cross-checked against the original source PDFs — no hallucinated pages, no dropped or fabricated citations

## Evaluation

Accuracy is measured, not assumed. `evaluation/run_eval.py` *(Stage 7)* will run a labeled question set — including real, expert-annotated clause data from CUAD — through the full pipeline and report retrieval and answer accuracy.

```bash
python evaluation/run_eval.py
```

## Roadmap

| Version | Scope |
|---|---|
| **V1** (in progress — Stages 1–6 done, evaluation/API/UI remaining) | PDF, DOCX, TXT + embedded image analysis, 3 Q&A modes |
| V2 | PPTX, XLSX/CSV support |
| V3 | Password-protected PDFs, legacy `.DOC`, handwriting OCR |
| V4 | Multi-user support, persistent history, confidence scoring UI |

## Documentation

- [`PRD.md`](./PRD.md) — Product requirements, scope, and build stages
- [`TDR.md`](./TDR.md) — Technical architecture, schemas, module design, and the full log of documented deviations from the original spec (Sections 2a–2e)

## License

Released under the [MIT License](LICENSE).
