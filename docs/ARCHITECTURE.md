# Architecture

**Audience:** an engineer joining the project.
**Scope:** what the components are, how they connect, how data flows, and *why* each major
choice was made. Written on post-coding Day 3 against the code as it actually exists —
every module, function and behaviour named here was read out of the source, not the spec.

Companion documents: [`API_REFERENCE.md`](API_REFERENCE.md) for the HTTP contract,
[`CONFIGURATION.md`](CONFIGURATION.md) for every setting.

---

## 1. The shape of the system

Three tiers, all on one machine, with no external network calls:

```
┌──────────────────────────────────────────────────────────────────────────┐
│  BROWSER                                                                 │
│  React 18 + Vite + Tailwind                                              │
│  ChatPage ──┐                                                            │
│             ├── useChat (hook, session state) ── api.js (axios) ──┐      │
│  DocumentsPage ───────────────────────────────────────────────────┤      │
└───────────────────────────────────────────────────────────────────┼──────┘
                       /api  (Vite dev proxy → :8000)               │
┌───────────────────────────────────────────────────────────────────▼──────┐
│  FastAPI  (uvicorn, single process)                                      │
│                                                                          │
│  routers/documents.py   routers/chat.py      routers/health.py           │
│         │                     │                     │                    │
│         │                     │                     └── probes all four  │
│         ▼                     ▼                         dependencies     │
│  services/pdf_processor  services/retriever ── services/llm_service      │
│    ├ ocr_processor         └ embedder                                    │
│    ├ text_cleaner            └ vector_store                              │
│    ├ chunker                                                             │
│    ├ embedder                                                            │
│    └ vector_store                                                        │
│                                                                          │
│  models/database.py (SQLite CRUD)   models/schemas.py (Pydantic contract) │
│  config.py  ← imported by everything; the only module that reads env vars │
└──────────┬─────────────────┬──────────────────┬──────────────────────────┘
           │                 │                  │
      ┌────▼────┐      ┌─────▼──────┐     ┌─────▼──────┐    ┌────────────┐
      │ SQLite  │      │  ChromaDB  │     │   Ollama   │    │ Tesseract  │
      │ metadata│      │  vectors   │     │ HTTP :11434│    │ subprocess │
      └─────────┘      └────────────┘     └────────────┘    └────────────┘
```

**Why everything is local.** The design constraint was zero cost and complete data
privacy: no document, or fragment of one, may leave the user's machine. That rules out
hosted embedding and generation APIs, and it is the reason the project cannot go on a free
hosting tier — it needs enough RAM to hold a language model resident.

---

## 2. Module map

### The dependency root

`app/config.py` is imported by literally every other backend module and is the **only**
module that calls `os.getenv`. Everything else imports already-typed, already-validated
constants from it.

Two things happen at import time, deliberately:

* **Validation.** `_int_env()` reads each integer setting with a minimum, and raises
  `ConfigurationError` naming the variable and the file to edit. A cross-field check
  rejects `CHUNK_OVERLAP >= CHUNK_SIZE`. Failing at import means the process dies during
  startup rather than at use time — see §5, decision D6.
* **Directory creation.** `UPLOAD_DIR`, `CHROMA_PERSIST_DIR` and the database's parent are
  `mkdir(parents=True, exist_ok=True)`'d, so a fresh clone needs no manual setup step.

### Data layer

| Module | Responsibility |
|---|---|
| `models/schemas.py` | The **external** contract — 7 Pydantic models. Imports only `pydantic` and `typing`. |
| `models/database.py` | The **internal** contract — SQLite connection plus CRUD over one `documents` table. Every query is parameterised. |

There is exactly one table. It holds metadata only; the chunk text and vectors live in
ChromaDB, and the PDF bytes live on disk.

### Document services (ingestion)

| Module | Responsibility |
|---|---|
| `services/pdf_processor.py` | Orchestrates ingestion end to end; owns the failure and cleanup semantics. |
| `services/ocr_processor.py` | Renders a page with PyMuPDF and runs Tesseract. Returns `None` on any failure. |
| `services/text_cleaner.py` | NFKC normalisation, control-character removal, whitespace collapsing, duplicate-line and repeated header/footer stripping. |
| `services/chunker.py` | Wraps LangChain's `RecursiveCharacterTextSplitter`. |

### AI services (query)

| Module | Responsibility |
|---|---|
| `services/embedder.py` | Lazy singleton around the sentence-transformers model. |
| `services/vector_store.py` | Thin ChromaDB wrapper — client and collection singletons, add, query, delete. |
| `services/retriever.py` | Embed → search → rank. Converts cosine distance to a 0–1 score. |
| `services/llm_service.py` | Context construction, prompt fencing, the Ollama call, refusal detection, citation extraction, and the prompt-disclosure output guard. |

`llm_service.py` is the largest module (548 lines) and deliberately so: context
construction, prompt building, the HTTP call and citation extraction are each a separate,
individually testable function, which is why 72 of the 146 tests live against it.

### API layer

`routers/documents.py`, `routers/chat.py`, `routers/health.py`, assembled by `main.py`
with CORS restricted to the single `FRONTEND_ORIGIN`.

### Not wired in

`app/utils/helpers.py` has three functions with no call sites — `generate_id()`,
`safe_filename()`, `file_size_mb()`. `documents.py` inlines the equivalent UUID
generation. The module is part of the spec §15.1 module list, so it is **kept and
documented rather than deleted**. Recorded again here so nobody rediscovers it as a
mystery.

---

## 3. Data flow

### Ingestion

```
POST /api/documents/upload
  │
  ├─ _validate_metadata(file)      name + declared MIME only — no body read yet
  ├─ _read_within_limit(file)      1 MB chunks, stops the moment the limit is passed
  ├─ write data/uploads/<uuid>.pdf generated name, never the user's
  ├─ INSERT documents (status='processing')
  ├─ background_tasks.add_task(process_document, ...)
  └─ 202 Accepted                  ← returns here; ingestion has not started
        │
        ▼  (FastAPI background task, synchronous inside)
  extract_text_from_pdf()
     └─ per page: PyMuPDF get_text()
          └─ under 10 chars? → render at OCR_DPI → Tesseract → extraction_method='ocr'
  clean_pages()
  chunk_pages()                    → [{chunk_text, metadata{document_id, filename,
                                        page_number, chunk_index, extraction_method}}]
  ── is the document still there?  ← deletion-during-ingestion check
  add_chunks(chunks, embedder)     → ChromaDB collection `pdf_chunks`
  UPDATE documents SET status='ready', total_pages, total_chunks, ocr_pages_count
```

A document becomes `failed` only if **every** page yields nothing from both native
extraction and OCR. Partial OCR failure is normal and is logged, not fatal.

### Query

```
POST /api/chat/ask  {question, document_id?}
  │
  ├─ retriever.retrieve(question, top_k=TOP_K_RESULTS, document_id=…)
  │     ├─ embed_query()                       same model as ingestion
  │     ├─ vector_store.query_chunks()         cosine, optionally filtered to one document
  │     └─ distance_to_score() + explicit sort  → best-first
  │     (never raises: empty store, embedding failure and ChromaDB errors all return [])
  │
  └─ llm_service.generate_answer(question, chunks)
        ├─ build_context()      neutralise_fences() on every chunk, then fill the budget
        │                       best-first; returns the INCLUDED chunks, not all of them
        ├─ (no chunks? → return NOT_FOUND_PHRASE without calling the LLM at all)
        ├─ build_prompt()       context and question each in their own delimiter block
        ├─ call_ollama()        POST /api/generate, stream=false, temperature 0.1
        ├─ discloses_prompt()?  → withhold the answer, return the "not found" response
        ├─ is_not_found_answer()? → return it with zero citations
        └─ extract_citations(answer, included)  → one citation per file, pages merged
```

**Citations can only name chunks the model actually saw.** `build_context` returns
`(context_string, included_chunks)` and the caller cites from `included_chunks`, never
from the full retrieval list. A chunk dropped by the token budget can therefore never be
cited.

---

## 4. Trust boundaries

Two inputs are attacker-controlled and are treated as such:

1. **The user's question** — arbitrary text from the browser.
2. **Retrieved chunk text** — *anyone who can put a PDF into the corpus chooses this*.
   This is the less obvious one and it is the one that actually broke: a poisoned PDF
   carrying a "SYSTEM OVERRIDE" block hijacked answers and leaked every fence marker.

Both are fenced inside explicit delimiter blocks, and retrieved text additionally passes
through `neutralise_fences()`, which strips the marker strings by name and collapses any
run of three or more angle brackets — so a document cannot forge or close a fence.

Because instructing a small model not to disclose its prompt demonstrably does not hold,
the final check is made in code: `discloses_prompt()` inspects the generated answer and
withholds it if it recites the system prompt or imitates the fence shape. This closes
*disclosure*. It cannot stop a poisoned document from influencing answer *content*, which
is inherent to retrieval augmentation and is recorded as a known limitation.

Other boundaries: uploads are stored under generated UUIDs and never under the
user-supplied name; every SQL statement is parameterised; ingestion error messages are
sanitised by `_safe_error_message()` before being stored, because the frontend renders
them verbatim.

---

## 5. Major decisions and why

| # | Decision | Rationale | What it cost |
|---|---|---|---|
| **D1** | Everything runs locally — Ollama, sentence-transformers, ChromaDB, Tesseract | Zero cost and complete data privacy; no document leaves the machine | Cannot be hosted on a free tier; speed is bounded by the user's hardware |
| **D2** | ChromaDB over FAISS/pgvector | Persists to a directory with no server to run, and carries metadata alongside vectors, which the citation path needs | Less tuning available at scale |
| **D3** | SQLite for metadata, ChromaDB for vectors | Status, page counts and error messages are relational and are queried on every list request; keeping them out of the vector store keeps both jobs simple | Two stores to keep consistent on delete |
| **D4** | Ingestion in a FastAPI **background task**, upload returns `202` | OCR is 1–3 s/page; holding the request open would time out the browser on a scanned document | The client must poll for `processing → ready` |
| **D5** | Handlers declared `def`, not `async def` | Everything they do is blocking. As coroutines they ran **on** the event loop: one 92 s question froze every other request for its full duration. Declared `def`, FastAPI runs them in its threadpool | Nothing — no body was awaiting anything |
| **D6** | Configuration validated at **import** time | A typo previously produced a backend that started cleanly, reported `/api/health: ok`, and then failed at use time three libraries deep. Failing at startup names the variable and the file | Import-time side effects, which tests must work around by reloading the module |
| **D7** | `OLLAMA_BASE_URL` defaults to `127.0.0.1`, not `localhost` | On Windows `localhost` resolves to `::1` first and Ollama binds IPv4 only, so every connection waited ~2 s for the refusal — 2065 ms vs 8.3 ms, paid on every question | The default is less portable if Ollama is remote; documented in `.env.example` |
| **D8** | Chunker separators omit a bare `"\n"` | PyMuPDF emits one `\n` per visual line, which made the split unit a *line*. Lines longer than `CHUNK_OVERLAP` can never be carried across, so dense pages produced **zero** overlap — 18/18 adjacent pairs measured. Dropping `"\n"` makes the unit a word | Paragraph structure is still honoured first; only the split point changes, never the characters |
| **D9** | Upload body read in bounded 1 MB chunks | Reading first and checking the size afterwards allocated the full body before declining: a rejected 400 MB post still cost 401.7 MB of memory — twenty times the app's own stated limit | Slightly more code than `await file.read()` |
| **D10** | Refusal detection is fuzzy, but only over the answer's **opening** | Small models paraphrase the refusal. But markers like "does not provide" also appear as a *hedge* at the end of a genuine answer, which stripped the citations off a correct three-page summary. A refusal leads; a hedge trails | A refusal stated only in the middle of a long answer would be missed |
| **D11** | Citation page numbers capped at 6 digits | `answer` is untrusted model output, and Python refuses `int()` on decimal strings over 4300 digits. An unguarded `int()` turned a successful answer into an HTTP 500 | A genuine 7-digit page reference would be dropped — no real document has one |
| **D12** | Test fixture PDFs committed, not generated | `test_retriever.py` asserts measured similarity thresholds against their exact bytes; regenerating with a different PyMuPDF version can shift glyph layout, hence text, hence embeddings, hence those scores | 157 KB in the repository |
| **D13** | The model call sits behind one interface (`llm_service.call_ollama`) | If the zero-cost/privacy constraint ever changes, swapping to a hosted API is one module and one environment variable | — |

Decisions D5, D7, D8, D9, D11 were each made *after* reproducing a measured failure. The
measurements are in [`POSTCODING_DAY_01_VERIFICATION.md`](POSTCODING_DAY_01_VERIFICATION.md)
and [`POSTCODING_DAY_02_HARDENING.md`](POSTCODING_DAY_02_HARDENING.md).

---

## 6. Degradation behaviour

The system is built to degrade rather than crash when a dependency is missing:

| Missing | Behaviour |
|---|---|
| **Tesseract** | `/api/health` reports `ocr_available: false`; scanned pages are skipped; native PDFs unaffected |
| **Ollama** | `POST /api/chat/ask` returns **503** with an actionable message ("make sure Ollama is running"), never a 500 |
| **ChromaDB** | `query_chunks()` logs and returns the empty result shape; the question is answered "not found" |
| **Embedding model** | `retrieve()` logs and returns `[]`; same path as above |
| **Empty vector store** | Short-circuits to the "not found" answer **without calling the LLM** — spending 10+ s for the model to say so would be slower and less reliable |

This is why `retrieve()` never raises: an empty store, an embedding failure and a ChromaDB
error all arrive at the caller as `[]`, and the caller has exactly one path to handle.

---

## 7. What the frontend owns

| Piece | Responsibility |
|---|---|
| `services/api.js` | The single axios client. **Per-request timeouts**, not one global: 30 s for documents/health, 120 s for upload, 360 s for `/chat/ask` |
| `hooks/useChat.js` | Session conversation state. A failed turn becomes a real entry in the history carrying its error and the question that produced it, so it can be rendered under the question and offered a Retry |
| `pages/DocumentsPage.jsx` | Upload, polling for `processing → ready`, delete with optimistic rollback, and an `initialLoadFailed` state so a failed load never claims the library is empty |
| `components/` | 9 presentational components; `CitationCard` carries the OCR badge and the "match strength" bar |

The `/chat/ask` timeout (360 s) is deliberately **longer** than the backend's
`OLLAMA_TIMEOUT_SECONDS` (300 s). The backend's clock starts only once retrieval is done,
so a backend request that gives up takes slightly over 300 s end to end. If the browser
aborted at exactly 300 s it would win the race and the user would see a bare "could not
reach the backend" instead of the backend's actionable 503. Losing that race is the point.

Conversation history is per-session and in-memory: refreshing clears it.

---

## 8. Known architectural constraints

* **Single process, single user.** No task queue, no worker pool. Ingestion runs in
  FastAPI's background tasks and generation in its threadpool; two simultaneous questions
  contend for one Ollama instance.
* **Two stores to keep consistent.** Deleting a document must remove the PDF, the SQLite
  row and the ChromaDB vectors. Deletion *during* ingestion is handled explicitly:
  Windows locks the file while PyMuPDF holds it open, so the handler removes the row and
  the vectors and leaves the file to the ingestion task, which checks whether its document
  still exists before storing anything and cleans up if not.
* **Header/footer stripping is more aggressive than specified** — it considers every line
  on a page, not only lines at page boundaries. Guarded so it can never empty a page.
  Documented deviation, not a bug; see the README's Known limitations.
* **No authentication, authorisation or HTTPS**, by design, bound to `127.0.0.1`. All
  three become mandatory if the deployment model changes.
