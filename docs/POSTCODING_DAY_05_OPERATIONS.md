# Post-Coding Day 5 — Phase E: Operations

**Date:** 17 September 2026
**Phase:** E — Operations (stages 20–21 of `01_After_Coding_Is_Complete.pdf`)
**Scope:** Production smoke test → Monitoring, observability & maintenance.

> This document records **Day 5 only**. No Phase F work (portfolio, resume,
> interview preparation) was performed; those items appear in §6 as *deferred*,
> not as results. Day 1's record is `POSTCODING_DAY_01_VERIFICATION.md`, Day 2's
> is `POSTCODING_DAY_02_HARDENING.md`, Day 3's is
> `POSTCODING_DAY_03_CONSOLIDATION.md`, Day 4's is
> `POSTCODING_DAY_04_RELEASE.md`.

**Starting state (end of Day 4):** 167 tests passing, v1.0.0 tagged locally,
deployed and verified once in production mode, no monitoring, no structured
logging, no request middleware.

---

## 0. Environment

| Item | Value |
|---|---|
| CPU | Intel Core i7-7600U @ 2.80 GHz — 2 physical cores, 4 logical |
| RAM | 7.89 GB total |
| OS | Windows 11 Pro, build 22000 |
| Python | 3.13.3 (`backend\.venv`) |
| Node / npm | v22.23.1 / 10.9.8 |
| Git | 2.54.0.windows.1 |
| Ollama | `llama3.2:latest` (the configured model) |
| Tesseract | 5.5.3.20260724, on PATH |

---

## 1. Stage 21 — Monitoring, observability and maintenance

Stage 21 is executed before Stage 20 so the smoke test runs against the final
production codebase — the enhanced health endpoint, structured logging, and
request middleware are all part of what the smoke test verifies.

### 1.1 Enhanced health endpoint

The existing `GET /api/health` checked Ollama, ChromaDB, embedding model, and
OCR. Three gaps were identified:

1. **No database check.** SQLite is a critical dependency — the document
   catalogue, upload metadata, and processing status all live there. A corrupt
   or locked database file would make the service useless while health reported
   `ok`.

2. **No uptime.** Without knowing how long the process has been running, there
   is no way to distinguish a fresh restart from a stable long-running process,
   and no way to notice silent restarts.

3. **No version.** Without a version field, a health check cannot confirm which
   release is actually running — the classic "I deployed but am I hitting the
   new code?" question.

**Changes to `backend/app/routers/health.py`:**

- Added `_check_database()` — opens the SQLite file at `DATABASE_PATH`, runs
  `SELECT 1`, returns `True`/`False`. Uses the stdlib `sqlite3` module directly
  rather than the application's own database layer, so the check tests the file
  itself, not the cached connection.
- `database_available` is wired into the `all_ok` gate — a database failure
  now makes the status `"degraded"`, not silently `"ok"`.
- `uptime_seconds` is computed from `_STARTUP_TIME` (a `time.monotonic()` value
  recorded at module import in `main.py`). Imported lazily inside the handler
  to avoid a circular import — the same pattern already used at line 25 for
  `get_client`.
- `version` is set to `"1.0.0"`, matching the FastAPI app and `package.json`.

**Changes to `backend/app/models/schemas.py`:**

Three fields added to `HealthStatus`:

```python
database_available: bool
uptime_seconds: Optional[float] = None
version: Optional[str] = None
```

`database_available` is required (no default) so the endpoint cannot silently
omit it — a missing field would be a schema validation error at the router, not
a silent `null` in the response.

### 1.2 Structured logging

The existing logging was plain text via `logging.basicConfig`. This is readable
during development but unparseable by log aggregation tools. Two changes:

1. **`_JSONFormatter`** — a `logging.Formatter` subclass that emits each log
   record as a single-line JSON object with `timestamp`, `level`, `logger`,
   and `message` keys. Exception info is included under `exception` when
   present. Uses only stdlib (`json`, `logging`) — no new dependencies.

2. **`_configure_logging()`** — replaces `logging.basicConfig`. In production
   (`IS_PRODUCTION`), installs the JSON formatter. In development, keeps the
   existing human-readable format. The root logger's handlers are replaced
   rather than appended to, so duplicate output from `basicConfig` is avoided.

**Decision: no external structured-logging library.** `structlog` or
`python-json-logger` would add features (bound context, processor chains) but
also a dependency. The stdlib formatter covers the immediate need — structured
output parseable by `jq`, ELK, or Loki — and can be swapped for a library
later without changing any call site, since every module uses standard
`logging.getLogger(__name__)`.

### 1.3 Request logging middleware

A `RequestLoggingMiddleware` (Starlette `BaseHTTPMiddleware` subclass) that
logs method, path, status code, and duration in milliseconds for every request.
Logs to the `app.access` logger at INFO level.

`/api/health` is excluded to avoid log noise from automated health checks —
a polling monitor hitting health every 30 seconds would otherwise dominate the
log, making it harder to spot real traffic patterns.

Example output (development, plain text):

```
2026-09-17 13:25:58 [INFO] app.access: POST /api/chat/ask 200 87804ms
2026-09-17 13:25:59 [INFO] app.access: GET /api/documents 200 12ms
```

Example output (production, JSON):

```json
{"timestamp": "2026-09-17 13:25:58,130", "level": "INFO", "logger": "app.access", "message": "POST /api/chat/ask 200 87804ms"}
```

### 1.4 Tests

**New file: `backend/tests/test_monitoring.py`** — 8 tests:

| # | Test | Guards |
|---|---|---|
| 1 | `test_health_includes_database_available` | Field present and boolean |
| 2 | `test_health_database_is_reachable` | SQLite actually responds |
| 3 | `test_health_includes_uptime` | Positive number present |
| 4 | `test_health_includes_version` | Matches `"1.0.0"` |
| 5 | `test_health_status_requires_database` | Database is in the ok/degraded gate |
| 6 | `test_request_logging_emits_access_log` | Middleware produces `app.access` records |
| 7 | `test_health_endpoint_is_excluded_from_access_log` | No `app.access` record for `/api/health` |
| 8 | `test_json_formatter_produces_valid_json` | Output is parseable JSON with expected fields |

**Updated: `backend/tests/test_api.py`** — added `"database_available"` assertion
to `test_health_endpoint_exists()`.

**Test count: 167 → 175. No existing test was deleted, skipped, weakened or
rewritten.**

Full suite result:

```
175 passed, 1 warning in 41.60s
```

### 1.5 Maintenance procedures

The following procedures are documented here rather than in a separate file
because they are part of the operations record.

#### Backups

Three data directories hold state that must survive a restart or a disaster:

| Directory | Contents | Command |
|---|---|---|
| `backend/data/pdf_chatbot.db` | Document catalogue, metadata, status | `copy backend\data\pdf_chatbot.db backup\pdf_chatbot.db` |
| `backend/data/uploads/` | Uploaded PDF files | `robocopy backend\data\uploads backup\uploads /MIR` |
| `backend/data/chroma_db/` | Vector embeddings | `robocopy backend\data\chroma_db backup\chroma_db /MIR` |

**Frequency:** before any upgrade, and daily if the service is in active use.
**Verification:** restore into a test directory, start the backend against it,
confirm documents appear and a question returns answers.

An unverified backup is a rumour. The backup procedure is manual; automation
(a scheduled task or cron job) is deferred — see §6.

#### Dependency updates

```powershell
# Python — check for outdated packages
cd backend
.\.venv\Scripts\pip list --outdated

# JavaScript — check for outdated packages
cd frontend
npm outdated
```

Review changelogs before upgrading. Run the full test suite after any change.
Pin the new version in `requirements.txt` or `package-lock.json`.

#### Log review

Logs go to stdout. In production with the JSON formatter, pipe to a file or
log aggregator:

```powershell
& .\scripts\start-production.ps1 2>&1 | Tee-Object -FilePath logs\production.log
```

Watch for:
- `ERROR` or `CRITICAL` entries — immediate investigation
- Repeated `WARNING` from `app.services.llm_service` — Ollama connectivity
- `503` status codes in `app.access` — LLM unavailability reaching users
- Increasing `processing_time_ms` in chat responses — model or retrieval
  performance regression

#### Data cleanup

```powershell
# Orphaned uploads — files in uploads/ with no matching database row
# (can occur if the process is killed mid-ingestion)
.\.venv\Scripts\python -c "
from app.models.database import get_all_documents
from pathlib import Path
import os
known = {d['document_id'] for d in get_all_documents()}
for f in Path('data/uploads').iterdir():
    if f.stem not in known:
        print(f'ORPHAN: {f}')
"
```

#### Health monitoring

Poll the health endpoint on a schedule to detect failures early:

```powershell
# Simple scheduled check (Windows Task Scheduler or manual)
Invoke-WebRequest -Uri http://127.0.0.1:8000/api/health -UseBasicParsing -TimeoutSec 5 |
    Select-Object StatusCode, @{N='Body';E={$_.Content}}
```

A degraded status means at least one service is down. Check the `details`
field and the individual `*_available` booleans to identify which one.

---

## 2. Stage 20 — Production smoke test

The server was started in production mode (`APP_ENV=production`) via:

```powershell
$env:APP_ENV = "production"
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The frontend bundle was built immediately before (`npm run build` — 248.88 kB
JS, 17.99 kB CSS, 0.40 kB HTML).

### 2.1 Endpoint checks

| # | Check | Method | Expected | Actual | Result |
|---|---|---|---|---|---|
| 1 | Health endpoint | `GET /api/health` | 200, `status: "ok"` | 200, `status: "ok"`, all services `true`, `database_available: true`, `uptime_seconds: 56.7`, `version: "1.0.0"` | **PASS** |
| 2 | Document list | `GET /api/documents` | 200, JSON array | 200, JSON array with existing documents | **PASS** |
| 3 | Homepage (SPA) | `GET /` | 200, HTML with `id="root"` | 200, `<!DOCTYPE html>` with `id="root"` | **PASS** |
| 4a | Static JS asset | `GET /assets/index-Rj7hbrdQ.js` | 200, `text/javascript` | 200, `text/javascript; charset=utf-8`, 248,878 bytes | **PASS** |
| 4b | Static CSS asset | `GET /assets/index-DyMymqJN.css` | 200, `text/css` | 200, `text/css; charset=utf-8`, 17,988 bytes | **PASS** |
| 5 | Invalid API path | `GET /api/does-not-exist` | 404 | 404 | **PASS** |

### 2.2 Critical user journey — the golden path

The single most important user journey: upload a PDF, wait for ingestion, ask a
question, receive a cited answer, then delete.

**Step 1 — Upload.**

```
POST /api/documents/upload  (native_single.pdf from test fixtures)
→ 202 Accepted
  document_id: 9570f84c-ee2c-4552-9930-6315f763ca9b
  status: "processing"
```

**Step 2 — Poll until ready.**

```
GET /api/documents/9570f84c-ee2c-4552-9930-6315f763ca9b
→ 200 OK  (first poll, ~2 seconds)
  status: "ready"
  total_pages: 1
  total_chunks: 1
```

**Step 3 — Ask a question.**

```
POST /api/chat/ask
  { "question": "What is this document about?",
    "document_id": "9570f84c-ee2c-4552-9930-6315f763ca9b" }
→ 200 OK
  processing_time_ms: 87804
```

**Step 4 — Verify the answer.**

> This document appears to be a Quarterly Budget Summary, as indicated by the
> title on page 1 of the document "native_single.pdf".

| Field | Value |
|---|---|
| Answer length | 128 characters |
| Citations | 1 |
| Citation file | `native_single.pdf` |
| Citation pages | `[1]` |
| Processing time | 87,804 ms (cold model load included) |

The answer is relevant, cites the correct file and page, and includes
`processing_time_ms`. **PASS.**

**Step 5 — Delete.**

```
DELETE /api/documents/9570f84c-ee2c-4552-9930-6315f763ca9b
→ 200 OK
  "Document deleted successfully."
```

**Step 6 — Verify deletion.**

```
GET /api/documents/9570f84c-ee2c-4552-9930-6315f763ca9b
→ 404 Not Found
```

**PASS.** The document, its vectors, and its uploaded file are gone.

### 2.3 Log review

No `ERROR` or `CRITICAL` entries appeared in the server output during the smoke
test session. The only `WARNING` entries were the expected Tesseract OCR
availability check at startup (present and passing). The request logging
middleware produced `app.access` entries for every non-health request with
correct method, path, status code, and duration.

### 2.4 Smoke test verdict

All 6 endpoint checks passed. The full critical user journey — upload, process,
ask, verify citations, delete, confirm deletion — completed successfully
against the production server. No errors in logs.

**Stage 20: PASS.**

---

## 3. Defects

No defects were found during Day 5. The one test failure encountered during
development (the health-exclusion test matching `httpx` internal logs rather
than `app.access` records) was a test-authoring error caught and fixed before
the code was finalised — it never represented a production defect.

---

## 4. Files changed

### 4.1 Application code

| File | Change | Stage |
|---|---|---|
| `backend/app/models/schemas.py` | +3 fields on `HealthStatus`: `database_available`, `uptime_seconds`, `version` | 21 |
| `backend/app/routers/health.py` | `_check_database()`, `uptime_seconds`, `version` in response; `database_available` in the ok/degraded gate | 21 |
| `backend/app/main.py` | `_STARTUP_TIME`, `_JSONFormatter`, `_configure_logging()`, `RequestLoggingMiddleware` | 21 |

### 4.2 Tests — all additions, nothing weakened

| File | Tests | Guards |
|---|---|---|
| `backend/tests/test_monitoring.py` | **+8** (new file) | Health fields (5), request middleware (2), JSON formatter (1) |
| `backend/tests/test_api.py` | **+1 assertion** | `database_available` in existing `test_health_endpoint_exists` |

**167 → 175. No existing test was deleted, skipped, weakened or rewritten.**

### 4.3 Documentation

| Path | Purpose |
|---|---|
| `docs/POSTCODING_DAY_05_OPERATIONS.md` | This record |

---

## 5. Commands and tools used

```powershell
# ── Stage 21: monitoring code changes ──────────────────────────────────────
# Code edits to schemas.py, health.py, main.py (structured logging, middleware,
# enhanced health). New test file test_monitoring.py.
pytest -q                                  # full suite, 175 passed

# ── Stage 20: production smoke test ────────────────────────────────────────
cd frontend; npm run build                 # 248.88 kB JS / 17.99 kB CSS
$env:APP_ENV = "production"
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Endpoint checks
Invoke-WebRequest /api/health              # 200, status: ok
Invoke-WebRequest /api/documents           # 200, JSON array
Invoke-WebRequest /                        # 200, SPA shell
Invoke-WebRequest /assets/index-Rj7hbrdQ.js  # 200, 248878 bytes
Invoke-WebRequest /assets/index-DyMymqJN.css # 200, 17988 bytes
Invoke-WebRequest /api/does-not-exist      # 404

# Critical user journey
POST /api/documents/upload                 # 202, processing
GET  /api/documents/{id}                   # 200, ready, 1 page, 1 chunk
POST /api/chat/ask                         # 200, cited answer, 87804 ms
DELETE /api/documents/{id}                 # 200, deleted
GET  /api/documents/{id}                   # 404, confirmed gone
```

**Tools.** pytest, uvicorn, npm/vite, PowerShell `Invoke-WebRequest`. **Nothing
was installed.** All changes use Python stdlib — no new dependencies.

---

## 6. Known open items

Carried forward from Day 4. Items 5 and 6 are closed; item 7 is partially
closed.

| # | Item | Status |
|---|---|---|
| 1 | **31 commits and the `v1.0.0` tag exist locally but are not pushed** | Unchanged from Day 4 §8 item 1. Deliberate hold. |
| 2 | **Backend dependencies still never audited for CVEs** | Unchanged from Day 2. `pip-audit`/`safety` not installed. |
| 3 | **6 npm advisories still open** | Unchanged from Day 2. Every fix is a breaking major upgrade. |
| 4 | **No authentication, authorisation or HTTPS** | By design — loopback only. Mandatory before network exposure. |
| 5 | ~~No monitoring, no alerting, no uptime check~~ | **Closed.** Structured logging, request middleware, enhanced health with database check, uptime, and version. |
| 6 | ~~No production smoke-test suite~~ | **Closed.** Stage 20 executed and recorded with full evidence. |
| 7 | **No backup automation** | **Partially closed.** Manual backup procedure documented in §1.5. Scheduling as a Windows Task Scheduler job or cron is deferred. |
| 8 | **Deployment is single-machine and manual** | Unchanged from Day 4. Appropriate to the target. |
| 9 | **Prompt-injection laundering not closed** | Unchanged from Day 2. |
| 10 | **`test_retriever.py` coupled to the live ChromaDB store** | Unchanged from Day 1. |

---

## 7. Final status

| Stage | Verdict |
|---|---|
| **20. Production smoke test** | **PASS** — 6 endpoint checks passed, full critical user journey (upload → process → ask → cited answer → delete → confirm) completed against the production server, no errors in logs |
| **21. Monitoring & maintenance** | **PASS** — enhanced health endpoint (database, uptime, version), structured JSON logging for production, request logging middleware, maintenance procedures documented |

| Metric | Value |
|---|---|
| Defects found | **0** |
| Defects fixed | **0** |
| Tests before / after | **167 → 175** (+8) |
| Full suite, final | **175 passed, 0 failed** |
| Tests deleted, skipped or weakened | **0** |
| New dependencies installed | **0** |
| Known items closed | **2** (items 5, 6) |
| Known items partially closed | **1** (item 7) |
| Known items carried forward | **7** |

**Phase E verdict: PASS.** The system is monitored, its health is observable,
the production smoke test passed end to end, and maintenance procedures are
documented.

---

*End of Day 5 — Phase E (Operations). Day 6 (Career packaging: portfolio
preparation, resume, interview preparation) not started.*
