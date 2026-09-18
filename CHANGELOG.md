# Changelog

All notable changes to this project are recorded here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **On version numbers.** `backend/app/__init__.py` holds `__version__` and is the single
> source for the backend; `frontend/package.json` keeps its own copy because npm owns that
> file's format. Both are reconciled here at release time, and `/api/health` reports the
> backend value so a partial bump is visible rather than silent.

---

## [1.1.0] — 2026-09-18

Completion release. No new user-facing feature: this closes the verification,
security and documentation gaps a full project audit found, and makes the test
suite reproducible on a machine other than the one that wrote it.

### Added

- **`tests/conftest.py`** — the suite now builds its own corpus from the committed
  fixture PDFs in throwaway directories. It reads and writes no real user data, and
  nothing has to be uploaded before it will pass.
- **`tests/test_ingestion_pipeline.py`** — seven end-to-end ingestion tests covering
  outcomes spec §19.2 and §32 require and nothing asserted: a scanned PDF reaching
  `ready` with `ocr_pages_count > 0`, per-page method tagging on a mixed document, a
  document with no text by either method reaching `failed` with a sanitised message,
  a 15+ page document, and the repeated-header document whose stripping guard exists
  to stop a page being emptied.
- **`scripts/health-monitor.ps1`** — scheduled health polling that alerts on
  `degraded`, unreachable, or unusually slow, writing one JSON line per check.
  Closes the alerting half of the monitoring stage.
- **`frontend/public/favicon.ico`** — listed in spec §14 and never created.
- **`docs/ui-verification/`** — 24 captures, eight UI states at 375 / 768 / 1280 px,
  produced by `.day6/ui_state_matrix.py` alongside measured overflow and console
  checks.
- **`.day6/`** — the harnesses behind every number in this release: functional probe,
  UI state matrix, throughput and memory measurement, and the dependency audit output.

### Changed

- **Version is read from one place.** `app.__version__` now feeds the FastAPI app and
  `/api/health`; previously the string was written out three times and a test asserted
  it as a literal, so a partial bump would still have passed.
- **`react-router-dom` 6 → 7.18.4 and `vite` 5 → 8.3.0** (with `@vitejs/plugin-react`
  4 → 6). `npm audit` goes from 4 vulnerabilities (1 high, 3 moderate) to **0**.
- **Documentation reconciled with the code.** The README no longer states that
  monitoring was not done, documents all 20 environment variables rather than 17,
  reports the real test count, and carries the measured throughput and memory numbers.
  `docs/API_REFERENCE.md` documents the health response the server actually returns
  and both behaviours of `GET /`.
- **`.day2` harnesses derive their paths from the checkout** instead of hard-coding
  absolute paths from one machine, so the published evidence can be re-run.

### Fixed

- **The test suite depended on the developer's live ChromaDB store.**
  `test_retriever.py` asserted the store held exactly five chunks, so uploading a
  fourth document through the application turned the suite red; `test_api.py`'s answer
  test failed on a fresh clone. Both now use the isolated fixture corpus.

### Security

- **The Python dependency CVE audit was run for the first time.** `pip-audit` reports
  nine advisories against two transitive packages. Each was traced to the code path it
  requires and none is reachable: all four `chromadb` advisories are ChromaDB **server**
  vulnerabilities and this project embeds `PersistentClient` with no server, and the
  `transformers` advisories need `Trainer`, `save_pretrained` or model paths the app
  never calls. Six of the nine have no published fix at any version. Full reasoning in
  the README's Security section.
- **`EMBEDDING_MODEL` documented as security-relevant.** It is the one setting that can
  cause code execution, because loading a model runs the `transformers` loader against
  that repository's config (PYSEC-2026-2289, unfixed below a major version this stack
  cannot take). Noted in `.env.example` and the README.

### Known limitations

Unchanged from 1.0.0 except where listed above. Monitoring now has alerting but still
has no metrics dashboard or time-series store, which is a deliberate trade-off for a
single-user loopback service and is recorded as such.

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
- 167 tests across 10 modules, with 8 committed fixture PDFs, requiring no running
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
- `/docs`, `/redoc` and `/openapi.json` are open **in development**. They are not
  mounted when `APP_ENV=production`, which is how the release runs.
- Backend Python dependencies have not been audited against a CVE database; no such
  tool was available. Versions are pinned and reconciled, so reproducibility holds,
  but the vulnerability check is genuinely unmet rather than passed.
  *(Closed in 1.1.0.)*
- Four npm advisories remain open — three are dev-server only and do not affect
  `vite build` output; the react-router ones are unreachable in this application.
  Every fix is a breaking major upgrade. *(Closed in 1.1.0.)*
- Answer latency is dominated by local generation: a warm answer takes a median of
  51.2 s on the recorded hardware. Retrieval is a flat 36.3 ms of that.
- `test_retriever.py` asserts measured similarity thresholds and needs its
  three-document corpus present in ChromaDB. On a fresh clone those tests fail with
  a message naming exactly what to upload.

[1.0.0]: https://github.com/niyatikadia/Rag-PDF-QA-Bot/releases/tag/v1.0.0
