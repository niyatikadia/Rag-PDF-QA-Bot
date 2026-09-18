# Post-Coding Day 6 — Completion and Audit Remediation

**Date:** 17–18 September 2026
**Scope:** Close the project-related findings of a full external audit of this
repository, re-verify everything the changes touch, and reconcile the
documentation with what the code actually does.

> This document records **Day 6 only**. The audit that drove it also raised
> Phase F items (portfolio, résumé, interview preparation, stages 22–24 of
> `01_After_Coding_Is_Complete.pdf`). Those were **explicitly excluded from this
> day's scope by the repository owner** and no work was done on them; they are
> not "done", they are out of scope. Day 5's record is
> `POSTCODING_DAY_05_OPERATIONS.md`.

**Starting state (end of Day 5):** 175 tests passing, `v1.0.0` tagged locally,
31 commits unpushed, monitoring without alerting, the Python dependency CVE
audit never run, and six documentation statements contradicting the tree.

---

## 0. Environment

| Item | Value |
|---|---|
| CPU | Intel Core i7-7600U @ 2.80 GHz — 2 physical cores, 4 logical |
| RAM | 7.89 GB total |
| OS | Windows 11 Pro, build 22000 |
| Python | 3.13.3 (`backend\.venv`) |
| Node / npm | v22.23.1 / 10.9.8 |
| Ollama | `llama3.2:latest` (the configured model) |
| Tesseract | 5.5.3.20260724, on PATH |
| Tooling env | `.venv-tools` (ruff, black, mypy, vulture, radon, **pip-audit**, **playwright**) |

**Nothing was installed into the application's own environment.**
`backend/requirements.txt` is unchanged. `pip-audit` and `playwright` went into
the existing throwaway `.venv-tools`, and Playwright's browser download was
directed inside the repository (`PLAYWRIGHT_BROWSERS_PATH=.venv-tools/ms-playwright`),
which `.gitignore` already excludes via `.venv-*/`.

---

## 1. What the audit found, and what happened to each item

Findings are numbered as the audit numbered them. Phase F items (F-15 hero
screenshot, F-16 demo recording, F-17 résumé, F-18 interview preparation) are
listed as **out of scope** rather than silently dropped.

| ID | Finding | Outcome |
|---|---|---|
| F-01 | README asserted Phase E monitoring "have **not** been done" on a tree where it was done | **Fixed** — §5.1 |
| F-02 | Test counts stale in three places (167/ten, "9 modules") | **Fixed** — real figure is 185 across 12 |
| F-03 | README documented 17 environment variables; the code reads 20 | **Fixed** — all 20 listed |
| F-04 | Project-structure tree stale; omitted `DEPLOYMENT.md`, `scripts/`, `.day*/`, `CHANGELOG.md` | **Fixed** |
| F-05 | README's health response missing three fields | **Fixed** |
| F-06 | `API_REFERENCE.md` documented a health response the server no longer returns | **Fixed** — §5.2 |
| F-07 | CHANGELOG 1.0.0 entry contradicted the tree it tags | **Fixed** — §5.3 |
| F-08 | `GET /` documented only in its development form | **Fixed** |
| F-09 | 32 commits and `v1.0.0` unpushed | **Still open by instruction** — §8 |
| F-10 | HEAD past `v1.0.0` with API schema changes and no version | **Fixed** — 1.1.0, §6 |
| F-11 | Day 5 commit bundled code, tests and a record | **Not actioned** — owner instructed that history is not to be rewritten |
| F-12 | Version string written out in three places | **Fixed** — §2.3 |
| F-13 | No `LICENSE` | **Not actioned** — owner decided against one |
| F-14 | Repository visibility unverifiable | **Still open** — only the owner can check it |
| F-15/16/17/18 | Portfolio screenshot, demo recording, résumé, interview preparation | **Out of scope by instruction** |
| F-19/F-25 | Clone-and-follow-the-README never performed | **Still open** — §8, requires a directory outside the project folder |
| F-20 | UI states verified but no screenshot evidence | **Fixed** — §4.2, 24 captures |
| F-21 | Monitoring had no dashboard and no alerting | **Partly fixed** — alerting added, dashboard deliberately declined, §3.2 |
| F-22 | Secret scan was a hand-written pattern sweep | **Re-run, unchanged verdict** — §3.3 |
| F-23 | Python dependencies never audited for CVEs | **Fixed** — §3.1, and it found nine |
| F-24 | Four npm advisories open | **Fixed** — now zero, §3.1 |
| F-26 | Fresh-start test | Already complete; re-run this day anyway — §4.1 |
| F-27 | Retriever suite bound to the developer's live store | **Fixed** — §2.1 |
| F-28/F-29 | No CI, no coverage figure | **Not actioned** — neither is required by the reference documents |
| F-30 | Load tooling differs from the PDF's suggestions | No action needed; the PDF specifies numbers, not tools |
| F-31 | Two published harnesses hard-coded machine paths | **Fixed** — §2.4 |
| F-32 | Live corpus correctly excluded from git | Confirmed again in §7 |
| F-33 | Screenshots would collide with the retriever suite | **Dissolved** — F-27's fix removes the collision entirely |
| F-34 | No favicon | **Fixed** — and it was spec-required, §2.2 |
| F-36 | Throughput and long-run memory never measured | **Fixed** — §3.4 |
| F-37 | Lint/type claims predated later code changes | **Fixed**, and the claim was false — §2.5 |
| F-38 | Audit report untracked at the repository root | **Fixed** — git-ignored deliberately |

### 1.1 Two findings the audit did not make

Both were found by walking the specification rather than the audit:

1. **`test_api.py` shared `test_retriever.py`'s coupling to the live store.**
   The audit named only `test_retriever.py`. `test_ask_returns_answer_and_citations`
   had the same dependency and the same fresh-clone failure mode.

2. **Spec §19.2 and §32 require ingestion outcomes nothing asserted.** A scanned
   PDF reaching `ready` with `ocr_pages_count > 0`, and a document with no text
   by either method reaching `failed`, are both named in the specification's own
   completeness checklist. `test_ocr_processor.py` covers `ocr_page()` with
   Tesseract mocked — which proves the function works but says nothing about
   whether the pipeline ever decides to call it. Five of the eight committed
   fixture PDFs had no test using them at all.

---

## 2. Code changes

### 2.1 The test suite no longer reads the developer's data

**New: `backend/tests/conftest.py`.**

`test_retriever.py` asserted measured similarity scores against whatever was in
`backend/data/chroma_db/`, including `len(retrieve(..., top_k=99)) == 5`. Uploading
a fourth document through the application therefore turned the suite red for a
reason unrelated to the code, and on a fresh clone the tests failed with an
instruction to go and upload three PDFs first.

Three session-scoped fixtures replace that:

| Fixture | Effect |
|---|---|
| `isolated_vector_store` (autouse) | Points `vector_store` at a throwaway ChromaDB directory |
| `isolated_database` (autouse) | Points `app.models.database` at a throwaway SQLite file |
| `fixture_corpus` | Ingests the three committed fixture PDFs through the **real** pipeline |

Both patches are applied to the *consuming module*, not to `app.config`, because
each binds its value at import (`from app.config import CHROMA_PERSIST_DIR`).
Patching config alone would have silently done nothing and the tests would have
gone on reading the live store — which is the kind of fix that looks right and
is not.

Counts are now derived from what was actually ingested (`corpus_chunk_count`)
rather than hard-coded, and the tests that need the OCR document skip with a
stated reason where Tesseract is absent (`corpus_has_ocr`).

**A defect this introduced, and how it was caught.** The new ingestion tests
(§2.6) wrote their documents into the same session store, raising it from 5
chunks to 30 and failing `test_returns_top_k_results` with `30 == 5`. The fix is
`scratch_vector_store`, a per-test private store that `test_ingestion_pipeline.py`
uses for every test.

That failure is also the **non-vacuity proof** for the whole change: the live
store contains exactly 5 chunks, so a test still reading it would have passed.
It failed precisely because it was reading the isolated corpus instead.

**Independently confirmed:** `backend/data` was last written at 13:59, before the
suite runs at 18:05 and later. The suite leaves the real corpus untouched.

### 2.2 `frontend/public/favicon.ico` (new)

Listed in spec §14's folder structure and never created, so `frontend/public/`
was empty. Generated at 256 px and saved as a multi-resolution `.ico`
(16/24/32/48/64/128/256). The generator was a throwaway script, run once and
deleted — it is not part of the project.

`index.html` declares the icon explicitly rather than relying on the browser's
implicit `/favicon.ico` request. In production the backend serves the SPA
catch-all, so an undeclared icon request returns `index.html` with HTTP 200 and
`text/html`: the browser falls back to its default while the request looks
successful. Verified in production: `GET /favicon.ico` → 200, `image/x-icon`,
13,404 bytes.

### 2.3 One version, one place

`"1.0.0"` appeared independently in `main.py`, `routers/health.py` and
`frontend/package.json`, and `test_monitoring.py` asserted the health value as a
literal. A release bump was four edits that had to agree, and the first missed
one would make `/api/health` report a version the process is not running — the
exact failure that field was added to expose.

`backend/app/__init__.py` now holds `__version__`, read by both backend sites.
Two tests guard it: one asserts the health response equals `app.__version__`,
the other that the FastAPI app agrees. `frontend/package.json` necessarily keeps
its own copy; the CHANGELOG records that they are reconciled at release time.

### 2.4 Harnesses that run on any machine

`.day2/perf_coldstart.ps1` hard-coded `C:\RAGPDFQABOT\pdf-rag-chatbot\backend`
and a log path; `.day2/security_probe.py` hard-coded `C:\RAGPDFQABOT\day2_pwned.pdf`
and `C:\Windows\Temp`. Both are published as the evidence behind Day 2's numbers,
on the stated grounds that a measurement nobody can re-run is an assertion — and
neither would have run anywhere else.

Paths now derive from each script's own location, the PowerShell harness fails
with an actionable message if the virtual environment is missing, and the
traversal probe resolves the system temp directory rather than assuming it.

**Correcting the Day 4 record.** `POSTCODING_DAY_04_RELEASE.md` §1.6 states
"Eight lines across four documents contain `C:\RAGPDFQABOT\…`". The sweep behind
that sentence covered `docs/` only; the same commit published two `.day2/`
scripts that also contained them. After this day's change, **no executable file
in the repository contains a machine-specific absolute path**, and the remaining
occurrences are nine lines across five `docs/` files, all of them historical
narrative published deliberately.

### 2.5 Lint cleanliness restored — the claim was false, not just stale

The audit could not verify the README's "ruff clean, mypy clean, prettier clean"
and recorded it as insufficient evidence. Re-running settled it: **ruff reported
two errors**, both pre-existing from Day 5 —

- `app/main.py:90` — 103 characters against the configured 100-column limit.
- `tests/test_monitoring.py:15` — `RequestLoggingMiddleware` imported and unused.

The first was wrapped. For the second, deleting the import would have satisfied
the linter; instead it now has a test asserting the class is present in
`app.user_middleware`. The two existing middleware tests observe log records,
which would also pass if some other logger emitted a matching line — this one
asserts the wiring itself.

### 2.6 New tests for specified-but-unasserted ingestion outcomes

**New: `backend/tests/test_ingestion_pipeline.py`** — seven tests running the
real pipeline against a private store and database:

| Test | Specification |
|---|---|
| `test_scanned_pdf_reaches_ready_via_ocr` | §32 "zero native text but readable scanned pages still reaches 'ready'" |
| `test_scanned_pdf_chunks_are_tagged_ocr` | §32 "chunks correctly tagged with extraction_method" |
| `test_mixed_document_tags_each_page_by_how_it_was_read` | §20 mixed native/scanned stress case |
| `test_document_with_no_text_at_all_is_marked_failed` | §32 "zero text from both methods is correctly marked 'failed'" |
| `test_failure_message_names_the_upload_not_the_storage_path` | §11 information disclosure, on the failure path |
| `test_large_native_document_ingests_every_page` | §20 15+ page stress case |
| `test_repeated_header_document_is_not_stripped_to_nothing` | §5.1 header-stripping guard |

### 2.7 Dependency upgrades

`react-router-dom` 6 → 7.18.4, `vite` 5 → 8.3.0, `@vitejs/plugin-react` 4 → 6.
Reasoning and verification in §3.1.

---

## 3. Hardening

### 3.1 Dependency audit — the first time it has been run

**Python.** `pip-audit` against `backend/requirements.txt` reports **nine unique
advisories in two transitive packages**. None of the 14 direct pins is affected.
Each was traced to the code path it requires, with the check recorded rather
than asserted:

```
grep -rn "HttpClient|chromadb.server|trust_remote_code" backend/app/   -> no matches
grep -rn "chromadb\."                 backend/app/  -> PersistentClient only
grep -rn "Trainer|save_pretrained|from_pretrained|AutoModel" backend/app/ -> no matches
embedder.py:23                                      -> SentenceTransformer(EMBEDDING_MODEL)
```

| Package | Advisories | Verdict |
|---|---|---|
| `chromadb` 1.5.9 | PYSEC-2026-311, ‑3813, ‑3814, ‑3815 | **Not reachable.** All four are vulnerabilities in the ChromaDB *server* — its HTTP collection endpoints with `trust_remote_code`, and its `SimpleRBACAuthorizationProvider`. This project embeds `PersistentClient`: no server, no HTTP API, no auth provider. **No fix is published at any version**, so there is nothing to upgrade to. |
| `transformers` 4.57.6 | PYSEC-2025-217, ‑2026-2288, ‑2289, ‑2290, ‑3929 | **Not reachable, with one condition.** They need `Trainer`, `save_pretrained`, X-CLIP conversion or LightGlue loading; the app calls none of them. PYSEC-2026-2289 (malicious `config.json` → RCE at load) becomes reachable **if `EMBEDDING_MODEL` points at an untrusted repository**. Fixed in transformers 5.3.0, a major version `sentence-transformers` 3.0.1 does not support. |

**Mitigation taken for the one conditional item:** `EMBEDDING_MODEL` is now
documented as security-relevant in `.env.example` and in the README's Security
section, naming the advisory and the condition. That is an operator control, not
a code fix, and it is described as such.

**JavaScript.** `npm audit` reported 4 vulnerabilities (1 high, 3 moderate).
They had been deferred since Day 2 because every fix was a breaking major. Both
halves of that reasoning were re-checked against the code — every `to=` in the
app is a hard-coded literal so no user input reaches a navigation target, and
there is no SSR — and both held. But "unreachable" is weaker than "fixed" when
the fix turns out to be affordable, and `App.jsx` already set the v7 future
flags, so the codebase was written for the upgrade.

**Result: 4 → 0.** `npm audit` reports `found 0 vulnerabilities`. Verified by a
clean build, the full 54-check UI matrix, and zero console errors on the
upgraded stack.

### 3.2 Monitoring: alerting added, dashboard declined

**New: `scripts/health-monitor.ps1`.** Polls `/api/health` and alerts on the
three symptoms a user would feel — unreachable, `degraded`, or slower than a
threshold — with a desktop notification and one JSON line per check appended to
a log, queryable with the same tooling as the application's production logs.
`-Once` mode exits non-zero on an alert, which is the shape a scheduler wants.

**A dashboard is deliberately not provided.** Prometheus and Grafana would be
more infrastructure than the single-user loopback service they watch. Checklist
item 25 names "dashboard and alerts configured"; this delivers the alerts and
declines the dashboard **with the reason recorded**, which is the professional
handling of a requirement that does not fit — not a claim that the item is
closed.

The Task Scheduler registration command is documented in the script's help
rather than executed: registering a scheduled task changes machine state outside
the project.

### 3.3 Secret scan

Re-run over the tree. The only `C:\Users\` match in any tracked file is prose in
`POSTCODING_DAY_04_RELEASE.md` describing the pattern list of the sweep itself.
No credential, token or key in any tracked file. `gitleaks` was not run — the
same tooling caveat the audit recorded stands, and the pattern sweep's result is
reported as a pattern sweep's result.

### 3.4 Performance — the two missing numbers

**New: `.day6/perf_throughput_memory.py`.** Hardware as §0.

| Measurement | Idle | During a 94.9 s generation |
|---|---|---|
| `GET /api/documents` | **129.5 req/s** — p50 5.98 ms, p95 15.18 ms, p99 18.34 ms, 0 errors | **82.8 req/s** — p50 7.10 ms, p95 20.74 ms, p99 44.11 ms, 0 errors |
| `GET /api/health` | **8.5 req/s** — p50 110.27 ms, p95 168.02 ms, p99 280.31 ms | — |

The second column is the one that matters. Day 2 found a defect where handlers
declared `async def` while doing blocking work froze every other request for the
full duration of a question. They are `def` now and run in the threadpool; under
the real model, reads keep flowing at 64% of idle throughput with zero errors.

`/api/health` is slower by design — a real HTTP call to Ollama, a ChromaDB
heartbeat, a SQLite query and a Tesseract subprocess spawn. It is a diagnostic,
not a liveness ping, and the API reference now says so with the measurement.

**Memory floor**, sampled between bursts across five cycles of three
ingest-and-delete rounds plus fifty reads:

```
145.7 -> 146.3 -> 146.6 -> 146.9 -> 147.2 MB     (+1.5 MB over 5 cycles)
```

A flat floor, not a rising one. No leak observed.

**What is still not measured, and why.** Concurrent multi-client throughput of
`/api/chat/ask`. The answer path is bounded by local CPU generation at 25–170 s
per question, so a concurrency figure would measure Ollama's queueing rather
than this service. What that concurrency would have been asked to prove — that
the service stays responsive during a generation — is measured directly above.

---

## 4. Verification

### 4.1 Functional testing and the clean-state gate, together

`backend/data` was **deleted entirely** — uploads, ChromaDB and the SQLite file —
and the backend cold-started from nothing. It recreated all three at import and
served an empty catalogue.

`.day6/functional_probe.py` then walked spec §32 over HTTP against that empty
system, with real Ollama, real Tesseract and real ChromaDB: **42 checks, 42
passed, 0 failed.** Transcript: `.day6/functional_probe_results.txt`.

Covered: health fields; upload rejection on extension, declared MIME, empty body
and over-size, plus the 19 MB boundary being *accepted* so the limit is a limit
and not a blanket refusal; native ingestion; scanned ingestion reaching `ready`
with `ocr_pages_count = 1`; a mixed document OCR-ing 2 of 4 pages; `no_text.pdf`
reaching `failed` with a message that mentions OCR and discloses no path or id;
list/get/delete and both 404s; empty, whitespace and over-length questions;
a grounded cited answer; an OCR-only answer whose citation carries
`extraction_method: "ocr"`; a "not found" answer for an unanswerable question;
and delete removing the vectors as well as the row.

> **One process-level trap worth recording.** The first attempt at this gate was
> invalid: a backend from earlier in the session was still holding port 8000, so
> the "cold start" was answered by the old process — visible only because
> `uptime_seconds` reported 5197 s on a supposedly fresh start, and the real
> cold-start process had exited with "address in use". This is the same trap the
> Day 1 record noted. The number that exposed it is the one Day 5 added.

### 4.2 UI/UX — 8 states × 3 breakpoints

**New: `.day6/ui_state_matrix.py`** (Playwright). **54 checks, 54 passed.**
24 captures in `docs/ui-verification/`.

| | 375 px | 768 px | 1280 px |
|---|---|---|---|
| `documents-empty` | ✅ | ✅ | ✅ |
| `documents-error` | ✅ | ✅ | ✅ |
| `documents-uploading` | ✅ | ✅ | ✅ |
| `documents-ready` (OCR badge + count) | ✅ | ✅ | ✅ |
| `chat-empty` | ✅ | ✅ | ✅ |
| `chat-loading` | ✅ | ✅ | ✅ |
| `chat-answered` (citations) | ✅ | ✅ | ✅ |
| `chat-error` (Retry) | ✅ | ✅ | ✅ |

Beyond the captures, each state is checked mechanically: horizontal overflow is
`scrollWidth` against viewport width (0 px at every state and width), keyboard
focus reaches the composer on the first Tab, the OCR badge and per-document OCR
count render, and the failed turn offers Retry rather than vanishing.

**Console errors: zero**, in every state the application is expected to succeed
in. Three `503` lines are logged in the `chat-error` states, where the harness
*injects* the failure — the browser reporting the response the test asked for.
Those are recorded separately rather than counted, because the alternative is
either reporting a defect that does not exist or weakening the check until it
proves nothing.

Two harness defects were found and fixed while building this, both worth
recording because both would have produced green-looking evidence:

1. **A check that could not fail.** The loading assertion was
   `any(w in body for w in ("Searching", "Thinking", "Reading", "s", "…"))` —
   `"s"` matches almost any page. Replaced with the indicator's actual copy.
2. **A capture that photographed the wrong thing.** Holding the response open
   with `time.sleep()` inside a Playwright sync route handler blocks the thread
   that drives the page, so React never re-rendered and the indicator was absent
   from the screenshot. The corrected version leaves the request genuinely
   pending, then releases it with a normal answer — aborting also works but makes
   the browser log `ERR_FAILED`, a console error the application never caused.

### 4.3 Integration

Frontend ↔ backend verified through the real Vite proxy in development and
same-origin in production, with the network panel observed rather than assumed.

One hypothesis investigated and **disproved by measurement**: `vite.config.js`
proxies to `http://localhost:8000` while the backend binds IPv4-only, which is
the exact IPv6-resolution trap the project measured and fixed for
`OLLAMA_BASE_URL` (2,065 ms vs 8.3 ms). Measured through the proxy: 13–27 ms,
against 9–28 ms direct. **No penalty; no change made.** Recorded because the
change would have looked reasonable and been unjustified.

### 4.4 Regression

Full suite after every change. **185 passed, 0 failed** (175 → 185). No test was
deleted, skipped, weakened or rewritten.

| Module | Tests | | Module | Tests |
|---|---|---|---|---|
| `test_llm_service.py` | 72 | | `test_ingestion_pipeline.py` | 7 **(new)** |
| `test_api.py` | 21 | | `test_chunker.py` | 6 |
| `test_production_mode.py` | 21 | | `test_ocr_processor.py` | 5 |
| `test_config_validation.py` | 17 | | `test_embedder.py` | 4 |
| `test_text_cleaner.py` | 10 | | `test_concurrency.py` | 3 |
| `test_monitoring.py` | 10 | | `test_retriever.py` | 9 |

### 4.5 Build verification

`npm run build` on vite 8, from a removed `dist/`: **0 errors, 0 warnings**,
1,565 modules, `index.js` 260.16 kB (87.78 kB gzipped), `index.css` 16.37 kB
(4.12 kB gzipped), `index.html` 0.92 kB, favicon copied to the bundle root.

Against the previous build (248.88 kB JS / 17.99 kB CSS on vite 5): JS +11.3 kB
for a major router version, CSS −1.6 kB. Both explainable; no unexpected jump.

### 4.6 Production smoke test

Served by `APP_ENV=production` on `127.0.0.1:8000` — one process, the built
bundle, no Vite.

| # | Check | Result |
|---|---|---|
| 1 | `GET /api/health` | 200, `status: ok`, `version: 1.1.0`, all five dependencies up |
| 2 | `GET /` | 200 `text/html` — the built shell |
| 3 | `GET /documents` (client route refresh) | 200 `text/html` — no 404 |
| 4 | `GET /favicon.ico` | 200 `image/x-icon`, 13,404 bytes |
| 5 | `GET /assets/*` | 200, correct types, exact byte counts |
| 6 | `/docs`, `/redoc`, `/openapi.json` | The 923-byte SPA shell — no schema, no Swagger |
| 7 | `GET /api/nope` | 404, not the shell |
| 8 | Traversal: `../../../secret.txt`, `assets/../../package.json`, `..%2f..%2fREADME.md` | All 923-byte shell; grep for `"dependencies"` and the README heading finds nothing. Contained. |
| 9 | Golden path in a browser | Question → cited answer, OCR badge, page number, match strength. Zero console errors; every request 200, same-origin, no CORS preflight |

---

## 5. Documentation reconciled

### 5.1 README

Phase E row added to the status table and the "monitoring has not been done"
sentence replaced with a precise statement of what monitoring *is* (structured
logs, request logging, five-dependency health, scheduled alerting) and what it
is not (no dashboard, no time-series store). Test counts corrected to 185 across
12 modules. All 20 environment variables listed. Structure tree regenerated.
Health response corrected. Measured throughput and memory added. A **Security**
section added covering the dependency audit with its per-advisory reasoning, the
controls that exist and the ones that deliberately do not.

### 5.2 `docs/API_REFERENCE.md`

The health section described a response with four dependency fields and a gate
that excluded the database. It now documents all five, plus `uptime_seconds` and
`version`, each with what it is for, and carries the measured cost. `GET /`
documents both of its behaviours.

### 5.3 `CHANGELOG.md`

A `[1.1.0]` entry added. Two statements in the `[1.0.0]` entry corrected: it
claimed "146 tests across 9 modules" where the tagged tree had 167 across 10,
and listed `/docs` being open as a known limitation when the same release had
closed it. The two dependency-audit limitations are marked closed in 1.1.0
rather than deleted, so the history stays readable.

---

## 6. Release

**Version 1.1.0.** Semantic versioning: the health response gained fields, which
is a backwards-compatible addition, so MINOR. `v1.0.0` is left exactly where it
is — the owner's instruction was to avoid unnecessary version history changes,
so this is additive rather than a re-tag.

`backend/app/__init__.py` and `frontend/package.json` both read 1.1.0, and
`/api/health` confirmed `version: "1.1.0"` on the running production process.

---

## 7. Repository audit

Against §10 of `09_10_Day_GitHub_Upload_Schedule.pdf`:

| Check | Result |
|---|---|
| Tracked file count | **166** (124 at the end of Day 4, +24 UI captures, +12 harnesses and records, +6 new source/test files) |
| `.env` tracked? | absent ✅ — only `backend/.env.example`; `git check-ignore -v backend/.env` names `.gitignore:59` |
| Anything under `backend/data/`? | absent ✅ |
| `.venv/`, `.venv-tools/`, `node_modules/`, `dist/` | absent ✅ |
| `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/` | absent ✅ |
| `.day2/backup/`, `.day6/backup/`, `*.before-day6` | absent ✅ |
| `PROJECT_COMPLETE_AUDIT_REPORT.pdf` | absent ✅ — ignored deliberately |
| Playwright browsers (`.venv-tools/ms-playwright`) | absent ✅ |
| 8 fixture PDFs | present ✅ |
| `package-lock.json`, `.env.example`, `.gitignore`, `.gitattributes` | present ✅ |
| Résumé / interview / portfolio material | **none — out of scope and none created** ✅ |

---

## 8. Known open items

| # | Item | Why it is open |
|---|---|---|
| 1 | **Nothing is pushed.** 40 commits and both tags are local | The owner's instruction is that no push happens without explicit authorisation. The commands are in §9. |
| 2 | **The clone-and-follow-the-README verification has not been done** | It needs a directory *outside* the project folder, which this session is not permitted to create without explicit approval, and it cannot meaningfully run before the push. This is the one item both reference documents call the real test of the documentation, and it is genuinely unmet. |
| 3 | **Repository visibility unconfirmed** | Only the owner can see whether the GitHub repository is private. It must stay private until the final audit passes. |
| 4 | **No metrics dashboard** | Declined deliberately, §3.2. |
| 5 | **Nine unfixable-in-place CVEs in two transitive packages** | Each traced to an unreachable code path; six have no published fix at any version. §3.1. |
| 6 | **`gitleaks` not run** | Not installed; the pattern sweep's result is reported as what it is. |
| 7 | **No CI, no coverage figure** | Neither is required by the reference documents. |
| 8 | **Phase F (portfolio, résumé, interview preparation)** | Excluded from this day's scope by instruction. |

---

## 9. To publish

Nothing has been sent to the remote. When authorised:

```powershell
cd C:\RAGPDFQABOT\pdf-rag-chatbot
git push origin main
git push origin v1.0.0
git push origin v1.1.0
```

Then, and only then, the item-2 verification becomes possible:

```powershell
git clone https://github.com/niyatikadia/Rag-PDF-QA-Bot.git C:\ragclone
# follow README.md from scratch, without improvising, and treat every
# question it fails to answer as a documentation defect
```

---

## 10. Final status

| Stage | Verdict |
|---|---|
| **1. Functional testing** | **PASS** — 42/42 against a wiped system, real model, real OCR |
| **2. Integration testing** | **PASS** — dev proxy and production single-origin, traffic observed; one hypothesis disproved by measurement |
| **3. Regression testing** | **PASS** — 185/185, nothing weakened |
| **5–7. Clean-state gate** | **PASS** — `backend/data` deleted entirely, cold start, full journey from nothing |
| **8. Performance** | **PASS** — throughput and memory floor measured, both gaps closed |
| **9. Security** | **PASS with recorded residue** — npm 4 → 0; nine Python advisories audited for the first time, each traced to an unreachable path, one operator control documented |
| **10. UI/UX** | **PASS** — 54/54, 24 captures, 0 px overflow, zero console errors |
| **11. Configuration** | **PASS** — 20 read / 20 documented / 20 in the README |
| **12. Code quality** | **PASS** — ruff, mypy (21 files), vulture, eslint, prettier all clean, re-run on the final tree |
| **13. Documentation** | **PASS** — six contradictions removed, every claim traced to code or a recorded measurement |
| **15. Build** | **PASS** — 0 errors, 0 warnings, artifact verified running |
| **17. Release** | **PASS** — 1.1.0, CHANGELOG written, versions reconciled |
| **20. Production smoke test** | **PASS** — 9 checks including traversal containment and the golden path |
| **21. Monitoring** | **PARTIAL** — alerting added, dashboard declined with the reason recorded |
| **14. Reproducibility** | **PARTIAL** — the suite is now self-contained; the fresh-clone check remains open (§8 item 2) |

| Metric | Value |
|---|---|
| Audit findings addressed | **24 fixed, 3 declined by instruction, 5 open with reasons, 4 out of scope** |
| Defects found and fixed | **6** (2 lint, 1 test-isolation, 2 harness, 1 stale API doc) |
| Tests before / after | **175 → 185** (+10) |
| Tests deleted, skipped or weakened | **0** |
| npm vulnerabilities | **4 → 0** |
| Python advisories | **0 audited → 9 audited and triaged** |
| New dependencies in `requirements.txt` | **0** |
| Verification checks run this day | **42 + 54 + 9 + 185 = 290** |

*End of Day 6. Nothing was pushed. No résumé, interview or portfolio material
was produced.*
