"""
documents.py — Document upload / list / delete endpoints.

POST   /api/documents/upload
GET    /api/documents
GET    /api/documents/{document_id}
GET    /api/documents/{document_id}/file
DELETE /api/documents/{document_id}
"""
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from app.config import UPLOAD_DIR, MAX_FILE_SIZE_BYTES
from app.models import database as db
from app.models.schemas import DeleteResponse, DocumentInfo, UploadResponse
from app.services.pdf_processor import process_document

logger = logging.getLogger(__name__)
router = APIRouter()


# How much of the body is pulled in at a time by _read_within_limit.
_UPLOAD_CHUNK_BYTES = 1024 * 1024


def _ascii_filename(filename: str) -> str:
    """
    Make a filename safe to put inside a Content-Disposition header.

    Two things would otherwise break the response rather than the download:
    HTTP headers are latin-1, so a non-ASCII name ("नमस्ते.pdf", "café.pdf")
    raises UnicodeEncodeError when the header is encoded and the whole request
    500s; and a name containing a double quote or newline would terminate the
    quoted string early, which is header injection.

    Dropping to ASCII and stripping quotes/control characters handles both. The
    name here is cosmetic — it is only what the browser suggests when the user
    saves from the viewer — so degrading it is the right trade against failing
    the request. A name that reduces to nothing falls back to "document.pdf".
    """
    cleaned = (filename or "").encode("ascii", "ignore").decode("ascii")
    cleaned = "".join(c for c in cleaned if c.isprintable() and c not in '"\\')
    return cleaned.strip() or "document.pdf"


def _validate_metadata(file: UploadFile) -> None:
    """
    Reject on name and declared type alone, before any of the body is read.

    Separated from the size check (Day 2) so that the cheap rejections stay
    cheap: a 500 MB .txt is refused on its extension without the server ever
    holding 500 MB.
    """
    # `or ""` because Starlette types UploadFile.filename as `str | None`.
    # A None filename is not reachable through FastAPI today — a multipart part
    # with no filename parameter is parsed as a plain form field, so validation
    # rejects it with 422 before this function runs (verified Day 3). Treating it
    # as the empty string keeps that unreachable case on the same path as the
    # reachable `filename=""` case, which is already refused with 400 below.
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .pdf files are accepted.",
        )
    if file.content_type and file.content_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MIME type must be application/pdf.",
        )


async def _read_within_limit(file: UploadFile) -> bytes:
    """
    Read the body, refusing as soon as it passes MAX_FILE_SIZE_BYTES.

    Day 2 measured the previous shape of this handler — `content = await
    file.read()` followed by a size check on the result — and found memory grew
    linearly with whatever the client sent, *irrespective of the limit*: a 400 MB
    body was correctly answered 400 "File exceeds the 20 MB limit", but only
    after the process had allocated 401.7 MB of private memory for it (1.00x the
    body, measured at 20/60/150/400 MB). The server would allocate twenty times
    its own stated maximum before declining, and on an 8 GB machine a few
    concurrent oversized posts are enough to exhaust it.

    Reading in bounded chunks and stopping at the limit caps the cost at the
    limit plus one chunk however large the request is. Content-Length is
    deliberately NOT trusted as the control here — a client supplies it, and it
    can be absent or wrong; the bound is enforced on bytes actually received.
    """
    chunks: List[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_UPLOAD_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File exceeds the {MAX_FILE_SIZE_BYTES // (1024*1024)} MB limit.",
            )
        chunks.append(chunk)

    if total == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )
    return b"".join(chunks)


@router.post(
    "/documents/upload", response_model=UploadResponse, status_code=202, tags=["documents"]
)
async def upload_document(
    background_tasks: BackgroundTasks, file: UploadFile = File(...)
) -> UploadResponse:
    """Validate and save a PDF, then trigger background ingestion."""
    # Order matters: name and declared type are checked first so an oversized
    # non-PDF costs nothing, then the body is read under a hard size cap.
    _validate_metadata(file)
    content = await _read_within_limit(file)

    # Narrowed to `str` once, here, rather than at each of the three uses below:
    # _validate_metadata() has already refused anything that is not a non-empty
    # name ending in .pdf, so this cannot be empty by the time it is reached.
    filename: str = file.filename or ""

    doc_id = str(uuid.uuid4())
    safe_path = Path(UPLOAD_DIR) / f"{doc_id}.pdf"
    safe_path.write_bytes(content)

    db.insert_document({
        "document_id": doc_id,
        "filename": filename,
        "original_path": str(safe_path),
        "upload_timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "processing",
    })

    background_tasks.add_task(process_document, doc_id, safe_path)
    logger.info("Uploaded %s → %s", filename, doc_id)

    return UploadResponse(
        document_id=doc_id,
        filename=filename,
        status="processing",
        message="File accepted. Processing will begin shortly.",
    )


@router.get("/documents", response_model=List[DocumentInfo], tags=["documents"])
async def list_documents() -> List[DocumentInfo]:
    """Return all documents with their current processing status."""
    rows = db.list_documents()
    return [
        DocumentInfo(
            document_id=r["document_id"],
            filename=r["filename"],
            upload_date=r["upload_timestamp"],
            status=r["status"],
            total_pages=r.get("total_pages", 0),
            total_chunks=r.get("total_chunks", 0),
            ocr_pages_count=r.get("ocr_pages_count", 0),
            error_message=r.get("error_message"),
        )
        for r in rows
    ]


@router.get("/documents/{document_id}", response_model=DocumentInfo, tags=["documents"])
async def get_document(document_id: str) -> DocumentInfo:
    """Return details for a single document."""
    row = db.get_document(document_id)
    if not row:
        raise HTTPException(status_code=404, detail="Document not found.")
    return DocumentInfo(
        document_id=row["document_id"],
        filename=row["filename"],
        upload_date=row["upload_timestamp"],
        status=row["status"],
        total_pages=row.get("total_pages", 0),
        total_chunks=row.get("total_chunks", 0),
        ocr_pages_count=row.get("ocr_pages_count", 0),
        error_message=row.get("error_message"),
    )


# Two paths, one handler. The `/{filename}` variant exists purely so the URL
# *ends* with the document's name — see the docstring's "Why the filename is in
# the path". The bare form stays because it is the honest API shape: the id is
# what identifies the document, and a caller that just wants the bytes should
# not have to know the name.
@router.get("/documents/{document_id}/file", tags=["documents"])
@router.get("/documents/{document_id}/file/{filename}", tags=["documents"])
async def get_document_file(document_id: str, filename: str | None = None) -> FileResponse:
    """
    Serve the stored PDF so the browser can display it (Day 12).

    Added because the Documents page could list a PDF but never show it — the
    only way to read an uploaded file was to find it on disk under its UUID
    filename and match that back to a name by hand.

    `Content-Disposition: inline` (not `attachment`) is the point of the
    endpoint: it asks the browser to render the PDF in its built-in viewer
    rather than download it, which is what lets the front end put it in an
    iframe. The original filename is sent back in that header so a "save" from
    the viewer writes `report.pdf`, not the UUID the file is stored under.

    ── Why the filename is in the path (Day 12, second pass) ──────────────────
    `filename` is decorative and is deliberately IGNORED: the document is
    located by `document_id` alone, and the bytes come from the database row's
    `original_path`. Nothing in the URL ever reaches the filesystem, so the
    segment cannot be used to reach another file.

    It is there because Chrome's built-in PDF viewer titles its toolbar from the
    PDF's own `/Title` metadata and, when that is empty, falls back to the last
    segment of the URL. With the bare route that segment is the literal word
    "file", so a PDF with no embedded title displayed as "file" in the viewer
    and in the print dialog — observed on scanned_image_only.pdf, whose /Title
    is "". Ending the URL with the real name makes that fallback land on
    something true.

    Status codes:
      200 — the PDF.
      404 — no such document, or the record exists but its file is gone (a
            delete that lost the race with ingestion, see delete_document).
    """
    row = db.get_document(document_id)
    if not row:
        raise HTTPException(status_code=404, detail="Document not found.")

    # `original_path` is written by this module's own upload handler, so it is
    # already trusted — but it is still a value read back out of the database,
    # and this is the one place it becomes a filesystem read driven by a URL.
    # Confining it to UPLOAD_DIR means a bad row can never turn into "serve me
    # any file on the box", and costs one resolve() per request.
    pdf_path = Path(row["original_path"]).resolve()
    uploads_root = Path(UPLOAD_DIR).resolve()
    if not pdf_path.is_relative_to(uploads_root):
        logger.error("Refusing to serve %s for %s: outside %s",
                     pdf_path, document_id, uploads_root)
        raise HTTPException(status_code=404, detail="Document not found.")

    if not pdf_path.is_file():
        logger.warning("Document %s has no file at %s", document_id, pdf_path)
        raise HTTPException(
            status_code=404,
            detail="The file for this document is no longer on disk.",
        )

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        # filename= would send `attachment`, which downloads instead of
        # displaying; the header is set directly to keep it inline.
        headers={
            "Content-Disposition": f'inline; filename="{_ascii_filename(row["filename"])}"'
        },
    )


@router.delete("/documents/{document_id}", response_model=DeleteResponse, tags=["documents"])
async def delete_document(document_id: str) -> DeleteResponse:
    """Delete PDF file, ChromaDB vectors, and SQLite record."""
    row = db.get_document(document_id)
    if not row:
        raise HTTPException(status_code=404, detail="Document not found.")

    # Remove PDF file.
    # On Windows the file is locked while PyMuPDF has it open, so deleting a
    # document that is still being ingested raises PermissionError (WinError 32).
    # Letting that escape aborted the whole delete: the caller got a 500 and the
    # record, the file and the vectors all survived (found Day 9). The record and
    # vectors are removed either way so the API stays consistent with what the
    # user sees; the background task cleans up the file it still owns.
    pdf_path = Path(row["original_path"])
    try:
        if pdf_path.exists():
            pdf_path.unlink()
    except OSError as exc:
        logger.warning(
            "Could not remove %s (still in use by ingestion?): %s — the "
            "ingestion task will clean it up when it finishes.", pdf_path, exc
        )

    # Remove vectors from ChromaDB
    try:
        from app.services.vector_store import delete_document_vectors
        delete_document_vectors(document_id)
    except Exception as exc:
        logger.warning("Could not delete vectors for %s: %s", document_id, exc)

    # Remove DB record
    db.delete_document(document_id)
    logger.info("Deleted document %s", document_id)

    return DeleteResponse(message="Document deleted successfully.", document_id=document_id)
