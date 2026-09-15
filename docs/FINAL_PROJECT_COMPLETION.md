# FINAL_PROJECT_COMPLETION.md

| | |
|---|---|
| **Project** | GenAI PDF Q&A RAG Chatbot |
| **Specification** | `PROJECT_SPECIFICATION_v2.md` (supersedes `PROJECT_SPECIFICATION.pdf` v1) |
| **Phase** | Phase 7 — Documentation & Final Completion (spec §23) |
| **Step** | `PROJECT_STEPS.md` step 11 / spec §27, Day 10 |
| **Date** | 2026-09-09 |
| **Mode / Model / Effort** | Cowork · Opus 5 · High |
| **Timeline** | 10 calendar days, as specified. Not extended. |
| **Cost** | ₹0 / $0. Every component is free, open-source and local. |
| **Status** | ✅ **PROJECT COMPLETE** |

---

## 1. Project summary

A standalone GenAI application that answers natural-language questions about PDFs the
user uploads, returning answers **grounded in those documents** and **cited to the file
and page** they came from. When a PDF is a scan with no text layer, it is recovered with
local OCR rather than rejected.

Everything runs on the user's machine: the LLM (Ollama), the embedding model
(sentence-transformers), the vector store (ChromaDB), the metadata database (SQLite) and
the OCR engine (Tesseract). There are no API keys, no external services, and no document
ever leaves the machine — which satisfies the project's two hard constraints
simultaneously: **zero cost** and **complete data privacy**.

**All 21 required features were implemented.** None was reclassified as optional to meet
the deadline, which spec §2.1 explicitly forbids. The v2 addition — F2b, the OCR
fallback — was absorbed into the existing Day 2-3 schedule as planned, without extending
the 10 days.

**Scale of the finished system:** 16 backend modules, 15 frontend modules, 7 test modules,
84 automated tests, 6 REST endpoints, 17 environment variables, 14 pinned Python
dependencies, 9 session records plus this document.

---

## 2. The 18-step completion procedure (spec §30)

Spec §30 is explicit that *"the project is NOT declared complete merely because coding is
finished."* Each step below is recorded with the evidence that closed it.

| # | Step | Status | Evidence |
|---|---|---|---|
| 1 | **Implementation Complete** | ✅ | All 16 backend app modules, 15 frontend modules and 7 test modules exist and are wired. Module counts match spec §15.1/§15.2/§15.3 exactly. |
| 2 | **Integration Check (frontend ↔ backend)** | ✅ | Day 7 replaced every Day 6 mock with real API calls and verified all 9 wiring criteria in the browser against a live backend. Re-confirmed today: `POST /api/chat/ask → 200 OK` observed in the network log during the Day 10 end-to-end question. |
| 3 | **Feature Completeness (all features)** | ✅ | All 21 required features (F1-F20 + F2b) mapped to implementation in §4 below. |
| 4 | **Functional Testing (each feature individually)** | ✅ | Spec §32's 33-item checklist run item by item on Day 9 — 33/33 PASS, 0 BLOCKED, each with recorded evidence (`SESSION_10_TESTING.md`). |
| 5 | **RAG Pipeline Testing (ingestion + query end-to-end)** | ✅ | Day 3 proved ingestion (PDF → vectors); Day 5 proved the query path (question → cited answer) across 9 scenarios; Day 9 re-ran both from a wiped store. Re-confirmed today through the UI. |
| 6 | **PDF Processing Testing (multiple PDF types)** | ✅ | 8 distinct fixture shapes ingested: native 1-page, native 3-page, image-only, 16-page, mixed native+scanned, 5×identical-page, shared header/footer, and 2 blank pages. |
| 7 | **Retrieval Testing (relevance, ranking, filtering)** | ✅ | `test_retriever.py`, 8 tests. Measured separation: on-topic 0.60-0.79, off-topic 0.06-0.08. `document_id` filtering verified, including correctly refusing a question scoped to the wrong document. |
| 8 | **Answer Quality / Grounding Verification** | ✅ | Verified on `llama3.1:8b` (Day 9, request 1 — correct answer, correct citation) *and* on `llama3.2:latest` across Days 7-10. An unrelated question returns the "not found" phrase with no hallucination. |
| 9 | **Source / Citation Verification** | ✅ | Citations extracted only from chunks the model was actually shown; merged one-per-file with sorted page lists; OCR-derived sources badged. Today: `native_multi.pdf, Page 1, MATCH STRENGTH 74%` — the correct page for that question. |
| 10 | **Error Handling Testing (all error paths)** | ✅ | 400 (×4 kinds), 404 (×2), 422, 503 and 500 all exercised against the live API, plus a corrupted PDF and a Tesseract-unavailable configuration. |
| 11 | **Frontend Testing (all UI states and flows)** | ✅ | Days 6-8: every component state driven in a real browser — multi-citation, OCR-badged, not-found, failed-with-retry, all three toast variants, all four document statuses, every empty state, keyboard-only navigation, 375/768/1280 px. |
| 12 | **Backend Testing (all API endpoints)** | ✅ | `test_api.py`, 15 tests covering all 6 endpoints. |
| 13 | **End-to-End Testing (complete user flow)** | ✅ | Day 9 fresh-start test: store and database deleted, backend cold-started, documents uploaded through the real dropzone, question answered with a citation, document deleted through the UI. Repeated today at a smaller scale. |
| 14 | **Bug Fixing (all discovered bugs)** | ✅ | 11 bugs found and fixed across the 10 days — §9 below. Zero known open bugs. |
| 15 | **Regression Testing** | ✅ | Day 9 re-confirmed all 8 Day 6/7/8 behaviours individually. Today: full suite re-run after every change; `npm run build` byte-identical to Day 9, proving no frontend drift. |
| 16 | **Final Verification (complete checklist pass)** | ✅ | 33/33 spec §32 items PASS (Day 9). Today's changes touched item 28 (error messages), which was re-verified live and improved. |
| 17 | **Documentation (README, session MDs, final MD)** | ✅ | `README.md` complete; `SESSION_02` … `SESSION_10` written per spec §29.1; this document. |
| 18 | **PROJECT COMPLETE** | ✅ | Declared here. |

---

## 3. Final verification results — Day 10, real output

Every command below was executed today against the real system.

### 3.1 Dependency install from scratch — the blocker that gated this day

`requirements.txt` had been wrong since Day 3 and was worse than the Day 9 handoff
recorded: **12 of the 14 pins disagreed with what was actually installed and working.**
The blocking one was `Pillow==10.3.0`, which has no wheel for Python 3.13 and fails to
build from source — and because that aborts the entire pip transaction, **nothing** in
the file installed on a fresh Python 3.13 machine. Spec §27 Day 10 requires verifying the
README setup works from scratch, so this could not be deferred again.

Every pin was reconciled to the exact version running in `backend/.venv` — the versions
Day 9's 83/83 suite and 33/33 checklist were actually verified against — and then proven
in a **throwaway** virtualenv. `backend/.venv` was never touched.

```
Python 3.13.3
pip install -r requirements.txt
...
Successfully installed ... Pillow-12.3.0 PyMuPDF-1.28.2 chromadb-1.5.9
  fastapi-0.141.1 httpx-0.28.1 langchain-text-splitters-1.1.2 pydantic-2.13.5
  pytesseract-0.3.13 pytest-9.1.1 python-dotenv-1.2.3 python-multipart-0.0.32
  requests-2.34.2 sentence-transformers-3.0.1 torch-2.14.0 transformers-4.57.6
  uvicorn-0.52.4 ...
=== PIP EXIT CODE: 0 ===

$ pip check
No broken requirements found.

$ python -c "import fastapi, uvicorn, fitz, chromadb, sentence_transformers,
             langchain_text_splitters, pytesseract, PIL, pydantic, httpx,
             requests, dotenv, multipart, pytest"
all 14 direct dependencies import OK
```

The resolver independently chose `torch-2.14.0` and `transformers-4.57.6` — the same
versions as the working environment. The throwaway venv was deleted afterwards.

**One genuine finding, now in the README.** The first attempt failed with
`OSError: [Errno 2] No such file or directory` while unpacking PyTorch, with a hint about
Windows Long Path support. That was **not** a dependency problem: PyTorch ships headers
with ~150-character relative paths, the install directory was ~110 characters deep, and
Windows caps a full path at 260 by default. Re-running from a short path succeeded
unchanged. This is a real setup trap for anyone cloning into a deep directory, so it is
documented in the README rather than quietly worked around.

### 3.2 Test suite — all 7 modules

```
platform win32 -- Python 3.13.3, pytest-9.1.1, pluggy-1.6.0
collected 84 items

tests\test_api.py ...............                                        [ 17%]
tests\test_chunker.py ....                                               [ 22%]
tests\test_embedder.py ....                                              [ 27%]
tests\test_llm_service.py ......................................         [ 72%]
tests\test_ocr_processor.py .....                                        [ 78%]
tests\test_retriever.py ........                                         [ 88%]
tests\test_text_cleaner.py ..........                                    [100%]

======================= 84 passed, 1 warning in 57.21s ========================
```

**84 passed, 0 failed** — Day 9's 83 plus the one regression test added today. The single
warning is a `DeprecationWarning` from Starlette's own `testclient.py`, not project code.

| File | Tests | Covers |
|---|---|---|
| `test_api.py` | 15 | All 6 endpoints, validation, 400/404/503, delete-during-ingestion, error-message sanitisation |
| `test_chunker.py` | 4 | Chunk size, overlap, metadata, empty input |
| `test_embedder.py` | 4 | 384 dimensions, determinism, batching, flat query vector |
| `test_llm_service.py` | 38 | Context construction and budgeting, prompt fencing, all 5 Ollama failure paths, refusal detection, citation merging |
| `test_ocr_processor.py` | 5 | OCR disabled, Tesseract unavailable, success, empty result |
| `test_retriever.py` | 8 | top-k, ranking, low-relevance separation, empty store, empty query, document filtering, OCR chunk metadata, score clamping |
| `test_text_cleaner.py` | 10 | Whitespace, control chars, unicode, empty-page filtering, header/footer stripping, repeated-page guard |

### 3.3 Production build

```
vite v5.4.21 building for production...
✓ 1576 modules transformed.
dist/index.html                   0.40 kB │ gzip:  0.28 kB
dist/assets/index-kY7vCitD.css   17.85 kB │ gzip:  4.12 kB
dist/assets/index-Ct6OnWYv.js   248.43 kB │ gzip: 82.52 kB
✓ built in 1m 21s
```

**Byte-identical to Day 9** (1576 modules, 248.43 kB / 17.85 kB), which independently
confirms no frontend source changed today.

### 3.4 Health check

```json
{"status":"ok","ollama_available":true,"chroma_available":true,
 "embedding_model_loaded":true,"ocr_available":true}
```

### 3.5 End-to-end question through the real UI

Asked at `http://localhost:5173/chat` against the live backend:

> **Q:** When did artificial intelligence research begin?
>
> **A:** *"According to the retrieved context, artificial intelligence research since the
> 1950s is mentioned on Page 1 of the document "native_multi.pdf"."*
>
> **1 SOURCE** — `native_multi.pdf` · **Page 1** · **MATCH STRENGTH 74%** · 133.0 s

Page 1 of `native_multi.pdf` is the AI-history page, so the citation is correct.
Server log for the same request:

```
retriever: Retrieved 5 chunk(s) for query 'When did artificial intelligence research begin?' (top_k=5, document_id=all)
llm_service: Built context from 5/5 chunk(s), 1086 chars (budget 10000).
llm_service: Generated answer (143 chars) with 1 citation(s).
chat: Answered ... in 132975 ms with 1 citation(s).
```

**Console: 0 errors** — only Vite's debug lines and the React DevTools info line.
Network: `POST /api/chat/ask → 200 OK`.

### 3.6 Corpus integrity

Verified after every test upload and delete today:

```
scanned_image_only.pdf     ready     1p 1chunks ocr=1
native_multi.pdf           ready     3p 3chunks ocr=0
native_single.pdf          ready     1p 1chunks ocr=0
documents: 3 · chroma chunks: 5 · PDFs on disk: 3
```

Exactly the 3-document / 5-chunk corpus `test_retriever.py` requires. Nothing in
`backend/data/` was deleted.

---

## 4. Feature completeness — all 21 required features

| Feature | Status | Where it is implemented |
|---|---|---|
| **F1** — PDF upload, single and multiple | ✅ | `routers/documents.py::upload_document` (202 + background task) · `_validate_file` for type/MIME/size/empty · frontend `components/FileUpload.jsx` (drag-drop, multi-file loop, pre-flight validation) |
| **F2** — PDF text extraction | ✅ | `services/pdf_processor.py::extract_text_from_pdf` — PyMuPDF page loop returning `{page_number, text, extraction_method}` |
| **F2b** — **OCR fallback [v2]** | ✅ | `services/ocr_processor.py::ocr_page` — PyMuPDF `get_pixmap(300 DPI)` → PIL → `pytesseract.image_to_string`. Called inline from `extract_text_from_pdf` when a page has fewer than `MIN_CHARS_FOR_NATIVE_TEXT = 10` chars, reusing the already-open page object |
| **F3** — Text cleaning | ✅ | `services/text_cleaner.py::clean_text` (NFKC, control chars, whitespace, consecutive-duplicate lines) and `clean_pages` (+ cross-page header/footer stripping). Applied identically to native and OCR text |
| **F4** — Intelligent chunking | ✅ | `services/chunker.py::chunk_pages` — `RecursiveCharacterTextSplitter`, `CHUNK_SIZE=500` / `CHUNK_OVERLAP=100` |
| **F5** — Embedding generation | ✅ | `services/embedder.py` — lazy `SentenceTransformer('all-MiniLM-L6-v2')` singleton, 384-dim; `embed_texts` / `embed_query` |
| **F6** — Vector storage & indexing | ✅ | `services/vector_store.py::add_chunks` — ChromaDB `pdf_chunks` collection, cosine space, ids `{document_id}_{page}_{chunk_index}`, 5 metadata fields including `extraction_method` |
| **F7** — Semantic retrieval | ✅ | `services/retriever.py::retrieve` — embed → `query_chunks` top-k → `distance_to_score` → explicit sort. Optional `document_id` filter |
| **F8** — Context construction | ✅ | `services/llm_service.py::build_context` + `format_source_label` — `[Source: file.pdf, Page 3]`, ` [OCR]` when applicable, inside a `MAX_CONTEXT_TOKENS`-derived character budget; returns `included_chunks` |
| **F9** — LLM answer generation | ✅ | `services/llm_service.py::call_ollama` — `/api/generate`, `stream:false`, `temperature 0.1`, with `SYSTEM_PROMPT`'s six grounding rules |
| **F10** — Source/citation display | ✅ | `llm_service.py::extract_citations` (merged one-per-file, sorted pages, best score, OCR flag) → `components/CitationCard.jsx` with the **OCR badge** and MATCH STRENGTH bar |
| **F11** — "Not found" handling | ✅ | Two layers: `generate_answer` short-circuits to `NOT_FOUND_PHRASE` without calling the LLM when retrieval is empty; and `is_not_found_answer` detects a refusal and strips citations |
| **F12** — Chat interface | ✅ | `components/ChatInterface.jsx` + `hooks/useChat.js` — all state in the hook, component is presentation only |
| **F13** — Conversation history | ✅ | `useChat.messages`, rendered by `MessageBubble.jsx`; "N questions this session" counter and Clear chat |
| **F14** — Document management | ✅ | `GET`/`DELETE /api/documents` → `pages/DocumentsPage.jsx`, `DocumentList.jsx`, `DocumentCard.jsx`. Delete removes file + vectors + row. Card shows `"12 pages (3 via OCR)"` |
| **F15** — Processing status feedback | ✅ | `components/LoadingIndicator.jsx` — three variants including the amber **"Running OCR on scanned pages…"**, plus time-escalating chat copy (0/4/12/30/75 s). `DocumentsPage` polls only while something is processing |
| **F16** — Error handling | ✅ | Backend: try/except per service, `LLMUnavailableError` → 503, structured `HTTPException`s. Frontend: `ErrorToast.jsx` with distinct 503 / 400 / generic variants, failed turns rendered inline with Retry |
| **F17** — Input validation | ✅ | Backend `_validate_file` + Pydantic `AskRequest(max_length=2000)` + explicit empty-question check. Frontend mirrors extension and 20 MB checks pre-upload |
| **F18** — API design | ✅ | 6 REST endpoints, correct codes: 202 accepted, 200 including the "not found" result, 400, 404, 422, 503, 500 |
| **F19** — Responsive UI | ✅ | Desktop-first as specified; verified no horizontal overflow at 768 px and 375 px on both pages, asserted on the document *and* the scroll container |
| **F20** — Health check | ✅ | `routers/health.py` — independently probes Ollama, ChromaDB, the embedding model and Tesseract; `ocr_available:false` degrades rather than fails |

---

## 5. Architecture

### 5.1 Three tiers

```
React + Vite + Tailwind (:5173)
        │  REST / JSON  (Vite proxies /api → :8000)
        ▼
FastAPI + Uvicorn (:8000)  ── orchestration, validation, status tracking
        │
        ├── Ollama (:11434)          LLM generation
        ├── sentence-transformers    embeddings, in-process
        ├── ChromaDB                 vector store, in-process, on disk
        ├── SQLite                   document metadata
        └── Tesseract                OCR, local binary via pytesseract
```

### 5.2 Ingestion pipeline (spec §5.1)

```
PDF  →  validate (.pdf · application/pdf · ≤20 MB · non-empty)
     →  save data/uploads/<uuid>.pdf · SQLite row status=processing
     →  202 Accepted   ← the user gets a response here
     →  [BackgroundTask]
          PyMuPDF page-by-page extraction
            └─ page < 10 chars native?  →  render 300 DPI → Tesseract
                                          →  extraction_method="ocr", ocr_pages_count++
          →  clean   (NFKC · control chars · whitespace · repeated header/footer)
          →  chunk   (500 chars, 100 overlap, metadata preserved)
          →  embed   (all-MiniLM-L6-v2, 384-dim)
          →  store   (ChromaDB `pdf_chunks`)
          →  SQLite  status=ready, total_pages, total_chunks, ocr_pages_count
```

A document becomes `failed` only when **every** page yields nothing from both methods
(spec §5.4). Partial OCR failure is logged and skipped, not fatal.

### 5.3 Query pipeline (spec §5.2)

```
question  →  embed_query
          →  ChromaDB top-5 cosine  (optionally scoped to one document_id)
          →  score = clamp(1 - distance), sorted best-first
          →  build_context  — labelled excerpts inside a ~10,000-char budget,
                              returning exactly what the model was shown
          →  build_prompt   — context and question each in their own fence
          →  call_ollama
          →  is_not_found_answer? → answer alone, zero citations
             otherwise            → extract_citations from included_chunks
          →  {answer, citations[], processing_time_ms}
```

### 5.4 Module inventory

**Backend app — 16 modules (spec §15.1):** `main.py`, `config.py`, `models/schemas.py`,
`models/database.py`, `routers/documents.py`, `routers/chat.py`, `routers/health.py`,
`services/pdf_processor.py`, `services/text_cleaner.py`, `services/chunker.py`,
`services/embedder.py`, `services/vector_store.py`, `services/retriever.py`,
`services/llm_service.py`, `services/ocr_processor.py`, `utils/helpers.py`

**Frontend — 15 modules (spec §15.2):** `App.jsx`, `main.jsx`, `pages/ChatPage.jsx`,
`pages/DocumentsPage.jsx`, `components/ChatInterface.jsx`, `MessageBubble.jsx`,
`CitationCard.jsx`, `FileUpload.jsx`, `DocumentList.jsx`, `DocumentCard.jsx`,
`LoadingIndicator.jsx`, `ErrorToast.jsx`, `Header.jsx`, `services/api.js`,
`hooks/useChat.js` (+ `index.css`, which is not a module)

**Tests — 7 modules (spec §15.3, as amended on Day 9):** `test_text_cleaner.py`,
`test_chunker.py`, `test_embedder.py`, `test_retriever.py`, `test_api.py`,
`test_ocr_processor.py`, `test_llm_service.py`

All three counts are unchanged from the specification. No module was added or removed on
Day 10.

### 5.5 Folder structure

```
pdf-rag-chatbot/
├── backend/
│   ├── app/  main.py, config.py, models/, routers/, services/, utils/
│   ├── tests/  7 modules + fixtures/ (8 PDFs + make_fixtures.py)
│   ├── data/   uploads/, chroma_db/, pdf_chatbot.db      (git-ignored)
│   ├── requirements.txt, .env.example, .env              (.env git-ignored)
├── frontend/
│   ├── src/    App, main, pages/, components/, services/, hooks/, index.css
│   ├── package.json, vite.config.js, tailwind.config.js, postcss.config.js
├── docs/       SESSION_02 … SESSION_10, FINAL_PROJECT_COMPLETION.md
├── README.md
└── .gitignore
```

---

## 6. Technology stack

| Component | Technology | Free | Local |
|---|---|---|---|
| LLM | Ollama — `llama3.1:8b` / `llama3.2:latest` | ✅ | ✅ |
| Embeddings | sentence-transformers `all-MiniLM-L6-v2` (384-dim) | ✅ | ✅ |
| Vector store | ChromaDB (in-process, persistent) | ✅ | ✅ |
| PDF extraction & rendering | PyMuPDF (fitz) | ✅ | ✅ |
| OCR **[v2]** | Tesseract + pytesseract | ✅ | ✅ |
| Backend | FastAPI + Uvicorn | ✅ | ✅ |
| Frontend | React 18 + Vite 5 + Tailwind 3 | ✅ | ✅ |
| Metadata DB | SQLite (stdlib) | ✅ | ✅ |
| Chunking | langchain-text-splitters | ✅ | ✅ |
| HTTP client | Axios | ✅ | ✅ |
| Icons | lucide-react | ✅ | ✅ |

**Total cost: ₹0 / $0.**

---

## 7. API reference

| Method | Endpoint | Request | Success | Errors |
|---|---|---|---|---|
| `POST` | `/api/documents/upload` | multipart, field `file` | **202** `{document_id, filename, status, message}` | **400** wrong extension / wrong MIME / >20 MB / empty |
| `GET` | `/api/documents` | — | **200** `[DocumentInfo]` | — |
| `GET` | `/api/documents/{id}` | — | **200** `DocumentInfo` | **404** |
| `DELETE` | `/api/documents/{id}` | — | **200** `{message, document_id}` | **404** |
| `POST` | `/api/chat/ask` | `{question, document_id?}` | **200** `{answer, citations[], processing_time_ms}` | **400** empty · **422** >2000 chars · **503** Ollama down/timeout · **500** unexpected |
| `GET` | `/api/health` | — | **200** `{status, ollama_available, chroma_available, embedding_model_loaded, ocr_available, details}` | — |

`DocumentInfo` = `{document_id, filename, upload_date, status, total_pages,
total_chunks, ocr_pages_count, error_message}`, `status ∈ {processing, ready, failed}`.

`Citation` = `{filename, pages: [int], relevance_score: float, extraction_method:
"native"|"ocr"}` — sorted by score descending, one per file, `pages` pre-sorted.

Two design points: upload returns **202** because ingestion is asynchronous, and
"not found" returns **200** because the pipeline succeeded and produced its designed
output — a 404 would describe a different problem with a different fix.

---

## 8. Dependencies and environment

### 8.1 Backend — 14 direct dependencies, reconciled and proven on Day 10

`fastapi==0.141.1` · `uvicorn[standard]==0.52.4` · `python-multipart==0.0.32` ·
`PyMuPDF==1.28.2` · `sentence-transformers==3.0.1` · `chromadb==1.5.9` ·
`langchain-text-splitters==1.1.2` · `requests==2.34.2` · `python-dotenv==1.2.3` ·
`pydantic==2.13.5` · `pytest==9.1.1` · `httpx==0.28.1` · `pytesseract==0.3.13` ·
`Pillow==12.3.0`

Transitive packages are deliberately left unpinned, so this stays a dependency list
rather than a lock file.

**System dependency, not pip-installable:** the Tesseract OCR binary (spec §18.2).

### 8.2 Frontend

`react` · `react-dom` · `react-router-dom` · `axios` · `lucide-react` · `tailwindcss` ·
`postcss` · `autoprefixer` · `vite` · `@vitejs/plugin-react`

**No dependency was added after Day 1** on either side. `package.json` has been
byte-identical since Day 6.

### 8.3 Environment variables — 17, all in `backend/.env`

`OLLAMA_BASE_URL` · `OLLAMA_MODEL` · `OLLAMA_TIMEOUT_SECONDS` · `EMBEDDING_MODEL` ·
`CHROMA_PERSIST_DIR` · `UPLOAD_DIR` · `DATABASE_PATH` · `MAX_FILE_SIZE_MB` ·
`CHUNK_SIZE` · `CHUNK_OVERLAP` · `TOP_K_RESULTS` · `MAX_CONTEXT_TOKENS` ·
`FRONTEND_ORIGIN` · `OCR_ENABLED` · `OCR_LANGUAGE` · `OCR_DPI` · `TESSERACT_CMD_PATH`

Verified on Day 10 by diffing `config.py`'s `os.getenv` names against `.env.example`:
**identical sets, 17 each**. The values in `.env.example` are also byte-identical to the
live `.env`, so `copy .env.example .env` provably produces the configuration this project
was verified on.

Spec §17 listed 14; `OLLAMA_TIMEOUT_SECONDS` and `MAX_CONTEXT_TOKENS` were added on
Day 5 when the cold-load timing and the context budget were measured, and
`.env.example` documents both.

**No secrets, by design** (spec §11) — no API keys, no credentials, everything points at
localhost.

---

## 9. Bugs found and fixed

Eleven, across the ten days. Every one was found by a test or a real run, not by
inspection alone.

| # | Day | Bug | Fix |
|---|---|---|---|
| 1 | 2 | `AskRequest.question` had `min_length=1`, so an empty question returned 422 where the handler's own check (and its test) expected 400 | Removed the Pydantic constraint so the explicit check fires — `schemas.py` |
| 2 | 3 | Chunk metadata stored the **UUID storage name** as `filename`, so every citation would have read `[Source: 8848dcca-….pdf, Page 3]` | Look the original filename up from SQLite before chunking — `pdf_processor.py` |
| 3 | 7 | A 220-char unbreakable token escaped the message bubble and pushed a horizontal scrollbar into the list; `break-words` alone did not fix it | A flex item's `min-width:auto` makes its min-content size the longest token — added `min-w-0 max-w-full` — `MessageBubble.jsx` |
| 4 | 8 | With two toasts on screen, one Escape dismissed only one | The inline `onDismiss` re-subscribed every render, so the first dismissal's flush removed the second listener mid-dispatch. Held `onDismiss` in a ref — `ErrorToast.jsx` |
| 5 | 8 | A 503 turn would have claimed *"No matching passages found in your documents"* — a different and wrong statement | Gated `isNotFound` on `!isFailed` — `MessageBubble.jsx` |
| 6 | 9 | `test_retriever.py` — 6 of 8 tests failing: the sample corpus had been destroyed by a Day 7 delete test | Regenerated `native_single.pdf` as a committed fixture and re-ingested through the real endpoint. **No assertion weakened** |
| 7 | 9 | `text_cleaner` **emptied** any document built from repeated pages — two identical pages were enough — marking it `failed` | Stripping can never empty a page: if removal would leave nothing, the page keeps its original text — `text_cleaner.py`. 5 regression tests |
| 8 | 9 | Deleting a document **during ingestion** returned HTTP 500 and left the record, the PDF *and* the vectors behind | Guarded the Windows-locked `unlink`, and made ingestion re-check the row before storing chunks, cleaning up if it is gone — `documents.py` + `pdf_processor.py`. 2 regression tests |
| 9 | 9 | A correct, fully-cited answer **lost every citation** because a trailing hedge ("…the context does not provide a comprehensive summary") matched a not-found marker | A refusal *leads*: fuzzy markers now count only within the first 200 characters; the verbatim phrase still counts anywhere — `llm_service.py`. 4 regression tests |
| 10 | 9 | *(security)* `llama3.2` **disclosed the system prompt** on a direct "reveal your instructions" request | Added an explicit confidentiality rule (rule 5) to `SYSTEM_PROMPT`; three injection styles re-tested and blocked |
| 11 | **10** | A corrupted PDF's `error_message` **leaked the full server path and the internal document id** into the browser, since `DocumentCard` renders it verbatim | `_safe_error_message()` substitutes every form of the storage path with the user's own filename — `pdf_processor.py`. 1 regression test |

### 9.1 Bug 11 in detail — and the near-miss inside it

This is the Day 9 carry-forward, closed today. Uploading garbage bytes named `.pdf`
correctly produced `failed`, but the stored message was PyMuPDF's raw `str(exc)`:

```
Failed to open file 'C:\RAGPDFQABOT\pdf-rag-chatbot\backend\data\uploads\<uuid>.pdf' as type pdf.
```

Worth recording honestly: **the first version of the fix was incomplete, and its unit
test passed anyway.** A live upload against the running backend produced:

```
"Failed to open file 'data\\uploads\\corrupt_report.pdf' as type pdf."
```

The document id was gone, but the directory survived — because **PyMuPDF escapes the
separators in its message**, so the text carries `data\\uploads\\…` while `str(pdf_path)`
carries `data\uploads\…`. They never matched. The unit test asserted
`str(pdf_path) not in message`, which was *true*, but true for the wrong reason: it
passed vacuously while the path was still visible to the user.

The fix now matches each candidate in its plain, backslash-escaped and posix forms, and
the test asserts all three forms of every candidate. Re-verified live after a backend
restart:

```json
{"status":"failed","error_message":"Failed to open file 'corrupt_report.pdf' as type pdf."}
```

Still specific enough to act on — it names which upload failed — while disclosing
nothing internal.

---

## 10. Key decisions

Every one of these was a real trade-off, taken for a stated reason.

**Architecture and RAG**

1. **Local-only, Ollama over cloud APIs.** Even free tiers risk charges and rate limits,
   which would violate the ₹0 constraint; local also gives complete data privacy for free.
2. **ChromaDB over FAISS.** FAISS needs manual persistence, metadata handling and
   serialization; ChromaDB provides all three, which bought days on a 10-day schedule.
3. **500-char chunks with 100-char overlap.** Balances retrieval precision against
   keeping enough surrounding context for an answer to read coherently.
4. **Scoring lives in `retriever.py`, not `vector_store.py`.** The storage layer returns
   raw distances; the retriever converts them. This keeps the vector store swappable and
   made `distance_to_score` unit-testable without a database.
5. **Low-relevance chunks are returned, not filtered.** No minimum-score cutoff — deciding
   "the answer isn't here" is the LLM's job under the grounded prompt, and a threshold
   would duplicate that decision in two places.
6. **Citations come from `included_chunks`, never the full retrieval list.** A chunk the
   context budget dropped was never shown to the model, so it must never be cited.
7. **Short-circuit before the LLM when retrieval is empty.** Nothing can ground an answer,
   so calling the model would only be slower and less reliable. An unknown `document_id`
   returns in 121 ms.
8. **Both context *and* question are fenced.** Injection can arrive inside an uploaded
   PDF just as easily as in a question; fencing only one would leave the likelier vector
   open.
9. **A refusal must *lead*.** The verbatim phrase counts anywhere, the fuzzy paraphrases
   only in the opening 200 characters — because a hedge appended to a real answer is not
   a refusal (bug 9).
10. **Synchronous ingestion in a background task.** Simple and sufficient for a
    single-user local app; a queue would add real complexity for no benefit at this scale.
11. **OCR runs inline in the existing page loop.** `extract_text_from_pdf` already holds
    the `fitz.Page` when it detects low native text, so it calls `ocr_page(page)`
    directly — no second file open, no separate pass.

**Frontend**

12. **`OLLAMA_TIMEOUT_SECONDS = 300`, client timeout 360 s.** The client is deliberately
    set to *lose* the race so the backend's actionable 503 ("start Ollama") reaches the
    user instead of a bare client-side abort.
13. **"MATCH STRENGTH", never "confidence".** The number is chunk-to-question similarity,
    not answer correctness — Day 5 saw a correct answer score 0.2156. Naming it
    "confidence" would misrepresent a correct answer as a doubtful one.
14. **Polling only while something is `processing`.** Ingestion is the only state that
    changes on its own; polling a settled list would be pure noise. Poll failures are
    swallowed so a dropped request never wipes the list.
15. **The OCR indicator is an inference, and is worded as one.** The backend exposes no
    mid-processing OCR signal, so the UI switches to the OCR message after 4 s of real
    observed processing — replacing Day 6's filename guess, which would have been a lie
    against real data.
16. **No `mockData.js` on Day 6.** Spec §15.2 fixes the frontend at 15 modules, so mocks
    lived inside `useChat.js` and `DocumentsPage.jsx` in fenced blocks. Day 7 deleted
    blocks, not files.
17. **Failed turns render inline with Retry.** A failed question used to sit answerless
    with a floating toast, and retrying duplicated it.

**Process**

18. **Test fixtures are committed, not regenerated.** `test_retriever.py` asserts measured
    similarity scores against these exact bytes; regenerating under a different PyMuPDF
    could shift text, embeddings and therefore scores, turning a green suite red on a
    fresh clone for reasons unrelated to the code. 157 KB is a trivial price for a suite
    that runs immediately after `git clone`.
19. **Requirements pinned to what actually works** (Day 10) rather than to what was
    guessed on Day 1 — and then proven by installing them in a fresh venv, not asserted.

---

## 11. Spec amendments

The specification was amended twice, both on Day 9, both dated and justified in place
rather than silently rewritten.

**§15.3 — test modules: 6 → 7.** `test_llm_service.py` was written on Day 5, after §15.3
was drafted, and the count was never updated. It is 38 pure unit tests covering
`llm_service.py` — a §8.2 service with no other coverage. The list was corrected rather
than the file removed.

**§6.1 — `OLLAMA_MODEL` is a two-tier setting.** See §12 below. The spec model is
*documented*, not retired.

---

## 12. The model decision, with measurements

Spec §6.1 specifies `llama3.1:8b`. The development machine has **7.89 GB** of RAM —
just below spec §18.1's own 8 GB minimum. Rather than quietly change the spec, the model
was measured end to end:

| Request | Result | Time |
|---|---|---|
| 1 (cold) | **HTTP 200** — correct grounded answer, correct citation | 243.5 s |
| 2 (model resident) | **HTTP 503** — exceeded `OLLAMA_TIMEOUT_SECONDS` (300 s) | 324.4 s |
| 3 | **HTTP 503** — exceeded the timeout | 325.7 s |

With the model resident (`ollama ps`: 5.6 GB, 100% CPU), free RAM fell to **0.11 GB** and
the machine thrashed.

Two conclusions. **Answer quality on `llama3.1:8b` is verified** — request 1 was correct
and correctly cited — so the problem is throughput and reliability, not quality. And one
answer in three is not a working configuration on this hardware.

`OLLAMA_MODEL` is therefore treated as a **two-tier setting**:

| RAM | Model | Notes |
|---|---|---|
| ≥16 GB | `llama3.1:8b` | The spec model. Best answer quality. |
| ~8 GB | `llama3.2:latest` | 2.0 GB, answers in 30-75 s. The default, and what the §32 checklist was verified against. |

Nothing else in the architecture changes — the model is one environment variable. The
rationale is recorded in `.env.example`, `README.md` and a dated amendment to spec §6.1.

One caveat that came with the smaller model: `llama3.2` is weaker at resisting prompt
injection and leaked the system prompt until rule 5 was added (bug 10). Fencing is
implemented regardless of model.

---

## 13. Known limitations

All deliberate, all recorded. None is a defect awaiting a fix.

1. **Header/footer stripping considers every line on a page, not only lines at page
   boundaries.** Spec §5.1 describes *"repeated short lines at page boundaries"*; the
   implementation checks every line, making it strictly more aggressive than specified.
   **This is a documented deviation, decided rather than overlooked.** Its harmful
   consequence — emptying a document built from a repeated template — is fully guarded
   (bug 7). Narrowing it to a positional heuristic would change extraction on *every*
   document, invalidate the 33/33 verification, and move the very retrieval scores the
   test suite asserts against; that is a design change, not a documentation-day cleanup.

2. **Throughput is bounded by the hardware.** 30-75 s per answer on `llama3.2` on an 8 GB
   machine; the first request after Ollama starts also pays for loading the model. Long or
   repetitive questions can exceed the 300 s timeout and return 503. The chat loading
   indicator escalates its copy precisely so this never looks like a hang.

3. **No document-scope picker in the chat UI**, by decision. The *capability* ships and is
   tested — `POST /api/chat/ask` accepts `document_id`, and `useChat.sendMessage` /
   `ChatInterface` thread it end to end — only the control is absent. Adding one is a
   feature, and Day 9/10 were verification and documentation days.

4. **Conversation history is per-session.** Spec §2.2 classes cross-session persistence as
   an optional enhancement.

5. **OCR is plain text only.** Tesseract reconstructs no tables or layout, and accuracy
   drops on handwriting, low-resolution scans and skewed pages. Adequate for printed
   scans; not a production OCR pipeline (spec §6.5 says as much).

6. **`relevance_score` is match strength, not answer confidence.** Surfaced honestly in
   the UI for this reason.

7. **`app/utils/helpers.py` has three functions with no call sites** — `generate_id()`,
   `safe_filename()`, `file_size_mb()`; `documents.py` inlines the equivalent UUID
   generation. The module is part of the spec §15.1 list so it is kept rather than
   deleted, and wiring it in would be a refactor rather than cleanup. Recorded rather
   than changed on a day whose remit was documentation.

8. **`import fitz` raises a deprecation warning** on PyMuPDF 1.28 (`use import pymupdf`).
   Harmless today and left alone for the same reason as 7 — but it is the one dependency
   change a future version will force.

9. **Single-user, local, no authentication** — deliberate (spec §33).

---

## 14. How to run

```bash
# 0. Prerequisites: Python 3.10+, Node 18+, Ollama, Tesseract
ollama pull llama3.2          # or llama3.1:8b on a ≥16 GB machine
ollama serve

# 1. Backend
cd backend
python -m venv .venv
.venv\Scripts\activate         # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env         # macOS/Linux: cp .env.example .env
uvicorn app.main:app --reload  # → http://localhost:8000 (docs at /docs)

# 2. Frontend
cd frontend
npm install
npm run dev                    # → http://localhost:5173
```

Then open http://localhost:5173, go to **Documents**, drop in a PDF, wait for **Ready**,
and ask a question on the **Chat** tab. `README.md` has the full detail, including the
Windows long-path caveat and how to set `TESSERACT_CMD_PATH`.

## 15. How to test

```bash
cd backend
.venv\Scripts\activate
pytest tests/ -v               # 84 tests, 7 modules
```

No running Ollama and no real Tesseract call is required — the model call is stubbed and
OCR is patched, while retrieval, context construction and citation extraction all still
run for real.

`test_retriever.py` needs its corpus (`native_single.pdf`, `native_multi.pdf`,
`scanned_image_only.pdf` — 5 chunks). On a fresh clone, restore it by starting the backend
and uploading the three committed fixtures:

```bash
curl -F "file=@tests/fixtures/native_single.pdf" http://localhost:8000/api/documents/upload
curl -F "file=@tests/fixtures/native_multi.pdf" http://localhost:8000/api/documents/upload
curl -F "file=@tests/fixtures/scanned_image_only.pdf" http://localhost:8000/api/documents/upload
```

---

## 16. Day 10 changes

| File | Change |
|---|---|
| `backend/requirements.txt` | All 14 pins reconciled to the verified-working versions; header explains why |
| `backend/app/services/pdf_processor.py` | `_safe_error_message()` added (bug 11); stale module docstring corrected |
| `backend/tests/test_api.py` | +1 regression test for the path leak; module docstring corrected |
| `backend/app/models/schemas.py` | Removed unused `datetime` import |
| `backend/app/services/embedder.py` | Removed unused `Optional` import |
| `backend/app/services/ocr_processor.py` | Removed a dead `mat = None` assignment |
| `backend/tests/test_ocr_processor.py` | Removed unused `pytest` import; docstring corrected |
| `backend/.env.example` | Every one of the 17 variables documented inline; parity with `config.py` re-verified |
| `.gitignore` | Added `.pytest_cache/`, `.coverage`, `*.log`, `.env.local`, `.eslintcache`, tool caches; recorded why the test fixtures are deliberately **not** ignored |
| `README.md` | Extended to cover the architecture, OCR, full setup, all 6 endpoints, all 17 variables, testing, and known limitations |
| `docs/FINAL_PROJECT_COMPLETION.md` | This document |

**Untouched by design:** `backend/.env`, `backend/.venv`, everything in `backend/data/`,
all 15 frontend modules, `PROJECT_SPECIFICATION_v2.md`, `PROJECT_STEPS.md`. The
byte-identical production build independently confirms no frontend change.

**Not a git repository.** `.gitignore` is finalised as a deliverable; no git command was
run. Note for whenever the repository is initialised: the natural root is
`pdf-rag-chatbot/`, which leaves `PROJECT_SPECIFICATION_v2.md` and `PROJECT_STEPS.md`
(currently one level above) outside it — a layout decision left to the user rather than
changed unilaterally on the last day.

---

## 17. Final status

| | |
|---|---|
| **Required features** | **21 / 21 implemented** (F1-F20 + F2b) |
| **Spec §32 checklist** | **33 / 33 PASS**, 0 BLOCKED |
| **Automated tests** | **84 passed, 0 failed** across 7 modules |
| **Production build** | Clean — 1576 modules, 248.43 kB JS / 17.85 kB CSS |
| **Console errors** | 0 |
| **Known open bugs** | 0 |
| **Dependency install from scratch** | Verified — `pip install -r requirements.txt` exits 0, `pip check` clean |
| **Modules** | 16 backend / 15 frontend / 7 tests — as specified |
| **Timeline** | 10 days, not extended |
| **Cost** | ₹0 / $0 |
| **Status** | ✅ **PROJECT COMPLETE** |

Nothing was marked complete without evidence, and nothing was weakened to make a check
pass. The two items carried into Day 10 were each resolved by explicit decision: the path
leak was **fixed** with a regression test, and the `text_cleaner` page-boundary deviation
was **recorded** as a documented deviation with its reasoning, in this document and in
the README.

---

*End of FINAL_PROJECT_COMPLETION.md — Day 10 complete. Phase 7 closed. Project delivered.*
