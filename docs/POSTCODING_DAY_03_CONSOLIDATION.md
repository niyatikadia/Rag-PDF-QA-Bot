# Post-Coding Day 3 — Phase C: Consolidation

**Date:** 13 September 2026
**Phase:** C — Consolidation (stages 12–15 of `01_After_Coding_Is_Complete.pdf`)
**Scope:** Code quality & cleanup → Documentation → Reproducibility → Build verification.

> This document records **Day 3 only**. No Phase D–F work (version control beyond
> preserving current state, release/versioning, deployment preparation, deployment,
> production smoke testing, monitoring, maintenance, portfolio, resume, interview
> preparation) was performed. Day 1's record is `POSTCODING_DAY_01_VERIFICATION.md`;
> Day 2's is `POSTCODING_DAY_02_HARDENING.md`.

**Starting state (end of Day 2):** 144 tests passing, 9 defects found and fixed,
0 left open, 13 known limitations carried forward, corpus at the Day 1 baseline
(3 documents / 3 PDFs / 5 vectors).

---

## 0. Environment

| Item | Value |
|---|---|
| OS | Windows 11 Pro, build 10.0.22000 |
| Python | 3.13.3 (`backend\.venv`) |
| Node / npm | v22.23.1 / 10.9.8 |
| Tesseract | 5.5.3.20260724 (on PATH) |
| Ollama | 0.34.0 |
| Backend | `uvicorn app.main:app` on `127.0.0.1:8000` |
| Built artifact | `vite preview` on `127.0.0.1:4173` |

### 0.1 Tool isolation — why a separate environment

None of the tools stage 12 names were installed. Installing was approved **on condition
they go somewhere other than `backend/.venv`**, because that environment is the one
`requirements.txt` is reconciled against and Day 1/Day 2 verified against; adding six dev
packages to it would have introduced exactly the drift stage 14 exists to detect.

They were installed into `.venv-tools/` at the project root instead. `backend/.venv` was
**not modified on Day 3** — proven by the drift check in §3.2, which found all 14 pins
still matching.

| Tool | Version | Used for |
|---|---|---|
| `ruff` | 0.16.7 | Linting |
| `black` | 26.5.1 | Formatting — **evaluated, deliberately not applied**, see §1.4 |
| `mypy` | 2.3.1 | Type checking |
| `vulture` | 2.16 | Dead-code detection |
| `radon` | 6.0.1 | Complexity / maintainability |
| `prettier` | 3.9.6 | JS/JSX/CSS formatting — **applied** |
| `eslint` | 9.39.5 + `eslint-plugin-react` 7.37.5, `eslint-plugin-react-hooks` 5.2.0 | JS/JSX linting |

`pip-audit` / `safety` were **not** installed, so Day 2's known gap — the 14 Python pins
have never been checked against a CVE database — is **still open**. It is not closed by
this day's work and is not claimed to be.

---

## 1. Stage 12 — Code quality and cleanup

### 1.1 What the tools found

The headline result is that the codebase was already clean on the axes cleanup actually
targets:

| Check | Result |
|---|---|
| `ruff` F-rules — unused imports (F401), unused variables (F841), redefinitions (F811), undefined names (F821) | **0 findings** |
| `ruff` E722 — bare `except:` | **0 findings** |
| `ruff` E711/E712 — `== None` / `== True` | **0 findings** |
| ESLint (correctness + `react-hooks`) over all 15 frontend modules | **0 findings** |
| Commented-out code blocks (manual read of all 21 backend modules) | **none present** |
| `radon cc` — average cyclomatic complexity | **A (3.43)** over 67 blocks |
| `radon mi` — maintainability index | **A on every one of 21 files** |

There was nothing to delete. The four most complex blocks are `_strip_repeated_headers_footers`
(C, 16), `_referenced_chunks` (C, 11), `extract_citations` (C, 11) and `retrieve` (C, 11) —
all moderate, all with a documented reason for their branching, and all left alone because
restructuring them is refactoring, not cleanup.

### 1.2 The one real finding: a type error mypy caught

`mypy` reported 5 errors. Four were missing annotations. The fifth was substantive:

```
app\routers\documents.py:38: error: Item "None" of "str | None" has no attribute "lower"
```

`_validate_metadata()` calls `file.filename.lower()`, and Starlette types
`UploadFile.filename` as `str | None`. If a request could make it `None`, the handler would
raise `AttributeError` and return **500** instead of the intended 400.

**It was reproduced before being touched** (`.day3/repro_filename_none.py`, three
hand-built multipart bodies, since httpx silently drops an empty filename and collapses
the cases):

| Case | Result |
|---|---|
| No `filename` parameter at all | **HTTP 422** — `"Expected UploadFile, received: <class 'str'>"` |
| `filename=""` | **HTTP 400** — `"Only .pdf files are accepted."` |
| `filename="ok.pdf"` (control) | **HTTP 202** |

**Verdict: not a defect.** Starlette parses a part with no `filename` parameter as a plain
form field, so request validation refuses it with 422 *before the handler is entered*. The
`None` branch is unreachable through FastAPI today.

It was still fixed, because a validation function should be total over its declared input
type and because leaving a known type error in place to be rediscovered is worse than one
`or ""`. Behaviour is identical for every reachable input.

### 1.3 Changes made

All behaviour-preserving. Nothing was restructured, no module was reorganised, no feature
was added or removed.

| File | Change | Why |
|---|---|---|
| `backend/app/routers/documents.py` | `file.filename` → `(file.filename or "")` in `_validate_metadata`; one `filename: str` local narrowing its three uses in `upload_document`; `@router.post(...)` decorator wrapped to fit 100 columns | mypy `union-attr` + `arg-type`; E501 |
| `backend/app/services/llm_service.py` | `Set`/`Any` imported; `_mentioned_pages` annotated `-> Set[int]`; `payload: Dict[str, Any]`; `# noqa: RUF001` plus a comment on the EN DASH in the page-range regex | mypy `var-annotated` + `arg-type`; ruff RUF001 |
| `backend/app/services/text_cleaner.py` | `deduped_lines: List[str]`; one `logger.debug` wrapped | mypy `var-annotated`; E501 |
| `backend/app/services/ocr_processor.py` | Removed an `else` after a `return` | ruff RET505 |
| `backend/app/config.py` | CRLF → LF (no content change) | line-ending consistency |
| `backend/app/services/vector_store.py` | CRLF → LF (no content change) | line-ending consistency |
| `frontend/src/**` (14 files) | `prettier --write` | see §1.5 |
| `backend/tests/test_api.py` | **+2 tests** | see §1.6 |

**New configuration files** — the project previously had *no* linter or formatter
configuration at all, which meant "the linter is clean" was not a statement anyone else
could reproduce:

| File | Purpose |
|---|---|
| `backend/pyproject.toml` | ruff (line-length 100, selected rule families), black, mypy. Every disabled rule family carries a written reason |
| `frontend/.prettierrc` | Matches the code's existing style: no semicolons, single quotes, trailing commas, 100 columns |
| `frontend/.prettierignore` | `node_modules`, `dist`, `package-lock.json` |
| `frontend/eslint.config.mjs` | Flat config; correctness rules only, since prettier owns formatting |
| `.gitattributes` | Line-ending policy — LF in the repository, fixture PDFs marked `binary` |

`frontend/package.json` gained `lint`, `format` and `format:check` scripts and the
corresponding devDependencies, so the quality gate is runnable by anyone with
`npm install` rather than only inside this session's throwaway environment.

### 1.4 Decision: black was evaluated and deliberately NOT applied

`black --check` reports 25 of 31 Python files as unformatted, and applying it produces a
**+661 / −326 line** diff. Every line of that diff is restyling; none of it fixes a defect.
Representative samples:

```diff
-        results.append({
-            "chunk_id": ids[i] if i < len(ids) else None,
-            ...
-        })
+        results.append(
+            {
+                "chunk_id": ids[i] if i < len(ids) else None,
+                ...
+            }
+        )
```

```diff
-        len(results), query[:60], top_k, document_id or "all",
+        len(results),
+        query[:60],
+        top_k,
+        document_id or "all",
```

The first adds a level of nesting; the second turns one readable line into four. The code
was hand-formatted to roughly 100 columns before any tool existed — the longest line in
`app/` is 103 characters and only 27 lines in the whole project exceed 88 — so black is
not correcting a mess, it is imposing a different style on a consistent one.

**Decision: adopt the configuration, do not run the formatter.** `[tool.black]` in
`pyproject.toml` pins line-length 100 so that anyone who does run it gets the project's
measure rather than black's default 88, and the file states in a comment that the codebase
is deliberately not black-formatted. This is recorded rather than left silent precisely
because a future reader will otherwise assume it was an oversight.

### 1.5 Decision: prettier WAS applied

The opposite call on the frontend, for a measured reason. Prettier's diff is
**+139 / −101 across 14 files** — an order of magnitude smaller than black's — and it
corrects genuine inconsistencies rather than imposing a preference. `useChat.js` used both
`prev =>` and `(index) =>` *in the same file*; prettier makes that one way.

It was applied only after a `.prettierrc` was written to match the code's **existing**
conventions. With prettier's defaults (double quotes, semicolons) 19 files were flagged,
which said nothing except that the defaults disagree with the project.

Prettier reprints from the AST, so semantics are preserved by construction; it was
verified anyway by the production build and a browser check of both pages (§4).

### 1.6 Tests added

Two, both in `backend/tests/test_api.py`, pinning the contract that makes §1.2's fix safe:

| Test | Asserts |
|---|---|
| `test_upload_without_filename_is_refused_before_the_handler` | A multipart part with no `filename` parameter → **422**, not a 500 from `AttributeError` |
| `test_upload_with_empty_filename_is_refused_as_a_non_pdf` | `filename=""` → **400** with a message naming PDF |

**Honesty note on non-vacuousness.** Day 2's discipline was to prove each new test fails
against the pre-fix code. These two **do not**: the `None` path was unreachable before the
fix as well, so both tests pass with or without it. They are *contract pins*, not defect
guards — they exist so that if a future Starlette or FastAPI release ever starts binding a
filename-less part to `UploadFile`, it fails here rather than as a 500 in production. They
are recorded as such rather than presented as regression guards they are not.

The first version of the second test was **wrong and was caught**: written with httpx's
`files={"file": ("", ...)}`, it returned 422 rather than the expected 400, because httpx
omits the filename parameter entirely when handed an empty string — collapsing it into the
*first* test's case. Both tests now build the multipart body by hand, and a comment in the
file says why.

### 1.7 Oddities kept, with reasons

Per the PDF: "when you decide not to change something, record the decision."

| Item | Decision |
|---|---|
| `app/utils/helpers.py` — 3 functions, no call sites | **Kept.** Part of the spec §15.1 module list. Already documented in `README.md` and `FINAL_PROJECT_COMPLETION.md`; now also in `ARCHITECTURE.md` §2 so it is not rediscovered as a mystery |
| `except Exception` in 13 places | **Kept.** Every one is a deliberate degradation boundary (OCR, ChromaDB, embedding model, Ollama) that logs and returns a safe default. Narrowing them means guessing four third-party libraries' exception types. `BLE001` disabled with this reason in `pyproject.toml` |
| `file: UploadFile = File(...)` (ruff B008) | **Kept.** That *is* FastAPI's documented dependency-injection idiom, not the mutable-default bug B008 targets. Ignored with a reason |
| `List`/`Dict`/`Optional` annotations (ruff UP006/UP035) | **Kept.** Modernising to `list`/`dict`/`X \| None` is ~60 call sites across every module for no behaviour or correctness benefit — refactoring, not cleanup. `UP` not enabled |
| Unsorted import blocks (ruff I001, 16 files) | **Kept.** The existing order is already consistent (stdlib → third-party → app) and readable. `I` not enabled |
| Unused `**kw` in test doubles (ruff ARG) | **Kept.** They must match the signature of the function they replace. `ARG` not enabled |
| EN DASH in `_mentioned_pages`' regex (ruff RUF001) | **Kept** with `# noqa` and an explanation. PDFs write ranges as "pages 1–4" with a real en dash; both characters must match |
| `vector_store.py:51`, 103 characters | **Kept.** An f-string with no whitespace past the limit; ruff's E501 correctly exempts an unsplittable token |
| `radon` C-rank blocks (4) | **Kept.** Moderate complexity with documented reasons; restructuring is refactoring |

`vulture` at 60% confidence also reported 24 items that are framework false positives —
FastAPI route handlers, Pydantic model fields, `row_factory` and `return_value` attribute
assignments. At `--min-confidence 80` over `app/`, vulture reports **nothing**.

### 1.8 Line endings — a real inconsistency, fixed

Of 51 text source files, four had drifted to CRLF while the other 47 used LF:
`backend/app/config.py`,
`backend/app/services/vector_store.py`, `frontend/src/App.jsx` and
`frontend/src/components/ChatInterface.jsx`. Nothing failed because of it, but it is the
kind of inconsistency that produces whole-file diffs the first time someone edits one of
them on another machine, hiding the real change in the noise.

All four are now LF (the two frontend files as a side effect of prettier), and
`.gitattributes` was added so it cannot drift again. Fixture PDFs are marked `binary` so
newline translation can never corrupt the exact bytes `test_retriever.py`'s similarity
thresholds are calibrated against.

### 1.9 Final linter state

| Tool | Scope | Result |
|---|---|---|
| `ruff check app tests` | 31 files | **All checks passed** |
| `mypy app` | 21 files | **Success: no issues found** |
| `vulture app --min-confidence 80` | 21 files | **No findings** |
| `npm run lint` (eslint) | 15 modules | **Clean, exit 0** |
| `npm run format:check` (prettier) | 19 files | **All matched files use Prettier code style** |
| `black --check` | 31 files | 25 would reformat — **expected and documented**, §1.4 |

---

## 2. Stage 13 — Documentation

### 2.1 Documentation defects found and fixed

The README had drifted from the code. These were wrong, not merely incomplete:

| Defect | Was | Now |
|---|---|---|
| `OLLAMA_BASE_URL` default | `http://localhost:11434` | `http://127.0.0.1:11434` — Day 2 changed the code and the README was never updated. Documented the 2065 ms → 8.3 ms reason |
| Test suite size | "Seven test modules" | **146 tests across nine modules**, with a per-module table. `test_config_validation.py` and `test_concurrency.py` were added on Day 2 and never documented |
| Project structure | `tests/ 7 test modules`, no `pyproject.toml`, no post-coding docs | Corrected and extended |
| Status | "Complete." | "Feature-complete and verified; **not deployed**", with a phase table linking each record |
| Known limitations | Predated Day 2 entirely | Added the 6 dependency advisories, the unaudited Python pins, the prompt-injection boundary, and the explicit not-deployed reason |

### 2.2 Documents created

The PDF's stage 13 documentation set had three gaps — architecture, API and configuration
existed only as README sections, with no document aimed at their actual audience.

| File | Audience | Contents |
|---|---|---|
| `docs/ARCHITECTURE.md` | An engineer joining the project | Component map, module-by-module responsibilities, both data flows, trust boundaries, **13 major decisions with rationale and cost**, degradation behaviour, architectural constraints |
| `docs/API_REFERENCE.md` | A consumer of the API | Every endpoint, request and response shape, both schemas field-by-field, every status code, every error case and its `detail` string, timeout semantics |
| `docs/CONFIGURATION.md` | Whoever runs or deploys it | All 17 variables with default, minimum and what each controls; why validation is at startup; system-level dependencies with verified versions; platform traps |
| `docs/POSTCODING_DAY_03_CONSOLIDATION.md` | A reviewer or successor | This document |

Everything in them was read out of the source, not the specification. Where the code and
the spec disagree, the code is documented and the deviation is named.

### 2.3 What was deliberately not claimed

* No performance numbers were invented; every figure is quoted from Day 1's or Day 2's
  measurements and attributed.
* The unaudited backend dependencies are described as a **genuinely unmet** checklist item,
  not as passed.
* The two new tests are described as contract pins, not as regression guards (§1.6).
* Deployment, monitoring and release are described as **not done**, because they are Day 4
  and Day 5 work.

---

## 3. Stage 14 — Reproducibility

### 3.1 Method

`.day3/repro_fresh_env.py` builds a **brand-new** virtual environment
(`.venv-repro-day3/`) inside the project folder and runs the whole check against it. The
existing `backend/.venv` is never activated, read as a package source, or modified. No
other project's environment was used or touched.

### 3.2 Results

| Check | Result |
|---|---|
| All 14 dependencies pinned with `==` | **Yes** — no ranges, no unpinned entries |
| Declared pins vs `backend/.venv` (drift) | **14/14 identical — zero drift** |
| `pip install -r requirements.txt` into an empty venv | **Succeeded** — 120 distributions including torch 2.14.0, transformers 4.57.6, numpy 2.5.3 |
| `pip check` | **"No broken requirements found."** |
| Every declared dependency imports | **14/14 OK** |
| Fresh-env versions match declared | **14/14 exact** |
| Runtime recorded | **Python 3.13.3** |

### 3.3 The strongest evidence: the suite runs in the fresh environment

Importing libraries proves the dependency list installs. It does not prove the list is
*sufficient to run the application*. So the full test suite was executed using the
throwaway environment's interpreter:

```
.venv-repro-day3\Scripts\python.exe -m pytest tests/ -q
  →  146 passed, 1 warning in 45.15s
```

A brand-new environment, built only from `requirements.txt`, runs every test green.

### 3.4 System-level dependencies recorded

Documented in `docs/CONFIGURATION.md`, since no package manager can install them:

| Dependency | Verified version | Required |
|---|---|---|
| Python | 3.13.3 | Yes — the only version verified |
| Node.js / npm | 22.23.1 / 10.9.8 | Frontend only |
| Ollama | 0.34.0 | Yes, plus the model in `OLLAMA_MODEL` |
| Tesseract OCR | 5.5.3.20260724 | **No** — the app degrades cleanly without it |
| Disk / RAM | ~5 GB free / 8 GB | Yes |

Platform traps documented: Windows 260-character path limit versus PyTorch's deep headers;
Windows IPv6-first `localhost` resolution; Windows file locking during ingestion; and the
line-ending policy.

### 3.5 Test fixtures

The eight fixture PDFs remain committed rather than generated, and `.gitattributes` now
marks `*.pdf` as `binary` so they can never be newline-translated. `test_retriever.py`
asserts measured similarity thresholds against their exact bytes.

### 3.6 Cleanup

`.venv-repro-day3/` was deleted after the run. `.gitignore` gained `.venv-*/` so neither it
nor `.venv-tools/` can ever be committed.

---

## 4. Stage 15 — Build verification

### 4.1 The build

```
frontend> npm run build      (vite v5.4.21)

✓ 1576 modules transformed.
dist/index.html                   0.40 kB │ gzip:  0.28 kB
dist/assets/index-DyMymqJN.css   17.99 kB │ gzip:  4.15 kB
dist/assets/index-Rj7hbrdQ.js   248.88 kB │ gzip: 82.60 kB
✓ built in 1m 56s
```

| Check | Result |
|---|---|
| Errors | **0** |
| Warnings | **0** — none emitted, so none to review |
| Output size | **261 KB total, 87 KB gzipped.** Sane for React 18 + react-router + axios + lucide-react |
| Unexpected large files | **None.** Exactly 3 files |
| Source maps, `.env`, PDFs or `.db` leaked into `dist/` | **None** |

### 4.2 The artifact actually runs

`vite preview` on port 4173, served against the real backend on 8000:

| Check | Result |
|---|---|
| `/documents` renders | **Yes** — all 3 real documents with correct page, chunk and OCR counts |
| `GET /api/documents` from the built bundle | **200, real JSON** |
| `/chat` renders | **Yes** — correct empty state |
| Console errors | **0** on both pages |

A hypothesis was investigated and **disproved** here rather than acted on: `vite.config.js`
declares the `/api` proxy only under `server:`, so the production preview looked like it
would fail to reach the backend — the classic production-only failure. It does not: Vite
defaults `preview.proxy` to `server.proxy`. Had this been "fixed by inspection", a
redundant config block would have been added for a defect that does not exist.

### 4.3 Rebuild after adding dev tooling — byte-identical

Adding eslint and prettier as devDependencies (180 packages) is a change to
`package.json` and `package-lock.json`, so the build was re-run:

| Artifact | Before | After |
|---|---|---|
| JS | `index-Rj7hbrdQ.js`, 248,935 B | `index-Rj7hbrdQ.js`, 248,935 B |
| CSS | `index-DyMymqJN.css`, 17,988 B | `index-DyMymqJN.css`, 17,988 B |
| HTML | 404 B | 404 B |

Vite's content hashes are **unchanged**, which proves the production artifact is
byte-identical and that the dev tooling ships nothing.

### 4.4 Dependency advisories after the change

`npm audit` reports **4 affected packages (1 high, 3 moderate)**. The underlying advisory
set is the same one Day 2 recorded — `vite`/`esbuild` and `react-router`; the count differs
because npm counts affected packages, not advisories. **The 180 added dev packages
introduced zero new advisories**, and `vite` is still 5.4.21.

Per the decision taken at the start of the day, the advisories were **not** fixed: both
remedies are breaking major upgrades (vite 5→8, react-router 6→7) that would invalidate the
Day 1/Day 2 verified baseline and require a full re-test cycle. All four vite/esbuild
issues are dev-server only and do not affect `vite build` output — confirmed by §4.3's
byte-identical artifact — and both react-router issues are unreachable here (no SSR, no
user-controlled navigation targets).

One honest note: `eslint@9.39.5` is the newest 9.x and npm warns that the 9.x line is no
longer supported. ESLint 10 cannot be used because `eslint-plugin-react`'s peer range caps
at `^9.7`. Dev-only tooling, not shipped.

---

## 5. Bugs and defects

| # | Item | Stage | Reproduced | Verdict |
|---|---|---|---|---|
| 1 | `file.filename.lower()` on `str \| None` → potential 500 | 12 | **Yes**, 3 multipart variants | **Not a defect** — unreachable (422 first). Type made total anyway; 2 contract-pin tests added |
| 2 | `vite preview` would not proxy `/api` | 15 | **Yes**, live against the built bundle | **Not a defect** — Vite defaults `preview.proxy` to `server.proxy`. Hypothesis disproved, no change made |
| 3 | My own test used httpx `files={"file": ("", …)}` and silently tested the wrong case | 12 | Yes — it failed | **My defect, fixed.** Both tests now build the multipart body by hand |

**0 product defects found, 0 product defects introduced.**

Three genuine *quality* issues were found and fixed: five mypy errors, four files with
inconsistent line endings, and a complete absence of linter/formatter configuration.

---

## 6. Regression testing

The full suite, never a subset. No test was deleted, skipped, weakened or rewritten.

| Run | Environment | Result |
|---|---|---|
| Day 2 final (baseline) | `backend/.venv` | 144 passed |
| After all Day 3 cleanup edits | `backend/.venv` | **144 passed** — behaviour preserved |
| After adding 2 tests | `.venv-repro-day3` (fresh) | **146 passed** in 45.15 s |
| **Final** | `backend/.venv` | **146 passed** in 83.31 s |

| Module | Day 2 | Day 3 |
|---|---|---|
| `test_llm_service.py` | 72 | 72 |
| `test_api.py` | 19 | **21** (+2) |
| `test_config_validation.py` | 17 | 17 |
| `test_text_cleaner.py` | 10 | 10 |
| `test_retriever.py` | 8 | 8 |
| `test_chunker.py` | 6 | 6 |
| `test_ocr_processor.py` | 5 | 5 |
| `test_embedder.py` | 4 | 4 |
| `test_concurrency.py` | 3 | 3 |
| **Total** | **144** | **146** |

### 6.1 Clean end state

The `repro_filename_none.py` reproduction uploaded a document (`ok.pdf`) as a side effect.
It was removed through the application's own delete path, and the corpus was verified back
at the Day 1/Day 2 baseline from three directions:

| Check | Value | Matches baseline |
|---|---|---|
| Documents in SQLite | 3 | yes |
| PDFs on disk | 3 | yes |
| Vectors in ChromaDB | 5 | yes |

Re-verified again after the fresh-environment suite run: still 3 / 3 / 5.

---

## 7. Files changed

### 7.1 Application code (6 files, all behaviour-preserving)

| File | Change |
|---|---|
| `backend/app/routers/documents.py` | `or ""` guard, `filename: str` local, decorator wrapped |
| `backend/app/services/llm_service.py` | `Set`/`Any` imports, 2 annotations, RUF001 `noqa` + comment |
| `backend/app/services/text_cleaner.py` | 1 annotation, 1 line wrapped |
| `backend/app/services/ocr_processor.py` | `else`-after-`return` removed |
| `backend/app/config.py` | CRLF → LF only |
| `backend/app/services/vector_store.py` | CRLF → LF only |

### 7.2 Frontend (14 files)

`prettier --write` over `src/**` and `tailwind.config.js`. Formatting only; verified by a
byte-identical production build (§4.3).

### 7.3 Tests

| File | Change |
|---|---|
| `backend/tests/test_api.py` | **+2 tests.** Nothing deleted, skipped, weakened or rewritten |

### 7.4 Configuration and tooling (created)

`backend/pyproject.toml` · `frontend/.prettierrc` · `frontend/.prettierignore` ·
`frontend/eslint.config.mjs` · `.gitattributes`

### 7.5 Configuration (modified)

| File | Change |
|---|---|
| `.gitignore` | `.venv-*/` and `.day3/node_modules/` |
| `frontend/package.json` | `lint`, `format`, `format:check` scripts; 6 devDependencies |
| `frontend/package-lock.json` | Consequence of the above (originals kept in `.day3/*.before-day3`) |
| `.claude/launch.json` | Added a `frontend-preview` entry for build verification |

### 7.6 Documentation

| File | Change |
|---|---|
| `README.md` | Status block, `OLLAMA_BASE_URL` default, test table, structure, code-quality section, limitations, documentation index |
| `docs/ARCHITECTURE.md` | **New** |
| `docs/API_REFERENCE.md` | **New** |
| `docs/CONFIGURATION.md` | **New** |
| `docs/POSTCODING_DAY_03_CONSOLIDATION.md` | **New** — this document |

### 7.7 Not application files

| Path | Purpose |
|---|---|
| `.day3/repro_fresh_env.py` | Stage 14 harness |
| `.day3/repro_filename_none.py` | §1.2 reproduction |
| `.day3/npm_audit_after_day3.json` | §4.4 evidence |
| `.day3/package*.before-day3` | Pre-change copies |
| `.venv-tools/` | Lint toolchain, git-ignored |

Whether `.day2/` and `.day3/` belong in the repository remains a **Day 4** decision.

---

## 8. Exact commands used

```powershell
# ── Tooling, isolated from backend/.venv ────────────────────────────────────
python -m venv .venv-tools
.\.venv-tools\Scripts\python.exe -m pip install ruff black vulture radon mypy

# ── Stage 12: code quality ──────────────────────────────────────────────────
.\.venv-tools\Scripts\ruff.exe   check app tests --output-format=concise
.\.venv-tools\Scripts\ruff.exe   check app tests --select F401,F811,F841,F821,E711,E712,E722
.\.venv-tools\Scripts\mypy.exe   app --python-executable backend\.venv\Scripts\python.exe
.\.venv-tools\Scripts\vulture.exe app tests --min-confidence 60
.\.venv-tools\Scripts\vulture.exe app --min-confidence 80
.\.venv-tools\Scripts\radon.exe  cc app -s -n C
.\.venv-tools\Scripts\radon.exe  cc app -s -a --total-average
.\.venv-tools\Scripts\radon.exe  mi app -s
.\.venv-tools\Scripts\black.exe  --check app tests          # evaluated, not applied
.\.venv-tools\Scripts\black.exe  --diff --line-length 100 app tests

npm run lint                      # eslint
npm run format:check              # prettier
npx prettier@3 --write "src/**/*.{js,jsx,css}" "*.js" index.html

# ── Reproduction ────────────────────────────────────────────────────────────
backend\.venv\Scripts\python.exe ..\.day3\repro_filename_none.py

# ── Stage 14: reproducibility ───────────────────────────────────────────────
.\.venv-tools\Scripts\python.exe .day3\repro_fresh_env.py
.venv-repro-day3\Scripts\python.exe -m pytest tests/ -q

# ── Stage 15: build ─────────────────────────────────────────────────────────
npm run build
npm run preview -- --port 4173 --strictPort
npm audit --json

# ── Regression ──────────────────────────────────────────────────────────────
backend\.venv\Scripts\python.exe -m pytest tests/ -q
```

---

## 9. Known open items carried forward

Day 2's 13 items stand unchanged, except where noted. Day 3 adds three.

| # | Item | Status |
|---|---|---|
| 1–13 | Day 2 §9 — dependency advisories, unaudited Python pins, prompt-injection laundering, poisoned-document influence, socket-inactivity timeout, nested-JSON 500, open `/docs`, no auth/HTTPS, cold-start variance, `test_retriever.py` corpus coupling, `llama3.1:8b` timeouts, small-model citation precision, `.day2/` untracked | **Unchanged.** Item 1 (advisories) was formally decided today — not upgraded, see §4.4 |
| 14 | **The codebase is not black-formatted** | Deliberate, §1.4. `[tool.black]` is configured so anyone who runs it uses the project's measure |
| 15 | **`eslint@9.39.5` is on an unsupported line** | Forced by `eslint-plugin-react`'s `^9.7` peer cap. Dev-only, not shipped |
| 16 | **Frontend has no automated tests** | Prettier's 14-file reformat was verified by a byte-identical production build and a browser check, not by a test suite. Adding frontend tests is outside a consolidation day's scope |

---

## 10. Final status

| Stage | Verdict |
|---|---|
| **12. Code quality & cleanup** | **PASS** — ruff, mypy, vulture and eslint all clean; 5 type errors fixed; 4 files' line endings normalised; tooling configured for the first time; 9 oddities kept with written reasons |
| **13. Documentation** | **PASS** — 5 README defects corrected; 3 new reference documents; every claim traced to code or a recorded measurement |
| **14. Reproducibility** | **PASS** — zero pin drift; fresh environment installs 120 distributions clean; `pip check` clean; 14/14 import; **146 tests green in the fresh environment** |
| **15. Build verification** | **PASS** — 0 errors, 0 warnings, 261 KB, artifact verified running against the real backend, byte-identical rebuild |

| Metric | Value |
|---|---|
| Product defects found | **0** |
| Product defects introduced | **0** |
| Quality issues found and fixed | **3** (5 mypy errors, 4 files CRLF, no tool config) |
| Investigations that disproved a hypothesis | **2** (§5 items 1 and 2) |
| Tests before / after | **144 → 146** (+2) |
| Tests deleted, skipped or weakened | **0** |
| Full suite, final | **146 passed, 0 failed** |
| Application files changed | **6** (2 of them line endings only) |
| Documentation files created | **4** |
| Corpus at end | Day 1's baseline exactly (3 documents / 3 PDFs / 5 vectors) |

**Phase C verdict: PASS.**

---

*End of Day 3 — Phase C (Consolidation). Day 4 (Release: version control, release &
versioning, deployment preparation, deployment) **not started**.*
