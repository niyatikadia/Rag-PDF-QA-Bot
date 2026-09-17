"""
test_ingestion_pipeline.py — end-to-end ingestion through `process_document`.

WHY THIS MODULE EXISTS
----------------------
The specification asks for ingestion outcomes that nothing in the suite
actually asserted:

  * §19.2 — "Upload a scanned/image-only test PDF and verify OCR fallback
    triggers and produces a 'ready' status with ocr_pages_count > 0."
  * §32   — "Document with zero native text but readable scanned pages still
    reaches 'ready' status via OCR."
  * §32   — "Document with zero text from both native extraction AND OCR is
    correctly marked 'failed'."
  * §32   — "Chunks correctly tagged with extraction_method (native vs ocr)."
  * §20   — stress/edge verification over large PDFs and PDFs mixing native and
    scanned pages.

`test_ocr_processor.py` covers `ocr_page` in isolation with Tesseract mocked,
which is the right shape for a unit test but proves nothing about the pipeline
decision — whether a page actually falls back, whether the count reaches SQLite,
whether the document still reaches 'ready'. That decision lives in
`pdf_processor.extract_text_from_pdf` and `process_document`, and was untested.

Five committed fixture PDFs existed for exactly these cases and were unused:
scanned_image_only.pdf, no_text.pdf, mixed_native_scanned.pdf,
large_native.pdf, repeated_header_footer.pdf.

These run the real pipeline against the isolated store and database that
conftest.py sets up. Nothing is mocked. Tests needing OCR skip, with the reason
named, where Tesseract is absent.
"""
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.models import database as db
from app.services.ocr_processor import is_ocr_available
from app.services.pdf_processor import extract_text_from_pdf, process_document

# Defined here rather than imported from conftest: `tests` is a package, so
# conftest is not importable as a top-level module, and importing it as
# `tests.conftest` would load the plugin module a second time under a
# different name. This mirrors test_api.py.
FIXTURE_DIR = Path(__file__).parent / "fixtures"

# Every test here ingests documents. They each get a private, empty vector store
# so their chunks never reach the session corpus that test_retriever.py measures
# against — see conftest.scratch_vector_store.
pytestmark = pytest.mark.usefixtures("scratch_vector_store")

OCR_AVAILABLE = is_ocr_available()
requires_ocr = pytest.mark.skipif(
    not OCR_AVAILABLE,
    reason="Tesseract is not installed — the OCR fallback cannot run on this machine.",
)


def _ingest(pdf_name: str, tmp_path) -> dict:
    """
    Copy a fixture to a temp location, register it, run the real ingestion, and
    return the resulting SQLite row.

    The file is copied rather than ingested in place because `process_document`
    is given the path the upload handler saved to, and a failure path deletes it.
    """
    doc_id = str(uuid.uuid4())
    pdf_path = tmp_path / f"{doc_id}.pdf"
    pdf_path.write_bytes((FIXTURE_DIR / pdf_name).read_bytes())

    db.insert_document({
        "document_id": doc_id,
        "filename": pdf_name,
        "original_path": str(pdf_path),
        "upload_timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "processing",
    })
    try:
        process_document(doc_id, pdf_path)
        return db.get_document(doc_id)
    finally:
        db.delete_document(doc_id)


# ── §19.2 / §32 — the OCR fallback, end to end ──────────────────────────────


@requires_ocr
def test_scanned_pdf_reaches_ready_via_ocr(tmp_path):
    """
    §32: "Document with zero native text but readable scanned pages still
    reaches 'ready' status via OCR."
    """
    row = _ingest("scanned_image_only.pdf", tmp_path)

    assert row["status"] == "ready", row["error_message"]
    assert row["total_pages"] == 1
    assert row["ocr_pages_count"] == 1, "the image-only page should have fallen back to OCR"
    assert row["total_chunks"] >= 1


@requires_ocr
def test_scanned_pdf_chunks_are_tagged_ocr(tmp_path):
    """§32: chunks from an OCR'd page must carry extraction_method='ocr'."""
    pages, ocr_pages = extract_text_from_pdf(FIXTURE_DIR / "scanned_image_only.pdf")

    assert ocr_pages == 1
    assert [p["extraction_method"] for p in pages] == ["ocr"]
    # The fixture's marker word proves Tesseract actually read the image rather
    # than the page having had a hidden text layer all along.
    assert "PINEAPPLE" in pages[0]["text"].upper()


@requires_ocr
def test_mixed_document_tags_each_page_by_how_it_was_read(tmp_path):
    """
    §20: a PDF mixing native-text and scanned pages must use native extraction
    where it can and OCR only where it must — per page, not per document.
    """
    pages, ocr_pages = extract_text_from_pdf(FIXTURE_DIR / "mixed_native_scanned.pdf")
    methods = [p["extraction_method"] for p in pages]

    assert len(pages) > 1
    assert "native" in methods, "at least one page has a real text layer"
    assert "ocr" in methods, "at least one page is image-only and must fall back"
    assert ocr_pages == methods.count("ocr")

    row = _ingest("mixed_native_scanned.pdf", tmp_path)
    assert row["status"] == "ready", row["error_message"]
    assert 0 < row["ocr_pages_count"] < row["total_pages"]


# ── §32 — the total-failure path ────────────────────────────────────────────


def test_document_with_no_text_at_all_is_marked_failed(tmp_path):
    """
    §32: "Document with zero text from both native extraction AND OCR is
    correctly marked 'failed'."

    §5.4 requires the stored message to explain that OCR was tried too, so the
    user is not left thinking the tool simply cannot read scans.
    """
    row = _ingest("no_text.pdf", tmp_path)

    assert row["status"] == "failed"
    assert row["total_chunks"] == 0
    assert "no text could be extracted" in (row["error_message"] or "").lower()
    assert "ocr" in (row["error_message"] or "").lower()


def test_failure_message_names_the_upload_not_the_storage_path(tmp_path):
    """
    The sanitising guard applies on this path too: a failed document's message
    is rendered verbatim by DocumentCard, so it must not disclose the server's
    filesystem layout or the internal document id.
    """
    doc_id = str(uuid.uuid4())
    pdf_path = tmp_path / f"{doc_id}.pdf"
    pdf_path.write_bytes((FIXTURE_DIR / "no_text.pdf").read_bytes())

    db.insert_document({
        "document_id": doc_id,
        "filename": "holiday-scan.pdf",
        "original_path": str(pdf_path),
        "upload_timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "processing",
    })
    try:
        process_document(doc_id, pdf_path)
        message = db.get_document(doc_id)["error_message"] or ""
    finally:
        db.delete_document(doc_id)

    for leak in (str(pdf_path), str(pdf_path.parent), doc_id, "uploads"):
        assert leak not in message, f"error message disclosed {leak!r}: {message!r}"


# ── §20 — larger and structurally awkward documents ─────────────────────────


def test_large_native_document_ingests_every_page(tmp_path):
    """§20 stress case: a multi-page native PDF chunks all of its pages."""
    row = _ingest("large_native.pdf", tmp_path)

    assert row["status"] == "ready", row["error_message"]
    assert row["total_pages"] >= 15, "large_native.pdf is the 15+ page stress fixture"
    assert row["ocr_pages_count"] == 0, "a native-text PDF must never pay for OCR"
    # Chunking at 500/100 must produce at least one chunk per page of real text.
    assert row["total_chunks"] >= row["total_pages"]


def test_repeated_header_document_is_not_stripped_to_nothing(tmp_path):
    """
    §5.1 header/footer stripping is deliberately aggressive, guarded so it can
    never empty a page. This is the document that guard exists for: every line
    looks like a running header, and without the guard the whole thing was
    reduced to nothing and reported unreadable.
    """
    row = _ingest("repeated_header_footer.pdf", tmp_path)

    assert row["status"] == "ready", row["error_message"]
    assert row["total_chunks"] > 0, "stripping emptied the document — the guard regressed"
