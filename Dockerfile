# DocSense API (backend). Built from the project root: docker compose build backend
FROM python:3.13.2-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/models

# Tesseract (OCR for scanned PDFs) and Poppler (pdf2image).
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# CPU-only PyTorch first, at the version pinned in requirements.txt (the default PyPI build pulls
# multi-GB CUDA libraries); requirements.txt then finds torch==2.13.0 already installed.
RUN pip install torch==2.13.0 --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY api/ api/
COPY chunking/ chunking/
COPY embedding/ embedding/
COPY evaluation/ evaluation/
COPY generation/ generation/
COPY ingestion/ ingestion/
COPY retrieval/ retrieval/

# Run as a normal user. The directories are created here so the named volumes mounted on them
# start out writable by that user.
RUN useradd --create-home --uid 1000 app \
    && mkdir -p /app/data/vector_store /app/data/uploads /app/data/processed /models \
    && chown -R app:app /app/data /models
USER app

EXPOSE 8000

# One process only: the embedded Qdrant store takes an exclusive lock, so no --workers and no --reload.
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
