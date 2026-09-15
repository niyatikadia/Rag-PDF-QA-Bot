"""
retriever.py — Orchestrates the query path: embed → search → ranked chunks.
Implemented: Day 4
"""
import logging
from typing import List, Dict, Optional

from app.config import TOP_K_RESULTS
from app.services.embedder import embed_query
from app.services.vector_store import query_chunks

logger = logging.getLogger(__name__)


def distance_to_score(distance: Optional[float]) -> float:
    """
    Convert a ChromaDB cosine distance into a 0.0-1.0 relevance score.

    The `pdf_chunks` collection uses cosine space, so distance = 1 - cosine
    similarity and lives in [0.0, 2.0]. Score is therefore `1 - distance`,
    clamped: floating-point error can push an exact match marginally below 0,
    and genuinely opposite vectors below -1 carry no extra meaning for
    citation display.
    """
    if distance is None:
        return 0.0
    return max(0.0, min(1.0, 1.0 - float(distance)))


def retrieve(query: str, top_k: int = TOP_K_RESULTS,
             document_id: Optional[str] = None) -> List[Dict]:
    """
    Embed the query and return the top-k relevant chunks, best first.

    Args:
      query       — the user's natural-language question.
      top_k       — how many chunks to return (default TOP_K_RESULTS from .env).
      document_id — when given, restrict retrieval to that single document.

    Returns:
      [{"chunk_id": str, "text": str, "metadata": {...},
        "score": float, "distance": float}]

      Sorted by score descending. Returns [] for an empty query, an empty
      vector store, or any retrieval failure — callers never get an exception
      from this function.
    """
    if not query or not query.strip():
        logger.warning("retrieve() called with an empty query — returning no results.")
        return []

    try:
        query_embedding = embed_query(query.strip())
    except Exception as exc:
        logger.error("Failed to embed query: %s", exc)
        return []

    raw = query_chunks(query_embedding, top_k=top_k, document_id=document_id)

    # ChromaDB nests one list per query embedding; we only ever send one.
    def _first(key: str) -> List:
        outer = raw.get(key) or [[]]
        return outer[0] if outer and outer[0] is not None else []

    ids = _first("ids")
    documents = _first("documents")
    metadatas = _first("metadatas")
    distances = _first("distances")

    results: List[Dict] = []
    for i, text in enumerate(documents):
        distance = distances[i] if i < len(distances) else None
        results.append({
            "chunk_id": ids[i] if i < len(ids) else None,
            "text": text,
            "metadata": dict(metadatas[i]) if i < len(metadatas) and metadatas[i] else {},
            "score": distance_to_score(distance),
            "distance": float(distance) if distance is not None else None,
        })

    # ChromaDB already returns nearest-first, but ranking is this module's
    # stated responsibility — sort explicitly rather than rely on that.
    results.sort(key=lambda r: r["score"], reverse=True)

    logger.info(
        "Retrieved %d chunk(s) for query %r (top_k=%d, document_id=%s)",
        len(results), query[:60], top_k, document_id or "all",
    )
    return results
