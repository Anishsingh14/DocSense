# Technical Design Report (TDR)
## Project: DocSense — Unified Document Intelligence & Q&A Platform

**Version:** 1.0 (V1 Scope)
**Companion document to:** PRD.md
**Status:** Draft for Agentic Build (Kiro)
**Last Updated:** 2026-09-15

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
| Embeddings | `voyage-3` (Voyage AI) — fallback: `BAAI/bge-large-en-v1.5` (local, free) | Strong retrieval-tuned embeddings; free fallback avoids API dependency during dev |
| Vector database | `Qdrant` (self-hosted via Docker) | Strong metadata filtering (doc_id, page_num, type) needed for multi-mode retrieval |
| Re-ranking | `bge-reranker-v2-m3` (local, free) | Improves precision of top-k retrieved chunks before generation |
| Vision analysis | Claude (Sonnet) vision API | Strong instruction-following for factual, non-speculative image description |
| LLM (generation) | Claude (Sonnet) for legal/precision mode, Claude (Haiku) for general/summary mode | Balances accuracy and cost |
| Orchestration | `LlamaIndex` (`CitationQueryEngine` as base, customized) | Built specifically for citation-grounded Q&A |
| Backend API | `FastAPI` | Async support, clean OpenAPI docs, easy to wire to a future frontend |
| Evaluation | `RAGAS` (open-source) + custom scoring script | Automates retrieval/answer accuracy scoring |
| Frontend (Stage 9 only) | `Streamlit` | Fastest path to a usable demo UI |

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
- Classifies image_type (chart/diagram/table/photo) either via prompt output or a lightweight heuristic
- Converts vision output into a schema-conformant chunk (`type: "image"`)

### Stage 4 — Embedding & Storage (`embedding/`)
- `embed_chunks.py`: batches all chunks (text + image) through the embedding model
- `vector_store.py`: handles Qdrant collection creation, upsert, and metadata indexing (doc_id, page_num, type, doc_type must be filterable fields)

### Stage 5 — Retrieval (`retrieval/`)
- `retriever.py`: mode-aware retrieval
  - `single_doc`: filter by one `doc_id`
  - `multi_doc`: retrieve across all `doc_id`s in the session, group by source
  - `legal`: filter `doc_type == legal`, boost `section`-tagged chunks, smaller top-k for precision
- `reranker.py`: re-scores retrieved chunks with `bge-reranker-v2-m3`, returns top 3–5

### Stage 6 — Generation (`generation/`)
- `prompt_templates.py`: holds the mode-specific and style-specific (full/summary) prompt templates described in PRD Section 9
- `answer_with_citations.py`: assembles labeled context (`[Source N | Page X]`), calls the LLM, parses citations back against actual retrieved metadata (never trust the LLM's own page-number memory — always cross-check against what was actually retrieved)
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
