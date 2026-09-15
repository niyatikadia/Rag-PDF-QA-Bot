# Configuration Reference

**Audience:** whoever runs or deploys this.
**Source of truth:** `backend/app/config.py` reads every variable listed here, and
`backend/.env.example` documents each one inline and is a working configuration as-is.

Written on post-coding Day 3. The variable set below was diffed both ways against
`config.py` on Day 2 — **17 variables read by the code, 17 documented, sets identical**.

---

## How configuration is loaded

`config.py` is imported by every other backend module and is the **only** module that
calls `os.getenv`. `python-dotenv` loads `backend/.env` at import; anything already in the
real environment wins over the file.

Two things happen at import time, deliberately:

1. **Every numeric variable is type- and range-checked.** A value that is not a whole
   number, or is below its minimum, raises `ConfigurationError` and the process stops
   during startup with a message naming the variable and the file to edit.
2. **Data directories are created.** `UPLOAD_DIR`, `CHROMA_PERSIST_DIR` and the database's
   parent directory are created if absent, so a fresh clone needs no manual setup.

### Why validation is at startup and not at use time

Before this was added, a typo produced a backend that started cleanly and reported
`/api/health: ok`, then failed later — and never said which variable was wrong:

| Misconfiguration | What actually happened |
|---|---|
| `CHUNK_OVERLAP >= CHUNK_SIZE` | Every upload reached `failed` with an error raised three layers deep inside `langchain_text_splitters` |
| `TOP_K_RESULTS <= 0` | Retrieval silently returned zero hits, so every question answered "not found" with nothing to explain why |
| `MAX_FILE_SIZE_MB = 0` | Every non-empty upload was rejected as oversized |
| `OCR_DPI = 0` | Page rendering failed inside MuPDF and OCR silently turned itself off |

All four now fail immediately, by name. 17 tests in
`backend/tests/test_config_validation.py` guard this.

### Relative paths

The three path variables default to `./data/...` and are resolved **from the directory you
run uvicorn in**, which is `backend/`. Running the server from elsewhere with the default
values will create a new, empty `data/` there.

### Secrets

There are none, and there never will be: the project uses no paid services and no external
APIs. `.env` is git-ignored regardless — the habit is what protects the next project that
*does* have secrets. `.env.example` is committed and contains no real values.

---

## The 17 variables

### LLM (Ollama)

| Variable | Default (`config.py`) | `.env.example` | Min | Controls |
|---|---|---|---|---|
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | same | — | Where Ollama is listening |
| `OLLAMA_MODEL` | `llama3.1:8b` | **`llama3.2:latest`** | — | The generation model |
| `OLLAMA_TIMEOUT_SECONDS` | `300` | same | 1 | Seconds to wait for a generation before returning 503 |

**`OLLAMA_BASE_URL` uses the literal IPv4 address on purpose.** On Windows `localhost`
resolves to `::1` before `127.0.0.1`, and Ollama binds IPv4 only, so every new connection
waited for the IPv6 refusal before falling back — measured at **2065 ms via `localhost`
against 8.3 ms via `127.0.0.1`**, paid on every health check and every question. Point it
at a hostname only if Ollama runs on another machine.

**`OLLAMA_MODEL` differs between the two files, deliberately.** `config.py` falls back to
`llama3.1:8b`, the specified model (spec §6.1); `.env.example` sets `llama3.2:latest`,
the model the completeness checklist was actually verified against on an 8 GB machine.
**Do not "fix" this divergence** — it is documented in both files and in the upload
schedule. Pick by RAM:

| RAM | Value | Behaviour |
|---|---|---|
| ≥16 GB | `llama3.1:8b` | Best answer quality; stronger against prompt injection |
| ~8 GB | `llama3.2:latest` | 2.0 GB. Answers in 30–75 s. On 7.89 GB of RAM `llama3.1:8b` occupies 5.6 GB and two questions in three exceeded the 300 s timeout |

**`OLLAMA_TIMEOUT_SECONDS` is generous on purpose** — the first request after
`ollama serve` starts also pays for loading the model, ~117 s for `llama3.1:8b` on the
development machine. Note this bounds **socket inactivity**, not total elapsed time.

### Embeddings

| Variable | Default | Min | Controls |
|---|---|---|---|
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | — | sentence-transformers model; 384-dim, ~80 MB, CPU-only |

Downloaded from Hugging Face on first use and cached. **Changing this invalidates every
vector already in ChromaDB** — the stored embeddings were produced by the old model and
are not comparable. Re-upload your documents if you change it.

### Storage

| Variable | Default | Min | Controls |
|---|---|---|---|
| `CHROMA_PERSIST_DIR` | `./data/chroma_db` | — | ChromaDB's persistent directory |
| `UPLOAD_DIR` | `./data/uploads` | — | Where uploaded PDFs are stored, named by generated UUID |
| `DATABASE_PATH` | `./data/pdf_chatbot.db` | — | SQLite file holding the `documents` table |
| `MAX_FILE_SIZE_MB` | `20` | **1** | Largest PDF accepted per file |

`MAX_FILE_SIZE_MB` is enforced server-side on **bytes actually received**, read in 1 MB
chunks — `Content-Length` is deliberately not trusted, because the client supplies it. The
frontend mirrors the limit so oversized files are rejected before upload, but that is a
convenience, never the control.

> All three directories hold state that must survive a restart. On an ephemeral filesystem
> (most container platforms) uploaded PDFs, the vector store and the database are silently
> deleted when the container restarts.

### Chunking

| Variable | Default | Min | Controls |
|---|---|---|---|
| `CHUNK_SIZE` | `500` | **1** | Characters per chunk |
| `CHUNK_OVERLAP` | `100` | **0** | Characters shared between consecutive chunks |

**Cross-field rule: `CHUNK_OVERLAP` must be strictly smaller than `CHUNK_SIZE`.** Chunks
cannot overlap by more than their own length, and the text splitter refuses to be
constructed otherwise — which used to surface as a failed document during ingestion rather
than a configuration error at startup.

500/100 balances retrieval precision against keeping enough surrounding context for an
answer to make sense. Changing either only affects **newly ingested** documents; existing
chunks keep the size they were created with.

### Retrieval and context

| Variable | Default | Min | Controls |
|---|---|---|---|
| `TOP_K_RESULTS` | `5` | **1** | How many chunks retrieval returns per question |
| `MAX_CONTEXT_TOKENS` | `2500` | **1** | Ceiling on the assembled context handed to the model |

`MAX_CONTEXT_TOKENS` is converted internally to a character budget at ~4 characters per
token. A real tokenizer would add a dependency for a limit that is a safety net, not a
precise contract. Chunks are added best-first, so spending the budget always drops the
*least* relevant ones — and citations are extracted only from the chunks that fit, so a
chunk the model never saw can never be cited.

Raising `TOP_K_RESULTS` without raising `MAX_CONTEXT_TOKENS` does little: the extra chunks
are retrieved and then dropped by the budget.

### Frontend / CORS

| Variable | Default | Min | Controls |
|---|---|---|---|
| `FRONTEND_ORIGIN` | `http://localhost:5173` | — | The **only** origin CORS allows |

A single specific origin, never `*`. `allow_credentials=True` is set, and `*` with
credentials is exactly the combination that must never ship. Change this if you serve the
frontend from another port or host.

### OCR (Tesseract)

| Variable | Default | Min | Controls |
|---|---|---|---|
| `OCR_ENABLED` | `true` | — | Master switch for the OCR fallback |
| `OCR_LANGUAGE` | `eng` | — | Tesseract language pack |
| `OCR_DPI` | `300` | **72** | Resolution used when rendering a page for OCR |
| `TESSERACT_CMD_PATH` | *(empty)* | — | Explicit path to the binary if it is not on PATH |

`OCR_ENABLED` is parsed as `os.getenv("OCR_ENABLED", "true").lower() == "true"` — so any
value other than the literal string `true` (case-insensitive) disables it. `false`, `0`,
`no` and a typo all disable OCR equally.

**`OCR_DPI`'s minimum of 72 is not arbitrary:** 72 is PDF user-space DPI, the 1:1 render.
Anything below it asks MuPDF for a sub-pixel pixmap, which fails inside the renderer
("Invalid bandwriter header dimensions") and makes every page's OCR return nothing — OCR
turning itself off with only a log line to show for it. Higher is more accurate and
slower; 300 is the usual scanning DPI.

**Leave `TESSERACT_CMD_PATH` empty if `tesseract --version` works in your terminal.** Set
it only if Tesseract is installed somewhere PATH does not cover, which is common on
Windows:

```
TESSERACT_CMD_PATH=C:\Program Files\Tesseract-OCR\tesseract.exe
```

If OCR is unavailable the app still runs: `/api/health` reports `ocr_available: false`,
scanned pages are skipped, and native PDFs are unaffected. `ocr_available` is deliberately
**not** part of the overall `status` field for this reason.

---

## System-level dependencies

These cannot be installed by pip or npm and are not in any dependency file.

| Dependency | Verified version | Required? | Notes |
|---|---|---|---|
| **Python** | 3.13.3 | Yes | The only version verified. README states 3.10+ as the floor because the code uses `X \| Y` syntax |
| **Node.js / npm** | 22.23.1 / 10.9.8 | Frontend only | Not needed to run the backend |
| **Ollama** | 0.34.0 | Yes | Must be running (`ollama serve`), with the model in `OLLAMA_MODEL` pulled |
| **Tesseract OCR** | 5.5.3.20260724 | **No** — degrades | `pytesseract` is only a wrapper; the binary is separate |
| Disk | ~5 GB free | Yes | Backend dependencies include PyTorch |
| RAM | 8 GB minimum | Yes | Determines which model is usable — see `OLLAMA_MODEL` |

### Platform traps

* **Windows long paths.** PyTorch ships headers with ~150-character relative paths and
  Windows caps a full path at 260 characters by default. If `pip install` fails part-way
  through unpacking torch with `OSError: [Errno 2] No such file or directory` and a hint
  about long-path support, the project directory is too deep — enable long paths or move
  the project somewhere shorter. This is a path-length problem, not a dependency problem.
* **Windows IPv6 resolution.** See `OLLAMA_BASE_URL` above.
* **Windows file locking.** A PDF cannot be deleted while PyMuPDF has it open, which is
  why deletion during ingestion is handled explicitly rather than assumed to succeed.
* **Line endings.** `.gitattributes` normalises text files to LF in the repository. The
  test fixture PDFs are marked `binary` so they are never newline-translated — their exact
  bytes are what `test_retriever.py`'s similarity thresholds are calibrated against.

---

## Verifying your configuration

```bash
# From backend/, with the venv active — a bad value fails here, by name.
python -c "import app.config; print('configuration OK')"

# All four dependencies, as the app sees them.
curl http://localhost:8000/api/health
```

A `status` of `degraded` with `ocr_available: false` is a working system without OCR. A
`degraded` caused by `ollama_available: false` means questions will return 503 until
Ollama is started.
