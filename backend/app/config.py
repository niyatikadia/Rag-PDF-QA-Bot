"""
config.py — Application settings loaded from .env
All constants and path references go through this module.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class ConfigurationError(RuntimeError):
    """
    Raised at import time when a configuration value cannot be used.

    Import time is deliberate: config.py is imported by everything, so raising
    here stops the process during startup, with the variable named, instead of
    letting a bad value reach the code that finally trips over it.

    Day 2 found the version of this file without these checks (the module only
    coerced types) allowed a typo to produce a backend that started cleanly and
    reported `/api/health: ok`, and then failed at *use* time:

      * CHUNK_OVERLAP >= CHUNK_SIZE — every upload reached 'failed' with
        "Got a larger chunk overlap (500) than chunk size (100)" raised from
        inside langchain_text_splitters, three layers below this project.
      * TOP_K_RESULTS <= 0 — retrieval silently returned zero hits, so every
        question answered "not found" with nothing to explain why.
      * MAX_FILE_SIZE_MB = 0 — every non-empty upload was rejected as oversized.
      * OCR_DPI = 0 — page rendering failed inside MuPDF ("Invalid bandwriter
        header dimensions") and OCR silently turned itself off.

    None of those told the operator which variable was wrong. That is the
    "works on my machine until it doesn't" failure the configuration stage
    exists to catch, so the values are checked once, here, up front.
    """


def _int_env(name: str, default: str, minimum: int) -> int:
    """
    Read an integer setting, failing at startup with an actionable message.

    `int(os.getenv(...))` alone raises `ValueError: invalid literal for int()
    with base 10: 'five-hundred'`, which names the value but not the file to
    edit; and it enforces no lower bound at all.
    """
    raw = os.getenv(name, default)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ConfigurationError(
            f"{name} must be a whole number, but is {raw!r}. "
            f"Fix it in backend/.env (or unset it to use the default {default})."
        ) from None
    if value < minimum:
        raise ConfigurationError(
            f"{name} must be at least {minimum}, but is {value}. "
            f"Fix it in backend/.env (or unset it to use the default {default})."
        )
    return value


# ── Runtime environment ──────────────────────────────────────────────────────
# Development and production are different programs, and the difference is
# declared here rather than inferred. In production the interactive API docs are
# not mounted: /docs, /redoc and /openapi.json describe every endpoint and its
# schema, which is useful on a developer's machine and is attack surface
# anywhere else. This was carried as a known open item out of Day 2 ("must be
# disabled if the service is ever exposed"); declaring the environment is what
# makes that switch exist.
APP_ENV: str = os.getenv("APP_ENV", "development").strip().lower()
if APP_ENV not in ("development", "production"):
    raise ConfigurationError(
        f"APP_ENV must be 'development' or 'production', but is {APP_ENV!r}. "
        f"Fix it in backend/.env (or unset it to use the default 'development')."
    )

IS_PRODUCTION: bool = APP_ENV == "production"

_VALID_LOG_LEVELS = ("CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG")
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").strip().upper()
if LOG_LEVEL not in _VALID_LOG_LEVELS:
    raise ConfigurationError(
        f"LOG_LEVEL must be one of {', '.join(_VALID_LOG_LEVELS)}, but is "
        f"{LOG_LEVEL!r}. Fix it in backend/.env (or unset it for the default INFO)."
    )

# Where `vite build` writes the production bundle. When this directory contains
# an index.html, the API also serves the frontend from it, so a deployment is
# one process on one origin with no Node runtime and no CORS. When it does not,
# the Vite dev server serves the frontend and proxies /api here, and nothing
# below changes.
#
# Unlike the three data paths, a relative value here is resolved against the
# backend package rather than the working directory. Those three are created at
# import time and are expected to sit under whatever directory you run from;
# this one points at a sibling of `backend/` whose location does not depend on
# where uvicorn was started, so `../frontend/dist` means the same thing from
# `backend/`, from the repository root, or from a service manager with no
# meaningful working directory at all.
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIST_DIR: str = str(
    (_BACKEND_ROOT / os.getenv("FRONTEND_DIST_DIR", "../frontend/dist")).resolve()
)

# ── LLM ─────────────────────────────────────────────────────────────────────
# 127.0.0.1, deliberately, not "localhost" (measured Day 2).
#
# On Windows "localhost" resolves to ::1 before 127.0.0.1, and Ollama binds IPv4
# only. Every NEW connection therefore tried ::1 first and sat waiting for that
# refusal, which this machine delivers after ~2047 ms, before falling back. The
# same request measured 2065 ms via "localhost" and 8.3 ms via 127.0.0.1 — a
# 248x difference paid on every health check and, more importantly, on every
# single question, on top of generation time.
#
# Set this back to a hostname if Ollama runs somewhere else; the literal address
# is only the default, and the cost only applies to a dual-stack name whose IPv6
# address nothing is listening on.
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
# Generation can legitimately take a long time on CPU: a cold llama3.1:8b spent
# ~117 s just loading ~5 GB into memory on this machine before emitting a token,
# so a 120 s ceiling failed the very first request of a session. Warm requests
# finish in seconds. Anything past this ceiling is treated as "Ollama is
# unavailable" (503), not a backend error.
OLLAMA_TIMEOUT_SECONDS: int = _int_env("OLLAMA_TIMEOUT_SECONDS", "300", minimum=1)

# ── Embeddings ───────────────────────────────────────────────────────────────
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

# ── Vector Store ─────────────────────────────────────────────────────────────
CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma_db")

# ── File Storage ─────────────────────────────────────────────────────────────
UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./data/uploads")
MAX_FILE_SIZE_MB: int = _int_env("MAX_FILE_SIZE_MB", "20", minimum=1)
MAX_FILE_SIZE_BYTES: int = MAX_FILE_SIZE_MB * 1024 * 1024

# ── Chunking ─────────────────────────────────────────────────────────────────
CHUNK_SIZE: int = _int_env("CHUNK_SIZE", "500", minimum=1)
CHUNK_OVERLAP: int = _int_env("CHUNK_OVERLAP", "100", minimum=0)

# The splitter itself rejects overlap >= size, but only when it is constructed —
# which happens during ingestion, long after startup, and surfaces as a failed
# document rather than a configuration error. Check it here instead.
if CHUNK_OVERLAP >= CHUNK_SIZE:
    raise ConfigurationError(
        f"CHUNK_OVERLAP ({CHUNK_OVERLAP}) must be smaller than CHUNK_SIZE "
        f"({CHUNK_SIZE}); chunks cannot overlap by more than their own length. "
        f"Fix them in backend/.env (defaults: CHUNK_SIZE=500, CHUNK_OVERLAP=100)."
    )

# ── Retrieval ─────────────────────────────────────────────────────────────────
TOP_K_RESULTS: int = _int_env("TOP_K_RESULTS", "5", minimum=1)

# ── Context construction ──────────────────────────────────────────────────────
# Spec 5.2 caps the assembled context at ~2000-3000 tokens.
MAX_CONTEXT_TOKENS: int = _int_env("MAX_CONTEXT_TOKENS", "2500", minimum=1)

# ── Frontend / CORS ───────────────────────────────────────────────────────────
FRONTEND_ORIGIN: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")

# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "./data/pdf_chatbot.db")

# ── OCR ───────────────────────────────────────────────────────────────────────
OCR_ENABLED: bool = os.getenv("OCR_ENABLED", "true").lower() == "true"
OCR_LANGUAGE: str = os.getenv("OCR_LANGUAGE", "eng")
# 72 is PDF user-space DPI, i.e. the 1:1 render. Anything below it asks MuPDF
# for a sub-pixel pixmap, which fails inside the renderer ("Invalid bandwriter
# header dimensions") and makes ocr_page() return None for every page — OCR
# turning itself off with only a log line to show for it.
OCR_DPI: int = _int_env("OCR_DPI", "300", minimum=72)
TESSERACT_CMD_PATH: str = os.getenv("TESSERACT_CMD_PATH", "")

# ── Ensure data dirs exist at startup ────────────────────────────────────────
Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
Path(CHROMA_PERSIST_DIR).mkdir(parents=True, exist_ok=True)
Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
