# SESSION_02_SETUP.md — Day 1: Foundation & Setup

**Date:** 2026-09-07
**Phase:** Phase 2 — Foundation & Setup
**Session Goal:** Create the complete project scaffold so every subsequent session
can code immediately without any environment or structure work.

---

## ✅ What Was Done This Session

### 1. Project Folder Structure Created
Complete directory tree created at `C:\RAGPDFQABOT\pdf-rag-chatbot\` per Section 14:
- `backend/app/` — FastAPI app package
- `backend/app/models/` — Pydantic schemas + SQLite database module
- `backend/app/routers/` — API endpoint routers
- `backend/app/services/` — Business logic services
- `backend/app/utils/` — Shared utilities
- `backend/tests/` — pytest test suite
- `backend/data/uploads/` — PDF upload directory
- `backend/data/chroma_db/` — ChromaDB persistent storage
- `frontend/src/components/` — React components
- `frontend/src/pages/` — Page-level components
- `frontend/src/services/` — API client
- `frontend/src/hooks/` — Custom React hooks
- `docs/` — Session documentation

### 2. Backend Files Created
| File | Status | Notes |
|---|---|---|
| `backend/requirements.txt` | ✅ Created | All deps from Section 16.1 |
| `backend/.env` | ✅ Created | All vars from Section 17 |
| `backend/.env.example` | ✅ Created | Safe to commit |
| `backend/app/main.py` | ✅ Created | FastAPI app, CORS, lifespan events |
| `backend/app/config.py` | ✅ Created | All env vars + data dir creation |
| `backend/app/models/schemas.py` | ✅ Created | All Pydantic models incl. [v2] fields |
| `backend/app/models/database.py` | ✅ Created | SQLite CRUD (incl. ocr_pages_count) |
| `backend/app/routers/health.py` | ✅ Created | **Health check endpoint fully implemented** |
| `backend/app/routers/documents.py` | ✅ Created | Upload/list/delete endpoints (stub processor call) |
| `backend/app/routers/chat.py` | ✅ Created | /api/chat/ask placeholder (Day 5) |
| `backend/app/services/pdf_processor.py` | ✅ Stub | Orchestration outline — implement Day 2-3 |
| `backend/app/services/text_cleaner.py` | ✅ Stub | Core function outlined — implement Day 2 |
| `backend/app/services/chunker.py` | ✅ Stub | LangChain splitter outlined — implement Day 3 |
| `backend/app/services/embedder.py` | ✅ Skeleton | Model loading pattern ready — implement Day 3 |
| `backend/app/services/vector_store.py` | ✅ Stub | ChromaDB client pattern — implement Day 3 |
| `backend/app/services/retriever.py` | ✅ Stub | Query pipeline — implement Day 4 |
| `backend/app/services/llm_service.py` | ✅ Stub | Prompt + Ollama call — implement Day 5 |
| `backend/app/services/ocr_processor.py` | ✅ **Scaffold** | [v2] Fully scaffolded — wire in Day 2-3 |
| `backend/app/utils/helpers.py` | ✅ Created | UUID, file utils |
| `backend/tests/*.py` | ✅ Created | All 6 test files (skips where impl. missing) |

### 3. Frontend Files Created
| File | Status | Notes |
|---|---|---|
| `frontend/package.json` | ✅ Created | React 18, Vite, Tailwind, Axios, Lucide |
| `frontend/vite.config.js` | ✅ Created | Dev server + /api proxy to :8000 |
| `frontend/tailwind.config.js` | ✅ Created | |
| `frontend/postcss.config.js` | ✅ Created | |
| `frontend/index.html` | ✅ Created | |
| `frontend/src/main.jsx` | ✅ Created | |
| `frontend/src/App.jsx` | ✅ Created | React Router: /chat + /documents |
| `frontend/src/index.css` | ✅ Created | Tailwind directives |
| `frontend/src/components/Header.jsx` | ✅ Created | Nav with Chat / Documents tabs |
| `frontend/src/components/ChatInterface.jsx` | ✅ Created | Message list + input bar (mock data) |
| `frontend/src/components/MessageBubble.jsx` | ✅ Created | User + assistant bubbles |
| `frontend/src/components/CitationCard.jsx` | ✅ Created | [v2] Includes OCR badge |
| `frontend/src/components/FileUpload.jsx` | ✅ Created | Drag-and-drop PDF upload UI |
| `frontend/src/components/DocumentList.jsx` | ✅ Created | |
| `frontend/src/components/DocumentCard.jsx` | ✅ Created | [v2] Includes OCR page count |
| `frontend/src/components/LoadingIndicator.jsx` | ✅ Created | Animated spinner |
| `frontend/src/components/ErrorToast.jsx` | ✅ Created | Dismissible error banner |
| `frontend/src/pages/ChatPage.jsx` | ✅ Created | |
| `frontend/src/pages/DocumentsPage.jsx` | ✅ Created | Upload + document list |
| `frontend/src/services/api.js` | ✅ Created | Axios client for all endpoints |
| `frontend/src/hooks/useChat.js` | ✅ Created | Chat state hook |

### 4. Root Files
| File | Status |
|---|---|
| `.gitignore` | ✅ Created |
| `README.md` | ✅ Created |
| `docs/SESSION_02_SETUP.md` | ✅ This file |

---

## ⚠️ Manual Steps YOU Must Complete Before Day 2

These cannot be done remotely — they need to be run in a terminal on your Windows machine:

### Step 1 — Install Ollama (if not already done)
```
Download from: https://ollama.com/download
After install, open PowerShell and run:
  ollama pull llama3.1:8b
  (downloads ~4.7 GB — do this now, it takes time)
```

### Step 2 — Install Tesseract OCR [v2]
```
Download the Windows installer from:
  https://github.com/UB-Mannheim/tesseract/wiki
Install it. Default path: C:\Program Files\Tesseract-OCR\
After install, open PowerShell and test: tesseract --version
If that fails, edit backend\.env and set:
  TESSERACT_CMD_PATH=C:\Program Files\Tesseract-OCR\tesseract.exe
```

### Step 3 — Set up Python virtual environment
```powershell
cd C:\RAGPDFQABOT\pdf-rag-chatbot\backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```
⏱ This takes 5-10 minutes (sentence-transformers downloads the model on first use).

### Step 4 — Install frontend dependencies
```powershell
cd C:\RAGPDFQABOT\pdf-rag-chatbot\frontend
npm install
```

### Step 5 — Start all three servers and verify
Open three separate PowerShell windows:

**Window 1 — Ollama:**
```
ollama serve
```

**Window 2 — Backend:**
```powershell
cd C:\RAGPDFQABOT\pdf-rag-chatbot\backend
.venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
```
→ Visit http://localhost:8000 — should see `{"message": "PDF RAG Chatbot API is running..."}`
→ Visit http://localhost:8000/api/health — check all services
→ Visit http://localhost:8000/docs — Swagger UI

**Window 3 — Frontend:**
```powershell
cd C:\RAGPDFQABOT\pdf-rag-chatbot\frontend
npm run dev
```
→ Visit http://localhost:5173 — should see the Chat UI with Header and nav

---

## 🧪 Verification Checklist for Day 1 Complete

- [ ] Backend starts without errors (`uvicorn app.main:app --reload`)
- [ ] `GET http://localhost:8000/` returns 200
- [ ] `GET http://localhost:8000/api/health` returns JSON with all keys
- [ ] `GET http://localhost:8000/docs` shows Swagger UI
- [ ] `GET http://localhost:8000/api/documents` returns `[]`
- [ ] Frontend starts (`npm run dev`)
- [ ] `http://localhost:5173` shows the chat page
- [ ] Navigating to `/documents` shows the upload page
- [ ] Ollama is running (`ollama serve`)
- [ ] `ollama list` shows `llama3.1:8b`
- [ ] `tesseract --version` works in PowerShell (or TESSERACT_CMD_PATH is set in .env)

---

## 🗂 Files NOT Yet Implemented (Stubs Only — Implement per Schedule)

| File | Implement on Day |
|---|---|
| `pdf_processor.py` | Day 2-3 |
| `text_cleaner.py` (full logic) | Day 2 |
| `ocr_processor.py` (wired in) | Day 2-3 |
| `chunker.py` | Day 3 |
| `embedder.py` (wired) | Day 3 |
| `vector_store.py` (wired) | Day 3 |
| `retriever.py` | Day 4 |
| `llm_service.py` | Day 5 |
| Frontend real API connections | Day 7 |

---

## 📋 Decisions Made This Session

- **Vite proxy** configured to forward `/api` → `http://localhost:8000` — no CORS issues during dev.
- **Lifespan events** used (FastAPI's modern approach) instead of deprecated `@app.on_event`.
- **Stub pattern**: every service file has the real function signature + commented-out implementation + a `logger.warning` stub call, so the pipeline orchestration in `main.py` and `pdf_processor.py` can be wired incrementally without import errors.
- **Test skips**: Day-3+ tests use `pytest.skip()` so `pytest` runs cleanly from Day 1 onward; tests are filled in alongside implementation.
- **OCR scaffold complete**: `ocr_processor.py` is fully implemented (not just a stub) — it checks Tesseract availability, renders PDF pages via PyMuPDF, and calls pytesseract. It just needs to be called from `pdf_processor.py` in Day 3.

---

## 🚀 What Day 2 Starts With

Day 2 picks up from **Section 27 — Day 2** of the spec:
1. Implement `text_cleaner.py` (full cleaning logic)
2. Implement PDF text extraction in `pdf_processor.py` (PyMuPDF page-by-page)
3. Implement document upload endpoint to actually trigger `process_document()`
4. Implement GET/DELETE document endpoints (verify they work end-to-end)
5. Write unit tests for `text_cleaner.py`
6. Test `ocr_processor.py` standalone against a scanned image

**Prerequisite for Day 2:** All 5 manual steps above must be complete and verified. If any server doesn't start, fix that before Day 2 begins.

---

*End of SESSION_02_SETUP.md*
