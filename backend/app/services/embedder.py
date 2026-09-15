"""
embedder.py — Load sentence-transformers model once at startup; expose encode methods.
Model: all-MiniLM-L6-v2  (384-dim embeddings, ~80 MB, CPU-only)

Implemented: Day 3
"""
import logging
from typing import List
from app.config import EMBEDDING_MODEL

logger = logging.getLogger(__name__)

_embedder = None   # module-level singleton


def get_embedder():
    """Return the loaded SentenceTransformer model (lazy singleton)."""
    global _embedder
    if _embedder is None:
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading embedding model '%s'…", EMBEDDING_MODEL)
            _embedder = SentenceTransformer(EMBEDDING_MODEL)
            logger.info("Embedding model loaded.")
        except Exception as exc:
            logger.error("Failed to load embedding model: %s", exc)
            raise
    return _embedder


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Encode a list of strings → list of 384-dim float vectors."""
    model = get_embedder()
    vectors = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
    return vectors.tolist()


def embed_query(query: str) -> List[float]:
    """Encode a single query string → 384-dim float vector."""
    return embed_texts([query])[0]
