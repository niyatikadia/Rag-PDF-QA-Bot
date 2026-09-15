# SESSION_05_RETRIEVAL_COMPLETE.md — Day 4: Retrieval Service (`retriever.py`)

**Date:** 2026-09-08
**Phase:** Phase 4 (Session 5) — Part 1 of the RAG Query Pipeline
**Session Goal:** Given a question, return the most relevant chunks with correct
metadata — query embedding → top-k ChromaDB search → ranked results, with optional
`document_id` filtering and graceful empty-store handling.

---

## ✅ What Was Done This Session

### 1. `vector_store.query_chunks()` — implemented (was a Day 3 stub)
- Thin, honest wrapper over `collection.query()`. It returns ChromaDB's raw
  result shape (`{"ids", "documents", "metadatas", "distances"}`, each nested
  one level per query embedding) and deliberately does **no** scoring or
  ranking — that is the retriever's job, keeping the storage layer free of
  retrieval policy.
- Signature: `query_chunks(query_embedding, top_k=TOP_K_RESULTS, document_id=None)`.
  The default now comes from `config.TOP_K_RESULTS` (`.env`, currently 5) instead
  of the hardcoded `5` in the stub.
- `document_id` becomes a ChromaDB `where={"document_id": ...}` filter; `None`
  searches every document.
- Graceful paths, all returning the empty-but-correctly-shaped result rather
  than raising: empty/missing embedding, `top_k <= 0`, an empty collection
  (`col.count() == 0`, checked explicitly), and any ChromaDB exception (logged).
- Added a small `_empty_result()` helper so every one of those paths returns
  the identical shape — callers never have to special-case a failure.

### 2. `retriever.py` — implemented
- `retrieve(query, top_k=TOP_K_RESULTS, document_id=None) -> List[Dict]`
  orchestrates the full query path: validate → `embedder.embed_query()` →
  `vector_store.query_chunks()` → unpack → score → rank.
- Returns per chunk:
  `{"chunk_id", "text", "metadata", "score", "distance"}`.
  `metadata` is the full stored dict (`document_id`, `filename`, `page_number`,
  `chunk_index`, `extraction_method`) — everything Day 5's citation extractor
  needs is already there, no second lookup required.
- `distance_to_score()` is a separate, independently testable function:
  the `pdf_chunks` collection uses cosine space, so `score = 1 - distance`,
  clamped to `[0.0, 1.0]`.
- Results are **explicitly sorted** by score descending. ChromaDB already
  returns nearest-first, but ranking is this module's stated responsibility
  per spec §5.2, so it does not silently depend on that behaviour.
- Never raises: an empty/whitespace query, an embedding failure, an empty
  store, or a ChromaDB error all return `[]` (logged). Day 5's `chat.py` can
  therefore treat "no chunks" as a single, simple condition.

### 3. `test_retriever.py` — 4 `pytest.skip()` stubs replaced with 8 real tests
Run against the three documents Day 3 left persisted in ChromaDB — no
re-ingestion, as planned.

| Test | What it proves |
|---|---|
| `test_returns_top_k_results` | `top_k` honoured (1, 3); `top_k=99` caps at the 5 stored chunks instead of erroring; every result has the documented keys, a `0.0–1.0` score, and all 5 metadata fields |
| `test_relevance_ordering` | Scores are monotonically non-increasing; an AI-history query tops out on `native_multi.pdf` p1, a Tesseract query on p3 — i.e. ranking tracks topic, not insertion order |
| `test_unrelated_query_returns_low_scores` | An off-topic question still returns chunks (no silent filtering) but the top score falls below 0.30 and below the on-topic query's top score |
| `test_empty_store_returns_empty_list` | With `vector_store._collection` monkeypatched to an empty ephemeral collection, `retrieve()` returns `[]` and `query_chunks()` keeps its shape |
| `test_empty_query_returns_empty_list` | `""` and whitespace short-circuit before embedding |
| `test_document_id_filter` | Unfiltered, the scanned doc wins the question; filtered to `native_multi.pdf` exactly its 3 chunks return; filtered to the scanned doc exactly 1; an unknown id returns `[]` |
| `test_ocr_chunk_retrievable_with_correct_metadata` | The OCR'd chunk is semantically retrievable, contains "PINEAPPLE", and carries `extraction_method: "ocr"`, correct filename/page, and the expected `chunk_id` |
| `test_distance_to_score_conversion` | Clamping at both ends, including the tiny negative distance ChromaDB returns for an exact match |

---

## 🧪 Testing Performed

### Full suite
`pytest tests/ -v` → **35 passed, 0 skipped, 0 failed.**
(Day 3 ended at 27 passed / 4 skipped; the 4 skips were this session's stubs,
and 8 real tests replaced them.)

### Measured retrieval quality (fresh process, persisted store)

| Query | Top result | Score |
|---|---|---|
| "history of artificial intelligence research since the 1950s" | native_multi.pdf p1 | **0.769** |
| "What is Tesseract optical character recognition?" | native_multi.pdf p3 | **0.788** |
| "What is ChromaDB used for?" | native_multi.pdf p2 | 0.411 |
| "What was the keyword for retrieval testing in the scanned document?" | scanned_image_only.pdf p1 (**ocr**) | **0.602** |
| "How do I bake a chocolate chip cookie…" | scanned_image_only.pdf p1 | **0.064** |
| "What is the current stock price of Tesla in Japanese yen?" | scanned_image_only.pdf p1 | **0.073** |

Each of the three distinct-topic pages in `native_multi.pdf` is retrieved
first by its own topic query — retrieval is genuinely semantic, not returning
a fixed order. The relevant/unrelated gap (0.58–0.79 vs 0.06–0.08) is wide,
which is why the test thresholds (0.50 floor / 0.30 ceiling) sit safely inside
it and assert *separation* rather than exact model output.

### Other checks
- `import app.main` still succeeds — the new module-level import of
  `embed_query` in `retriever.py` costs nothing at startup, since the model
  itself still loads lazily inside `embedder.get_embedder()`.
- Retrieval verified from a cold Python process against the on-disk store —
  the Day 3 persistence guarantee holds for the query path too.

---

## 📋 Decisions Made This Session

- **Scoring lives in `retriever.py`, not `vector_store.py`.** `query_chunks()`
  returns raw ChromaDB distances; the retriever converts them. This keeps the
  storage layer swappable (a different vector DB with a different distance
  metric would only change one function) and made `distance_to_score()`
  unit-testable without touching a database.
- **Explicit re-sort by score even though ChromaDB returns nearest-first.**
  Spec §5.2 assigns ranking to the Retriever; relying on an undocumented
  ordering guarantee from a dependency is the kind of thing that breaks
  silently on a version bump. The sort is O(5 log 5).
- **Score is clamped to `[0.0, 1.0]`.** Cosine distance is in `[0, 2]`, so the
  raw `1 - distance` can go negative for opposed vectors, and floating-point
  error made an exact match return `-1.5e-06` (i.e. a score of 1.0000015).
  Clamping keeps `Citation.relevance_score` a clean 0-1 value for the UI.
- **Low-relevance chunks are returned, not filtered out.** No minimum-score
  cutoff was added. Deciding "the answer isn't in these documents" (F11) is
  the LLM's job in Day 5 with the grounded prompt; a threshold here would
  duplicate that decision in two places and could starve the LLM of context
  on a legitimately hard question. The score is surfaced so Day 5 *can* use it.
- **`retrieve()` never raises.** Every failure path returns `[]` and logs, so
  `chat.py` handles one condition instead of three exception types.
- **Empty-store test uses an ephemeral collection via `monkeypatch`**, not a
  wipe-and-restore of the real store — the Day 3 sample data stays intact and
  the test has no ordering dependency on the others.
- **The sample-data fixture `pytest.fail`s rather than skips** when the three
  Day 3 documents are missing. A skip would let a wiped store read as a green
  suite while retrieval is actually untested; the failure message says exactly
  what to re-upload.

---

## ⚠️ Known follow-ups (unchanged from Day 3, still not blocking)

- `requirements.txt` pins `Pillow==10.3.0`, which has no wheel and fails to
  build on Python 3.13 (installed: 12.3.0).
- `requirements.txt` pins `chromadb==0.5.3`; installed is `1.5.9`.

Both remain candidates for a dependency-pin cleanup in Day 10 (Phase 7).
Neither affects the running environment.

---

## 🚀 What Day 5 Starts With

Day 5 is **Phase 4 part 2** (`PROJECT_STEPS.md` step 6 / spec §27):

1. **Context constructor** — take `retrieve()`'s output (already ranked, already
   carrying full metadata) and build the prompt context string, each chunk
   prefixed `[Source: {filename}, Page {page_number}]`, with ` [OCR]` appended
   when `extraction_method == "ocr"` (spec §5.2). Cap total context at
   ~2000-3000 tokens.
2. **`llm_service.py`** — RAG prompt building (answer only from context,
   distinct delimiters for prompt-injection mitigation per §11), Ollama call
   to `llama3.1:8b` at `OLLAMA_BASE_URL`, response parsing.
3. **Citation extractor** — cross-reference the LLM response against the chunk
   metadata to produce `Citation` objects. The schema
   (`filename`, `pages`, `relevance_score`, `extraction_method`) maps directly
   onto what `retrieve()` already returns — `score` → `relevance_score`, and
   multiple chunks from the same file should be merged into one citation with a
   `pages` list.
4. **`POST /api/chat/ask`** — replace the placeholder in
   `app/routers/chat.py` (which still returns the "not yet implemented"
   message) with the real pipeline, honouring the optional `document_id` in
   `AskRequest` by passing it straight through to `retrieve()`.
5. **"Not found" handling (F11)** and **Ollama-down handling** — return a clear
   message rather than hallucinating / 500ing. Note `retrieve()` returning `[]`
   is already a clean single signal for "nothing to answer from".

Everything Day 5 needs from retrieval is done: `retrieve(question, top_k,
document_id)` returns ranked chunks with text, score, and full metadata, and
never raises.

**Completion criteria (Day 4 — met):** A question returns the most relevant
chunks with correct metadata. On-topic queries return the correct chunks
(0.60-0.79); unrelated queries return low scores (0.06-0.08); `document_id`
filtering restricts results to a single document; the empty store is handled
gracefully. All unit tests pass — **35 passed, 0 skipped**.

---

*End of SESSION_05_RETRIEVAL_COMPLETE.md — Day 4 complete, awaiting approval
to start Day 5.*
