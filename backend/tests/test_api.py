"""
test_api.py — API integration tests using FastAPI TestClient.

Covers every endpoint in spec §9: upload (valid, wrong extension, wrong MIME,
empty), list, get, delete, /chat/ask (answer, not-found short circuit, 503,
empty question) and /health. Only `llm_service.call_ollama` is ever stubbed —
retrieval, context construction and citation extraction all run for real, so
the suite is meaningful without a running Ollama.
"""
import asyncio
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models import database as db
from app.services import llm_service

client = TestClient(app)

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def test_root_returns_200():
    response = client.get("/")
    assert response.status_code == 200


def test_health_endpoint_exists():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "ollama_available" in data
    assert "ocr_available" in data
    assert "database_available" in data


def test_document_list_initially_empty():
    response = client.get("/api/documents")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_upload_rejects_non_pdf():
    response = client.post(
        "/api/documents/upload",
        files={"file": ("test.txt", b"not a pdf", "text/plain")},
    )
    assert response.status_code == 400


def test_upload_rejects_empty_file():
    response = client.post(
        "/api/documents/upload",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert response.status_code == 400


# ── Missing / empty multipart filename (Day 3 — mypy union-attr) ──────────────
#
# mypy flagged `file.filename.lower()` in _validate_metadata(), because Starlette
# types UploadFile.filename as `str | None`. Reproducing it showed the None case
# is NOT reachable through FastAPI: a multipart part carrying no filename
# parameter is parsed as a plain form field, so request validation refuses it
# with 422 before the handler is entered. The handler was still made total over
# its declared input type (`file.filename or ""`), and these two tests pin the
# contract that makes that safe — if a future Starlette or FastAPI release ever
# started binding a filename-less part to UploadFile, the first test would fail
# here rather than surfacing as an AttributeError 500 in production.

# The bodies are hand-built rather than passed through httpx's `files=`, because
# httpx omits the filename parameter entirely when given an empty string — which
# collapses the two cases below into the same request and would silently stop the
# second test from exercising what it names.
def _multipart(disposition: bytes) -> bytes:
    return (
        b"--BOUNDARY\r\n" + disposition + b"\r\n"
        b"Content-Type: application/pdf\r\n"
        b"\r\n"
        b"%PDF-1.4 body\r\n"
        b"--BOUNDARY--\r\n"
    )


_MULTIPART_HEADERS = {"Content-Type": "multipart/form-data; boundary=BOUNDARY"}


def test_upload_without_filename_is_refused_before_the_handler():
    """A part with no filename parameter never reaches _validate_metadata()."""
    response = client.post(
        "/api/documents/upload",
        content=_multipart(b'Content-Disposition: form-data; name="file"'),
        headers=_MULTIPART_HEADERS,
    )
    # 422 from request validation, NOT 500 from an AttributeError on None.
    assert response.status_code == 422


def test_upload_with_empty_filename_is_refused_as_a_non_pdf():
    """The reachable near-miss: filename present but empty is a clean 400."""
    response = client.post(
        "/api/documents/upload",
        content=_multipart(b'Content-Disposition: form-data; name="file"; filename=""'),
        headers=_MULTIPART_HEADERS,
    )
    assert response.status_code == 400
    assert "pdf" in response.json()["detail"].lower()


# ── Oversized uploads must not be buffered whole (Day 2 — PERF-3) ─────────────
#
# The handler used to do `content = await file.read()` and check the size
# afterwards, so memory grew with whatever the client sent regardless of the
# limit: measured on Day 2 at 20/60/150/400 MB, a rejected 400 MB body still
# allocated 401.7 MB of private memory (1.00x the body) before the server
# answered "File exceeds the 20 MB limit". The server would allocate twenty times
# its own stated maximum before declining.
#
# Memory is asserted indirectly, by counting bytes actually read: a peak-RSS
# assertion would be flaky, whereas "it stopped reading" is exact and is the
# property that bounds the memory.

class _CountingUpload:
    """
    Minimal UploadFile stand-in that serves a large body in chunks and records
    how much was consumed. Only `.filename`, `.content_type` and `.read(n)` are
    used by the upload path.
    """

    def __init__(self, total_bytes, filename="huge.pdf",
                 content_type="application/pdf"):
        self.filename = filename
        self.content_type = content_type
        self._remaining = total_bytes
        self.bytes_served = 0

    async def read(self, size=-1):
        if self._remaining <= 0:
            return b""
        n = self._remaining if size is None or size < 0 else min(size, self._remaining)
        self._remaining -= n
        self.bytes_served += n
        return b"0" * n


def test_oversized_upload_stops_reading_at_the_limit():
    from app.config import MAX_FILE_SIZE_BYTES
    from app.routers.documents import _UPLOAD_CHUNK_BYTES, _read_within_limit
    from fastapi import HTTPException

    body = MAX_FILE_SIZE_BYTES * 20          # 400 MB against a 20 MB limit
    upload = _CountingUpload(body)

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(_read_within_limit(upload))

    assert excinfo.value.status_code == 400
    assert "limit" in excinfo.value.detail

    # The whole point: it must not have consumed the entire body. The bound is
    # the limit plus the one chunk that crossed it.
    ceiling = MAX_FILE_SIZE_BYTES + _UPLOAD_CHUNK_BYTES
    assert upload.bytes_served <= ceiling, (
        f"read {upload.bytes_served:,} bytes of a {body:,}-byte body; the cap is "
        f"{ceiling:,}. The size limit is being applied after buffering, not "
        f"during — that is the Day 2 PERF-3 defect."
    )
    assert upload.bytes_served < body, "the entire body was buffered"


def test_upload_within_the_limit_is_read_in_full():
    """The bound must not truncate a legitimate file."""
    from app.config import MAX_FILE_SIZE_BYTES
    from app.routers.documents import _read_within_limit

    body = MAX_FILE_SIZE_BYTES          # exactly at the limit, which is allowed
    upload = _CountingUpload(body)
    content = asyncio.run(_read_within_limit(upload))

    assert len(content) == body
    assert upload.bytes_served == body


def test_empty_body_still_rejected_by_the_chunked_reader():
    from app.routers.documents import _read_within_limit
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(_read_within_limit(_CountingUpload(0)))
    assert excinfo.value.status_code == 400
    assert "empty" in excinfo.value.detail.lower()


def test_oversized_non_pdf_is_rejected_on_its_name_not_its_size():
    """
    Cheap rejections stay cheap: metadata is checked before the body is touched,
    so a huge .txt is refused on its extension and never buffered at all.
    """
    response = client.post(
        "/api/documents/upload",
        files={"file": ("huge.txt", b"x" * 1024, "text/plain")},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Only .pdf files are accepted."


def test_get_nonexistent_document_returns_404():
    response = client.get("/api/documents/nonexistent-id")
    assert response.status_code == 404


def test_delete_nonexistent_document_returns_404():
    response = client.delete("/api/documents/nonexistent-id")
    assert response.status_code == 404


def test_ask_empty_question_returns_400():
    response = client.post("/api/chat/ask", json={"question": ""})
    assert response.status_code == 400


def test_ask_whitespace_question_returns_400():
    response = client.post("/api/chat/ask", json={"question": "   \n  "})
    assert response.status_code == 400


# The Ollama call is stubbed in the tests below. Day 5 replaced the placeholder
# endpoint with the real pipeline, so an unstubbed request would spend minutes
# generating on CPU and make the suite depend on a running Ollama. Retrieval,
# context building and citation extraction all still run for real — only the
# HTTP call to the model is faked. End-to-end answers against the live model are
# verified manually (see docs/SESSION_06_RAG_PIPELINE_COMPLETE.md).

def test_ask_returns_answer_and_citations(monkeypatch):
    monkeypatch.setattr(
        llm_service, "call_ollama",
        lambda *a, **kw: "The documents describe a test page (native_single.pdf, Page 1).",
    )

    response = client.post("/api/chat/ask",
                           json={"question": "What is in the document?"})

    assert response.status_code == 200
    data = response.json()
    # Retrieval runs for real, so this needs the Day 3 sample PDFs in ChromaDB.
    # Without them the endpoint correctly short-circuits to the F11 answer —
    # which would fail here for a reason that has nothing to do with the API.
    assert data["answer"] != llm_service.NOT_FOUND_PHRASE, (
        "Nothing was retrieved — re-ingest the Day 3 sample PDFs "
        "(native_single.pdf, native_multi.pdf, scanned_image_only.pdf)."
    )
    assert "test page" in data["answer"]
    assert isinstance(data["citations"], list)
    assert data["processing_time_ms"] >= 0
    for citation in data["citations"]:
        assert set(citation) == {"filename", "pages", "relevance_score",
                                 "extraction_method"}
        assert 0.0 <= citation["relevance_score"] <= 1.0


def test_ask_unknown_document_id_returns_not_found_without_calling_llm(monkeypatch):
    """
    Retrieval finds nothing for an unknown document_id, so the F11 answer comes
    back without the LLM ever being consulted.
    """
    def explode(*a, **kw):
        raise AssertionError("Ollama must not be called when nothing was retrieved")

    monkeypatch.setattr(llm_service, "call_ollama", explode)

    response = client.post(
        "/api/chat/ask",
        json={"question": "What is in the document?", "document_id": "no-such-doc"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == llm_service.NOT_FOUND_PHRASE
    assert data["citations"] == []


def test_ask_returns_503_when_ollama_is_unavailable(monkeypatch):
    """A stopped Ollama is an unavailable dependency (503), not a backend bug (500)."""
    def down(*a, **kw):
        raise llm_service.LLMUnavailableError(
            "Cannot reach the language model. Make sure Ollama is running."
        )

    monkeypatch.setattr(llm_service, "call_ollama", down)

    response = client.post("/api/chat/ask",
                           json={"question": "What is in the document?"})

    assert response.status_code == 503
    assert "ollama" in response.json()["detail"].lower()


# ── Delete during ingestion (Day 9 regression) ────────────────────────────────
#
# Deleting a document while it was still being ingested returned HTTP 500 and
# left the record, the file AND the vectors in place. Cause: on Windows the PDF
# is locked while PyMuPDF has it open, so `pdf_path.unlink()` raised
# PermissionError (WinError 32) and aborted the handler before the record was
# removed. Verified live against the running backend on Day 9; these tests pin
# both halves of the fix.

@pytest.fixture
def temporary_document(tmp_path):
    """A real SQLite record pointing at a real file, cleaned up afterwards."""
    doc_id = f"day9-test-{uuid.uuid4()}"
    pdf_path = tmp_path / f"{doc_id}.pdf"
    shutil.copy(FIXTURE_DIR / "native_single.pdf", pdf_path)
    db.insert_document({
        "document_id": doc_id,
        "filename": "delete_test.pdf",
        "original_path": str(pdf_path),
        "upload_timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "processing",
    })
    yield doc_id, pdf_path
    db.delete_document(doc_id)


def test_delete_succeeds_even_when_the_pdf_file_is_locked(temporary_document, monkeypatch):
    """
    A locked PDF must not abort the delete. The record has to go regardless, or
    the user is left with a document they cannot remove and a 500 they cannot act on.
    """
    doc_id, _ = temporary_document

    def locked(self, *a, **kw):
        raise PermissionError(
            32, "The process cannot access the file because it is being used "
                "by another process"
        )

    monkeypatch.setattr(Path, "unlink", locked)

    response = client.delete(f"/api/documents/{doc_id}")

    assert response.status_code == 200, response.text
    assert db.get_document(doc_id) is None, "record survived the delete"


def test_ingestion_discards_its_work_if_the_document_was_deleted(tmp_path, monkeypatch):
    """
    Ingestion runs after the upload response, so a delete can land mid-flight.
    When the record is gone by the time chunks are ready they must be dropped —
    storing them would leave vectors for a document nobody can see or delete —
    and the file this task still held open must be removed.
    """
    from app.services import pdf_processor

    stored = []
    monkeypatch.setattr("app.services.vector_store.add_chunks",
                        lambda *a, **kw: stored.append(a))

    removed = []
    monkeypatch.setattr("app.services.vector_store.delete_document_vectors",
                        lambda doc_id: removed.append(doc_id))

    # No SQLite row is ever created — the same state a completed delete leaves.
    doc_id = f"day9-deleted-{uuid.uuid4()}"
    pdf_path = tmp_path / f"{doc_id}.pdf"
    shutil.copy(FIXTURE_DIR / "native_single.pdf", pdf_path)

    pdf_processor.process_document(doc_id, pdf_path)

    assert stored == [], "chunks were stored for a deleted document"
    assert removed == [doc_id], "vectors were not cleaned up"
    assert not pdf_path.exists(), "the orphaned PDF was left on disk"


# ── Error messages must not leak server paths (Day 10 regression) ─────────────

def test_failed_ingestion_error_message_names_the_upload_not_the_server_path(tmp_path):
    """
    A corrupted PDF is correctly marked 'failed', but PyMuPDF's own message names
    the absolute file it was handed —
    "Failed to open file 'C:\\...\\data\\uploads\\<uuid>.pdf'" — and DocumentCard
    renders `error_message` verbatim to the user. Storing the raw exception
    therefore disclosed the server's filesystem layout and the internal document
    id in the browser (reported Day 9, closed Day 10).

    The message must still identify *which* upload failed, by the name the user
    gave it, and must contain nothing internal.
    """
    from app.services import pdf_processor

    doc_id = f"day10-corrupt-{uuid.uuid4()}"
    uploads = tmp_path / "data" / "uploads"
    uploads.mkdir(parents=True)
    pdf_path = uploads / f"{doc_id}.pdf"
    pdf_path.write_bytes(b"this is not a pdf, it is garbage bytes with a .pdf name")

    db.insert_document({
        "document_id": doc_id,
        "filename": "broken_upload.pdf",
        "original_path": str(pdf_path),
        "upload_timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "processing",
    })
    try:
        pdf_processor.process_document(doc_id, pdf_path)
        row = db.get_document(doc_id)

        assert row["status"] == "failed"
        message = row["error_message"] or ""
        assert message, "a failed document must explain why"

        # Still actionable: the user can tell which of their uploads failed.
        # This also proves the path was *substituted*, not merely truncated —
        # the filename only appears here because it replaced the storage path.
        assert "broken_upload.pdf" in message

        # Nothing internal — checked in every form the path can appear in.
        # PyMuPDF escapes its separators, so the raw message carries
        # `data\\uploads\\<uuid>.pdf` while str(pdf_path) carries
        # `data\uploads\<uuid>.pdf`. Asserting only the plain form passed
        # vacuously while the directory was still visible to the user; that is
        # exactly the bug a live upload exposed, so each candidate is asserted
        # plain, backslash-escaped and posix.
        leaks = [str(pdf_path), str(pdf_path.parent), str(tmp_path), doc_id]
        for leak in leaks:
            for form in (leak, leak.replace("\\", "\\\\"), leak.replace("\\", "/")):
                assert form not in message, f"leaked {form!r} in: {message}"

        # And nothing that merely looks like a path fragment of the store.
        assert "uploads" not in message, f"upload directory leaked: {message}"
    finally:
        db.delete_document(doc_id)
