"""
health.py — GET /api/health
Reports availability of all services: Ollama, ChromaDB, embedding model, OCR.
"""
import logging
import requests
from fastapi import APIRouter
from app.models.schemas import HealthStatus
from app.config import OLLAMA_BASE_URL

logger = logging.getLogger(__name__)
router = APIRouter()


def _check_ollama() -> bool:
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


def _check_chroma() -> bool:
    try:
        from app.services.vector_store import get_client
        client = get_client()
        client.heartbeat()
        return True
    except Exception:
        return False


def _check_embedding_model() -> bool:
    try:
        from app.services.embedder import get_embedder
        emb = get_embedder()
        return emb is not None
    except Exception:
        return False


def _check_ocr() -> bool:
    try:
        import pytesseract
        from app.config import TESSERACT_CMD_PATH
        if TESSERACT_CMD_PATH:
            pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD_PATH
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


@router.get("/health", response_model=HealthStatus, tags=["health"])
def health_check() -> HealthStatus:
    """
    Check that all services are available and responding.

    Deliberately `def`, not `async def` (changed Day 2 — performance). All four
    checks block: an HTTP call to Ollama, a ChromaDB heartbeat, and a Tesseract
    subprocess spawn (~47 ms on its own). On the event loop those stalled every
    other request for the duration; in the threadpool they do not.
    """
    ollama_ok = _check_ollama()
    chroma_ok = _check_chroma()
    embedding_ok = _check_embedding_model()
    ocr_ok = _check_ocr()

    all_ok = ollama_ok and chroma_ok and embedding_ok
    status = "ok" if all_ok else "degraded"

    return HealthStatus(
        status=status,
        ollama_available=ollama_ok,
        chroma_available=chroma_ok,
        embedding_model_loaded=embedding_ok,
        ocr_available=ocr_ok,
        details={
            "note": "ocr_available=false means Tesseract is not installed — "
                    "scanned PDFs will skip OCR fallback but the app still works."
        }
    )
