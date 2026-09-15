# SESSION_04_INGESTION_COMPLETE.md — Day 3: Chunking, Embeddings, Vector Storage & OCR Integration

**Date:** 2026-09-08
**Phase:** Phase 3 (Session 4) — Part 2
**Session Goal:** Complete the full ingestion pipeline from PDF to vectors in ChromaDB,
with OCR fallback fully wired in.

---

## ✅ What Was Done This Session

### 1. Resolved the Day 2 known gap — sentence-transformers
- `pip install -r requirements.txt` failed outright: `Pillow==10.3.0` has no
  prebuilt wheel for Python 3.13 and its sdist build errors
  (`KeyError: '__version__'` in `setup.py`) — this aborted the whole
  transaction, so nothing after it in `requirements.txt` installed either.
- Confirmed Pillow was already present (12.3.0, pulled in earlier by
  `pytesseract`) and works fine, so the fix was to install
  `sentence-transformers==3.0.1` directly rather than editing the pin — its own
  dependencies (torch, transformers, huggingface-hub) were already present
  from a prior environment state.
- Verified in isolation before touching `embedder.py`: loaded
  `all-MiniLM-L6-v2` and confirmed 384-dim output.
- **Note for later:** `requirements.txt`'s `Pillow==10.3.0` pin is stale for
  this Python version. Not changed this session (out of scope), but a fresh
  `pip install -r requirements.txt` on a new machine with Python 3.13 will
  hit the same build failure. Worth bumping the pin in a later cleanup pass.

### 2. `chunker.py` — implemented
- `chunk_pages()` now uses `langchain_text_splitters.RecursiveCharacterTextSplitter`
  with `CHUNK_SIZE=500` / `CHUNK_OVERLAP=100` (from `.env`/`config.py`).
- Each chunk carries `document_id`, `filename`, `page_number`, `chunk_index`
  (index resets per page), `extraction_method`.

### 3. `embedder.py` — verified, no code changes needed
- Was already fully implemented on a prior day; only the missing dependency
  blocked it. `get_embedder()` / `embed_texts()` / `embed_query()` all work
  now that `sentence-transformers` is installed.

### 4. `vector_store.py` — `add_chunks()` implemented
- Encodes chunk texts via the passed-in `SentenceTransformer` instance,
  builds IDs as `{document_id}_{page_number}_{chunk_index}`, stores in the
  `pdf_chunks` ChromaDB collection with full metadata.
- `query_chunks()` intentionally left as a stub — that's Day 4 (retriever)
  scope per spec, not touched this session.

### 5. OCR fallback wired into `pdf_processor.py`
- `extract_text_from_pdf()` now opens the PDF once and, for any page whose
  native text is below `MIN_CHARS_FOR_NATIVE_TEXT` (10 chars), calls
  `ocr_processor.ocr_page()` directly on that page object (no second file
  open needed — reuses the already-open PyMuPDF page).
- If OCR recovers usable text, the page's `extraction_method` becomes
  `"ocr"` and it counts toward `ocr_pages_count`; if OCR also returns
  nothing, the page is left with its (empty) native text and gets filtered
  out later by `clean_pages()`, same as before.
- `process_document()` now runs the complete pipeline: extract (+ OCR
  fallback) → clean → chunk → embed → store in ChromaDB → update SQLite with
  `status="ready"`, `total_pages`, `total_chunks`, `ocr_pages_count`.
- Per spec §5.4: a document is marked `failed` only if **every** page
  produces zero usable text from both native extraction and OCR combined
  (unchanged logic — `clean_pages()` returning empty triggers this).

### 6. Bug found and fixed: chunk metadata used the wrong filename
- `pdf_processor.py` was calling `chunk_pages(cleaned, document_id, pdf_path.name)`,
  where `pdf_path` is the UUID-based storage path
  (`data/uploads/{document_id}.pdf`) — so every chunk's `filename` metadata
  was a UUID, not the name the user uploaded (e.g. `report.pdf`). This would
  have silently broken citations in Day 5 (`[Source: 8848dcca-....pdf, Page 3]`
  instead of `[Source: report.pdf, Page 3]`).
- Fixed by looking up the original filename from SQLite
  (`db.get_document(document_id)["filename"]`) before chunking, with a
  fallback to `pdf_path.name` if the row is somehow missing. Verified by
  inspecting ChromaDB metadata directly after the fix — filenames are now
  correct (see Testing section).

### 7. Unit tests written (all real, no more `pytest.skip`)
- **`test_chunker.py`** (3 new + 1 existing): chunk size ≤ `CHUNK_SIZE`,
  adjacent chunks overlap (checked via longest matching suffix/prefix rather
  than an exact-length slice, since the splitter breaks on word boundaries
  near the target overlap, not at an exact character count), metadata
  fields all present and correct, empty input → empty output.
- **`test_embedder.py`** (4 tests, real model calls): 384-dim output, same
  text → identical vector, batch encoding returns one vector per input,
  `embed_query` returns a flat `list[float]` (not nested).
- **`test_ocr_processor.py`** (1 new + 4 existing): added
  `test_ocr_page_returns_text_on_success` (mocks `is_ocr_available`,
  `PIL.Image.open`, and `pytesseract.image_to_string` — no real Tesseract
  call needed) and `test_ocr_page_returns_none_when_ocr_yields_empty_text`
  (whitespace-only OCR result → `None`, page stays textless rather than
  storing garbage).
- **Full suite: 27 passed, 4 skipped** (skips are `test_retriever.py`,
  explicitly Day 4 scope, untouched this session).

---

## 🧪 Testing Performed

### Automated
`pytest tests/ -v` → **27 passed, 4 skipped, 0 failed.**

### Manual end-to-end (live `uvicorn` server, via `curl`)
Generated three fresh test PDFs with PyMuPDF/Pillow:
- `native_single.pdf` — 1 page, native text.
- `native_multi.pdf` — 3 pages, native text, distinct topic per page
  (AI history / ChromaDB / Tesseract) for later retrieval testing.
- `scanned_image_only.pdf` — 1 page that is **only** a rendered PNG image
  (confirmed `page.get_text()` returns `""` before upload) containing the
  text "SCANNED DOCUMENT TEST PAGE ... Keyword for retrieval testing:
  PINEAPPLE OCR SUCCESS".

Uploaded all three via `POST /api/documents/upload`:

| File | Status | total_pages | total_chunks | ocr_pages_count |
|---|---|---|---|---|
| native_single.pdf | ready | 1 | 1 | 0 |
| native_multi.pdf | ready | 3 | 3 | 0 |
| scanned_image_only.pdf | **ready** | 1 | 1 | **1** |

Server log confirmed the OCR path fired: `Page 1 recovered via OCR (279 chars)`.

**ChromaDB inspection** (direct Python, `get_collection().get(...)`):
all 5 chunks present, `extraction_method` correctly tagged (`native` ×4,
`ocr` ×1), `filename` metadata correctly shows the original uploaded names
(`native_single.pdf`, `native_multi.pdf`, `scanned_image_only.pdf`) — not
UUIDs, confirming the filename-metadata fix above.

**Semantic search sanity check:** embedded the query "What was the keyword
in the scanned document?" and ran `collection.query(...)` — the OCR-derived
chunk came back as the top (lowest-distance) result, ahead of two native
chunks, confirming the OCR text is genuinely searchable, not just stored.

**Persistence across restart:** killed the `uvicorn` process (`taskkill`),
restarted it fresh, then confirmed via `GET /api/documents` that all 3 SQLite
records were intact and via direct ChromaDB inspection that the chunk count
was still 5 — nothing lost across restart (`chroma_db/` and
`pdf_chatbot.db` are both on-disk/persistent, as designed).

**Delete removes chunks:** `DELETE /api/documents/{scanned_doc_id}` →
`GET /api/documents` dropped to 2 records, and ChromaDB chunk count dropped
from 5 → 4, with the remaining 4 chunks' filenames confirming only the
scanned document's chunk was removed. Re-uploaded the scanned PDF afterward
so all 3 sample documents are present for the next session to pick up from.

**Health check:** `GET /api/health` → `{"status":"ok", "ollama_available":
true, "chroma_available": true, "embedding_model_loaded": true,
"ocr_available": true}` — all four services green.

---

## 📋 Decisions Made This Session

- **OCR runs inline during the single PyMuPDF page loop**, not as a separate
  pass that reopens the file — `extract_text_from_pdf()` already has the
  `fitz.Page` object in hand when it detects low native-text, so it calls
  `ocr_page(page)` directly. Simpler than the alternative (collect flagged
  page numbers, reopen the doc, re-render), and avoids opening the PDF twice
  per upload.
- **`chunk_index` resets per page**, matching the Day 1 scaffold's stub
  comment and the ChromaDB ID scheme (`{document_id}_{page_number}_{chunk_index}`)
  — a global chunk_index wasn't needed since the ID is already unique via
  the page_number/chunk_index pair.
- **Overlap test uses longest-matching-suffix/prefix, not an exact
  `CHUNK_OVERLAP`-length slice** — `RecursiveCharacterTextSplitter` breaks
  on word/paragraph boundaries near the target overlap, not at an exact
  character offset, so asserting an exact 100-char match would be testing
  LangChain's internals rather than the actual guarantee (that consecutive
  chunks share content).
- **Chunk metadata `filename` is looked up from SQLite by `document_id`**,
  not derived from the file path — this is the fix described above; keeping
  the lookup in `pdf_processor.py` (rather than changing `documents.py`'s
  call signature) meant no changes to the router or its background-task
  wiring.
- **`vector_store.query_chunks()` left as a stub.** Explicitly Day 4 scope
  (`retriever.py` orchestrates it) — implementing it now would be scope
  creep ahead of the day it's actually needed, and `test_retriever.py`'s
  skips already reflect that boundary.

---

## ⚠️ Known follow-ups (not blocking, not done this session)

- **`requirements.txt`'s `Pillow==10.3.0` pin doesn't build on Python 3.13.**
  Worked around by installing `sentence-transformers` directly (Pillow
  12.3.0 was already present and compatible). A future session should bump
  the Pillow pin so `pip install -r requirements.txt` works cleanly on a
  fresh machine — flagging rather than fixing now since it's outside today's
  scope and the running environment isn't affected.
- **`requirements.txt`'s `chromadb==0.5.3` pin is also stale** — the
  installed version is `1.5.9` (pre-existing from an earlier session, not
  changed today). Both this and the Pillow pin are candidates for a
  dependency-pin cleanup pass, likely Day 10 (Phase 7 docs/cleanup) rather
  than blocking Day 4.

---

## 🚀 What Day 4 Starts With

Per Section 27 / `PROJECT_STEPS.md`, Day 4 is **Phase 4 part 1 — `retriever.py`**:
1. Query embedding via `embedder.embed_query()` (already implemented and
   tested this session — Day 4 just calls it).
2. Implement `vector_store.query_chunks()` (currently a stub) — top-k
   ChromaDB search via `collection.query()`.
3. `retriever.py` — orchestrate query → embed → search → ranked results,
   with optional `document_id` filtering.
4. Unit tests for `retriever.py` — `test_retriever.py` already has 4 tests
   scaffolded with `pytest.skip()`, ready to be filled in against the 3
   sample documents already ingested and persisted in ChromaDB
   (`native_single.pdf`, `native_multi.pdf` with 3 distinct-topic pages,
   `scanned_image_only.pdf` with its OCR'd "PINEAPPLE OCR SUCCESS" chunk) —
   no need to re-ingest test data from scratch.

**Completion criteria (Day 3 — met):** End-to-end ingestion works for 3+
PDFs, including one scanned/image-only PDF that now reaches `status: "ready"`
via OCR instead of `"failed"`. Persistence across restart confirmed. Delete
removes chunks. All unit tests pass (27 passed, 4 skipped — skips are
explicitly Day 4 scope).

---

*End of SESSION_04_INGESTION_COMPLETE.md — Day 3 complete, awaiting approval
to start Day 4.*
