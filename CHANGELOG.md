# Changelog

All notable changes to this project are recorded here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] — 2026-09-15

First release. Local, zero-cost retrieval-augmented question answering over
user-uploaded PDFs, with file-and-page citations and automatic OCR fallback for
scanned documents.

Everything runs on the user's own machine: the language model (Ollama), the
embedding model (sentence-transformers), the vector store (ChromaDB), the document
store (SQLite) and the OCR engine (Tesseract). There are no API keys, no external
services and no per-request cost, and no document leaves the machine.

### Added

**Ingestion**

- PDF upload with server-side validation of extension, MIME type and size, and a
  matching client-side check before the request is sent.
- Text extraction from multi-page PDFs via PyMuPDF.
- OCR fallback: a page yielding under 10 characters of native text is rendered at
  300 DPI and read with Tesseract, so scans are processed rather than rejected.
  The extraction method is recorded per chunk and surfaced in the UI as a badge.
- Text cleaning — unicode normalisation, control-character removal, whitespace
  collapsing and running header/footer stripping, with a guard that stripping can
  never empty a page.
- Chunking at 500 characters with 100 characters of overlap, split per page so a
  chunk never spans a page boundary and page-level citation stays possible.
- Asynchronous processing: upload returns `202` and ingestion continues in a
  background task, with status polled by the client.

**Retrieval and generation**

- 384-dimensional embeddings from `all-MiniLM-L6-v2`, loaded once as a module
  singleton and used for both documents and queries.
- Vector storage in ChromaDB (cosine space) with document, page, chunk and
  extraction-method metadata.
- Top-5 semantic retrieval with distance-to-score conversion and ranking kept out
  of the store, as a pure and testable function.
- Context assembly with per-excerpt source labels inside a token budget.
- Grounded answer generation through Ollama, restricted to the retrieved context,
  with an exact sanctioned refusal sentence so the model can always decline.
- Citation extraction limited to chunks that fit inside the context budget, so a
  chunk the model was never shown cannot be cited.

**API**

- Six REST endpoints across three routers — upload, list, get, delete, ask and
  health — with correct status codes and error cases documented in
  `docs/API_REFERENCE.md`.
- Health check reporting Ollama, ChromaDB, the embedding model and the OCR engine.
- An unreachable Ollama returns `503`, not `500`: a stopped dependency tells the
  user to start it rather than to file a bug.

**Interface**

- React chat interface with per-session conversation history, retry on a failed
  turn, and a loading indicator that escalates its message at 0, 4, 12, 30 and 75
  seconds with an elapsed timer.
- Citation cards showing filename, page numbers, match strength and an OCR badge.
- Document management — list, status, page and OCR counts, and delete that removes
  the file, the row and the vectors together.
- Responsive down to 375 px with no horizontal overflow; WCAG AA contrast verified
  on all pages.

**Configuration, tests and documentation**

- Central configuration module: every setting read once from the environment with
  typed defaults and validated ranges, failing at startup with the variable name
  rather than at the point of use.
- `.env.example` documenting every variable, its default and its minimum.
- 146 tests across 9 modules, with 8 committed fixture PDFs, requiring no running
  Ollama and making no real Tesseract call.
- README, architecture notes, API reference, configuration reference, one record
  per build day, and the post-coding verification, hardening and consolidation
  records.

### Fixed

These defects were found and fixed during pre-release verification and hardening.
They never reached a released version; they are listed because the evidence behind
each one is part of the repository, in `docs/POSTCODING_DAY_0*.md`.

- **Ollama connection latency** — `OLLAMA_BASE_URL` defaulted to `localhost`, which
  resolves `::1` first on Windows while Ollama listens on IPv4 only. Every call paid
  a measured 2,047 ms connection refusal first. Defaulting to `127.0.0.1` took the
  endpoint from 2,123 ms to 81.6 ms p50.
- **Server-wide blocking** — request handlers declared `async def` while doing
  blocking work ran on the event loop, so one question froze every other request for
  its full duration, measured at 92 s. Declared `def`, they run in a threadpool;
  3,275 concurrent reads during a 96.8 s question now complete unblocked.
- **Unbounded upload allocation** — a rejected oversized upload still allocated its
  full size before validation; a 400 MB body cost 401.7 MB of process memory.
  Metadata is now validated before the body is read, and the body is read in bounded
  1 MB chunks: the same request costs 59.1 MB.
- **Unhandled model output** — an unbounded integer literal in generated text raised
  `ValueError` during page-number parsing, returning `500` and discarding an
  otherwise correct answer. Page numbers are now length-bounded before `int()`.
- **Prompt-injection disclosure** — a direct request could make the model recite the
  system prompt verbatim, and a poisoned PDF could hijack answers and leak the fence
  markers. Fence markers inside retrieved text are neutralised, and an output-side
  guard replaces a disclosing answer with the refusal sentence.
- **Colour contrast** — nine element classes failed WCAG AA, the keyboard hint worst
  at 2.54:1 against its background. Corrected to gray-500; zero failures across all
  three pages.
- **False empty-library claim** — a failed document load rendered "(0) — No documents
  yet", asserting as fact something the page did not know. It now reports that the
  list could not be loaded and withholds the count.
- **Unvalidated configuration ranges** — settings were coerced for type but not
  range, so a typo produced a server that reported healthy and failed later at the
  point of use. Integer settings now carry range floors, with a cross-field check
  that `CHUNK_OVERLAP` is less than `CHUNK_SIZE`.
- **Path disclosure in ingestion errors** — the server filesystem path and the
  internal document id reached the browser in an error message. Errors are sanitised
  before storage.

### Known limitations

Carried into this release deliberately, with the reasoning recorded in
`docs/POSTCODING_DAY_02_HARDENING.md` §9 and the README.

- No authentication, authorisation or HTTPS. The service is single-user and binds to
  `127.0.0.1`. All three become mandatory if the deployment model changes.
- `/docs`, `/redoc` and `/openapi.json` are open, which is correct for a local-only
  API and must be disabled if the service is ever exposed.
- Backend Python dependencies have not been audited against a CVE database; no such
  tool was available. Versions are pinned and reconciled, so reproducibility holds,
  but the vulnerability check is genuinely unmet rather than passed.
- Six npm advisories remain open — four are dev-server only and do not affect
  `vite build` output; two are unreachable in this application. Every fix is a
  breaking major upgrade.
- Answer latency is dominated by local generation: a warm answer takes a median of
  51.2 s on the recorded hardware. Retrieval is a flat 36.3 ms of that.
- `test_retriever.py` asserts measured similarity thresholds and needs its
  three-document corpus present in ChromaDB. On a fresh clone those tests fail with
  a message naming exactly what to upload.

[1.0.0]: https://github.com/niyatikadia/Rag-PDF-QA-Bot/releases/tag/v1.0.0
