"""
pdf_processor.py — Orchestrates the full PDF ingestion pipeline.
Called after a PDF is saved to disk; updates SQLite status when done.

Pipeline:
  PDF file → text extractor → [OCR fallback] → cleaner → chunker
           → embedder → vector store → status = 'ready'

The OCR fallback runs per page, only when native extraction yields less than
MIN_CHARS_FOR_NATIVE_TEXT characters (spec §5.1). A document is marked 'failed'
only if every page yields zero usable text from both native extraction and OCR
(spec §5.4).

Implemented: Day 2 (extraction + cleaning) → Day 3 (OCR fallback, chunking,
embedding, vector storage) → Day 9 (delete-during-ingestion cleanup) →
Day 10 (error messages sanitised before they reach the user).
"""
import logging
from pathlib import Path
from typing import Dict, List, Tuple

from app.models import database as db

logger = logging.getLogger(__name__)

MIN_CHARS_FOR_NATIVE_TEXT = 10   # below this, a page is treated as textless


def extract_text_from_pdf(pdf_path: Path) -> Tuple[List[Dict], int]:
    """
    Open the PDF with PyMuPDF and extract text page by page. Any page whose
    native text is below MIN_CHARS_FOR_NATIVE_TEXT is rendered to an image
    and run through the OCR fallback (ocr_processor.ocr_page); if OCR
    recovers usable text, that page's extraction_method becomes "ocr".

    Returns:
        (pages, ocr_pages_count) where pages is
        [{"page_number": int, "text": str, "extraction_method": "native"|"ocr"}, ...]
    """
    import fitz  # PyMuPDF
    from app.services.ocr_processor import ocr_page

    pages: List[Dict] = []
    ocr_pages_count = 0
    doc = fitz.open(str(pdf_path))
    try:
        for i, page in enumerate(doc, start=1):
            text = page.get_text() or ""
            extraction_method = "native"

            if len(text.strip()) < MIN_CHARS_FOR_NATIVE_TEXT:
                logger.debug(
                    "Page %d has little/no native text (%d chars) — "
                    "attempting OCR fallback", i, len(text.strip())
                )
                ocr_text = ocr_page(page)
                if ocr_text and ocr_text.strip():
                    text = ocr_text
                    extraction_method = "ocr"
                    ocr_pages_count += 1
                    logger.info("Page %d recovered via OCR (%d chars)", i, len(text.strip()))
                else:
                    logger.debug("Page %d yielded no usable text via native extraction or OCR", i)

            pages.append({"page_number": i, "text": text, "extraction_method": extraction_method})
    finally:
        doc.close()
    return pages, ocr_pages_count


def _cleanup_deleted_document(document_id: str, pdf_path: Path) -> None:
    """
    Remove what is left of a document that was deleted while it was ingesting.

    The DELETE handler already dropped the SQLite row and asked ChromaDB to
    remove the document's vectors; it could not remove the PDF because this
    task still had it open. Vectors are removed again here because any chunks
    written between the two are ours to clean up.
    """
    try:
        from app.services.vector_store import delete_document_vectors
        delete_document_vectors(document_id)
    except Exception as exc:
        logger.warning("Could not remove vectors for deleted %s: %s", document_id, exc)
    try:
        if pdf_path.exists():
            pdf_path.unlink()
    except OSError as exc:
        logger.warning("Could not remove file for deleted %s: %s", document_id, exc)


def _safe_error_message(exc: Exception, pdf_path: Path, filename: str) -> str:
    """
    Turn an ingestion exception into a message that is safe to show the user.

    PyMuPDF reports a failure with the absolute path it was handed, e.g.
    "Failed to open file 'C:\\...\\backend\\data\\uploads\\<uuid>.pdf'". That
    string goes straight into `documents.error_message`, and DocumentCard
    renders it verbatim in the browser — so the raw exception disclosed the
    server's filesystem layout and the internal document id to the user
    (reported Day 9, closed Day 10).

    Every form the storage path can take is replaced with the name the user
    actually uploaded, so the message stays specific and actionable — "Failed to
    open file 'broken.pdf'" tells them exactly which upload failed — while
    naming nothing internal.

    "Every form" is doing real work here. PyMuPDF **escapes** the separators in
    its message, so the text carries `data\\\\uploads\\\\<uuid>.pdf` while
    `str(pdf_path)` carries `data\\uploads\\<uuid>.pdf` — matching only the
    plain form redacted the document id but left the directory visible (caught
    live on Day 10, after the first version of this function). Each candidate is
    therefore also matched in its backslash-escaped and forward-slash forms.
    Substitutions run longest-first so a full path is consumed before its own
    directory or basename can match inside it.
    """
    message = str(exc)

    paths = [pdf_path]
    try:
        resolved = pdf_path.resolve()
        if resolved != pdf_path:
            paths.append(resolved)
    except OSError:   # a path that cannot be resolved is still worth redacting
        pass

    # (needle, replacement) — the full file paths and the storage basename all
    # become the user's filename; the containing directory becomes a neutral
    # phrase, since on its own it names a location rather than this document.
    candidates = []
    for path in paths:
        candidates += [(str(path), filename), (path.as_posix(), filename)]
        candidates += [(str(path.parent), "the upload directory"),
                       (path.parent.as_posix(), "the upload directory")]
    candidates += [(pdf_path.name, filename), (pdf_path.stem, Path(filename).stem)]

    substitutions = []
    for needle, replacement in candidates:
        if not needle:
            continue
        substitutions.append((needle, replacement))
        escaped = needle.replace("\\", "\\\\")
        if escaped != needle:
            substitutions.append((escaped, replacement))

    for needle, replacement in sorted(substitutions, key=lambda s: len(s[0]), reverse=True):
        message = message.replace(needle, replacement)
    return message


def process_document(document_id: str, pdf_path: Path) -> None:
    """
    Entry point for document ingestion.
    Runs synchronously; FastAPI calls this in a background task.
    """
    logger.info("Starting ingestion for document %s", document_id)
    try:
        # ── Step 1: Extract text (native + OCR fallback per page) ──────────────
        page_data, ocr_pages_count = extract_text_from_pdf(pdf_path)
        total_pages = len(page_data)

        # ── Step 2: Clean text ────────────────────────────────────────────────
        from app.services.text_cleaner import clean_pages
        cleaned = clean_pages(page_data)

        if not cleaned:
            raise ValueError(
                "No text could be extracted from this PDF, even with OCR. "
                "It may be a corrupted file or contain no readable content."
            )

        # ── Step 3: Chunk ─────────────────────────────────────────────────────
        # Use the user's original filename (not the UUID-based storage name)
        # so citations shown later reference something the user recognizes.
        doc_row = db.get_document(document_id)
        original_filename = doc_row["filename"] if doc_row else pdf_path.name

        from app.services.chunker import chunk_pages
        chunks = chunk_pages(cleaned, document_id, original_filename)

        # ── Step 4: Embed + store ─────────────────────────────────────────────
        # Ingestion runs as a background task, so the user can delete the
        # document while we are still working on it. If the record is gone by
        # now, storing these chunks would leave vectors for a document nobody
        # can see or delete again (found Day 9). Clean up and stop instead —
        # the delete could not remove the PDF itself because this task still
        # had it open, so removing the file is our responsibility.
        if db.get_document(document_id) is None:
            logger.info("Document %s was deleted during ingestion — discarding "
                        "%d chunk(s) and removing its file.", document_id, len(chunks))
            _cleanup_deleted_document(document_id, pdf_path)
            return

        from app.services.embedder import get_embedder
        from app.services.vector_store import add_chunks
        embedder = get_embedder()
        add_chunks(chunks, embedder)

        logger.info(
            "Ingested %s: %d/%d pages usable (%d via OCR), %d chunks stored",
            document_id, len(cleaned), total_pages, ocr_pages_count, len(chunks),
        )
        db.update_document_status(
            document_id, "ready",
            total_pages=total_pages,
            total_chunks=len(chunks),
            ocr_pages_count=ocr_pages_count,
        )

    except Exception as exc:
        # The log keeps the raw exception — it is server-side and the full path
        # is what makes it debuggable. What is *stored* is sanitised, because
        # error_message is rendered to the user by DocumentCard.
        logger.error("Ingestion failed for %s: %s", document_id, exc)
        failed_row = db.get_document(document_id)
        failed_filename = failed_row["filename"] if failed_row else pdf_path.name
        db.update_document_status(
            document_id, "failed",
            error_message=_safe_error_message(exc, pdf_path, failed_filename),
        )
