"""
test_embedder.py — Unit tests for embedder.py
Implemented Day 3. Requires the all-MiniLM-L6-v2 model (downloaded on first
run / cached by sentence-transformers afterward).
"""
from app.services.embedder import embed_texts, embed_query


def test_embedding_dimensions():
    """all-MiniLM-L6-v2 must produce 384-dim vectors."""
    vectors = embed_texts(["hello world"])
    assert len(vectors) == 1
    assert len(vectors[0]) == 384


def test_embedding_consistency():
    """Same text must produce identical embeddings."""
    v1 = embed_texts(["the quick brown fox"])[0]
    v2 = embed_texts(["the quick brown fox"])[0]
    assert v1 == v2


def test_batch_encoding():
    """Batch encoding must return one vector per input text."""
    texts = ["first chunk", "second chunk", "third chunk"]
    vectors = embed_texts(texts)
    assert len(vectors) == len(texts)
    for v in vectors:
        assert len(v) == 384


def test_embed_query_returns_flat_list():
    """embed_query must return a flat list of floats, not a nested list."""
    vector = embed_query("what is in the document?")
    assert isinstance(vector, list)
    assert len(vector) == 384
    assert all(isinstance(x, float) for x in vector)
