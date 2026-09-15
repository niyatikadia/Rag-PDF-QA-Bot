"""
chat.py — POST /api/chat/ask

The RAG query path end to end: retrieve the relevant chunks, hand them to the
LLM with a grounded prompt, and return the answer with structured citations.

Implemented: Day 5 (Phase 4 part 2).
"""
import logging
import time

from fastapi import APIRouter, HTTPException

from app.config import TOP_K_RESULTS
from app.models.schemas import AskRequest, AskResponse, Citation
from app.services import llm_service, retriever
from app.services.llm_service import LLMUnavailableError

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/chat/ask", response_model=AskResponse, tags=["chat"])
def ask_question(request: AskRequest) -> AskResponse:
    """
    Answer a question from the uploaded documents.

    Deliberately `def`, not `async def` (changed Day 2 — performance).

    Everything this handler does is blocking and slow: `retrieve()` runs the
    embedding model and a ChromaDB query, and `generate_answer()` makes a
    synchronous HTTP call to Ollama that can legitimately run for minutes. A
    coroutine runs ON the event loop, so as an `async def` this handler stalled
    the whole server for the entire generation: with one question in flight for
    92 s, a `GET /api/documents` issued during it waited the full 92 s before
    being served — past the frontend's own 30 s timeout for that call, so a
    second user simply saw the document list fail.

    Declared `def`, FastAPI runs it in its threadpool instead, so one person
    waiting for an answer no longer freezes the application for everyone else.
    Nothing inside the body is awaited, so this is a declaration change only.

    `document_id` is optional; when present it is passed straight through to
    retrieval so the answer is grounded in that one document only.

    Status codes:
      200 — an answer (including the "not found" answer, which is a valid
            result, not an error: the pipeline worked, the documents simply
            did not contain the answer).
      400 — empty question.
      503 — Ollama is unreachable or timed out.
    """
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    start = time.time()

    # retrieve() never raises — an empty store, an embedding failure and a
    # ChromaDB error all arrive here as [], which generate_answer() turns into
    # the "not found" answer without calling the LLM.
    chunks = retriever.retrieve(
        question,
        top_k=TOP_K_RESULTS,
        document_id=request.document_id,
    )

    try:
        answer, citations = llm_service.generate_answer(question, chunks)
    except LLMUnavailableError as exc:
        # A stopped Ollama is an unavailable dependency, not a bug in this
        # service — 503 tells the user to start it, 500 would not.
        logger.error("LLM unavailable while answering %r: %s", question[:60], exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected failure answering %r", question[:60])
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while generating the answer.",
        ) from exc

    elapsed_ms = int((time.time() - start) * 1000)
    logger.info("Answered %r in %d ms with %d citation(s).",
                question[:60], elapsed_ms, len(citations))

    return AskResponse(
        answer=answer,
        citations=[Citation(**c) for c in citations],
        processing_time_ms=elapsed_ms,
    )
