"""vector_store.py — Stage 4 module.

Handles Qdrant collection creation, upsert, and metadata indexing.
`doc_id`, `page_num`, `type`, and `doc_type` are indexed as filterable
fields, per TDR Section 4, so Stage 5's mode-aware retrieval
(single_doc / multi_doc / legal) can filter efficiently.

DEVIATION FROM TDR (see TDR.md Section 2b): TDR specified a
self-hosted Qdrant server via Docker. Docker is not installed in the
local build environment, so this module uses Qdrant's embedded/local
mode instead — the same `qdrant-client` package, persisting to a
local folder rather than talking to a server over HTTP.

The Qdrant client is constructed in exactly one place in this module
(`_get_client`) so that switching to a Dockerized or hosted Qdrant
server later is a one-line change, isolated from every other module
that imports from here.
"""

from __future__ import annotations

import os
from typing import List, Literal, Optional, TypedDict

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "docsense_chunks")

# Local embedded Qdrant storage path (see module docstring / TDR
# Section 2b). Kept separate from data/processed/ (Stage 1 image
# output) since this is Qdrant's own on-disk index format, not
# human-inspectable content.
LOCAL_QDRANT_PATH = os.getenv("QDRANT_LOCAL_PATH", os.path.join("data", "vector_store"))

# Must match embed_chunks.EMBEDDING_OUTPUT_DIMENSIONALITY. Kept as a
# separate constant here (rather than importing) so this module has
# no hard dependency on embed_chunks.py — vector_store.py only cares
# about storing/filtering vectors, not how they were produced.
VECTOR_SIZE = 768

_client: Optional[QdrantClient] = None


def _get_client() -> QdrantClient:
    """Returns a singleton Qdrant client.

    SWAP-BACK POINT: to use a Dockerized or hosted Qdrant server
    instead of local embedded mode, replace the QdrantClient(path=...)
    call below with QdrantClient(url=..., api_key=...). No other
    module needs to change.
    """
    global _client
    if _client is None:
        qdrant_url = os.getenv("QDRANT_URL")
        if qdrant_url:
            _client = QdrantClient(url=qdrant_url, api_key=os.getenv("QDRANT_API_KEY"))
        else:
            os.makedirs(LOCAL_QDRANT_PATH, exist_ok=True)
            _client = QdrantClient(path=LOCAL_QDRANT_PATH)
    return _client


def ensure_collection() -> None:
    """Creates the chunks collection if it doesn't already exist.

    NOTE on payload indexes (tied to TDR Section 2b's local-embedded-
    Qdrant deviation): TDR Section 4 calls for doc_id/page_num/type/
    doc_type to be "filterable fields", and server Qdrant would
    normally use explicit payload indexes (create_payload_index) to
    make that filtering fast. Local embedded mode does not support
    payload indexes at all — the client accepts the call but performs
    a no-op (confirmed: Qdrant logs "Payload indexes have no effect in
    the local Qdrant"). Filtering itself still works correctly without
    an index (verified: filtering by doc_id returns the right subset
    of points), just via an unindexed scan instead of an indexed
    lookup — acceptable for V1's per-document chunk volumes (a 50-page
    doc cap per PRD Section 11 keeps total points per collection
    small). This function intentionally does NOT call
    create_payload_index here to avoid a misleading no-op call;
    revisit if/when swapping to a real Qdrant server (see
    _get_client's swap-back note).
    """
    client = _get_client()

    if not client.collection_exists(COLLECTION_NAME):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=qmodels.VectorParams(
                size=VECTOR_SIZE,
                distance=qmodels.Distance.COSINE,
            ),
        )


def upsert_chunks(embedded_chunks: List[dict]) -> int:
    """Upserts embedded chunks into the collection.

    Uses each chunk's `chunk_id` (deterministic, e.g.
    "docA_p4_c2") as the Qdrant point ID after hashing to an integer,
    since Qdrant point IDs must be an unsigned int or UUID, not an
    arbitrary string. This keeps upserts idempotent — re-embedding the
    same chunk_id overwrites the existing point rather than
    duplicating it, which is what TDR Section 6's idempotent-
    processing requirement calls for at the chunk level.

    Args:
        embedded_chunks: list of chunk dicts with an "embedding" field
            (as produced by embedding.embed_chunks.embed_chunks()).

    Returns:
        The number of points upserted.
    """
    if not embedded_chunks:
        return 0

    ensure_collection()
    client = _get_client()

    points = [
        qmodels.PointStruct(
            id=_chunk_id_to_point_id(chunk["chunk_id"]),
            vector=chunk["embedding"],
            payload={
                "chunk_id": chunk["chunk_id"],
                "doc_id": chunk["doc_id"],
                "doc_name": chunk["doc_name"],
                "doc_type": chunk["doc_type"],
                "page_num": chunk["page_num"],
                "section": chunk.get("section"),
                "type": chunk["type"],
                "image_type": chunk.get("image_type"),
                "text": chunk["text"],
                "source_image_path": chunk.get("source_image_path"),
            },
        )
        for chunk in embedded_chunks
    ]

    client.upsert(collection_name=COLLECTION_NAME, points=points)
    return len(points)


def search(
    query_vector: List[float],
    limit: int = 20,
    doc_ids: Optional[List[str]] = None,
    doc_type: Optional[str] = None,
) -> List[dict]:
    """Vector-similarity search with optional metadata filtering.

    Used by Stage 5's retriever.py to implement mode-aware retrieval:
    - single_doc: pass doc_ids=[the one doc_id]
    - multi_doc: pass doc_ids=[all doc_ids in the session]
    - legal: pass doc_type="legal"

    Args:
        query_vector: the embedded user question (from
            embedding.embed_chunks.embed_query()).
        limit: max number of results to return.
        doc_ids: if given, restrict results to chunks from these
            doc_id(s).
        doc_type: if given, restrict results to chunks with this
            doc_type.

    Returns:
        List of dicts, each a chunk's full payload plus a "score"
        field (cosine similarity, higher is more similar), ordered by
        descending score.
    """
    client = _get_client()
    if not client.collection_exists(COLLECTION_NAME):
        return []

    conditions = []
    if doc_ids:
        conditions.append(
            qmodels.FieldCondition(key="doc_id", match=qmodels.MatchAny(any=doc_ids))
        )
    if doc_type:
        conditions.append(
            qmodels.FieldCondition(key="doc_type", match=qmodels.MatchValue(value=doc_type))
        )

    query_filter = qmodels.Filter(must=conditions) if conditions else None

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        query_filter=query_filter,
        limit=limit,
        with_payload=True,
    ).points

    hits = []
    for point in results:
        hit = dict(point.payload)
        hit["score"] = point.score
        hits.append(hit)

    return hits


def delete_document(doc_id: str) -> int:
    """Deletes all chunks belonging to a given doc_id.

    Used when re-processing a document that already exists (e.g., if
    idempotency checks at the ingestion layer are bypassed
    intentionally), so stale chunks don't linger alongside new ones.
    """
    client = _get_client()
    if not client.collection_exists(COLLECTION_NAME):
        return 0

    result = client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=qmodels.FilterSelector(
            filter=qmodels.Filter(
                must=[qmodels.FieldCondition(key="doc_id", match=qmodels.MatchValue(value=doc_id))]
            )
        ),
    )
    return 1 if result.status == qmodels.UpdateStatus.COMPLETED else 0


def count_points(doc_id: Optional[str] = None) -> int:
    """Returns the number of points in the collection, optionally
    filtered to a single doc_id. Used by the manual test script to
    verify upserts landed correctly.
    """
    client = _get_client()
    if not client.collection_exists(COLLECTION_NAME):
        return 0

    count_filter = None
    if doc_id:
        count_filter = qmodels.Filter(
            must=[qmodels.FieldCondition(key="doc_id", match=qmodels.MatchValue(value=doc_id))]
        )

    result = client.count(collection_name=COLLECTION_NAME, count_filter=count_filter)
    return result.count


def _chunk_id_to_point_id(chunk_id: str) -> int:
    """Deterministically maps a string chunk_id to an unsigned integer
    Qdrant point ID, so the same chunk_id always maps to the same
    point (idempotent upserts) without needing a separate ID-mapping
    table.
    """
    import hashlib

    digest = hashlib.sha256(chunk_id.encode("utf-8")).hexdigest()
    # Take the first 15 hex chars (60 bits) to stay safely within a
    # 64-bit unsigned integer range.
    return int(digest[:15], 16)
