"""
main.py — FastAPI application factory.
Startup: init DB, load embedding model, configure CORS.
"""
import json
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app import __version__
from app.config import (
    APP_ENV,
    FRONTEND_DIST_DIR,
    FRONTEND_ORIGIN,
    IS_PRODUCTION,
    LOG_LEVEL,
)
from app.models.database import init_db
from app.routers import documents, chat, health

_STARTUP_TIME: float = time.monotonic()


class _JSONFormatter(logging.Formatter):
    """Single-line JSON log records for production log aggregation."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0] is not None:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def _configure_logging() -> None:
    root = logging.getLogger()
    root.setLevel(getattr(logging, LOG_LEVEL))
    handler = logging.StreamHandler()
    if IS_PRODUCTION:
        handler.setFormatter(_JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
    root.handlers = [handler]


_configure_logging()
logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log method, path, status and duration for every request."""

    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/api/health":
            return await call_next(request)
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = (time.monotonic() - start) * 1000
        logging.getLogger("app.access").info(
            "%s %s %d %.0fms",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("=== PDF RAG Chatbot — Starting up ===")
    frontend_state = (
        f"served from {FRONTEND_DIST_DIR}" if SERVING_FRONTEND
        else "not served (dev server expected)"
    )
    logger.info(
        "Environment: %s | API docs: %s | Frontend: %s",
        APP_ENV,
        "disabled" if IS_PRODUCTION else "/docs",
        frontend_state,
    )

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


# In production the interactive docs are not mounted at all. Passing None to
# these three arguments is what removes the routes; leaving them at their
# defaults and merely "not linking to them" would leave them reachable.
app = FastAPI(
    title="PDF RAG Chatbot API",
    description="GenAI Q&A over uploaded PDFs using Ollama + ChromaDB.",
    version=__version__,
    lifespan=lifespan,
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
    openapi_url=None if IS_PRODUCTION else "/openapi.json",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request logging ──────────────────────────────────────────────────────────
app.add_middleware(RequestLoggingMiddleware)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(documents.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(health.router, prefix="/api")


# ── Frontend ──────────────────────────────────────────────────────────────────
# Registered last, so every /api route above is matched first and the catch-all
# below can never shadow one.
_dist = Path(FRONTEND_DIST_DIR)
_dist_resolved = _dist.resolve()
_index = _dist / "index.html"
SERVING_FRONTEND = _index.is_file()

if SERVING_FRONTEND:
    # Hashed, immutable build output.
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str):
        """
        Serve the built single-page app, falling back to index.html so that a
        client-side route (/documents) survives a page refresh.

        An unmatched /api path must not fall through to here: returning the HTML
        shell with a 200 for a mistyped endpoint would turn a clear 404 into a
        JSON parse error in the client. It is re-raised as a real 404 instead.
        """
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")

        # full_path is user-controlled, so it is resolved and confirmed to be
        # inside the build directory before anything is read. Without this,
        # "../../.." escapes the bundle and turns a static handler into an
        # arbitrary-file-read primitive.
        if full_path:
            candidate = (_dist / full_path).resolve()
            if candidate.is_file() and candidate.is_relative_to(_dist_resolved):
                return FileResponse(candidate)
        return FileResponse(_index)

else:

    @app.get("/", tags=["root"])
    async def root():
        return {
            "message": "PDF RAG Chatbot API is running. Visit /docs for the API reference."
        }
