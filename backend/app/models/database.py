"""
database.py — SQLite connection and document-metadata CRUD.
Table: documents
"""
import sqlite3
import logging
from typing import Optional, List, Dict, Any
from app.config import DATABASE_PATH

logger = logging.getLogger(__name__)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables on first run."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                document_id     TEXT PRIMARY KEY,
                filename        TEXT NOT NULL,
                original_path   TEXT NOT NULL,
                upload_timestamp TEXT NOT NULL,
                status          TEXT NOT NULL DEFAULT 'processing',
                error_message   TEXT,
                total_pages     INTEGER DEFAULT 0,
                total_chunks    INTEGER DEFAULT 0,
                ocr_pages_count INTEGER DEFAULT 0
            )
        """)
        conn.commit()
    logger.info("Database initialised at %s", DATABASE_PATH)


# ── CRUD ──────────────────────────────────────────────────────────────────────

def insert_document(doc: Dict[str, Any]) -> None:
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO documents
                (document_id, filename, original_path, upload_timestamp, status)
            VALUES (:document_id, :filename, :original_path, :upload_timestamp, :status)
        """, doc)
        conn.commit()


def get_document(document_id: str) -> Optional[Dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM documents WHERE document_id = ?", (document_id,)
        ).fetchone()
    return dict(row) if row else None


def list_documents() -> List[Dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM documents ORDER BY upload_timestamp DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def update_document_status(
    document_id: str,
    status: str,
    total_pages: int = 0,
    total_chunks: int = 0,
    ocr_pages_count: int = 0,
    error_message: Optional[str] = None,
) -> None:
    with get_connection() as conn:
        conn.execute("""
            UPDATE documents
            SET status = ?, total_pages = ?, total_chunks = ?,
                ocr_pages_count = ?, error_message = ?
            WHERE document_id = ?
        """, (status, total_pages, total_chunks, ocr_pages_count,
              error_message, document_id))
        conn.commit()


def delete_document(document_id: str) -> bool:
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM documents WHERE document_id = ?", (document_id,)
        )
        conn.commit()
    return cursor.rowcount > 0
