<div align="center">

# DocSense

**Unified document intelligence — upload any document, ask questions, get page-cited answers.**

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![LlamaIndex](https://img.shields.io/badge/LlamaIndex-Orchestration-8A2BE2?style=flat)](https://www.llamaindex.ai/)
[![Qdrant](https://img.shields.io/badge/Qdrant-Vector_DB-DC244C?style=flat&logo=qdrant&logoColor=white)](https://qdrant.tech/)
[![Streamlit](https://img.shields.io/badge/Streamlit-Frontend-FF4B4B?style=flat&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Docker](https://img.shields.io/badge/Docker-Qdrant_Host-2496ED?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat)](LICENSE)

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
  - **Legal** — exact clause retrieval with no paraphrasing
- **Image understanding** — charts, diagrams, and tables embedded in documents are analyzed and become searchable
- **Two answer styles** — full/verbatim or summarized
- **Built-in evaluation framework** — accuracy is measured against a labeled Q&A set, not eyeballed

## Architecture

```
Document Upload
      │
      ▼
Ingestion (text + image extraction, per page)
      │
      ├──► Text Chunking (semantic / legal-clause aware)
      └──► Image Analysis (vision LLM → text description)
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
| Chunking | LlamaIndex semantic chunker + custom legal-clause splitter |
| Embeddings | Voyage AI (`voyage-3`) — local fallback: BGE (`bge-large-en-v1.5`) |
| Vector database | Qdrant |
| Re-ranking | `bge-reranker-v2-m3` |
| Vision analysis | Claude (Sonnet) vision API |
| Generation | Claude (Sonnet / Haiku) |
| Orchestration | LlamaIndex |
| Backend API | FastAPI |
| Evaluation | RAGAS |
| Frontend | Streamlit |

## Project Structure

```
docsense/
├── ingestion/       # Text and image extraction (Stage 1)
├── chunking/        # Semantic and legal-clause chunking (Stage 2)
├── embedding/        # Embedding generation and vector storage (Stage 4)
├── retrieval/        # Mode-aware retrieval and re-ranking (Stage 5)
├── generation/        # Citation-grounded answer generation (Stage 6)
├── evaluation/       # Accuracy scoring against a labeled Q&A set (Stage 7)
├── api/                # FastAPI backend (Stage 8)
├── frontend/           # Streamlit UI (Stage 9 — built last)
├── data/
│   ├── sample_docs/     # Test documents
│   └── eval/            # Evaluation Q&A set
├── PRD.md               # Product Requirements Document
├── TDR.md                # Technical Design Report
└── README.md
```

## Getting Started

```bash
# Clone the repository
git clone https://github.com/<your-username>/docsense.git
cd docsense

# Install dependencies
pip install -r requirements.txt

# Start the vector database
docker run -p 6333:6333 qdrant/qdrant

# Run the backend API
uvicorn api.main:app --reload

# Run the frontend (once Stage 9 is built)
streamlit run frontend/app.py
```

Environment variables (API keys for your chosen LLM/embedding provider) are read from a `.env` file — see `.env.example`.

## Evaluation

Accuracy is measured, not assumed. `evaluation/run_eval.py` runs a labeled question set through the full pipeline and reports retrieval and answer accuracy.

```bash
python evaluation/run_eval.py
```

## Roadmap

| Version | Scope |
|---|---|
| **V1** (current) | PDF, DOCX, TXT + embedded image analysis, 3 Q&A modes |
| V2 | PPTX, XLSX/CSV support |
| V3 | Password-protected PDFs, legacy `.DOC`, handwriting OCR |
| V4 | Multi-user support, persistent history, confidence scoring UI |

## Documentation

- [`PRD.md`](./PRD.md) — Product requirements, scope, and build stages
- [`TDR.md`](./TDR.md) — Technical architecture, schemas, and module design

## License

Released under the [MIT License](LICENSE).
