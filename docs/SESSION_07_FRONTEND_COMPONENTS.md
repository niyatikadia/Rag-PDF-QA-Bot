# SESSION_07_FRONTEND_COMPONENTS.md — Day 6: React Components (Mock Data)

| | |
|---|---|
| **Phase** | Phase 5 part 1 — Frontend Implementation (spec §23) |
| **Step** | `PROJECT_STEPS.md` step 7 / spec §27, Day 6 |
| **Mode / Model / Effort** | Cowork · Opus 5 · High |
| **Features covered** | F10, F12, F13, F14, F15, F16, F19 |
| **Backend used** | **None.** Mock data only — wiring is Day 7. |
| **Status** | ✅ Complete — all components render, 0 console errors, build clean |

---

## 📌 Starting state (important)

All 15 frontend modules from spec §15.2 **already existed** as Day 1 scaffold,
and `node_modules` was already installed. Per the Day 5 lesson (an earlier
attempt had silently left half-finished work behind), **every existing file was
read in full before anything was written.** Nothing was blind-overwritten.

Audit result:

| File | Found as | Action taken |
|---|---|---|
| `package.json`, `vite.config.js`, `tailwind.config.js`, `postcss.config.js`, `index.html`, `main.jsx` | Complete and correct (Vite proxy `/api` → `:8000`, `brand` palette) | **Untouched** |
| `services/api.js` | Complete; all 6 endpoints already match `schemas.py` | **Untouched** — Day 7 imports it as-is |
| `Header.jsx` | Working nav | Extended (a11y `aria-current`, `flex-shrink-0`, RAG chip) |
| `DocumentList.jsx` | Working, had a plain-text empty state | Extended (illustrated empty state) |
| `MessageBubble.jsx` | Working, already handled `citations.length === 0` correctly | Extended (source count, timing, not-found note) |
| `App.jsx`, `ChatPage.jsx`, `index.css` | Working, but chat height was hard-coded `h-[calc(100vh-57px)]` | Replaced with a robust flex shell |
| `CitationCard.jsx` | Had the OCR badge already; labelled the score `"% match"` | Relabelled **MATCH STRENGTH** + rank + bar |
| `DocumentCard.jsx` | Had OCR count as a separate chip; no `error_message` | Reformatted to "12 pages (3 via OCR)", added chunks/date/error |
| `LoadingIndicator.jsx`, `ErrorToast.jsx` | Single generic variant each | Rewritten with variants (below) |
| `ChatInterface.jsx` | Good shell, but held its own `useState` and duplicated `useChat` | Rewritten to consume `useChat()` |
| `useChat.js` | Imported the **real** `api.js` — would have thrown with no backend | Made mock-backed behind a marked block |
| `FileUpload.jsx`, `DocumentsPage.jsx` | Working; no mock data, no size validation | Extended |

**No new files were created** — spec §15.2 fixes the frontend at exactly 15
modules, so the mock data lives *inside* `useChat.js` and `DocumentsPage.jsx`
in clearly fenced `DAY 6 MOCK` blocks rather than in a new `mockData.js`.

**No new dependencies were added.** `package.json` is byte-identical.

---

## ✅ What Was Built This Session

### 1. `useChat.js` — mock-backed chat state (F12, F13)

The whole Day 7 swap is isolated here. The mock:

- returns objects matching `schemas.AskResponse` exactly
  (`{answer, citations[], processing_time_ms}`),
- **rejects with an Axios-shaped error** (`err.response.status`,
  `err.response.data.detail`), so the `catch` block in `sendMessage` is already
  the final production code and needs no edit on Day 7,
- honours `document_id` filtering the way the backend does (a question scoped to
  the wrong document falls back to the "not found" response).

Mock triggers (documented so every UI state is reachable from the input box):

| Question contains | Response |
|---|---|
| `!503` prefix | HTTP 503 — Ollama down |
| `!400` prefix | HTTP 400 — empty question |
| `ocr` / `scan` / `attendee` | single OCR-badged citation (0.5726) |
| `machine learning` | correct answer at **0.2156** match strength |
| `weather`, `moon`, `pizza`, `football`, `recipe`, `capital of`, `stock price` | "not found", `citations: []` |
| anything else | 3 citations — 2 native + 1 OCR (0.8008 / 0.6431 / 0.5726) |

### 2. `CitationCard.jsx` — F10

- filename + `Page 1` / `Pages 1, 2, 3` + rank badge.
- **"OCR" badge** with a `ScanLine` icon when `extraction_method === "ocr"`,
  tooltipped "may contain recognition errors".
- The score is labelled **MATCH STRENGTH**, never "confidence", with a tooltip
  explaining it is chunk-to-question vector similarity and *not* a measure of
  answer correctness — the Day 5 case where a correct broad answer scored
  0.2156 is exactly why.
- Relies on (and never re-sorts) the backend guarantees: pre-sorted by
  `relevance_score` descending, `pages` already sorted, one citation per file.

### 3. `MessageBubble.jsx` — F13

Renders one turn. When `citations` is `[]` (a "not found" answer) it renders the
answer alone with **no empty Sources strip**, replacing it with a quiet
"No matching passages found in your documents" line.

### 4. `LoadingIndicator.jsx` — F15, three variants

- `default` — spinner + message (upload, misc).
- `ocr` — amber, `ScanLine`, **"Running OCR on scanned pages…"** plus
  "This page had no embedded text. OCR is slower than native extraction."
- `chat` — the **patient** state. Holds its own elapsed-seconds timer and
  escalates its copy, so a ~4-minute first answer never looks hung:

  | Elapsed | Copy |
  |---|---|
  | 0s | Searching your documents… |
  | 4s | Reading the most relevant passages… |
  | 12s | Generating the answer… |
  | 30s | Still working — the model is warming up. |
  | 75s | This is the first answer since Ollama started; it can take a few minutes. |

  From 30s it also shows "Answers are generated locally by Ollama — please keep
  this tab open." The escalation lives inside the component, so Day 7 keeps it
  unchanged.

### 5. `ErrorToast.jsx` — F16 / F12

Accepts a string **or** an Axios-shaped `{status, message}`, so Day 7 can pass
the real error straight through. Three visually distinct variants:

| Status | Colour | Title | Actionable hint |
|---|---|---|---|
| **503** | orange, `ServerCrash` | "Ollama is not running" | *Start it with "ollama serve" in a terminal, then send your question again.* |
| **400** | amber, `AlertTriangle` | "Check your question" | *Type a question before sending. Questions are limited to 2000 characters.* |
| other / none | red, `AlertCircle` | "Something went wrong" | — |

### 6. `DocumentCard.jsx` — F14

Renders `schemas.DocumentInfo` directly, no adapter. Status pill
(ready / processing / failed), chunk count, upload date, and `error_message`
inline for failures. **[v2]** the page count reads exactly
**"12 pages (3 via OCR)"** when `ocr_pages_count > 0`, plus an OCR pill.

### 7. `FileUpload.jsx` — F1 / F15 / F16

Drag-drop + click + keyboard-activatable. Validates extension and the 20 MB
limit *before* upload. The mock upload stages through
`Uploading…` → `Running OCR on scanned pages…` for scanned-looking filenames.
Emits a `DocumentInfo`-shaped object so `DocumentCard` needs no adapter.

### 8. Pages, shell and routing

- `App.jsx` — `h-screen` flex column so each page owns its scrolling; the chat
  input bar stays pinned and the message list scrolls independently. Added a
  `*` catch-all redirect to `/chat`, and React Router v7 future flags
  (`v7_startTransition`, `v7_relativeSplatPath`) to keep the console clean.
- `ChatPage.jsx` — thin wrapper; the brittle `h-[calc(100vh-57px)]` is gone.
- `DocumentsPage.jsx` — seeded with 4 mock documents covering every status,
  plus a summary line ("2 ready · 3 pages via OCR").
- `index.css` — full-height html/body/#root, scrollbar styling, and a
  `prefers-reduced-motion` block that disables the spinners and pulses.
- Empty states for both pages.

---

## 🧪 Testing Performed

Dev server on `http://localhost:5173`, viewport 1280×900. **Backend not running.**

| # | Scenario | Result |
|---|---|---|
| 1 | Chat empty state | ✅ icon + guidance copy |
| 2 | Multi-citation answer | ✅ 3 ranked sources — 80% / 64% / 57%, OCR badge on the third |
| 3 | OCR-only answer | ✅ single source, OCR badge, 57% |
| 4 | "Not found" answer | ✅ answer alone, **no citation strip**, quiet explanatory note |
| 5 | Low match strength | ✅ correct answer at **22%** — proves the label is not "confidence" |
| 6 | 503 error | ✅ orange toast, "Ollama is not running", HTTP 503, "ollama serve" hint |
| 7 | 400 error | ✅ amber toast, "Check your question", visually distinct from 503 |
| 8 | Patient loading escalation | ✅ verified live at 51s ("Still working — the model is warming up.") and at **1m 33s** ("This is the first answer since Ollama started…") with a running elapsed timer; input + send disabled throughout |
| 9 | Conversation history (F13) | ✅ turns accumulate, "N questions this session" counter, Clear chat empties it |
| 10 | Enter to send | ✅ verified by dispatching a real `keydown`: `defaultPrevented === true`, input cleared, new bubbles rendered |
| 11 | Documents page — all statuses | ✅ ready / ready+OCR / processing / failed-with-error all render |
| 12 | OCR count format (F14) | ✅ renders **"12 pages (3 via OCR)"** |
| 13 | Delete (F14) | ✅ removes the card; deleting all reaches the empty state |
| 14 | Documents empty state | ✅ illustrated, mentions automatic OCR |
| 15 | Upload OCR indicator (F15) | ✅ "Running OCR on scanned pages…" for a scanned-looking file |
| 16 | Non-PDF rejection | ✅ "Only .pdf files are supported — rejected notes.txt." |
| 17 | Oversize rejection | ✅ "Each file must be 20 MB or smaller — huge.pdf is 21.0 MB." |
| 18 | Unknown route | ✅ redirects to `/chat` |
| 19 | Console | ✅ **0 errors, 0 warnings** after the router future flags |
| 20 | `npm run build` | ✅ 1520 modules, 194.74 kB JS / 16.81 kB CSS, no errors |

### Note on the browser automation

Synthetic `type` and `key Enter` from the automation tool do not reach React's
change tracker, so UI driving was done with `form_input` + click, and
Enter-to-send was verified by dispatching a genuine `KeyboardEvent`. **This is an
automation artifact, not an application bug** — test 10 confirms the handler
runs, calls `preventDefault`, and sends.

---

## 📋 Decisions Made This Session

1. **No `mockData.js`.** Spec §15.2 fixes the frontend at 15 modules, so mocks
   live inside `useChat.js` and `DocumentsPage.jsx` in fenced
   `DAY 6 MOCK — DELETE ON DAY 7` blocks. Day 7 deletes blocks, not files.
2. **Mock errors are Axios-shaped.** `sendMessage`'s `catch` and `ErrorToast`'s
   normaliser are already production code — Day 7 changes one call, not the
   error path.
3. **"MATCH STRENGTH", not confidence.** Naming the number honestly is the whole
   point of the Day 5 0.2156 finding; calling it confidence would misrepresent a
   correct answer as a doubtful one.
4. **Loading escalation lives in `LoadingIndicator`.** It is time-based, not
   request-based, so it survives the Day 7 swap untouched.
5. **`ChatInterface` holds no chat state.** All of it is in `useChat()`, which
   confines the backend swap to one file.
6. **Controlled textarea.** The first pass used an uncontrolled `ref`; switched
   to controlled state — idiomatic React, and it removes direct DOM mutation.
7. **`api.js` left completely untouched.** It already matches `schemas.py`.

---

## ⚠️ Known follow-ups (none blocking, all Day 7/8)

- `DocumentsPage` does not poll for `processing → ready`; the mock card stays in
  Processing forever. Polling is explicitly Day 7 scope.
- No document-scope selector in the chat UI yet. `useChat.sendMessage` and
  `ChatInterface` already accept and thread `documentId` through, so the
  plumbing exists — only the picker control is missing.
- `axios` timeout in `api.js` is **60 s**, but Day 5 measured a 63.6 s answer and
  a cold first answer can take ~4 minutes. **Day 7 must raise this** or the first
  real question will time out client-side even though the backend succeeded.
- Responsive layout is desktop-first (F19 only requires desktop). Mobile polish
  is Day 8.

---

## 🚀 What Day 7 Starts With

Day 7 is **Phase 5 part 2** (`PROJECT_STEPS.md` step 8): wire `api.js` and
connect every component to the real backend.

The swap is deliberately small:

1. **`useChat.js`** — delete the `DAY 6 MOCK` block, uncomment
   `import { askQuestion } from '../services/api'`, and change one line:
   `const response = await mockAskQuestion(...)` → `await askQuestion(...)`.
   The error handling, loading states and message shaping need no change.
2. **`DocumentsPage.jsx`** — delete `MOCK_DOCUMENTS`, start from `[]`, add
   `useEffect(() => { listDocuments().then(setDocuments) }, [])`, add status
   polling for `processing` documents, and `await deleteDocument(id)` before
   removing a card.
3. **`FileUpload.jsx`** — replace the body of `uploadOne()` with
   `api.uploadDocument(file)`. Validation, drag state and the OCR stage stay.
4. **`api.js`** — raise the 60 s timeout (see follow-ups above).

Everything else — `CitationCard`, `MessageBubble`, `DocumentCard`,
`DocumentList`, `LoadingIndicator`, `ErrorToast`, `Header`, `App`, `ChatPage`,
`index.css` — is already final and consumes the real backend shapes directly.

**Completion criteria (Day 6 — met):** every component renders correctly with
mock data; both pages verified in the browser; multi-citation, OCR-badged and
"not found" answers all render correctly; ready / processing / failed / OCR-count
document cards all render; 0 console errors; production build clean.

---

*End of SESSION_07_FRONTEND_COMPONENTS.md — Day 6 complete, awaiting approval to
start Day 7.*
