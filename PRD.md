# Product Requirements Document (PRD)
## Project: DocSense — Unified Document Intelligence & Q&A Platform

**Version:** 1.0 (V1 Scope)
**Owner:** [Your Name]
**Status:** Draft for Agentic Build (Kiro)
**Last Updated:** 2026-09-15

---

## 1. Overview

DocSense is a document intelligence platform that allows a user to upload a document (PDF, DOCX, or TXT) and ask natural-language questions about it. The system retrieves only the relevant portions of the document, generates an accurate answer, and always cites the **exact page number(s)** the answer came from. It also analyzes **images embedded in documents** (charts, diagrams, tables-as-images, photos) so questions about visual content can be answered just like questions about text.

The system does not require any model training. It is a **Retrieval-Augmented Generation (RAG)** application built entirely on pre-trained models (LLMs, embedding models, vision models) orchestrated through a custom pipeline.

---

## 2. Problem Statement

Reading long documents to find specific information is slow and error-prone. Existing generic AI chatbots either:
- Cannot handle long documents accurately (context gets lost or hallucinated), or
- Give answers without telling the user *where* in the document that answer came from, making it hard to verify.

DocSense solves this by combining accurate retrieval with mandatory page-level citation, and by extending "reading" to include embedded images and charts, not just text.

---

## 3. Goals & Objectives

| Goal | Success Criteria |
|---|---|
| Accurate answers | ≥85% of test questions answered correctly against evaluation set |
| Verifiable answers | Every answer includes correct page number(s) and, where relevant, doc name |
| Multi-mode support | Single-doc Q&A, multi-doc comparison, and legal clause precision mode all work from one unified pipeline |
| Image understanding | Charts/diagrams/photos embedded in documents are analyzed and become answerable, not skipped |
| No training required | System works out-of-the-box on any new uploaded document with zero fine-tuning |

---

## 4. Target Users

- Data analysts / students building a portfolio-grade RAG project
- Professionals who need quick, verifiable answers from long reports, contracts, or papers
- Researchers comparing multiple documents/papers

---

## 5. Scope of Version 1 (V1)

### 5.1 In Scope
- File types: **PDF (text-based and scanned), DOCX, TXT**
- Image analysis for images embedded **within** the above file types (charts, diagrams, tables-as-images, photos)
- Three Q&A modes from one unified backend:
  1. **General Q&A** — single document
  2. **Multi-document comparison** — cross-document synthesis
  3. **Legal/Clause precision mode** — exact clause retrieval, no paraphrasing
- Page-level citation on every answer (mandatory, not optional)
- Two answer styles: **Full (verbatim/precise)** and **Summary (synthesized)**
- Backend-first build; a minimal API is fully functional and testable via requests/Postman **before** any UI is built
- Evaluation framework to measure retrieval and answer accuracy

### 5.2 Out of Scope for V1 (Future Versions)
- PPTX, XLSX/CSV, HTML, EML support (Version 2+)
- Old `.DOC`, password-protected PDFs, handwriting OCR (Version 3+)
- Multi-user accounts, authentication, persistent user history
- Fine-tuning any model
- Real-time collaborative features
- Frontend UI (built only after backend is fully functional — final stage of V1)

---

## 6. Functional Requirements (User Stories)

| ID | User Story | Priority |
|---|---|---|
| FR-1 | As a user, I can upload a PDF/DOCX/TXT file and have it processed automatically. | Must |
| FR-2 | As a user, I can ask a question about the uploaded document and get an answer with page number(s) cited. | Must |
| FR-3 | As a user, I can upload multiple documents and ask comparison questions ("what do these agree/disagree on?"). | Must |
| FR-4 | As a user, I can select "legal mode" to get exact clause quotes instead of paraphrased summaries. | Must |
| FR-5 | As a user, I can choose between a "full/verbatim" answer and a "summarized" answer. | Should |
| FR-6 | As a user, if my document contains a chart or diagram, I can ask about it and get a factual description with page number. | Must |
| FR-7 | As a user, I'm told when the system's answer has low retrieval confidence, so I know to verify manually. | Should |
| FR-8 | As a developer, I can run an evaluation script that scores the system's accuracy against a known Q&A test set. | Must |

---

## 7. Non-Functional Requirements

| Requirement | Target |
|---|---|
| Answer latency | Under 8 seconds for a single-document query (excluding first-time doc processing) |
| Document processing time | Under 30 seconds for a 20-page PDF (text-based) |
| Accuracy (retrieval) | Correct page retrieved in top-3 results ≥90% of the time on eval set |
| Cost control | Vision API only called on non-decorative images (filtered by size/heuristic) |
| Traceability | 100% of answers must include at least one page citation, or explicitly state "not found in document" |
| No hallucinated citations | System must never cite a page number not actually retrieved |

---

## 8. Build Stages (Backend First, UI Last)

This project must be built in the following stages. Each stage should be independently testable (e.g., via a script or terminal) before moving to the next.

### **Stage 1 — Ingestion & Parsing**
Extract text and images from PDF/DOCX/TXT with page-number metadata preserved for every piece of content.

### **Stage 2 — Chunking**
Split extracted text into retrievable chunks (semantic + structure-aware for legal mode), each tagged with page number and document ID.

### **Stage 3 — Image Analysis Branch**
Detect, filter, and analyze embedded images using a vision-capable LLM; convert results into searchable text chunks with the same metadata schema as text chunks.

### **Stage 4 — Embedding & Vector Storage**
Convert all chunks (text + image-derived) into embeddings and store them in a vector database with full metadata (doc_id, doc_name, page_num, type, chunk_id).

### **Stage 5 — Retrieval & Re-ranking**
Given a user question, retrieve the most relevant chunks (with mode-aware filtering: single-doc / multi-doc / legal) and re-rank for precision.

### **Stage 6 — Answer Generation with Citation**
Pass labeled, retrieved chunks to the LLM with strict citation instructions; generate the final answer in full or summary style.

### **Stage 7 — Evaluation Framework**
Build a scoring script that runs a test Q&A set through the pipeline and reports retrieval accuracy and answer correctness.

### **Stage 8 — API Layer**
Wrap the full pipeline (Stages 1–6) behind a clean backend API (upload endpoint, query endpoint, mode selector) so it is UI-ready.

### **Stage 9 — Frontend UI (Final Stage)**
Build the user-facing interface (upload, mode selector, chat-style Q&A, citation display, image preview for image-based sources).

---

## 9. Sample Answer Output (Reference for Expected Behavior)

```
Q: What's the termination clause in this contract?

Answer (Full mode):
"Either party may terminate this agreement with thirty (30) days
written notice, or immediately in the event of material breach
that remains uncured for fifteen (15) days after written notice."

Source: Page 6, Section 4.2 (Termination)
Confidence: High
```

```
Q: What does the revenue chart on page 5 show?

Answer:
The chart shows revenue growing from $2.1M in 2020 to $4.2M in 2023,
with the steepest increase between 2022 and 2023.

Source: Page 5 (Image — Bar Chart)
```

---

## 10. Datasets Required (No Training — Testing & Evaluation Only)

See **TDR.md, Section 9** for the full list of recommended public datasets, their sources, and exact usage per build stage. In summary:
- Sample documents are needed to **test ingestion/parsing** (Stages 1–3)
- A labeled Q&A set is needed to **measure accuracy** (Stage 7)
- No dataset is used to train or fine-tune any model.

---

## 11. Assumptions & Constraints

- Documents are assumed to be in English for V1.
- Maximum document size for V1: 50 pages (larger docs deferred to a future version with chunked/batched processing).
- The system relies on external LLM/embedding/vision APIs; an API key and internet access are required.
- No user authentication in V1 — single-session, local use only.

---

## 12. Future Roadmap (Post-V1)

| Version | Additions |
|---|---|
| V2 | PPTX support, XLSX/CSV support (structured-data retrieval mode) |
| V3 | Password-protected PDFs, old `.DOC` support, handwriting OCR |
| V4 | Multi-user support, persistent history, hallucination-confidence scoring UI |
