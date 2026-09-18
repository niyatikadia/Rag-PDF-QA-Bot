# PDF Q&A RAG Chatbot

Upload PDFs, ask questions about them in natural language, and get answers that are
**grounded in your documents and cite the file and page they came from**. If a PDF is a
scan with no text layer, it is run through OCR automatically rather than being rejected.

Everything runs locally. There are no API keys, no cloud services and no cost — the LLM,
the embedding model, the vector store and the OCR engine are all on your machine, and no
document ever leaves it.

**Stack:** FastAPI · Ollama (Llama 3.1 8B / Llama 3.2 — see [Choosing a model](#choosing-a-model)) ·
sentence-transformers (all-MiniLM-L6-v2) · ChromaDB · SQLite · React + Vite + Tailwind CSS · Tesseract OCR

> **Status:** **v1.0.0 — released and deployed** (self-hosted, local). Built over 10 days
> against `PROJECT_SPECIFICATION_v2.md` — all 21 required features implemented and all 33
> items of the spec §32 completeness checklist verified — then taken through a post-coding
> lifecycle: verification, hardening, consolidation and release.
>
> | Phase | Record | Outcome |
> |---|---|---|
> | Build (10 days) | [`docs/SESSION_02…10`](docs/), [`FINAL_PROJECT_COMPLETION.md`](docs/FINAL_PROJECT_COMPLETION.md) | 21/21 features, 33/33 checklist |
> | A — Verification | [`POSTCODING_DAY_01_VERIFICATION.md`](docs/POSTCODING_DAY_01_VERIFICATION.md) | Functional, integration, regression, clean-state gate |
> | B — Hardening | [`POSTCODING_DAY_02_HARDENING.md`](docs/POSTCODING_DAY_02_HARDENING.md) | 9 defects found and fixed; performance, security, UI/UX, configuration |
> | C — Consolidation | [`POSTCODING_DAY_03_CONSOLIDATION.md`](docs/POSTCODING_DAY_03_CONSOLIDATION.md) | Lint/type clean, docs reconciled, fresh-env install proven, production build verified |
> | D — Release | [`POSTCODING_DAY_04_RELEASE.md`](docs/POSTCODING_DAY_04_RELEASE.md), [`CHANGELOG.md`](CHANGELOG.md), [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) | Layered history, v1.0.0 tagged, deployed and verified in production mode |
> | E — Operations | [`POSTCODING_DAY_05_OPERATIONS.md`](docs/POSTCODING_DAY_05_OPERATIONS.md) | Production smoke test, structured logging, request middleware, health check extended to five dependencies |
> | Completion | [`POSTCODING_DAY_06_COMPLETION.md`](docs/POSTCODING_DAY_06_COMPLETION.md) | Tests decoupled from live data, OCR/failure ingestion tests added, dependency CVE audit, throughput and memory measured, UI state matrix captured, docs reconciled |
>
> **Deployed** means: production mode, one process serving both the API and the built
> frontend on `127.0.0.1:8000`, interactive API docs not mounted, verified with a real
> question end to end. It is **self-hosted and loopback-only** — a 2 GB local model does
> not fit any free hosting tier, and there is no authentication, so it is not exposed to a
> network. See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for the reasoning, the
> persistence plan and the rollback plan.
>
> **What "monitored" means here, precisely.** The service emits structured JSON
> logs in production, logs every request with its status and duration, and
> reports the health of all five dependencies plus uptime and version on
> `/api/health`. A scheduled health check with a failure alert ships in
> [`scripts/health-monitor.ps1`](scripts/health-monitor.ps1). There is **no
> metrics dashboard and no time-series store** — see
> [Known limitations](#known-limitations).

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

> Those commands are the **development** setup: `--reload` on, API docs mounted, and the
> frontend served separately by Vite. To run the released version instead — one process,
> no API docs, frontend served by the backend — see
> [Running in production](#running-in-production).

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

### Running in production

The released version runs as **one process on one origin**: the backend serves the built
frontend as well as the API, so there is no Node runtime, no second port and no CORS.

```bash
cd frontend && npm ci && npm run build && cd ..
```

Then, with Ollama running:

```bash
powershell -ExecutionPolicy Bypass -File scripts\start-production.ps1
```

The script checks the virtual environment, `.env`, the built bundle and Ollama before it
binds a port, then starts uvicorn with `APP_ENV=production`. The whole application is at
**http://127.0.0.1:8000**.

What changes in production: `/docs`, `/redoc` and `/openapi.json` are **not mounted**,
`--reload` is off, and the frontend comes from `frontend/dist` rather than Vite.

> `--host 127.0.0.1` is loopback-only and deliberate. There is no authentication, so
> binding `0.0.0.0` would expose an open upload endpoint to the network.

[`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) covers the target decision, what persists
across restarts, the rollback plan and the pre-deploy checklist.

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

Base URL `http://localhost:8000`. Full interactive reference at `/docs` in development —
in production it is not mounted, and [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md) is
the written equivalent.

| Method | Endpoint | Request | Success | Errors |
|---|---|---|---|---|
| `POST` | `/api/documents/upload` | `multipart/form-data`, field `file` | **202** `{document_id, filename, status, message}` | **400** not `.pdf` / wrong MIME / over 20 MB / empty |
| `GET` | `/api/documents` | — | **200** `[DocumentInfo]` | — |
| `GET` | `/api/documents/{id}` | — | **200** `DocumentInfo` | **404** unknown id |
| `DELETE` | `/api/documents/{id}` | — | **200** `{message, document_id}` | **404** unknown id |
| `POST` | `/api/chat/ask` | `{question, document_id?}` | **200** `{answer, citations[], processing_time_ms}` | **400** empty question · **422** over 2000 chars · **503** Ollama unreachable or timed out · **500** unexpected |
| `GET` | `/api/health` | — | **200** `{status, ollama_available, chroma_available, embedding_model_loaded, ocr_available, database_available, uptime_seconds, version, details}` | — |

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

All 20 live in `backend/.env`; `backend/.env.example` documents every one of them
inline and is a working configuration as-is. No secrets — the project uses no paid
services and no external APIs. [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) is
the full reference; this table is the summary.

| Variable | Default | Purpose |
|---|---|---|
| `APP_ENV` | `development` | `development` or `production`. In production the interactive API docs are not mounted and the backend serves the built frontend |
| `LOG_LEVEL` | `INFO` | `CRITICAL`, `ERROR`, `WARNING`, `INFO` or `DEBUG` |
| `FRONTEND_DIST_DIR` | `../frontend/dist` | Where `npm run build` writes the bundle. Resolved against `backend/`, not the working directory |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Where Ollama is listening. The literal IPv4 address is deliberate — see the note below the table |
| `OLLAMA_MODEL` | `llama3.2:latest` | The generation model — see [Choosing a model](#choosing-a-model) |
| `OLLAMA_TIMEOUT_SECONDS` | `300` | Generation timeout before a 503; covers cold model loading |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | sentence-transformers model (384-dim). **Point this only at a model you trust** — see [Security](#security) |
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

> **Why `OLLAMA_BASE_URL` is `127.0.0.1` and not `localhost`.** On Windows,
> `localhost` resolves to `::1` before `127.0.0.1`, and Ollama binds IPv4 only. Every new
> connection therefore waited for the IPv6 refusal before falling back — measured at
> 2065 ms via `localhost` against 8.3 ms via `127.0.0.1`, paid on every health check and
> every question. Point it at a hostname only if Ollama runs on another machine.

> **Every numeric variable is range-checked at startup.** A value that is not a whole
> number, or is below its minimum, stops the backend immediately with a message naming the
> variable, instead of letting it start "healthy" and fail later during an upload or a
> question. `CHUNK_OVERLAP` must also be strictly smaller than `CHUNK_SIZE`. The minimum
> for each variable is documented inline in `.env.example`, and
> [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) is the full reference.

---

## Running the tests

From `backend/`, with the virtual environment active:

```bash
pytest tests/ -v
```

**184 tests across twelve modules**, all passing:

| Module | Tests | Covers |
|---|---|---|
| `test_llm_service.py` | 72 | Context budget, prompt fencing, citation extraction, refusal detection, prompt-injection output guard |
| `test_api.py` | 21 | Every endpoint and status code, bounded upload reads, multipart filename edge cases |
| `test_production_mode.py` | 21 | `APP_ENV`/`LOG_LEVEL` validation, API docs absent in production, SPA fallback, static path-traversal containment |
| `test_config_validation.py` | 17 | Startup range/type checking of every numeric setting |
| `test_text_cleaner.py` | 10 | Normalisation, control characters, header/footer stripping |
| `test_retriever.py` | 9 | Ranking, scoring, document scoping, OCR chunk retrieval |
| `test_monitoring.py` | 9 | Health database/uptime/version fields, request middleware, JSON log formatter |
| `test_ingestion_pipeline.py` | 7 | End-to-end ingestion: OCR fallback, mixed documents, the `failed` path, large and repeated-header PDFs |
| `test_chunker.py` | 6 | Chunk size, overlap, metadata propagation |
| `test_ocr_processor.py` | 5 | OCR fallback, disabled/unavailable degradation |
| `test_embedder.py` | 4 | Embedding shape and determinism |
| `test_concurrency.py` | 3 | Handlers run in the threadpool, so one question cannot freeze the server |

**The suite is self-contained.** It needs no running Ollama — every test that would
call the model stubs `llm_service.call_ollama`, so retrieval, context construction and
citation extraction all still run for real while the suite stays fast and deterministic.

It also needs nothing uploaded first. `tests/conftest.py` points the vector store and the
SQLite catalogue at throwaway directories for the session and rebuilds its corpus from the
committed fixture PDFs through the real ingestion pipeline. That means the suite never
reads or writes your actual documents, and uploading anything through the application
cannot turn it red. (Before this it asserted against whatever happened to be in
`backend/data/chroma_db/`, so a fourth uploaded document broke it.)

The fixture PDFs are committed rather than regenerated precisely so the measured
similarity thresholds stay reproducible — same bytes, same extracted text, same
embeddings, same scores. `tests/fixtures/make_fixtures.py` regenerates all eight if you
ever need to, with the caveat that a different PyMuPDF version can shift those scores.

**Tesseract is optional for the suite.** `test_ocr_processor.py` patches it entirely. The
tests that exercise the real OCR path — the scanned fixture in `test_retriever.py` and
`test_ingestion_pipeline.py` — skip with a stated reason when Tesseract is not installed,
rather than failing as though the code were broken.

---

## Project structure

```
pdf-rag-chatbot/
├── backend/
│   ├── app/
│   │   ├── __init__.py  __version__ — the single source of the version
│   │   ├── main.py, config.py
│   │   ├── models/      schemas.py, database.py
│   │   ├── routers/     documents.py, chat.py, health.py
│   │   ├── services/    pdf_processor, text_cleaner, chunker, embedder,
│   │   │                vector_store, retriever, llm_service, ocr_processor
│   │   └── utils/       helpers.py
│   ├── tests/           conftest.py + 12 test modules
│   │                    fixtures/ (8 PDFs + make_fixtures.py)
│   ├── data/            uploads/, chroma_db/, pdf_chatbot.db   (git-ignored)
│   ├── requirements.txt, .env.example, pyproject.toml
├── frontend/
│   ├── public/          favicon.ico
│   ├── src/             App, main, 2 pages, 9 components, api.js, useChat.js
│   └── .prettierrc, eslint.config.mjs, vite.config.js, tailwind.config.js
├── scripts/             start-production.ps1, health-monitor.ps1
├── docs/                ARCHITECTURE, API_REFERENCE, CONFIGURATION, DEPLOYMENT,
│                        SESSION_02 … SESSION_10, POSTCODING_DAY_01 … 06,
│                        FINAL_PROJECT_COMPLETION, ui-verification/ (24 captures)
├── .day2/ .day3/ .day6/ post-coding harnesses and their recorded output
├── .gitattributes       line-ending policy (LF in the repository)
├── CHANGELOG.md
└── README.md
```

16 backend app modules, 15 frontend modules — matching spec §15. The test suite has grown
from the 7 modules spec §15 lists to 12: `test_config_validation.py` and
`test_concurrency.py` were added during hardening, `test_production_mode.py` at release,
`test_monitoring.py` in operations, and `test_ingestion_pipeline.py` to cover the OCR and
failure outcomes spec §19.2 and §32 specify but nothing asserted.
`PROJECT_SPECIFICATION_v2.md` has the full architecture.

### Code quality

Linting and formatting are configured but the tools are **not** project dependencies —
they are developer tooling, so they are not in `requirements.txt` or `package.json`.
Install them into a throwaway environment and run:

```bash
# Python — from backend/
python -m venv ../.venv-tools && ../.venv-tools/Scripts/pip install ruff black mypy
../.venv-tools/Scripts/ruff check app tests     # config in pyproject.toml
../.venv-tools/Scripts/mypy app

# JavaScript — from frontend/
npx prettier --check "src/**/*.{js,jsx,css}"    # config in .prettierrc
```

Current state: **ruff clean, mypy clean (21 files), prettier clean.** `pyproject.toml`
records which rule families are deliberately disabled and why.

---

## Security

The full checklist, its per-item results and the attack attempts behind them are in
[`POSTCODING_DAY_02_HARDENING.md`](docs/POSTCODING_DAY_02_HARDENING.md) §2 and
[`POSTCODING_DAY_06_COMPLETION.md`](docs/POSTCODING_DAY_06_COMPLETION.md). The parts a
reader should know before running it:

**Dependency advisories.** `npm audit` reports **0 vulnerabilities**. `pip-audit` reports
nine against two *transitive* Python packages — none of the 14 direct pins. Every one was
traced to the code path it needs:

| Package | Advisories | Reachable here? |
|---|---|---|
| `chromadb` 1.5.9 | PYSEC-2026-311, ‑3813, ‑3814, ‑3815 | **No.** All four are vulnerabilities in the ChromaDB **server** — its HTTP API, its `trust_remote_code` collection endpoints and its `SimpleRBACAuthorizationProvider`. This project uses `chromadb.PersistentClient` only: an in-process library with no server, no HTTP API and no auth provider. No fix is published for any of them at any version. |
| `transformers` 4.57.6 | PYSEC-2025-217, ‑2026-2288, ‑2289, ‑2290, ‑3929 | **No, with one condition.** The app never calls `Trainer`, `save_pretrained`, `AutoModel*` or the X-CLIP/LightGlue paths these need; it loads one model through `SentenceTransformer(EMBEDDING_MODEL)`. PYSEC-2026-2289 (malicious `config.json` → RCE at load) becomes reachable **if you point `EMBEDDING_MODEL` at an untrusted repository**, so treat that variable as security-relevant. Its fix is in transformers 5.3.0, a major version that `sentence-transformers` 3.0.1 does not support. |

Run the audit yourself — it needs no project dependency:

```bash
python -m venv .venv-tools && .venv-tools/Scripts/pip install pip-audit
.venv-tools/Scripts/pip-audit -r backend/requirements.txt --desc
cd frontend && npm audit
```

**What protects the service.** Uploads are validated on extension, declared MIME and
size, read in bounded 1 MB chunks so an oversized body cannot exhaust memory before it is
refused, and stored under a generated UUID — never the user's filename. Retrieved context
and the user's question are fenced in separate delimiter blocks and declared to be data,
with fence markers inside retrieved text neutralised and an output-side guard that
replaces a system-prompt-disclosing answer with the refusal sentence. Ingestion errors are
sanitised before storage, so no server path or internal id reaches the browser. CORS
allows exactly one configured origin. In production the static handler resolves every
requested path and confirms it is inside the bundle before reading it.

**What does not protect it.** There is no authentication, authorisation or HTTPS, by
design — `--host 127.0.0.1` is the only thing keeping an open upload endpoint off the
network. All three become mandatory before any network exposure.

---

## Known limitations

These are recorded deliberately rather than hidden — each is a decision with a reason.

- **Speed is bounded by your hardware.** Answers take 25-95 s on `llama3.2` on an 8 GB
  machine once the model is resident; the first request after Ollama starts additionally
  pays for loading it, measured at 172 s. The chat loading indicator escalates its
  message over time for exactly this reason. Long or repetitive questions can exceed the
  300 s timeout and return a 503 on the 8 GB tier.

  Generation is the only slow part, and it does not block anything else. Measured on the
  reference machine (i7-7600U, 7.89 GB RAM, Windows 11):

  | Measurement | Idle | While a 94.9 s answer is generating |
  |---|---|---|
  | `GET /api/documents` throughput | **129.5 req/s** (p50 5.98 ms, p99 18.34 ms) | **82.8 req/s** (p50 7.10 ms, p99 44.11 ms), 0 errors |
  | `GET /api/health` throughput | **8.5 req/s** (p50 110.27 ms) | — |

  `/api/health` is deliberately slower: it makes a real HTTP call to Ollama, a ChromaDB
  heartbeat, a SQLite query and a Tesseract subprocess spawn. It is a diagnostic, not a
  liveness ping — do not poll it aggressively.

  **No memory leak observed.** Across five cycles of three ingest-and-delete rounds plus
  fifty reads each, the backend's working set moved from 145.7 MB to 147.2 MB (+1.5 MB),
  which is a flat floor rather than a rising one. Harness:
  [`.day6/perf_throughput_memory.py`](.day6/perf_throughput_memory.py).

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
  without improving the RAG pipeline, and the app binds to `127.0.0.1`. Authentication,
  authorisation and HTTPS all become mandatory if the deployment model ever changes.
  `--host 127.0.0.1` is the only thing keeping an unauthenticated upload endpoint off the
  network; do not change it to `0.0.0.0` without adding auth and TLS first.
  *(`/docs`, `/redoc` and `/openapi.json` are no longer part of this limitation — they are
  not mounted when `APP_ENV=production`.)*

- **Deployed only as a self-hosted local service; not cloud-hostable as designed.** The
  LLM, the embedding model and the vector store all run locally by design (zero cost,
  complete data privacy), which needs a machine with enough RAM to hold the model
  resident — no free hosting tier provides that, and deploying there would yield a service
  that passes a health check and fails every question. Swapping to a hosted model API is
  one service module and one environment variable, because the model call sits behind a
  single interface. See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) §1 for the options
  considered and why each was rejected.

- **Nine open CVEs in two transitive Python dependencies, none of them reachable here.**
  `pip-audit` reports 4 advisories against `chromadb` and 5 against `transformers`. Each
  was checked against this code rather than waved away, and **no fix exists for six of
  them at any version**. See [Security](#security) for the per-advisory reasoning. This
  is an honest "not reachable", not a "not checked" — which is what it used to be.

- **Prompt-injection defence stops disclosure, not influence.** The output guard blocks
  verbatim recitation of the system prompt and its fence markers, but a model that
  paraphrases can defeat a substring filter, and a poisoned document can still bias the
  *content* of an answer — inherent to retrieval augmentation. Mitigation is controlling
  what gets uploaded, which for a single-user local app is the user.

> The full carried-forward list, with the reason each item was not closed, is in
> [`POSTCODING_DAY_02_HARDENING.md`](docs/POSTCODING_DAY_02_HARDENING.md) §9 (13 items)
> and [`POSTCODING_DAY_03_CONSOLIDATION.md`](docs/POSTCODING_DAY_03_CONSOLIDATION.md).

---

## Documentation

**Reference**

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — components, how they connect, data flow, and why each major choice was made
- [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md) — every endpoint, request and response shape, status codes, error cases
- [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) — every variable, its default, what it controls, and how it is validated

**Records**

- [`docs/FINAL_PROJECT_COMPLETION.md`](docs/FINAL_PROJECT_COMPLETION.md) — final build verification, feature-by-feature
- [`docs/SESSION_02_SETUP.md`](docs/) … [`SESSION_10_TESTING.md`](docs/) — one record per build day, including what broke and why
- [`docs/POSTCODING_DAY_01_VERIFICATION.md`](docs/POSTCODING_DAY_01_VERIFICATION.md) — phase A: functional, integration, regression, clean-state gate
- [`docs/POSTCODING_DAY_02_HARDENING.md`](docs/POSTCODING_DAY_02_HARDENING.md) — phase B: performance, security, UI/UX, configuration
- [`docs/POSTCODING_DAY_03_CONSOLIDATION.md`](docs/POSTCODING_DAY_03_CONSOLIDATION.md) — phase C: cleanup, documentation, reproducibility, build

**Specification** — `PROJECT_SPECIFICATION_v2.md` is the document this project was built
against. It lives one level *above* the repository root and is deliberately not published:
the repository is rooted at `pdf-rag-chatbot/` so that it contains exactly the application.
It is referenced here by name rather than by link, because a link would 404 on GitHub.
