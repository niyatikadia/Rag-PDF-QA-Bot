"""
schemas.py — Pydantic request / response models for all API endpoints.
"""
from typing import List, Optional
from pydantic import BaseModel, Field


# ── Document models ───────────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    document_id: str
    filename: str
    status: str              # "processing" | "ready" | "failed"
    message: str


class DocumentInfo(BaseModel):
    document_id: str
    filename: str
    upload_date: str
    status: str
    total_pages: int = 0
    total_chunks: int = 0
    ocr_pages_count: int = 0   # [v2] pages extracted via OCR
    error_message: Optional[str] = None


class DeleteResponse(BaseModel):
    message: str
    document_id: str


# ── Chat / Q&A models ─────────────────────────────────────────────────────────

class AskRequest(BaseModel):
    question: str = Field(..., max_length=2000)
    document_id: Optional[str] = None   # if None → search all documents


class Citation(BaseModel):
    filename: str
    pages: List[int]
    relevance_score: float
    extraction_method: str = "native"   # [v2] "native" | "ocr"


class AskResponse(BaseModel):
    answer: str
    citations: List[Citation]
    processing_time_ms: int


# ── Health ────────────────────────────────────────────────────────────────────

class HealthStatus(BaseModel):
    status: str                      # "ok" | "degraded"
    ollama_available: bool
    chroma_available: bool
    embedding_model_loaded: bool
    ocr_available: bool              # [v2]
    details: Optional[dict] = None
