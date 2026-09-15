# SESSION_08_FRONTEND_WIRING.md — Day 7: Connect the Frontend to the Real Backend

| | |
|---|---|
| **Phase** | Phase 5 part 2 — Frontend Implementation (spec §23) |
| **Step** | `PROJECT_STEPS.md` step 8 / spec §27, Day 7 |
| **Mode / Model / Effort** | Cowork · Opus 5 · High |
| **Features covered** | F1, F10, F12, F13, F14, F15, F16, F18 |
| **Backend used** | **Real.** `uvicorn app.main:app --port 8000`, live ChromaDB + SQLite + Tesseract + Ollama |
| **Status** | ✅ All 9 completion criteria verified through the UI — with one honest caveat on criterion 3–6 (see §"The llama3.1:8b blocker") |

---

## 📌 What Day 7 had to do

Delete every Day 6 mock, point all four wiring files at the real API, add status
polling, and prove each feature works through the browser against a live backend.

**All mocks are gone.** `grep -rn "MOCK\|mockAsk" src/` returns nothing but a
single historical mention inside a comment.

**No new dependencies.** `package.json` is byte-identical to Day 6. Tailwind only.

**No component rewrites.** `CitationCard`, `MessageBubble`, `DocumentCard`,
`DocumentList`, `LoadingIndicator`, `ErrorToast`, `Header`, `App`, `ChatPage`,
`index.css` were **not touched** — they already consumed the real backend shapes.

---

## ✅ The four wiring changes

### 1. `services/api.js` — per-request timeouts (the highest-risk item)

The single 60 s instance timeout was replaced with three per-request values:

| Request | Timeout | Why |
|---|---|---|
| documents, health | 30 s | local SQLite / in-process reads; a hang is a real failure |
| upload | 120 s | carries up to 20 MB; returns **202** as soon as the file is saved |
| **`/chat/ask`** | **360 s** | blocked on local LLM generation |

**Why 360 s and not 300 s.** My first pass used 300 s. That is wrong, and
measurement showed why: the backend's own `OLLAMA_TIMEOUT_SECONDS` is **300 s**,
and that clock only starts *after* retrieval finishes. So a backend request that
gives up takes slightly **more** than 300 s end to end. A 300 s browser timeout
would race the backend and usually win — and the user would get a bare
client-side abort ("Could not reach the backend") instead of the backend's
actionable 503 ("start Ollama / it can be slow while the model loads"). The
client is now deliberately set to lose that race so the useful message wins.
This was verified: the 503 test produced the orange "Ollama is not running"
toast, never a client-side abort.

### 2. `hooks/useChat.js` — one-line swap, as designed on Day 6

The whole `DAY 6 MOCK` block (`mockAskQuestion`, `MOCK_RESPONSES`, `OFF_TOPIC`,
`mockHttpError`, `MOCK_LATENCY_MS`) was deleted, the real import uncommented,
and `await mockAskQuestion(...)` became `await askQuestion(trimmed, documentId)`.
**The `catch` block was not modified** — Day 6's decision to make the mock reject
with an Axios-shaped error paid off exactly as intended.

### 3. `components/FileUpload.jsx` — real upload

`uploadOne()` now calls `api.uploadDocument(file)`. The extension check, the
20 MB check, the drag state and the OCR loading stage are unchanged.

Two backend facts shaped this:

- `POST /api/documents/upload` answers **202 with an `UploadResponse`**
  (`{document_id, filename, status, message}`), **not** a `DocumentInfo`. It has
  no `total_pages` / `total_chunks` / `ocr_pages_count`. So the component hands
  the raw response up and **the page refetches the list** rather than pushing a
  half-populated card in.
- Ingestion runs in a FastAPI `BackgroundTask` *after* the 202, so the upload
  call finishes long before OCR does.

**The OCR stage is no longer a filename guess.** Day 6 showed
"Running OCR on scanned pages…" whenever the filename matched `/scan|image/i` —
a mock behaviour that would have been a lie against a real backend. It is now
driven by `ingestStatus`, a prop computed by `DocumentsPage` from real polled
document status.

### 4. `pages/DocumentsPage.jsx` — real list, polling, real delete

`MOCK_DOCUMENTS` deleted; state starts at `[]` and loads via `listDocuments()`.

**Polling** (`POLL_INTERVAL_MS = 2500`):
- runs **only** while at least one document is `processing`, and stops when none
  are. Ingestion is a background task, so `processing` is the only state that can
  change on its own — polling a settled list would be pure noise.
- `clearInterval` on unmount, and every `setState` guarded by a `mountedRef`.
- **a failed poll is swallowed**: it never wipes the list and never raises a
  toast. Only 3 consecutive failures surface, as a quiet inline line.

**Delete** removes the card optimistically, `await deleteDocument(id)`, and on
failure shows a toast and calls `refresh()` — reverting to the backend's own
truth rather than trying to re-insert the card by hand (which would race a poll).

**The OCR hint is an inference, and is worded as one.** The backend writes only
`processing → ready|failed`, with no intermediate "OCR is running" signal, so the
frontend genuinely cannot know. Native extraction of these documents completes in
well under a second; OCR is ~1–3 s per page. So after `OCR_HINT_AFTER_MS = 4000`
of real observed processing the indicator switches to the amber OCR variant. This
is a measured inference from real state, not a filename guess and not a mock.

---

## 🧪 Testing against the real backend

Backend: `uvicorn` on `:8000`, health `{"status":"ok", ollama/chroma/embedding/ocr all true}`.
Frontend: Vite dev server on **:5174** (`:5173` was occupied by another session;
a `frontend-day7` entry was added to `.claude/launch.json`). CORS never came up —
all traffic went through the existing Vite proxy, same-origin from the browser.

Every result below was read from **real network responses and real server logs**,
not assumed.

| # | Criterion | Result |
|---|---|---|
| 1 | Upload native PDF → card → polling → ready | ✅ `202 Accepted` → card in **Processing…** → poll flipped it to **Ready, 3 pages · 3 chunks** → polling stopped |
| 2 | Upload scanned PDF → `ocr_pages_count > 0` | ✅ **"1 page (1 via OCR)"** + OCR pill; server log `Page 1 recovered via OCR (279 chars)` |
| 3 | Grounded answer + filename/page citation | ✅ *"ChromaDB is a vector database used to store embeddings for retrieval augmented generation (native_multi.pdf, Page 2)"* — 1 source, **native_multi.pdf, Page 2, MATCH STRENGTH 41 %**, 12.7 s |
| 4 | OCR-only answer → OCR badge | ✅ retrieved **"PINEAPPLE OCR SUCCESS"** from `scanned_image_only.pdf`; citation carries the **OCR** badge, Page 1, 59 %, 36.5 s |
| 5 | Unrelated question → not found, 0 citations | ✅ *"I could not find an answer to that in your uploaded documents."* — **no citation strip**, quiet "No matching passages found" note |
| 6 | Ollama stopped → 503, not generic, not a timeout | ✅ killed `ollama`/`llama-server`; real **HTTP 503**, orange toast **"Ollama is not running"** with the backend's own detail + *"Start it with 'ollama serve'…"* |
| 7 | Delete → gone from list and backend | ✅ `DELETE → 200`; `GET /api/documents` dropped the record **and** the PDF disappeared from `backend/data/uploads/` |
| 8 | Cold first answer, no client-side timeout | ✅ no client-side abort in any run; the cold first answer took **96.5 s** — which the old 60 s timeout would have killed |
| 9 | No console errors | ✅ clean page loads show only Vite debug + the React DevTools info line. The only `[error]` entries are the browser's own "Failed to load resource" lines for the **deliberately induced** 500 and 503 — no React errors, no uncaught exceptions, no warnings |

### Extra checks beyond the criteria

- **Polling really stops.** After the last document settled, `GET /api/documents`
  issued **zero** further requests over 18 s of idling.
- **Unmount safety.** Navigated `/documents → /chat` while a document was still
  processing: no new console output, no "setState on unmounted component".
- **Failed-document card, from a real backend failure** (see below): status pill
  **Failed** plus the backend's real `error_message` rendered inline.
- **`npm run build`** — 1576 modules, `245.62 kB` JS / `16.86 kB` CSS, no errors.
- Test fixtures were served from a temporary `public/__day7_fixtures/` folder to
  drive the real file input; **that folder was deleted** and `dist/` was checked
  to confirm nothing leaked into the build.

---

## ⚠️ What broke, and what it actually was

### 1. The 500 that was not a frontend bug — the backend process was being killed

The first cold question returned **HTTP 500** at ~3 m 50 s. Rather than assume a
timeout, I read the Vite proxy log:

```
[vite] http proxy error: /api/chat/ask
Error: read ECONNRESET
```

and the uvicorn log, which had **no** access-log line for the request at all.
`Get-NetTCPConnection -LocalPort 8000` returned nothing: **the backend process
had exited mid-request.** The 500 was Vite reporting a dead upstream.

The frontend behaved correctly here — it surfaced an error toast rather than
hanging — but the message ("Could not reach the backend. Check that the API
server is running.") happened to be exactly right, because the API server really
was not running.

### 2. The llama3.1:8b blocker — a genuine environment limit, measured

Root cause of the crashes and the slowness, measured directly against Ollama with
no application code involved:

| Measurement | Value |
|---|---|
| Total machine RAM | **7.89 GB** (spec §18.1 minimum is 8 GB) |
| `llama3.1:8b` Q4_K_M resident size | **~5.3 GB** |
| Free RAM with the model loaded | **0.27 GB** |
| Cold model load | **82 s**, and on a second attempt **166 s** |
| Generation while thrashing | **14.7 s/token** |
| Generation once genuinely warm | **661 ms/token** |

With the 8B model resident there is no room for the backend (torch +
sentence-transformers + ChromaDB), and the uvicorn process was terminated —
cleanly, with **no crash event in the Windows Application log** and no Python
traceback, i.e. `TerminateProcess`, not an exception. This reproduced **three
times**. Without the model resident, generation exceeds the backend's 300 s
Ollama timeout and correctly returns 503.

So on this machine the stack is caught between the two: model loaded → backend
gets killed; model not loaded → 300 s timeout.

**How criteria 3–6 were verified honestly.** `llama3.2:latest` (1.88 GB) was
already pulled locally, so the backend was started with `OLLAMA_MODEL=llama3.2:latest`
**in the process environment only**. `backend/.env` was **not edited** and still
reads `OLLAMA_MODEL=llama3.1:8b`; `load_dotenv()` does not override the process
environment, so this was fully reversible and left no trace.

This is a **real LLM through the real RAG pipeline** — retrieval, context
construction, generation, citation extraction all ran for real. Nothing was
mocked. What it does **not** prove is answer quality under the spec's own model.
**Day 9 must re-run the answer-quality checks on `llama3.1:8b`**, and that will
need memory headroom (close browsers/editors, or accept the cold-load wait).

### 3. A real backend edge case found by accident (Day 9 input, not Day 7 scope)

To make a document whose OCR takes long enough to exercise the amber OCR
indicator, I built a 5-page scanned PDF by repeating the single scanned page.
All 5 pages OCR'd successfully (`Page N recovered via OCR (279 chars)` ×5), yet
ingestion was marked **failed** with *"No text could be extracted from this PDF,
even with OCR."*

Cause, confirmed by reading `services/text_cleaner.py`:
`_strip_repeated_headers_footers()` removes lines ≤80 chars that appear on a
majority of pages. Because every page was identical, **every line qualified as a
running header** and the whole document was emptied.

This is arguably correct behaviour for a pathological fixture rather than a bug,
and it is **Day 2/3 backend code, out of Day 7 scope**, so it was deliberately
left unfixed. But a real document with a short repeated body (a form, a
certificate, a repeated template page) could hit it. Worth a decision on Day 9.

**Silver lining:** it produced a genuine backend `failed` document, which
verified the failed card variant and inline `error_message` against real data
rather than a mock.

### 4. Automation artifact (not an application bug)

`form_input` on the chat textarea does not reach React's value tracker, so the
send button stayed disabled. Driving it required the native
`HTMLTextAreaElement.prototype.value` setter plus a real bubbling `input` event.
This is the same class of automation artifact recorded on Day 6 — the
application's own `onChange` path is fine.

---

## 📋 Decisions made this session

1. **Per-request timeouts, not one global value** — a 30 s hang on
   `GET /api/documents` is a real failure; 30 s on `/chat/ask` is normal.
2. **Client `/chat/ask` timeout (360 s) deliberately exceeds the backend's
   Ollama timeout (300 s)** so the backend's actionable 503 always wins the race.
3. **Refetch after upload instead of trusting the 202 body**, because
   `UploadResponse` has no page/chunk/OCR counts.
4. **Polling lives only in `DocumentsPage`**, and only while something is
   processing. `FileUpload` takes `ingestStatus` as a prop rather than running a
   second poller.
5. **The OCR indicator is inferred from measured elapsed processing time and
   worded as an inference** — the backend exposes no mid-processing OCR signal,
   and Day 6's filename guess would have been dishonest against real data.
6. **Poll failures are swallowed**; only a sustained outage surfaces, quietly.
7. **Delete is optimistic with a `refresh()` revert**, avoiding a manual
   re-insert that could race a poll.
8. **`.env` was never edited.** The model swap was process-environment only.

---

## 🚀 What Day 8 starts with

Day 8 is **Phase 5 part 3** (`PROJECT_STEPS.md` step 9): UI polish — consistent
styling, empty states, error toasts, keyboard shortcuts, responsive layout,
edge-case handling. **Not started — awaiting explicit approval.**

Carried forward:

- **`llama3.1:8b` memory blocker (highest priority, Day 9 gate).** Answer quality
  is currently only verified on `llama3.2`. Needs headroom or a documented
  decision to change the spec model.
- **Repeated-page header stripping** empties documents whose pages are identical
  (§"What broke" #3). Needs a Day 9 decision.
- **A failed question leaves its user bubble in the history** with no answer
  under it (visible in the 503 screenshot: the question appears twice after a
  retry). A retry affordance or a failed-turn marker is Day 8 UX work.
- **No document-scope selector in the chat UI.** `useChat.sendMessage` and
  `ChatInterface` already thread `documentId`; only the picker control is missing.
- **Responsive layout is desktop-first** (F19 only requires desktop).
- **`.claude/launch.json` gained a `frontend-day7` entry on port 5174** because
  another session held 5173. Harmless; drop it if not wanted.

**Completion criteria (Day 7 — met):** every mock deleted; all four files wired
to the real backend; status polling implemented with unmount safety and
failure tolerance; all 9 criteria verified through the UI against a live backend,
with the `llama3.1:8b` caveat stated above; 0 application console errors;
production build clean.

---

*End of SESSION_08_FRONTEND_WIRING.md — Day 7 complete, awaiting approval to
start Day 8.*
