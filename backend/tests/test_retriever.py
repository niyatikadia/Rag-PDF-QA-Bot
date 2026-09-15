"""
test_retriever.py — Unit tests for retriever.py and vector_store.query_chunks
Implemented: Day 4.

These run against the persisted ChromaDB store (CHROMA_PERSIST_DIR), which
already holds the three sample documents ingested end-to-end in Day 3:

  native_single.pdf        1 page,  native text
  native_multi.pdf         3 pages, native text, one distinct topic per page
                           (p1 = AI history, p2 = ChromaDB, p3 = Tesseract OCR)
  scanned_image_only.pdf   1 page,  image-only, recovered via OCR
                           (contains "PINEAPPLE OCR SUCCESS")

Total: 5 chunks. Re-ingesting is not required — see SESSION_04_INGESTION_COMPLETE.md.
"""
import pytest

from app.services import vector_store
from app.services.retriever import retrieve, distance_to_score

# Documents the Day 3 session left in the store.
EXPECTED_FILENAMES = {
    "native_single.pdf",
    "native_multi.pdf",
    "scanned_image_only.pdf",
}
EXPECTED_CHUNK_COUNT = 5

# Score bands measured against this corpus: an on-topic query tops out around
# 0.58-0.79, an off-topic one around 0.06-0.08. The thresholds sit well inside
# that gap so the tests assert separation, not exact model output.
RELEVANT_SCORE_FLOOR = 0.50
UNRELATED_SCORE_CEILING = 0.30


@pytest.fixture(scope="module")
def sample_docs():
    """
    Map filename → document_id for the Day 3 sample documents.

    Fails loudly (rather than skipping) if the store is missing them, since
    a wiped store means retrieval is untested, not that it's fine.
    """
    collection = vector_store.get_collection()
    stored = collection.get(include=["metadatas"])
    metadatas = stored.get("metadatas") or []

    by_filename = {m["filename"]: m["document_id"] for m in metadatas}
    missing = EXPECTED_FILENAMES - set(by_filename)
    if missing:
        pytest.fail(
            f"Sample documents missing from ChromaDB: {sorted(missing)}. "
            "Re-upload the Day 3 test PDFs (see docs/SESSION_04_INGESTION_COMPLETE.md) "
            "before running the retriever tests."
        )
    return by_filename


def test_returns_top_k_results(sample_docs):
    """retrieve() must honour top_k, and cap at the number of stored chunks."""
    assert len(retrieve("artificial intelligence", top_k=1)) == 1
    assert len(retrieve("artificial intelligence", top_k=3)) == 3

    # top_k larger than the store returns everything available, not an error.
    everything = retrieve("artificial intelligence", top_k=99)
    assert len(everything) == EXPECTED_CHUNK_COUNT

    # Every result carries the documented shape.
    for result in everything:
        assert set(result) == {"chunk_id", "text", "metadata", "score", "distance"}
        assert isinstance(result["text"], str) and result["text"]
        assert 0.0 <= result["score"] <= 1.0
        for field in ("document_id", "filename", "page_number",
                      "chunk_index", "extraction_method"):
            assert field in result["metadata"]


def test_relevance_ordering(sample_docs):
    """Results are ranked best-first, and an on-topic query surfaces the right chunk."""
    results = retrieve(
        "history of artificial intelligence research since the 1950s", top_k=5
    )
    assert len(results) == EXPECTED_CHUNK_COUNT

    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True), f"not ranked by score: {scores}"

    # native_multi.pdf page 1 is the AI-history page.
    top = results[0]
    assert top["metadata"]["filename"] == "native_multi.pdf"
    assert top["metadata"]["page_number"] == 1
    assert top["score"] >= RELEVANT_SCORE_FLOOR

    # A different on-topic query must promote a different page of the same doc.
    ocr_topic = retrieve("What is Tesseract optical character recognition?", top_k=5)
    assert ocr_topic[0]["metadata"]["filename"] == "native_multi.pdf"
    assert ocr_topic[0]["metadata"]["page_number"] == 3
    assert ocr_topic[0]["score"] >= RELEVANT_SCORE_FLOOR


def test_unrelated_query_returns_low_scores(sample_docs):
    """An off-topic question still returns chunks, but with clearly low relevance."""
    relevant = retrieve("What is ChromaDB used for?", top_k=5)
    unrelated = retrieve(
        "How do I bake a chocolate chip cookie with butter and sugar?", top_k=5
    )

    # Nothing is filtered out — scoring is the caller's cue, not an empty list.
    assert len(unrelated) == EXPECTED_CHUNK_COUNT
    assert unrelated[0]["score"] < UNRELATED_SCORE_CEILING
    assert unrelated[0]["score"] < relevant[0]["score"]


def test_empty_store_returns_empty_list(monkeypatch):
    """An empty vector store yields [] rather than raising."""
    import chromadb

    empty_collection = chromadb.EphemeralClient().get_or_create_collection(
        name="empty_test_collection", metadata={"hnsw:space": "cosine"}
    )
    assert empty_collection.count() == 0
    monkeypatch.setattr(vector_store, "_collection", empty_collection)

    assert retrieve("anything at all", top_k=5) == []
    # The raw store wrapper keeps ChromaDB's result shape, just with no hits.
    raw = vector_store.query_chunks([0.0] * 384, top_k=5)
    assert raw["documents"] == [[]]
    assert raw["metadatas"] == [[]]
    assert raw["distances"] == [[]]


def test_empty_query_returns_empty_list(sample_docs):
    """Empty or whitespace-only questions short-circuit before embedding."""
    assert retrieve("", top_k=5) == []
    assert retrieve("   \n\t ", top_k=5) == []


def test_document_id_filter(sample_docs):
    """document_id restricts retrieval to a single document."""
    multi_id = sample_docs["native_multi.pdf"]
    scanned_id = sample_docs["scanned_image_only.pdf"]
    question = "What was the keyword for retrieval testing in the scanned document?"

    # Unfiltered, the scanned document wins this question.
    unfiltered = retrieve(question, top_k=5)
    assert unfiltered[0]["metadata"]["document_id"] == scanned_id

    # Filtered to native_multi.pdf, only its 3 chunks come back.
    filtered = retrieve(question, top_k=5, document_id=multi_id)
    assert len(filtered) == 3
    assert all(r["metadata"]["document_id"] == multi_id for r in filtered)
    assert all(r["metadata"]["filename"] == "native_multi.pdf" for r in filtered)

    # Filtering to the scanned document returns only its single chunk.
    scanned_only = retrieve(question, top_k=5, document_id=scanned_id)
    assert len(scanned_only) == 1
    assert scanned_only[0]["metadata"]["document_id"] == scanned_id

    # An unknown document_id matches nothing.
    assert retrieve(question, top_k=5, document_id="no-such-document-id") == []


def test_ocr_chunk_retrievable_with_correct_metadata(sample_docs):
    """OCR-derived text is searchable and tagged extraction_method='ocr'."""
    results = retrieve(
        "What was the keyword for retrieval testing in the scanned document?", top_k=5
    )
    top = results[0]

    assert "PINEAPPLE" in top["text"].upper()
    assert top["metadata"]["filename"] == "scanned_image_only.pdf"
    assert top["metadata"]["page_number"] == 1
    assert top["metadata"]["extraction_method"] == "ocr"
    assert top["score"] >= RELEVANT_SCORE_FLOOR
    assert top["chunk_id"] == f"{sample_docs['scanned_image_only.pdf']}_1_0"


def test_distance_to_score_conversion():
    """Cosine distance → 0.0-1.0 relevance score, clamped at both ends."""
    assert distance_to_score(0.0) == 1.0
    assert distance_to_score(0.5) == 0.5
    assert distance_to_score(1.0) == 0.0
    assert distance_to_score(-1e-06) == 1.0    # float error on an exact match
    assert distance_to_score(1.8) == 0.0       # near-opposite vectors
    assert distance_to_score(None) == 0.0
