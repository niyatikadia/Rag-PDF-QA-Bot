# Post-Coding Day 4 — Phase D: Release

**Date:** 15–17 September 2026
**Phase:** D — Release (stages 16–19 of `01_After_Coding_Is_Complete.pdf`)
**Scope:** Version control → Release & versioning → Deployment preparation → Deployment.

> This document records **Day 4 only**. No Phase E–F work (production smoke
> testing, monitoring, maintenance, portfolio, resume, interview preparation)
> was performed; those items appear in §8 as *deferred*, not as results. Day 1's
> record is `POSTCODING_DAY_01_VERIFICATION.md`, Day 2's is
> `POSTCODING_DAY_02_HARDENING.md`, Day 3's is
> `POSTCODING_DAY_03_CONSOLIDATION.md`.

**Starting state (end of Day 3):** 146 tests passing, repository at 2 commits
with every source file untracked, no CHANGELOG, no tag, not deployed.

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
| Remote | `github.com/niyatikadia/Rag-PDF-QA-Bot` |

### 0.1 A note on what this day did *not* start from

The instruction for the day described Days 2 and 3 as not yet done. They were:
`POSTCODING_DAY_02_HARDENING.md` (11–12 September) and
`POSTCODING_DAY_03_CONSOLIDATION.md` (13 September) already existed. Rather than
re-running two days of work against already-patched code, the records were
**verified instead of trusted**: every one of the nine Day 2 fixes was confirmed
present in the working tree, and the suite was re-run green at 146. Only then
did Day 4 begin. That check is recorded here because "the document exists" and
"the fix exists" are different claims.

---

## 1. Stage 16 — Version control

### 1.1 What the repository looked like at the start

Two commits — `.gitignore` and `README.md`, matching Day 1 of the upload
schedule — and **138 untracked entries** covering the entire application. The
remote existed and local `main` was level with `origin/main`.

### 1.2 The history that was built

**26 commits, in dependency order**, following the layering in
`09_10_Day_GitHub_Upload_Schedule.pdf` §11 rather than a single "initial commit".
The ordering principle is bottom-up by actual import: configuration before the
modules that read it, services before the routers that call them, tests after
the code they test.

| # | Layer | Commits |
|---|---|---|
| 1 | `.gitignore` correction (see §1.3) | 1 |
| 2 | Configuration and dependencies | 2 |
| 3 | Data layer | 1 |
| 4 | Document services + helpers | 3 |
| 5 | AI and retrieval services | 2 |
| 6 | API layer — backend becomes runnable | 1 |
| 7 | Tests, fixtures, tooling config | 3 |
| 8 | Frontend build config and entry point | 2 |
| 9 | Frontend API client, chat, documents, lint config | 4 |
| 10 | `.gitattributes` | 1 |
| 11 | Documentation — sessions, references, post-coding records | 3 |
| 12 | Post-coding harnesses (`.day2/`, `.day3/`) | 1 |
| 13 | Tooling exclusion, README link fix | 2 |

Commit messages are in the imperative mood and state **why**, not what a diff
already shows. The API-layer commit records why the handlers are `def` rather
than `async def`; the configuration commit records the measured 2,047 ms IPv6
penalty behind the `127.0.0.1` default.

### 1.3 VC-1 — user data sat outside every `.gitignore` rule

**Severity: high.** The one defect on this day that would have been irreversible
if it had been pushed.

**Reproduced.** Before staging anything:

```powershell
git check-ignore -v .day2/backup/data_baseline/pdf_chatbot.db
# exit 1 — NOT IGNORED
git check-ignore -v .day2/backup/data_baseline/chroma_db/chroma.sqlite3
# exit 1 — NOT IGNORED
git check-ignore -v .day2/backup/data_baseline/uploads/<uuid>.pdf
# exit 1 — NOT IGNORED
```

**What it was.** `.day2/backup/data_baseline/` held a copy of the live corpus —
the SQLite row store, the ChromaDB vectors and **3 real uploaded PDFs**, 0.9 MB
in total — taken during Day 2 so the baseline could be restored after
destructive probes.

**Root cause.** `.gitignore` excludes `backend/data/uploads/`,
`backend/data/chroma_db/` and `backend/data/*.db` **by path**, not by content.
The Day 2 backup is the same data under a different path, so every rule missed
it. The never-upload list was correct and was simply not reached. A `git add .`
would have committed user documents and a vector store.

**Fixed.** `.day2/backup/` excluded, together with the stale source copies kept
for diffing (`*.day2fix`, `*.before-day3`) and captured stdout (`.day2/*.out`).

**Re-verified.**

```
IGNORED  .gitignore:39:.day2/backup/   .day2/backup/data_baseline/pdf_chatbot.db
IGNORED  .gitignore:39:.day2/backup/   .day2/backup/data_baseline/chroma_db/chroma.sqlite3
IGNORED  .gitignore:39:.day2/backup/   .day2/backup/data_baseline/uploads/<uuid>.pdf
IGNORED  .gitignore:40:*.day2fix       .day2/chat.py.day2fix
IGNORED  .gitignore:41:*.before-day3   .day3/package.json.before-day3
IGNORED  .gitignore:42:.day2/*.out     .day2/backend_slowdep.out
```

Untracked entries fell from 138 to 121, and the final audit (§1.6) confirms
nothing under `.day2/backup/` is tracked.

### 1.4 VC-2 — the README's specification link 404s

**Severity: low.** `README.md` linked to `../PROJECT_SPECIFICATION_v2.md`, which
lives one level above the repository root and is deliberately unpublished. The
schedule PDF (§1, §10) flagged this as a decision to take explicitly.

Day 3 had already documented it honestly — the README said the link would be
dead — but documenting a broken link still leaves a stranger a link to click.
The document is now named in plain text with the reason it is absent. The
specification itself was **not** copied into the repository: the decision is to
keep the repository containing exactly the application.

### 1.5 The `.day2/` and `.day3/` decision

Day 2 §9 item 13 deferred this to Day 4. **Decided: publish the harnesses,
exclude three categories.**

Published, because the POSTCODING records cite these files as the source of
their measurements, and a measurement nobody can re-run is an assertion. 33
scripts and transcripts.

Excluded: `backup/` (user data, §1.3), `*.day2fix` and `*.before-day3` (stale
copies of application source — the real files are tracked, and duplicates of
them in the repository would mislead a reader), and `.day2/*.out` (captured
server stdout, the same category as the already-ignored `*.log`).

Before publishing, the transcripts were checked for content rather than assumed
harmless: `uploaded_ids.txt` holds UUIDs only, `gen_warm.txt` holds generic test
questions and timings, `recheck_fence.txt` holds refusal sentences. No document
text, no personal data.

`.claude/launch.json` is **not** published — it is agent tooling configuration,
the same category as the already-excluded `.vscode/` and `.idea/`.

### 1.6 Pre-push audit

Run before anything left the machine, against the schedule PDF §10 checklist.

| Check | Result |
|---|---|
| Tracked file count | **124** — low hundreds, as expected |
| `.env` tracked? | absent ✅ |
| Anything under `backend/data/`? | absent ✅ |
| `.venv/`, `node_modules/`, `dist/` | absent ✅ |
| `__pycache__/`, `.pytest_cache/` | absent ✅ |
| `.day2/backup/`, `*.day2fix`, `*.before-day3` | absent ✅ |
| `.claude/` | absent ✅ |
| 8 fixture PDFs | **present, all 8** ✅ |
| `package-lock.json`, `.env.example`, `.gitignore`, `.gitattributes` | present ✅ |
| Largest tracked file | `package-lock.json`, 194 KB — nothing oversized |

**Secret sweep — two passes, both clean:**

| Pass | Scope | Patterns | Result |
|---|---|---|---|
| Working tree | 88 files staged for commit | `sk-`, `ghp_`, `github_pat_`, `AKIA…`, private-key headers, `api_key=`, `password=`, `secret=`, `token=` | **0 matches** |
| Full history | `git log --all -p`, every commit and diff | same, plus `C:\Users\` | **0 matches** |

**Documents reviewed before publication.** The 16 markdown files in `docs/` were
swept for personal data, credentials and machine paths rather than skimmed. The
`credential` hits are all prose about the project *not having* any; the two
`TODO` hits are historical narrative in a session record describing past state,
not open work. Eight lines across four documents contain `C:\RAGPDFQABOT\…` —
a drive-root project folder that discloses no username and no personal directory
structure. Published deliberately.

> **Correction (post-coding Day 6).** That sweep covered `docs/` only. The same
> commit also published `.day2/perf_coldstart.ps1` and `.day2/security_probe.py`,
> both of which hard-coded absolute paths from this machine — so the count above
> was an undercount of the repository, not just of the documents. The two scripts
> now derive their paths from the checkout (Day 6 §2.4), and no executable file
> in the repository contains a machine-specific absolute path. The remaining
> occurrences are nine lines across five `docs/` files, still published
> deliberately. See `POSTCODING_DAY_06_COMPLETION.md` §2.4.

### 1.7 Not pushed

**The commits were built and audited locally; the push was deliberately not
run.** The schedule PDF §0 offers "stage locally, push once" as an explicit
alternative, and that is what was chosen when the push was put to the repository
owner before anything left the machine. The history is complete and the audit
passed; publishing it is two commands (§9). The day added five further commits
after this audit — release, deployment and documentation — for **31** in total,
all held the same way.

---

## 2. Stage 17 — Release and versioning

**Version 1.0.0**, semantic versioning. First release, so the whole feature set
is *Added*.

`CHANGELOG.md` was created — the project had none — in Keep a Changelog format:

- **Added** — the feature set, grouped by ingestion, retrieval and generation,
  API, interface, and configuration/tests/documentation.
- **Fixed** — the nine defects found during Days 1–2. These are listed with an
  explicit caveat that they never reached a released version: they are there
  because the evidence behind each is in the repository. Presenting pre-release
  fixes as if they were fixes *to* a release would be dishonest.
- **Known limitations** — the six carried into the release deliberately,
  including the two genuine gaps Day 2 recorded as unmet rather than passed.

`frontend/package.json` and the two root entries in `package-lock.json` moved
from `0.1.0` to `1.0.0` so the declared version matches the tag. A third
`"version": "0.1.0"` at line 5797 belongs to the `yocto-queue` dependency and was
checked and left alone.

**Tag:** `v1.0.0`, annotated, **created locally** on the Day 4 record commit.
Tagging is a local operation, so it was completed; only publishing it to the
remote is held with the push (§9). The message names what the release is, the
module and test counts, the four post-coding phases behind it, and points at
`DEPLOYMENT.md` for the hosting constraint and the rollback plan.

---

## 3. Stage 18 — Deployment preparation

The artifact is `docs/DEPLOYMENT.md`. Its contents, against the PDF's list:

### 3.1 Target decision

**Self-hosted on the machine that runs the models, as one process.**

The PDF is explicit that "a service that needs a local GPU or a large local model
cannot go on a free hobby tier", and that is the binding constraint here. The
options were evaluated rather than assumed:

| Option | Verdict |
|---|---|
| Free PaaS (Render / Railway / Fly.io) | **Rejected.** `llama3.2:latest` is 2 GB resident, `llama3.1:8b` 5.6 GB; free tiers offer a fraction. The result would start, pass a health check and fail every question — worse than not deploying, because it would look deployed. |
| Static frontend on Netlify/Vercel + local backend | **Rejected.** The deployed frontend cannot reach a laptop; exposing it would mean publishing an unauthenticated upload endpoint. |
| Docker Compose | **Rejected for now, defensible later.** Docker is not installed, containerising adds a dependency for no behavioural gain on a single-user local service, and 7.89 GB of RAM is already the binding constraint. |
| Managed vector DB + hosted LLM API | **Rejected.** Works, costs money per request, and sends documents off the machine — the opposite of the design. |

### 3.2 Production configuration, separate from development

Four declared differences, none inferred:

| Setting | Development | Production |
|---|---|---|
| `APP_ENV` | `development` | `production` |
| `/docs`, `/redoc`, `/openapi.json` | mounted | **not mounted** |
| Frontend | Vite dev server, proxying `/api` | **served by the backend** from `frontend/dist` |
| `--reload` | on | off |

This closes **Day 2 §9 item 7** ("`/docs` … must be disabled if the service is
ever exposed"), which had been carried as open since Day 2.

### 3.3 Secret management

There are none, and that is a design property rather than an oversight — no paid
services, no external APIs. `.env` remains git-ignored anyway, because the habit
is what protects the next project. Recorded in `DEPLOYMENT.md` §2, with the rule
that any future secret goes in a platform secret store.

### 3.4 Persistence plan

Three directories hold state that must survive a restart —
`backend/data/uploads/`, `backend/data/pdf_chatbot.db`,
`backend/data/chroma_db/` — documented with **what breaks if each is lost
individually**, since they are written independently and are not transactional
with each other. The document notes that the same application in a container
would lose all three on restart without volume mounts.

### 3.5 Rollback plan

One sentence, as the PDF requires: *stop the service, check out the previous
tag, rebuild the frontend, start it again.* Data is untouched because it is not
in the repository. There are no migrations to reverse today — `init_db()` uses
`CREATE TABLE IF NOT EXISTS` on a single table — with an explicit note that this
changes the moment one is added.

### 3.6 Pre-deploy checklist

Seven items, in `DEPLOYMENT.md` §5: tests green, build clean, configuration
present, migrations (none today), backup taken, dependencies running, rollback
target known.

### 3.7 `scripts/start-production.ps1`

Deployment preparation exists so the deploy is boring, so the three failures
that would otherwise be silent are checked before a port is bound: no `APP_ENV`
(docs stay mounted), no built bundle (backend silently serves only the API), no
Ollama (every question returns 503). The first two refuse; the third warns,
because a stopped dependency is already correctly reported as 503.

---

## 4. Stage 19 — Deployment

### 4.1 Executed

```
Pre-flight checks
  ok      virtual environment
  ok      backend\.env present
  ok      frontend bundle present
  ok      Ollama reachable

Starting
  APP_ENV     production (API docs not mounted)
  Frontend    served from frontend\dist
  Address     http://127.0.0.1:8000

2026-09-16 19:35:46 [INFO] app.main: Environment: production | API docs: disabled |
                            Frontend: served from ...\frontend\dist
2026-09-16 19:37:13 [INFO] app.services.embedder: Embedding model loaded.
2026-09-16 19:37:16 [INFO] app.main: Tesseract OCR available: True
INFO:     Uvicorn running on http://127.0.0.1:8000
```

**Build:** `vite build`, clean — 1,576 modules, `index.js` 248.88 kB (82.60 kB
gzipped), `index.css` 17.99 kB (4.15 kB gzipped), 1 m 08 s. Sizes are in line
with the Day 3 build; no unexpected jump.

**Strategy: recreate** (stop old, start new). Chosen because it is a single-user
local service where the seconds of downtime cost nothing, and the alternatives —
rolling, blue-green, canary — all require infrastructure this deployment does
not have and would not benefit from.

### 4.2 Verification

| # | Check | Result |
|---|---|---|
| 1 | `GET /api/health` | **200**, `application/json` — `ollama_available`, `chroma_available`, `embedding_model_loaded`, `ocr_available` all `true` |
| 2 | `GET /` served by the backend | **200**, `text/html`, 404 bytes — the built shell, not Vite |
| 3 | `GET /documents` (client-side route) | **200**, the shell — a refresh on an SPA route does not 404 |
| 4 | `GET /openapi.json` | No schema. Body is the SPA shell; contains no `paths` key and no `/api/chat/ask` |
| 5 | `GET /docs`, `GET /redoc` | Same — 371-byte shell, no Swagger markup |
| 6 | `GET /api/does-not-exist` | **404**, not the shell |
| 7 | Real question in the browser | **Answered correctly with a citation** |

**Check 7 in full**, because a health check proves only that a process is alive:

> **Q:** "What keyword is used for retrieval?"
> **A:** *"According to the retrieved context, the keyword for retrieval testing
> is 'PINEAPPLE' (source: scanned_image_only.pdf, Page 1 [OCR])."*
> 1 source · `scanned_image_only.pdf` · OCR badge · Page 1 · match strength 33%
> · **118.6 s**

Network panel: `GET /api/documents` → 200 and `POST /api/chat/ask` → 200, both
against `127.0.0.1:8000` — same origin, no CORS preflight, confirming the single-
origin deployment. Browser console: **zero errors**.

118.6 s is a cold-model first request after a restart, consistent with the Day 2
cold-start finding (27.6–110.4 s of variance driven by OS file-cache state, over
a 51.2 s warm median). The loading indicator escalated through its 4 s, 12 s,
30 s and 75 s messages as designed.

### 4.3 What "deployed" means here, stated plainly

Production mode, one process, serving both the API and the built frontend on
`127.0.0.1:8000`, API docs not mounted, dev servers stopped, verified with a real
question. It is **not** reachable from any other machine, and that is deliberate:
`--host 127.0.0.1` is the only thing standing between an unauthenticated upload
endpoint and the network.

---

## 5. Defects

Each went through reproduce → diagnose → fix → guard → re-verify.

| # | Defect | Stage | Severity | Reproduced | Fixed | Guarded | Re-verified |
|---|---|---|---|---|---|---|---|
| **VC-1** | Live corpus (SQLite + ChromaDB + 3 real PDFs) matched no `.gitignore` rule | 16 | **High** | `git check-ignore` exit 1 on all three | ✅ `.day2/backup/` + stale-copy rules | pre-push audit | `check-ignore` names the rule; audit confirms untracked |
| **VC-2** | README linked to a file outside the repository — 404 on GitHub | 16 | Low | Link target is one level above root | ✅ named in plain text, not linked | — | No `../` link remains in README |
| **CFG-1** | `FRONTEND_DIST_DIR` read by the code but absent from `.env.example` | 18 | Moderate | Day 2 `config_audit.py` → **FAIL** | ✅ documented and uncommented in both files | the audit itself | **PASS** — 20 read / 20 example / 20 live |
| **DEP-1** | New static handler could read outside the bundle | 18 | **High** (pre-empted) | 2 of 5 payloads escaped with the guard removed | ✅ resolve + `is_relative_to` containment | 6 tests | All 5 payloads contained; positive case still served |

**DEP-1 is a defect I introduced on this day and caught before committing**, not
one found in existing code. Serving the frontend from the backend turns a
user-controlled URL path into a filesystem read. It is recorded at the same
weight as the others because the containment check was proven non-vacuous:
removing `is_relative_to` made `../secret.txt` and `assets/../../secret.txt`
return the sibling file, and restoring it made them fail. Untested security code
is a guess.

### 5.1 Investigated and cleared — not defects

| Observation | Verdict |
|---|---|
| "`vite preview` has no `/api` proxy, so the production build cannot reach the backend" | **Wrong hypothesis, disproved by measurement.** Vite 5's `preview.proxy` inherits `server.proxy`; `GET localhost:4173/api/health` returned 200 JSON. Recorded because it was the starting assumption for the whole deployment design. |
| `vite preview` unreachable on `127.0.0.1:4173` | **Not a defect.** It binds IPv6 `localhost` only. The mirror image of Day 2's PERF-1, and moot in the final deployment, which does not use `vite preview` at all. |
| `/docs` returning 200 in production | **Not a disclosure.** The 200 is the SPA catch-all serving the 371-byte shell. The schema routes are absent from `app.routes`; the body contains no Swagger markup. Asserted on the app object in tests, since a 200 over HTTP proves nothing either way. |
| `"version": "0.1.0"` at `package-lock.json:5797` | **Not the project version** — it is the `yocto-queue` dependency. Left untouched. |

---

## 6. Files changed

### 6.1 Application code

| File | Change | Defect / stage |
|---|---|---|
| `backend/app/config.py` | `APP_ENV` + `IS_PRODUCTION` with validation; `LOG_LEVEL` validated against the five levels; `FRONTEND_DIST_DIR` resolved against `backend/` | 18 |
| `backend/app/main.py` | `docs_url`/`redoc_url`/`openapi_url` `None` in production; log level from config; static mount + SPA fallback with traversal containment and an `/api` 404 guard; startup line naming the mode | 18, DEP-1 |

### 6.2 Configuration

| File | Change |
|---|---|
| `backend/.env.example` | Runtime-environment section documenting `APP_ENV`, `LOG_LEVEL`, `FRONTEND_DIST_DIR`; header 17 → 20 |
| `backend/.env` | Same three added (git-ignored, no secrets) |
| `.gitignore` | `.day2/backup/`, `*.day2fix`, `*.before-day3`, `.day2/*.out`, `.claude/` |
| `frontend/package.json`, `frontend/package-lock.json` | `0.1.0` → `1.0.0` (root entries only) |

### 6.3 Tests — all additions, nothing weakened

| File | Tests | Guards |
|---|---|---|
| `backend/tests/test_production_mode.py` | **+21** (new file) | `APP_ENV`/`LOG_LEVEL` validation (7), CWD independence (2), production app behaviour (6), traversal containment (6) |

**146 → 167. No existing test was deleted, skipped, weakened or rewritten.**

### 6.4 Documentation and tooling

| Path | Purpose |
|---|---|
| `CHANGELOG.md` | **New.** v1.0.0 release entry |
| `docs/DEPLOYMENT.md` | **New.** Target decision, production config, persistence, rollback, pre-deploy checklist, verification |
| `scripts/start-production.ps1` | **New.** Pre-flight-checked production start |
| `docs/POSTCODING_DAY_04_RELEASE.md` | This record |
| `README.md` | Status → released and deployed; "Running in production"; 146 → 167; `/docs` limitation closed; specification link fixed |
| `docs/CONFIGURATION.md` | Runtime-environment section; 17 → 20 |

---

## 7. Commands and tools used

```powershell
# ── Stage 16: version control ───────────────────────────────────────────────
git check-ignore -v <path>                  # ignore-rule attribution, VC-1
git log --all -p | Select-String <9 credential patterns>   # history sweep
git status --porcelain --untracked-files=all
git add <explicit paths>                    # never `git add .`
git commit -F -                             # 30 commits, heredoc messages
git ls-files                                # pre-push audit, 124 files

# ── Stage 17: release ───────────────────────────────────────────────────────
# CHANGELOG.md authored; package.json / package-lock.json 0.1.0 -> 1.0.0

# ── Stage 18: deployment preparation ────────────────────────────────────────
python .day2\config_audit.py                # Day 2 harness, re-run — CFG-1
pytest tests/test_production_mode.py -q     # 21 new tests
# guard removed, tests re-run, guard restored — DEP-1 non-vacuity proof
pytest -q                                   # full suite, 167 passed

# ── Stage 19: deployment ────────────────────────────────────────────────────
npm run build                               # 248.88 kB JS / 17.99 kB CSS
& .\scripts\start-production.ps1            # APP_ENV=production, :8000
Invoke-WebRequest /api/health /  /openapi.json /docs /api/does-not-exist
# In-app Chromium: real question end to end, console and network captured
```

**Tools.** git 2.54.0, npm/vite 5.4.21, pytest, uvicorn, PowerShell, the in-app
Chromium, and Day 2's own `config_audit.py`. **Nothing was installed.** No
`gh` CLI is present on this machine, which is why §9 leaves the push and the tag
as commands rather than claiming them as done.

---

## 8. Known open items

Carried forward. Each is recorded with why it was not closed today.

| # | Item | Why not closed on Day 4 |
|---|---|---|
| 1 | **31 commits and the `v1.0.0` tag exist locally but are not pushed** | Deliberate — the repository owner chose "stage locally, push once", which the schedule PDF §0 offers explicitly. The tag itself *was* created; only publishing is held. The audit passed and §9 has the exact commands. |
| 2 | **Backend dependencies still never audited for CVEs** | Unchanged from Day 2 §9 item 2. `pip-audit`/`safety` are not installed and installing was not approved. Genuinely unmet, not passed. |
| 3 | **6 npm advisories still open** | Unchanged from Day 2 §9 item 1. Every fix is a breaking major upgrade (vite 5→8, react-router-dom 6→7); four are dev-server-only and do not affect `vite build` output, two are unreachable here. Day 3 reviewed and deferred them; that stands. |
| 4 | **No authentication, authorisation or HTTPS** | By design, and now the *only* control is `--host 127.0.0.1`. All three become mandatory before this is exposed to any network. |
| 5 | **No monitoring, no alerting, no uptime check** | Stage 20 — Day 5. The service currently logs to stdout and nothing watches it. |
| 6 | **No production smoke-test suite** | Stage 20 — Day 5. §4.2 is a manual verification run once, not an automated check. |
| 7 | **No backup automation** | `DEPLOYMENT.md` documents the manual copy. Scheduling it is maintenance (stage 21, Day 5). |
| 8 | **Deployment is single-machine and manual** | No CI, no automated deploy. Appropriate to the target; would be the first thing to change if this moved to a server. |
| 9 | **Prompt-injection laundering not closed** | Unchanged from Day 2 §9 item 3. |
| 10 | **`test_retriever.py` coupled to the live ChromaDB store** | Unchanged from Day 1 §9 item 1 / Day 2 §9 item 10. |

---

## 9. To publish

The commits and the tag exist locally; **nothing has been sent to the remote.**
Two commands remain:

```powershell
cd C:\RAGPDFQABOT\pdf-rag-chatbot
git push origin main
git push origin v1.0.0
```

Two things to confirm first, from the schedule PDF §10:

- The repository is **private until the final audit passes**, then made public
  deliberately. §1.6 is that audit; it passed.
- A clone into a fresh directory, followed by the README from scratch, is the
  real test of the documentation. Note the Windows long-path caveat the README
  records — clone somewhere with a short path.

---

## 10. Final status

| Stage | Verdict |
|---|---|
| **16. Version control** | **PASS** — 26 layered commits, 2 defects found and fixed, full audit clean, push held at owner's instruction |
| **17. Release and versioning** | **PASS** — 1.0.0 declared, CHANGELOG written, versions reconciled, annotated `v1.0.0` tag created; publishing held |
| **18. Deployment preparation** | **PASS** — target decided with rejected options recorded, production config separated, persistence and rollback documented, checklist written, 2 defects fixed |
| **19. Deployment** | **PASS** — deployed in production mode and verified end to end with a real question |

| Metric | Value |
|---|---|
| Commits created | **31** (26 application + 5 release/deployment) |
| Tags created | **1** — `v1.0.0`, annotated, local |
| Defects found | **4** |
| Defects fixed | **4** |
| Defects left open | **0** |
| Tests before / after | **146 → 167** (+21) |
| Full suite, final | **167 passed, 0 failed** |
| Tests deleted, skipped or weakened | **0** |
| Tracked files | **124** |
| Secrets committed | **0** (two sweeps, working tree and full history) |
| Known items carried forward | **10** |

**Phase D verdict: PASS**, with publishing to the remote held deliberately at
the owner's instruction and recorded in §8 item 1 as open rather than described
as done.

---

*End of Day 4 — Phase D (Release). Day 5 (Operations and career packaging:
production smoke testing, monitoring, maintenance, portfolio, resume, interview
preparation) not started.*
