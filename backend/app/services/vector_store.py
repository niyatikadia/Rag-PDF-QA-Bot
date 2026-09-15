"""
vector_store.py — ChromaDB client management, collection CRUD, querying.
Collection name: pdf_chunks

Implemented: Day 3
"""
import logging
from typing import List, Dict, Optional
from app.config import CHROMA_PERSIST_DIR, TOP_K_RESULTS

logger = logging.getLogger(__name__)

COLLECTION_NAME = "pdf_chunks"
_client = None
_collection = None


def get_client():
    global _client
    if _client is None:
        import chromadb
        _client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
        logger.info("ChromaDB client initialised at %s", CHROMA_PERSIST_DIR)
    return _client


def get_collection():
    global _collection
    if _collection is None:
        client = get_client()
        _collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def add_chunks(chunks: List[Dict], embedder) -> None:
    """
    Store chunk embeddings + metadata in ChromaDB.
    chunks: [{"chunk_text": str, "metadata": {...}}]
    embedder: a SentenceTransformer instance (from embedder.get_embedder()).
    """
    if not chunks:
        return

    col = get_collection()
    texts = [c["chunk_text"] for c in chunks]
    embeddings = embedder.encode(texts, show_progress_bar=False, convert_to_numpy=True).tolist()
    ids = [
        f"{c['metadata']['document_id']}_{c['metadata']['page_number']}_{c['metadata']['chunk_index']}"
        for c in chunks
    ]
    metadatas = [c["metadata"] for c in chunks]
    col.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)
    logger.info("Stored %d chunks in ChromaDB", len(chunks))


def _empty_result() -> Dict:
    """ChromaDB's query result shape, with no hits."""
    return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}


def query_chunks(query_embedding: List[float], top_k: int = TOP_K_RESULTS,
                 document_id: Optional[str] = None) -> Dict:
    """
    Return the top_k most similar chunks for the given query embedding.

    The collection is created with cosine space, so `distances` are cosine
    distances (0.0 = identical, 2.0 = opposite). Ranking into similarity
    scores is the retriever's job — this function stays a thin ChromaDB wrapper.

    Args:
      query_embedding — 384-dim vector from embedder.embed_query().
      top_k           — number of chunks to return.
      document_id     — when given, restrict the search to that document.

    Returns:
      ChromaDB's raw query result:
        {"ids": [[...]], "documents": [[...]],
         "metadatas": [[...]], "distances": [[...]]}
      An empty / missing collection returns the same shape with empty
      inner lists rather than raising.
    """
    if not query_embedding or top_k <= 0:
        return _empty_result()

    try:
        col = get_collection()
        if col.count() == 0:
            logger.info("Vector store is empty — returning no results.")
            return _empty_result()

        where = {"document_id": document_id} if document_id else None
        return col.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
    except Exception as exc:
        logger.error("ChromaDB query failed: %s", exc)
        return _empty_result()


def delete_document_vectors(document_id: str) -> None:
    """Remove all chunks belonging to a document from ChromaDB."""
    try:
        col = get_collection()
        col.delete(where={"document_id": document_id})
        logger.info("Deleted vectors for document %s", document_id)
    except Exception as exc:
        logger.error("Error deleting vectors for %s: %s", document_id, exc)
