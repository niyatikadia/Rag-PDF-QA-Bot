# API Reference

**Audience:** a consumer of this API.
**Base URL:** `http://localhost:8000` · **Prefix:** every application endpoint is under
`/api`. An interactive, always-current reference is served at `/docs` (Swagger) and
`/redoc` while the backend is running.

Written on post-coding Day 3 from the router source and the Pydantic models, and checked
against the 21 integration tests in `backend/tests/test_api.py`.

> **Security note.** `/docs`, `/redoc` and `/openapi.json` are open, which is correct and
> useful for a local-only development API. They **must** be disabled if this service is
> ever exposed. There is no authentication, authorisation or HTTPS — by design, for a
> single-user app bound to `127.0.0.1`.

---

## Conventions

* All request and response bodies are `application/json`, except the upload, which is
  `multipart/form-data`.
* CORS allows exactly one origin, `FRONTEND_ORIGIN` (default `http://localhost:5173`).
  Not `*`.
* Errors use FastAPI's standard shape: `{"detail": "<message>"}` for `HTTPException`, and
  `{"detail": [ … ]}` (a list of per-field objects) for request-validation failures.
* Error messages shown to callers are sanitised: they never contain filesystem paths,
  internal document ids, stack traces or library versions. The unredacted detail is
  logged server-side.

---

## Endpoint summary

| Method | Path | Success | Errors |
|---|---|---|---|
| `GET` | `/` | 200 | — |
| `GET` | `/api/health` | 200 | — |
| `POST` | `/api/documents/upload` | **202** | 400, 422 |
| `GET` | `/api/documents` | 200 | — |
| `GET` | `/api/documents/{document_id}` | 200 | 404 |
| `DELETE` | `/api/documents/{document_id}` | 200 | 404 |
| `POST` | `/api/chat/ask` | 200 | 400, 422, 500, 503 |

---

## Schemas

### `DocumentInfo`

```json
{
  "document_id": "14458171-0921-43f2-a667-db2ee1c1faf5",
  "filename": "native_single.pdf",
  "upload_date": "2026-09-12T21:51:23.104512+00:00",
  "status": "ready",
  "total_pages": 1,
  "total_chunks": 1,
  "ocr_pages_count": 0,
  "error_message": null
}
```

| Field | Type | Notes |
|---|---|---|
| `document_id` | string | Server-generated UUID4. Also the storage filename. |
| `filename` | string | The **user's** original filename, kept for display and citations. |
| `upload_date` | string | ISO-8601, UTC. Serialised from `upload_timestamp`. |
| `status` | string | `processing` \| `ready` \| `failed` |
| `total_pages` | int | 0 until ingestion finishes. |
| `total_chunks` | int | 0 until ingestion finishes. |
| `ocr_pages_count` | int | How many pages were recovered by OCR rather than native extraction. |
| `error_message` | string \| null | Present only when `status` is `failed`. Sanitised — see below. |

### `Citation`

```json
{
  "filename": "native_multi.pdf",
  "pages": [1, 3],
  "relevance_score": 0.6142,
  "extraction_method": "native"
}
```

| Field | Type | Notes |
|---|---|---|
| `filename` | string | The user's filename. |
| `pages` | int[] | Already sorted ascending. Merged across all cited chunks from that file. |
| `relevance_score` | float | 0.0–1.0, rounded to 4 dp. The **best** score among that file's cited chunks. |
| `extraction_method` | string | `native` \| `ocr`. Becomes `ocr` if **any** cited chunk from that file came from OCR, so the UI's badge errs toward flagging lower-confidence text. |

There is **exactly one citation per file**, and citations arrive sorted by
`relevance_score` descending.

> `relevance_score` is **match strength, not confidence**. It measures how closely a
> retrieved passage matched the question, not how correct the answer is. A correct answer
> to a broad question can score low.

---

## `GET /`

**Two different responses, depending on how the backend was started.**

In **development**, or in any run where `FRONTEND_DIST_DIR` holds no `index.html`, the
backend serves only the API and `/` is a liveness message:

```json
{ "message": "PDF RAG Chatbot API is running. Visit /docs for the API reference." }
```

In **production** — where `npm run build` has produced a bundle — the backend also serves
the built frontend, and `/` returns that application's HTML shell instead. The same
catch-all answers any client-side route (`/chat`, `/documents`) so a page refresh does not
404. One exception is deliberate: an unmatched path beginning `api/` is re-raised as a
real `404` rather than falling through to the shell, because returning HTML with a `200`
for a mistyped endpoint would surface in the client as a JSON parse error instead of a
clear not-found.

---

## `GET /api/health`

Probes all five dependencies and returns `200` **regardless of their state** — the body,
not the status code, carries the verdict. A monitoring check should read `status`.

```json
{
  "status": "ok",
  "ollama_available": true,
  "chroma_available": true,
  "embedding_model_loaded": true,
  "ocr_available": true,
  "database_available": true,
  "uptime_seconds": 56.7,
  "version": "1.1.0",
  "details": { "note": "ocr_available=false means Tesseract is not installed — …" }
}
```

| Field | Meaning |
|---|---|
| `status` | `ok` when Ollama **and** ChromaDB **and** the embedding model **and** the database are all up; otherwise `degraded`. |
| `ocr_available` | Tesseract reachable. **Deliberately not part of `status`** — OCR is a fallback, and the app is fully usable for native PDFs without it. |
| `database_available` | SQLite at `DATABASE_PATH` answered a `SELECT 1`. Checked with the standard library directly rather than through the application's own connection, so it tests the file rather than a cached handle. Required field, no default — a missing value is a schema error at the router, not a silent `null`. |
| `uptime_seconds` | Seconds since the process started. Distinguishes a stable process from one that has been silently restarting. |
| `version` | The running release, read from `app.__version__`. Answers "I deployed, but am I hitting the new code?". |

**Cost.** This endpoint makes a real HTTP call to Ollama, a ChromaDB heartbeat, a SQLite
query and a Tesseract subprocess spawn. Measured at **p50 110 ms, 8.5 requests per second**
on the reference hardware, against 129.5 req/s for `GET /api/documents`. It is a
diagnostic, not a liveness ping — do not poll it aggressively.
`scripts/health-monitor.ps1` polls it on a schedule and alerts on `degraded`,
unreachable, or unusually slow.

---

## `POST /api/documents/upload`

Accepts one PDF and returns **`202 Accepted`**, not `200` — the file has been saved and
validated, but ingestion (extraction, OCR, chunking, embedding) runs afterwards in a
background task. Poll `GET /api/documents` for `processing → ready`.

**Request** — `multipart/form-data` with a single part named `file`.

```bash
curl -F "file=@report.pdf" http://localhost:8000/api/documents/upload
```

**`202` response**

```json
{
  "document_id": "3f0c…",
  "filename": "report.pdf",
  "status": "processing",
  "message": "File accepted. Processing will begin shortly."
}
```

> This is an `UploadResponse`, **not** a `DocumentInfo`. It has no page, chunk or OCR
> counts because processing has not run yet.

**Errors**

| Status | `detail` | Cause |
|---|---|---|
| 400 | `Only .pdf files are accepted.` | Filename does not end in `.pdf` (case-insensitive), **or** the filename is empty |
| 400 | `MIME type must be application/pdf.` | A `Content-Type` was declared on the part and it was not `application/pdf` |
| 400 | `File exceeds the 20 MB limit.` | Body exceeded `MAX_FILE_SIZE_MB` |
| 400 | `Uploaded file is empty.` | Zero bytes received |
| 422 | validation list | No `file` part at all, or a part with **no filename parameter** — Starlette parses that as a plain form field, so it fails model validation before the handler runs |

**Validation order matters.** The name and declared MIME type are checked *before any of
the body is read*, so an oversized non-PDF is refused without the server ever holding it.
The body is then read in 1 MB chunks and refused the moment it passes the limit —
`Content-Length` is deliberately **not** trusted as the control, because the client
supplies it and it can be absent or wrong.

**Storage.** The file is written as `data/uploads/<uuid>.pdf`. The user-supplied name is
never used as a path.

**Ingestion outcome.** Ingestion sets `status` to `ready`, or to `failed` with an
`error_message`, which the frontend renders verbatim — so it is sanitised first: every
form of the storage path (plain, backslash-escaped and forward-slash) is replaced with the
user's own filename, and the containing directory becomes "the upload directory".

---

## `GET /api/documents`

Returns `200` with an array of `DocumentInfo`, newest first (`ORDER BY upload_timestamp
DESC`). An empty library is `[]`, not a 404.

---

## `GET /api/documents/{document_id}`

Returns `200` with one `DocumentInfo`.

| Status | `detail` | Cause |
|---|---|---|
| 404 | `Document not found.` | Unknown `document_id` |

---

## `DELETE /api/documents/{document_id}`

Removes the PDF file, the ChromaDB vectors and the SQLite row.

```json
{ "message": "Document deleted successfully.", "document_id": "3f0c…" }
```

| Status | `detail` | Cause |
|---|---|---|
| 404 | `Document not found.` | Unknown `document_id` |

**Deleting a document that is still ingesting is supported.** On Windows the PDF is locked
while PyMuPDF holds it open, so removing the file can raise `PermissionError`. That is
caught and logged: the row and the vectors are removed anyway so the API stays consistent
with what the user sees, and the background ingestion task — which checks whether its
document still exists before storing anything — cleans up the file it still owns. Letting
the error escape previously produced a 500 with the record, the file *and* the vectors all
surviving.

---

## `POST /api/chat/ask`

The RAG query path. **Slow by nature** — expect 30–75 s on an 8 GB machine, and
substantially longer for the first request after Ollama starts, which also pays for
loading the model into memory. Set a client timeout **longer** than the backend's
`OLLAMA_TIMEOUT_SECONDS` (see §Timeouts below).

**Request**

```json
{ "question": "What does the report say about revenue?", "document_id": null }
```

| Field | Type | Notes |
|---|---|---|
| `question` | string, **max 2000 chars** | Required. Over the limit is a 422 from Pydantic. |
| `document_id` | string \| null | Optional. When present, retrieval is restricted to that one document. |

**`200` response**

```json
{
  "answer": "Revenue grew 12% year over year (native_multi.pdf, Page 2).",
  "citations": [ { "filename": "native_multi.pdf", "pages": [2],
                   "relevance_score": 0.7431, "extraction_method": "native" } ],
  "processing_time_ms": 41230
}
```

**Errors**

| Status | `detail` | Cause |
|---|---|---|
| 400 | `Question cannot be empty.` | `question` is empty or whitespace only |
| 422 | validation list | `question` over 2000 characters, or a malformed body |
| 503 | `Cannot reach the language model at …` | Ollama unreachable |
| 503 | `The language model did not respond within N seconds. …` | Generation exceeded `OLLAMA_TIMEOUT_SECONDS` |
| 503 | `The language model returned an error (HTTP …)` | Ollama answered non-200 — usually the model is not pulled |
| 500 | `An unexpected error occurred while generating the answer.` | Anything else. Deliberately generic; the real exception is logged server-side |

### Two behaviours worth knowing

**"Not found" is a `200`, not a `404`.** The pipeline ran correctly and produced its
designed output — the documents simply did not contain the answer. The body is:

```json
{ "answer": "I could not find an answer to that in your uploaded documents.",
  "citations": [], "processing_time_ms": 12 }
```

`citations` is always `[]` in that case. This also happens, *without the LLM being called
at all*, when the vector store is empty or retrieval returns nothing — which is why
`processing_time_ms` can be a few milliseconds.

**A 503 means the dependency is down, not that the backend is broken.** It is the signal
to start Ollama and retry; it is deliberately distinguished from a 500.

### Answers may be withheld

If the generated answer recites the system prompt or imitates the fence markers — whether
because the *question* asked it to, or because a poisoned document in the corpus did — the
answer is **not returned**. The caller receives the ordinary "not found" response with no
citations, and the event is logged server-side. This is indistinguishable from a genuine
"not found" by design.

### Timeouts

| Layer | Value | Why |
|---|---|---|
| Backend → Ollama | `OLLAMA_TIMEOUT_SECONDS`, default **300 s** | Covers cold model loading |
| Reference frontend → backend | **360 s** (`api.js`) | Deliberately longer, so the backend's actionable 503 wins the race instead of a bare client-side abort |

The backend's clock starts only once retrieval is done and it calls Ollama, so a request
that gives up takes slightly *more* than 300 s end to end. Any client should allow for
that.

> Known limitation: the timeout bounds **socket inactivity**, not total elapsed time. A
> dependency dribbling bytes held one request for 32.8 s against a 30 s setting. Ollama is
> local and trusted here, so there is no exposure, but a total-deadline is not implemented.

---

## Status codes used, at a glance

| Code | Where | Meaning in this API |
|---|---|---|
| **200** | most | Success — *including* the "not found" answer |
| **202** | upload | File accepted and saved; ingestion has not run yet |
| **400** | upload, ask | Caller-fixable input problem, with a specific message |
| **404** | get, delete | Unknown `document_id` |
| **422** | upload, ask | Request-shape validation failed (FastAPI/Pydantic) |
| **500** | ask | Unexpected server fault. Generic message; detail is logged |
| **503** | ask | Ollama unreachable, timed out, or erroring — start it and retry |

> One known imperfection: deeply nested JSON in a narrow depth band returns **500** rather
> than 422. It is refused in every case with a 21-byte body and no stack trace, and the
> server stays healthy; fixing it properly needs a global `RecursionError` handler, which
> has no reproduced defect behind it.
