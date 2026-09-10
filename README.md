# PDF Q&A RAG Chatbot

Upload PDFs, ask questions about them in natural language, and get answers that are
**grounded in your documents and cite the file and page they came from**. If a PDF is a
scan with no text layer, it is run through OCR automatically rather than being rejected.

Everything runs locally. There are no API keys, no cloud services and no cost — the LLM,
the embedding model, the vector store and the OCR engine are all on your machine, and no
document ever leaves it.

**Stack:** FastAPI · Ollama (Llama 3.1 8B / Llama 3.2 — see [Choosing a model](#choosing-a-model)) ·
sentence-transformers (all-MiniLM-L6-v2) · ChromaDB · SQLite · React + Vite + Tailwind CSS · Tesseract OCR

> **Status:** Complete. Built over 10 days against `PROJECT_SPECIFICATION_v2.md`; all 21
> required features implemented and all 33 items of the spec §32 completeness checklist
> verified. See [`docs/`](docs/) for the per-day session records and
> [`docs/FINAL_PROJECT_COMPLETION.md`](docs/FINAL_PROJECT_COMPLETION.md) for the final
> verification.

---

## What it does

| | Feature |
|---|---|
| **F1** | Upload one or many PDFs, with type and size validation |
| **F2** | Text extraction from multi-page PDFs via PyMuPDF |
| **F2b** | **OCR fallback** — a page with no embedded text is rendered to an image and read with Tesseract |
| **F3** | Text cleaning: unicode normalisation, control-character removal, whitespace collapsing, running-header stripping |
| **F4** | Chunking at 500 characters with 100 characters of overlap |
| **F5** | 384-dimensional embeddings from all-MiniLM-L6-v2 |
| **F6** | Vector storage in ChromaDB with document / page / chunk / extraction-method metadata |
| **F7** | Top-5 semantic retrieval by cosine similarity |
| **F8** | Context assembly with per-excerpt source labels, inside a token budget |
| **F9** | Grounded answer generation through Ollama |
| **F10** | Citation cards showing filename, page numbers, match strength, and an **OCR badge** for OCR-derived text |
| **F11** | Says "I could not find an answer" instead of inventing one |
| **F12/F13** | Chat interface with the session's conversation history |
| **F14** | Document management — list, status, page/OCR counts, delete (file + record + vectors) |
| **F15** | Upload, processing and answering indicators, including an OCR-specific message |
| **F16/F17** | Error handling and validation on both sides of the API |
| **F18** | REST API with correct status codes |
| **F19** | Responsive UI (desktop-first; no horizontal overflow down to 375 px) |
| **F20** | Health check reporting Ollama, ChromaDB, the embedding model and the OCR engine |

---

## Architecture

Three tiers: **React frontend → FastAPI backend → local AI services** (Ollama, ChromaDB,
sentence-transformers, Tesseract).

### Ingestion pipeline

```
PDF upload  →  validate (.pdf, MIME, ≤20 MB, non-empty)
            →  save as data/uploads/<uuid>.pdf, insert SQLite row (status=processing)
            →  [background task]
                 PyMuPDF page-by-page text extraction
                   └─ page under 10 chars of native text?
                        → render at 300 DPI → Tesseract → tag extraction_method="ocr"
                 →  clean (NFKC, control chars, whitespace, repeated header/footer lines)
                 →  chunk (500 chars, 100 overlap, metadata preserved)
                 →  embed (all-MiniLM-L6-v2, 384-dim)
                 →  store in ChromaDB collection `pdf_chunks`
                 →  SQLite status=ready, total_pages, total_chunks, ocr_pages_count
```

A document is marked `failed` only if **every** page yields nothing from both native
extraction and OCR. Partial OCR failure is fine — those pages are logged and skipped.

Ingestion is synchronous inside a FastAPI background task; the upload endpoint returns
`202` as soon as the file is saved, and the frontend polls for status.

### Query pipeline

```
question  →  embed the query (same model)
          →  ChromaDB top-5 cosine search (optionally scoped to one document_id)
          →  rank, convert distance to a 0-1 score
          →  build context: each chunk prefixed "[Source: file.pdf, Page 3]",
             " [OCR]" appended for OCR-derived text, inside a ~2500-token budget
          →  Ollama with a grounded system prompt; context and question each fenced
             in their own delimiter block (prompt-injection mitigation)
          →  detect a refusal; otherwise extract citations from the chunks the model
             was actually shown, merged one-per-file with sorted page lists
          →  {answer, citations[], processing_time_ms}
```

Two details worth knowing: citations are extracted only from the chunks that fit inside
the context budget, so a chunk the model never saw can never be cited; and when retrieval
returns nothing the "not found" answer is returned **without calling the LLM at all**.

### The OCR fallback (F2b)

Scanned PDFs — photographed pages, old textbooks, faxed forms — have no text layer, and
a naive extractor returns an empty string for every page. Here, any page yielding fewer
than 10 characters natively is rendered to an image with PyMuPDF's own `get_pixmap()` (no
extra PDF-to-image dependency) and passed to Tesseract.

OCR text is cleaned, chunked and embedded **identically** to native text, but tagged
`extraction_method: "ocr"` all the way through to the citation — so the UI can flag
answers drawn from potentially lower-confidence text with an OCR badge, and the document
list shows e.g. `12 pages (3 via OCR)`.

OCR is roughly 1-3 seconds per page, so ingesting a scanned document is noticeably
slower — which is why the upload indicator switches to "Running OCR on scanned pages…".

If Tesseract is missing the app **degrades rather than crashes**: `/api/health` reports
`ocr_available: false`, scanned pages are skipped as they were before OCR existed, and
native PDFs are unaffected.

---

## Quick Start

### Prerequisites

- **Python 3.10+** (developed and verified on 3.13.3)
- **Node.js 18+** (ships with npm)
- **[Ollama](https://ollama.com)** installed and running (`ollama serve`)
- **[Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki)** — on Windows use the
  UB-Mannheim installer; macOS `brew install tesseract`; Debian/Ubuntu
  `sudo apt install tesseract-ocr`. Verify with `tesseract --version`. If that command is
  not found, the app still runs — just set `TESSERACT_CMD_PATH` in `.env` (below) to
  enable OCR.
- **An Ollama model pulled — which one depends on your RAM**, see
  [Choosing a model](#choosing-a-model):
  - `ollama pull llama3.1:8b` (≥16 GB RAM)
  - `ollama pull llama3.2` (~8 GB RAM — the default in `.env.example`)
- ~5 GB free disk space (the backend dependencies include PyTorch).

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows.  macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # macOS/Linux: cp .env.example .env
uvicorn app.main:app --reload
```

API at http://localhost:8000 · interactive docs at http://localhost:8000/docs

`.env.example` is a working configuration as-is — copy it and edit nothing unless
`tesseract --version` failed, in which case set `TESSERACT_CMD_PATH`. The
`data/uploads/`, `data/chroma_db/` directories and the SQLite schema are all created
automatically on first start.

The embedding model (~80 MB) downloads from Hugging Face the first time the backend
starts, so give the first launch a minute.

> **Windows note.** If `pip install` fails part-way through unpacking PyTorch with
> `OSError: [Errno 2] No such file or directory` and a hint about *Windows Long Path
> support*, your project path is too deep: PyTorch ships headers with ~150-character
> relative paths, and Windows caps a full path at 260 characters by default. Either
> enable long paths, or put the project somewhere shorter. This bit during verification
> of this very README and has nothing to do with the dependency list.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

App at http://localhost:5173. Vite proxies `/api` to `http://localhost:8000`, so there is
nothing else to configure.

For a production bundle: `npm run build`.

### Order to start things in

1. `ollama serve` (or the Ollama desktop app)
2. `uvicorn app.main:app --reload` from `backend/`
3. `npm run dev` from `frontend/`

Then open http://localhost:5173, go to **Documents**, drop in a PDF, wait for **Ready**,
and ask a question on the **Chat** tab.

---

## Choosing a model

The LLM is a single environment variable, `OLLAMA_MODEL` in `backend/.env`.
Pick it to match your RAM:

| RAM | `OLLAMA_MODEL` | Notes |
|---|---|---|
| **≥16 GB** | `llama3.1:8b` | The specified model (spec §6.1). Best answer quality. |
| **~8 GB** | `llama3.2:latest` | 2.0 GB. The default, and the configuration the §32 checklist was verified against. |

**Why the default is not the spec model.** Measured on the development machine
(7.89 GB total RAM — just under the 8 GB minimum in spec §18.1), `llama3.1:8b`
loads but occupies **5.6 GB**, leaving **0.11 GB** free. Three consecutive
questions gave:

| Request | Result | Time |
|---|---|---|
| 1 (cold) | HTTP 200 — correct answer, correct citation | 243.5 s |
| 2 | HTTP 503 — exceeded the 300 s `OLLAMA_TIMEOUT_SECONDS` | 324.4 s |
| 3 | HTTP 503 — exceeded the 300 s timeout | 325.7 s |

Answer *quality* on `llama3.1:8b` is fine — request 1 was correct and correctly
cited. The problem is throughput: the machine thrashes and two questions in
three time out. On the same corpus `llama3.2:latest` answers in 30–75 s. If you
have the headroom spec §18.1 assumes, set `OLLAMA_MODEL=llama3.1:8b` and expect
better answers.

> One caveat on the smaller model: `llama3.2` is weaker at resisting prompt
> injection than `llama3.1:8b`. It leaked the system prompt on a direct
> "reveal your instructions" request until an explicit non-disclosure rule was
> added to `llm_service.SYSTEM_PROMPT`; three injection styles are blocked with
> that rule in place. Fencing context and question separately (spec §11) is
> implemented regardless of model.

---

## API

Base URL `http://localhost:8000`. Full interactive reference at `/docs`.

| Method | Endpoint | Request | Success | Errors |
|---|---|---|---|---|
| `POST` | `/api/documents/upload` | `multipart/form-data`, field `file` | **202** `{document_id, filename, status, message}` | **400** not `.pdf` / wrong MIME / over 20 MB / empty |
| `GET` | `/api/documents` | — | **200** `[DocumentInfo]` | — |
| `GET` | `/api/documents/{id}` | — | **200** `DocumentInfo` | **404** unknown id |
| `DELETE` | `/api/documents/{id}` | — | **200** `{message, document_id}` | **404** unknown id |
| `POST` | `/api/chat/ask` | `{question, document_id?}` | **200** `{answer, citations[], processing_time_ms}` | **400** empty question · **422** over 2000 chars · **503** Ollama unreachable or timed out · **500** unexpected |
| `GET` | `/api/health` | — | **200** `{status, ollama_available, chroma_available, embedding_model_loaded, ocr_available, details}` | — |

`DocumentInfo` is `{document_id, filename, upload_date, status, total_pages,
total_chunks, ocr_pages_count, error_message}` where `status` is
`processing` \| `ready` \| `failed`.

Each citation is `{filename, pages: [int], relevance_score: float,
extraction_method: "native" | "ocr"}`. Citations arrive sorted by
`relevance_score` descending, `pages` is already sorted, and there is exactly one
citation per file.

Two behaviours worth calling out:

- **Upload returns 202, not 200.** Ingestion runs in the background afterwards, so poll
  `GET /api/documents` (or watch the UI) for `processing → ready`.
- **"Not found" is a 200, not a 404.** The pipeline ran correctly and produced its
  designed output; the documents simply did not contain the answer. `citations` is `[]`
  in that case.

---

## Environment variables

All 17 live in `backend/.env`; `backend/.env.example` documents every one of them
inline and is a working configuration as-is. No secrets — the project uses no paid
services and no external APIs.

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Where Ollama is listening |
| `OLLAMA_MODEL` | `llama3.2:latest` | The generation model — see [Choosing a model](#choosing-a-model) |
| `OLLAMA_TIMEOUT_SECONDS` | `300` | Generation timeout before a 503; covers cold model loading |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | sentence-transformers model (384-dim) |
| `CHROMA_PERSIST_DIR` | `./data/chroma_db` | ChromaDB storage |
| `UPLOAD_DIR` | `./data/uploads` | Uploaded PDFs, stored under generated UUIDs |
| `DATABASE_PATH` | `./data/pdf_chatbot.db` | SQLite metadata database |
| `MAX_FILE_SIZE_MB` | `20` | Per-file upload limit |
| `CHUNK_SIZE` | `500` | Characters per chunk |
| `CHUNK_OVERLAP` | `100` | Overlap between consecutive chunks |
| `TOP_K_RESULTS` | `5` | Chunks retrieved per question |
| `MAX_CONTEXT_TOKENS` | `2500` | Context budget handed to the model |
| `FRONTEND_ORIGIN` | `http://localhost:5173` | The only origin CORS allows |
| `OCR_ENABLED` | `true` | Master switch for the OCR fallback |
| `OCR_LANGUAGE` | `eng` | Tesseract language pack |
| `OCR_DPI` | `300` | Render resolution for OCR |
| `TESSERACT_CMD_PATH` | *(empty)* | Explicit path to the Tesseract binary if it is not on PATH |

---

## Running the tests

From `backend/`, with the virtual environment active:

```bash
pytest tests/ -v
```

Seven test modules: `test_text_cleaner.py`, `test_chunker.py`, `test_embedder.py`,
`test_retriever.py`, `test_llm_service.py`, `test_ocr_processor.py`, `test_api.py`.

No running Ollama is required — every test that would call the model stubs
`llm_service.call_ollama`, so retrieval, context construction and citation extraction all
still run for real while the suite stays fast and deterministic. No real Tesseract call is
made either.

**`test_retriever.py` needs a corpus.** It asserts measured similarity scores against
three documents that must be present in ChromaDB: `native_single.pdf`, `native_multi.pdf`
and `scanned_image_only.pdf` — 5 chunks in total. On a fresh clone the store is empty, so
those tests will fail with a message telling you exactly what to upload. Restore it by
starting the backend and uploading the three committed fixtures:

```bash
curl -F "file=@tests/fixtures/native_single.pdf" http://localhost:8000/api/documents/upload
curl -F "file=@tests/fixtures/native_multi.pdf" http://localhost:8000/api/documents/upload
curl -F "file=@tests/fixtures/scanned_image_only.pdf" http://localhost:8000/api/documents/upload
```

(Or just drag them onto the Documents page.) The fixture PDFs are committed rather than
regenerated precisely so those thresholds stay reproducible; `tests/fixtures/make_fixtures.py`
regenerates all eight of them if you ever need to.

---

## Project structure

```
pdf-rag-chatbot/
├── backend/
│   ├── app/
│   │   ├── main.py, config.py
│   │   ├── models/      schemas.py, database.py
│   │   ├── routers/     documents.py, chat.py, health.py
│   │   ├── services/    pdf_processor, text_cleaner, chunker, embedder,
│   │   │                vector_store, retriever, llm_service, ocr_processor
│   │   └── utils/       helpers.py
│   ├── tests/           7 test modules + fixtures/ (8 PDFs + make_fixtures.py)
│   ├── data/            uploads/, chroma_db/, pdf_chatbot.db   (git-ignored)
│   ├── requirements.txt, .env.example
├── frontend/
│   └── src/             App, main, 2 pages, 9 components, api.js, useChat.js
└── docs/                SESSION_02 … SESSION_10, FINAL_PROJECT_COMPLETION.md
```

16 backend app modules, 15 frontend modules, 7 test modules — matching spec §15.
`PROJECT_SPECIFICATION_v2.md` has the full architecture.

---

## Known limitations

These are recorded deliberately rather than hidden — each is a decision with a reason.

- **Speed is bounded by your hardware.** Answers take 30-75 s on `llama3.2` on an 8 GB
  machine, and the first request after Ollama starts pays for loading the model. The chat
  loading indicator escalates its message over time for exactly this reason. Long or
  repetitive questions can exceed the 300 s timeout and return a 503 on the 8 GB tier.

- **Header/footer stripping considers every line on a page, not only lines at page
  boundaries.** Spec §5.1 describes "repeated short lines at page boundaries"; the
  implementation checks every line, so it is strictly more aggressive than specified.
  This is a **documented deviation, not a bug**. It is guarded: stripping can never empty
  a page — a document built from a repeated template (a form, a certificate, the same
  scanned page twice) makes every line look like a running header, and without the guard
  the whole document was reduced to nothing and reported as unreadable. Narrowing it to a
  positional heuristic would change extraction on every document and move the retrieval
  scores the test suite asserts against, so it was left as-is with the guard in place.

- **There is no document-scope picker in the chat UI**, by decision rather than
  omission. Scoping a question to one document is fully implemented and tested
  end to end — `POST /api/chat/ask` accepts an optional `document_id` that is
  passed straight through to retrieval, and `useChat.sendMessage` /
  `ChatInterface` already thread it — but no control is wired to it in the
  interface. Adding one is a feature, not part of the verification scope.

- **Conversation history is per-session.** Refreshing the page clears it; spec §2.2
  classifies cross-session persistence as an optional enhancement.

- **OCR is plain text only.** Tesseract does not reconstruct tables or layout, and
  accuracy drops on handwriting, low-resolution scans and skewed pages. Good enough for
  printed scans; not a production OCR pipeline.

- **`relevance_score` is match strength, not confidence.** It measures how closely a
  retrieved passage matched the question, not how correct the answer is — a correct
  answer to a broad question can score low. The UI labels it "MATCH STRENGTH" for this
  reason and never calls it confidence.

- **`app/utils/helpers.py` is currently unused.** Its three functions have no call sites
  (`documents.py` inlines the equivalent UUID generation). The module is part of the
  spec §15.1 module list, so it is kept rather than deleted.

- **Single-user, local, no authentication.** Deliberate (spec §33): auth adds days
  without improving the RAG pipeline, and the app binds to localhost.

---

## Documentation

- [`PROJECT_SPECIFICATION_v2.md`](../PROJECT_SPECIFICATION_v2.md) — the full specification
- [`docs/FINAL_PROJECT_COMPLETION.md`](docs/FINAL_PROJECT_COMPLETION.md) — final verification, feature-by-feature
- [`docs/SESSION_02_SETUP.md`](docs/) … [`SESSION_10_TESTING.md`](docs/) — one record per build day, including what broke and why
