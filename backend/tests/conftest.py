"""
conftest.py — shared pytest fixtures.

WHY THIS FILE EXISTS
--------------------
Before it, two test modules read the **developer's live ChromaDB store**:

  * test_retriever.py asserted measured similarity scores against whatever was
    in `backend/data/chroma_db/`, and asserted the total chunk count was
    exactly 5 — so uploading a fourth document through the application turned
    the suite red for a reason that had nothing to do with the code.
  * test_api.py::test_ask_returns_answer_and_citations needed the same corpus
    present, and failed with a "re-ingest the Day 3 sample PDFs" message on a
    fresh clone.

That made a green suite depend on mutable state outside the repository, which
is the one thing the committed fixtures were supposed to prevent. It also meant
running the tests read (and, on a wrong turn, could have written to) the user's
real uploaded documents.

WHAT IT DOES INSTEAD
--------------------
`isolated_vector_store` redirects `vector_store` at a throwaway ChromaDB
directory created by pytest for the session, and `fixture_corpus` ingests the
committed fixture PDFs into it through the **real** pipeline — the same
extraction, OCR fallback, cleaning, chunking and embedding the application
runs. Nothing is mocked except, elsewhere, the Ollama HTTP call.

So the corpus is now reproduced from committed bytes on every run, on any
machine, and the developer's live store is never touched. The reason the
fixture PDFs are committed (recorded in .gitignore) is unchanged and now
actually holds: the same bytes produce the same text, hence the same
embeddings, hence the same scores.

OCR AVAILABILITY
----------------
`scanned_image_only.pdf` is image-only and only yields text through Tesseract.
Where Tesseract is absent the corpus is still built — that document simply
contributes no chunks — and the tests that depend on it skip with a message
naming the reason, rather than failing as though the code were broken.
`corpus_has_ocr` is the flag those tests use.
"""
import uuid
from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).parent / "fixtures"

# The documents the retrieval tests reason about. Kept small on purpose: the
# suite re-embeds these on every session, so each extra page costs real time.
CORPUS_FILES = (
    "native_single.pdf",        # 1 page, native text
    "native_multi.pdf",         # 3 pages, native, one distinct topic per page
    "scanned_image_only.pdf",   # 1 page, image-only — OCR path
)


@pytest.fixture(scope="session", autouse=True)
def isolated_vector_store(tmp_path_factory):
    """
    Point the vector store at a throwaway directory for the whole session.

    autouse, so no test can reach the real store by forgetting to ask for the
    fixture. `CHROMA_PERSIST_DIR` is patched on the `vector_store` module rather
    than on `app.config`, because vector_store binds the value at import with
    `from app.config import CHROMA_PERSIST_DIR` — patching config alone would
    silently do nothing and the tests would quietly go back to the live store.
    """
    from app.services import vector_store

    store_dir = tmp_path_factory.mktemp("chroma_test_store")
    saved = (
        vector_store.CHROMA_PERSIST_DIR,
        vector_store._client,
        vector_store._collection,
    )
    vector_store.CHROMA_PERSIST_DIR = str(store_dir)
    vector_store._client = None
    vector_store._collection = None

    yield store_dir

    (
        vector_store.CHROMA_PERSIST_DIR,
        vector_store._client,
        vector_store._collection,
    ) = saved


@pytest.fixture(scope="session", autouse=True)
def isolated_database(tmp_path_factory):
    """
    Give the suite its own SQLite file instead of the developer's real one.

    Several tests insert and delete real `documents` rows. Against the live
    database that writes into the user's actual document catalogue — harmless in
    practice, but it makes the suite a process that mutates real data, and a
    test that died between insert and cleanup would leave a phantom row visible
    in the running application's document list.

    Patched on `app.models.database` for the same reason as CHROMA_PERSIST_DIR
    above: the module binds DATABASE_PATH at import.

    `routers/health.py` keeps checking the real database file, which is correct —
    `database_available` should report on the deployment, not on the fixture.
    """
    from app.models import database

    db_path = tmp_path_factory.mktemp("sqlite_test_db") / "pdf_chatbot_test.db"
    saved = database.DATABASE_PATH
    database.DATABASE_PATH = str(db_path)
    database.init_db()

    yield db_path

    database.DATABASE_PATH = saved


@pytest.fixture
def scratch_vector_store(tmp_path):
    """
    A private, empty vector store for ONE test.

    Tests that ingest documents to assert an ingestion *outcome* must not write
    into the session corpus the retrieval tests measure against. Without this,
    test_ingestion_pipeline.py's four ingested fixtures raised the shared store
    from 5 chunks to 30 and turned test_returns_top_k_results red — the same
    class of shared-state coupling this conftest exists to remove, reintroduced
    from inside the suite.
    """
    from app.services import vector_store

    saved = (
        vector_store.CHROMA_PERSIST_DIR,
        vector_store._client,
        vector_store._collection,
    )
    vector_store.CHROMA_PERSIST_DIR = str(tmp_path / "chroma_scratch")
    vector_store._client = None
    vector_store._collection = None

    yield

    (
        vector_store.CHROMA_PERSIST_DIR,
        vector_store._client,
        vector_store._collection,
    ) = saved


def ingest_fixture(pdf_name: str, document_id: str | None = None) -> dict:
    """
    Run one committed fixture PDF through the real ingestion pipeline.

    Deliberately bypasses `pdf_processor.process_document`, which requires a
    SQLite row and writes status back to it. Everything that shapes the vectors
    — extraction, the OCR fallback, cleaning, chunking, embedding — is the
    production code path.

    Returns {document_id, filename, pages, ocr_pages, chunks}.
    """
    from app.services.chunker import chunk_pages
    from app.services.embedder import get_embedder
    from app.services.pdf_processor import extract_text_from_pdf
    from app.services.text_cleaner import clean_pages
    from app.services.vector_store import add_chunks

    document_id = document_id or str(uuid.uuid4())
    pages, ocr_pages = extract_text_from_pdf(FIXTURE_DIR / pdf_name)
    cleaned = clean_pages(pages)
    chunks = chunk_pages(cleaned, document_id, pdf_name)
    if chunks:
        add_chunks(chunks, get_embedder())

    return {
        "document_id": document_id,
        "filename": pdf_name,
        "pages": len(pages),
        "ocr_pages": ocr_pages,
        "chunks": len(chunks),
    }


@pytest.fixture(scope="session")
def fixture_corpus(isolated_vector_store):
    """
    The ingested corpus: {filename: {document_id, pages, ocr_pages, chunks}}.

    Session-scoped because ingesting costs an embedding-model load plus, for the
    scanned page, a real Tesseract call — a few seconds once, rather than once
    per test module.
    """
    return {name: ingest_fixture(name) for name in CORPUS_FILES}


@pytest.fixture(scope="session")
def corpus_chunk_count(fixture_corpus):
    """Total chunks actually stored — derived, never hard-coded."""
    return sum(doc["chunks"] for doc in fixture_corpus.values())


@pytest.fixture(scope="session")
def corpus_has_ocr(fixture_corpus):
    """True when Tesseract was available and the scanned fixture produced chunks."""
    scanned = fixture_corpus["scanned_image_only.pdf"]
    return scanned["ocr_pages"] > 0 and scanned["chunks"] > 0


@pytest.fixture(scope="session")
def sample_docs(fixture_corpus):
    """filename → document_id, for tests that scope retrieval to one document."""
    return {name: doc["document_id"] for name, doc in fixture_corpus.items()}
