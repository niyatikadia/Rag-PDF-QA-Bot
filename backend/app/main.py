"""
main.py — FastAPI application factory.
Startup: init DB, load embedding model, configure CORS.
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import FRONTEND_ORIGIN
from app.models.database import init_db
from app.routers import documents, chat, health

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("=== PDF RAG Chatbot — Starting up ===")

    # Initialise SQLite schema
    init_db()

    # Pre-load embedding model so first request isn't slow
    try:
        from app.services.embedder import get_embedder
        get_embedder()
    except Exception as exc:
        logger.warning("Could not pre-load embedding model: %s", exc)

    # Check Tesseract availability at startup
    try:
        from app.services.ocr_processor import is_ocr_available
        ocr_ok = is_ocr_available()
        logger.info("Tesseract OCR available: %s", ocr_ok)
    except Exception:
        logger.warning("OCR availability check failed.")

    yield  # app is running

    logger.info("=== PDF RAG Chatbot — Shutting down ===")


app = FastAPI(
    title="PDF RAG Chatbot API",
    description="GenAI Q&A over uploaded PDFs using Ollama + ChromaDB.",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(documents.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(health.router, prefix="/api")


@app.get("/", tags=["root"])
async def root():
    return {"message": "PDF RAG Chatbot API is running. Visit /docs for the API reference."}
