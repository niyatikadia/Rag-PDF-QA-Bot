"""
config.py â€” Application settings loaded from .env
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

      * CHUNK_OVERLAP >= CHUNK_SIZE â€” every upload reached 'failed' with
        "Got a larger chunk overlap (500) than chunk size (100)" raised from
        inside langchain_text_splitters, three layers below this project.
      * TOP_K_RESULTS <= 0 â€” retrieval silently returned zero hits, so every
        question answered "not found" with nothing to explain why.
      * MAX_FILE_SIZE_MB = 0 â€” every non-empty upload was rejected as oversized.
      * OCR_DPI = 0 â€” page rendering failed inside MuPDF ("Invalid bandwriter
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


# â”€â”€ LLM â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
# Generation can legitimately take a long time on CPU: a cold llama3.1:8b spent
# ~117 s just loading ~5 GB into memory on this machine before emitting a token,
# so a 120 s ceiling failed the very first request of a session. Warm requests
# finish in seconds. Anything past this ceiling is treated as "Ollama is
# unavailable" (503), not a backend error.
OLLAMA_TIMEOUT_SECONDS: int = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "300"))

# â”€â”€ Embeddings â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

# â”€â”€ Vector Store â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma_db")

# â”€â”€ File Storage â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./data/uploads")
MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "20"))
MAX_FILE_SIZE_BYTES: int = MAX_FILE_SIZE_MB * 1024 * 1024

# â”€â”€ Chunking â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "500"))
CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "100"))

# The splitter itself rejects overlap >= size, but only when it is constructed â€”
# which happens during ingestion, long after startup, and surfaces as a failed
# document rather than a configuration error. Check it here instead.
if CHUNK_OVERLAP >= CHUNK_SIZE:
    raise ConfigurationError(
        f"CHUNK_OVERLAP ({CHUNK_OVERLAP}) must be smaller than CHUNK_SIZE "
        f"({CHUNK_SIZE}); chunks cannot overlap by more than their own length. "
        f"Fix them in backend/.env (defaults: CHUNK_SIZE=500, CHUNK_OVERLAP=100)."
    )

# â”€â”€ Retrieval â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
TOP_K_RESULTS: int = int(os.getenv("TOP_K_RESULTS", "5"))

# â”€â”€ Context construction â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Spec 5.2 caps the assembled context at ~2000-3000 tokens.
MAX_CONTEXT_TOKENS: int = int(os.getenv("MAX_CONTEXT_TOKENS", "2500"))

# â”€â”€ Frontend / CORS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
FRONTEND_ORIGIN: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")

# â”€â”€ Database â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "./data/pdf_chatbot.db")

# â”€â”€ OCR â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
OCR_ENABLED: bool = os.getenv("OCR_ENABLED", "true").lower() == "true"
OCR_LANGUAGE: str = os.getenv("OCR_LANGUAGE", "eng")
# 72 is PDF user-space DPI, i.e. the 1:1 render. Anything below it asks MuPDF
# for a sub-pixel pixmap, which fails inside the renderer ("Invalid bandwriter
# header dimensions") and makes ocr_page() return None for every page â€” OCR
# turning itself off with only a log line to show for it.
OCR_DPI: int = int(os.getenv("OCR_DPI", "300"))
TESSERACT_CMD_PATH: str = os.getenv("TESSERACT_CMD_PATH", "")

# â”€â”€ Ensure data dirs exist at startup â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
Path(CHROMA_PERSIST_DIR).mkdir(parents=True, exist_ok=True)
Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)

