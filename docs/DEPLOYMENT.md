# Deployment

How this project is deployed, why it is deployed that way, what survives a
restart, and how to get back to the previous version if a deploy is bad.

Written for whoever operates the service — which for now is one person on one
machine, but the document assumes that will not always be true.

---

## 1. Target decision

**Target: self-hosted, on the machine that runs the models. One process.**

This is not the default choice, so here is the reasoning rather than just the
conclusion.

The application depends on four things that all run locally: Ollama serving a
2 GB language model, a sentence-transformers embedding model, a ChromaDB vector
store and a Tesseract binary. The model is the constraint. A free hobby tier on
Render, Railway or Fly.io provides on the order of 512 MB of RAM and no
persistent GPU; Ollama alone needs several gigabytes resident before it emits a
token. Deploying there would produce a service that starts, passes a health
check and fails every question — worse than not deploying, because it would look
deployed.

The alternatives were considered and rejected for specific reasons:

| Option | Why not |
|---|---|
| Free PaaS (Render / Railway / Fly.io) | The model does not fit. Measured resident size on this machine is 2 GB for `llama3.2:latest` and 5.6 GB for `llama3.1:8b`; free tiers offer a fraction of that. A paid tier with a GPU is outside the project's zero-cost constraint. |
| Static frontend on Netlify/Vercel, backend local | The deployed frontend cannot reach a backend on someone's laptop. It would require exposing the machine to the internet, which the security posture explicitly does not support — there is no authentication. |
| Docker Compose | Defensible, and the natural next step if this ever moves to a server. Rejected for now because Docker is not installed on the target machine, containerising adds a dependency for no behavioural gain on a single-user local service, and the 7.89 GB of RAM is already the binding constraint. |
| Managed vector DB + hosted LLM API | Would work, and would cost money per request. The entire point of the design is that no document leaves the machine and nothing is billed. |

**What "deployed" means here:** the application runs in production mode, as a
single process, serving both the API and the built frontend on one origin, with
the development servers stopped. That is a real deployment — a different program
from the development one, with different configuration — even though the
infrastructure is a laptop.

---

## 2. Production configuration

Production differs from development in four declared ways. Nothing is inferred.

| Setting | Development | Production | Why |
|---|---|---|---|
| `APP_ENV` | `development` | `production` | Selects the two below. An unrecognised value stops startup rather than defaulting. |
| `/docs`, `/redoc`, `/openapi.json` | mounted | **not mounted** | They publish every endpoint and schema. Closes the Day 2 open item. |
| Frontend | Vite dev server on `:5173`, proxying `/api` | **served by the backend** from `frontend/dist` | One process, one origin, no Node at runtime, and CORS stops being involved. |
| `--reload` | on | **off** | Reload watches the filesystem and restarts on change. In production it is a liability. |

`LOG_LEVEL` stays `INFO`: this is a single-user service where the startup
banner, each ingestion step and each question are exactly what an operator wants
to see. `WARNING` would hide the ingestion progress that explains why a document
is not ready yet.

### Secrets

**There are none, and this is a design property rather than an oversight.** The
project uses no paid services and no external APIs: Ollama, ChromaDB, SQLite,
sentence-transformers and Tesseract are all local. `backend/.env` contains
hostnames, paths and tuning numbers, nothing more.

That is why `.env` is still git-ignored and still never committed. The habit is
what protects the next project, which will have secrets. If this service ever
gains one — an auth token, a managed database URL — it goes in the platform's
secret store, never in a committed file.

---

## 3. Persistence plan

Three directories hold state that must survive a restart. All three are under
`backend/data/`, all three are git-ignored, and none is recreated with its
contents if deleted.

| Path | Holds | If lost |
|---|---|---|
| `backend/data/uploads/` | The uploaded PDF files themselves | The source documents are gone. Metadata rows and vectors survive and will reference files that no longer exist. |
| `backend/data/pdf_chatbot.db` | The SQLite `documents` table: filename, status, page and chunk counts | The library appears empty. The files and vectors still exist but nothing lists them. |
| `backend/data/chroma_db/` | The vector store — embeddings and chunk metadata | Retrieval returns nothing, so every question answers "I could not find an answer". The files and rows survive, but nothing is searchable until re-ingested. |

The three are **written independently and are not transactional with each
other.** Deleting a document removes all three together; losing one directory on
its own leaves the other two inconsistent with it.

**Backup is a directory copy.** Stop the service first — SQLite and ChromaDB are
both open while it runs:

```bash
xcopy /E /I /Y backend\data backend\data.backup-YYYY-MM-DD
```

**This matters more than it looks.** The deployment runs on an ordinary
filesystem, so nothing here is ephemeral. But the same application in a
container would lose all three on every restart unless these exact paths were
mounted as volumes. That is the mistake to avoid if this ever moves.

---

## 4. Rollback plan

**One sentence:** stop the service, `git checkout` the previous tag, rebuild the
frontend, and start it again — the data directories are untouched by a rollback
because they are not in the repository.

In full:

```bash
# 1. Stop the running service (Ctrl-C, or kill the uvicorn process).
# 2. Go back to the previous release.
git checkout v1.0.0

# 3. Rebuild the frontend, because dist/ is build output and is not tracked.
cd frontend && npm ci && npm run build && cd ..

# 4. Start it again (see section 6).
```

**What a rollback does not undo.** Code reverts cleanly; data does not. There
are no schema migrations today — `init_db()` uses `CREATE TABLE IF NOT EXISTS`
against a single table — so no migration needs reversing. **If a future release
adds a migration, that changes: take a copy of `backend/data/` before deploying
it, because rolling the code back will not roll the schema back.**

---

## 5. Pre-deploy checklist

Run through this before every deploy. It is short on purpose.

- [ ] **Tests green.** `pytest -q` from `backend/` with the venv active — expect
      **167 passed**. `test_retriever.py` needs its 3-document corpus present;
      on an empty store those tests fail with a message naming what to upload.
- [ ] **Build clean.** `npm run build` from `frontend/` — zero errors, and read
      the warnings rather than scrolling past them. Expect roughly 250 kB of JS
      and 18 kB of CSS; a sudden jump means something large was pulled in.
- [ ] **Configuration present.** `backend/.env` exists and `APP_ENV=production`
      is set for the deployment. Every variable in `.env.example` is covered.
- [ ] **Migrations.** None today. If that changes, they must be ready *and
      reversible*, and step 6 below becomes mandatory rather than advisable.
- [ ] **Backup taken.** Copy `backend/data/` with the service stopped.
- [ ] **Dependencies present.** Ollama running with the configured model pulled,
      and Tesseract on `PATH` if OCR is wanted.
- [ ] **Rollback target known.** You can name the tag you would go back to.

---

## 6. Running it

Ollama must be running and the configured model pulled:

```bash
ollama serve
ollama pull llama3.2:latest
```

Build the frontend once per release:

```bash
cd frontend && npm ci && npm run build
```

Then start the service:

```bash
cd backend && .venv\Scripts\activate && set APP_ENV=production && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Or use the script, which sets the environment and checks the bundle exists
first:

```bash
powershell -ExecutionPolicy Bypass -File scripts\start-production.ps1
```

The whole application is then on **<http://127.0.0.1:8000>** — the frontend at
`/`, the API under `/api`, and no second server.

### Binding and exposure

`--host 127.0.0.1` is deliberate and load-bearing. It binds the loopback
interface only, so nothing outside the machine can reach the service. **This is
the only thing standing between the application and the open internet**, because
there is no authentication, no authorisation and no HTTPS.

Changing it to `0.0.0.0` exposes an unauthenticated service that will accept
file uploads from anyone who can route to the machine. Do not do that without
first adding authentication and putting it behind TLS — see the limitations in
the README and `CHANGELOG.md`.

---

## 7. Verifying a deploy

After starting, confirm these four. Each is checking a different thing, and the
first three take seconds.

```bash
# 1. The API is up and its dependencies are reachable.
curl http://127.0.0.1:8000/api/health

# 2. The frontend is being served by the backend, not by Vite.
curl -I http://127.0.0.1:8000/          # 200, content-type: text/html

# 3. Production mode really is on - the schema must not be served.
curl http://127.0.0.1:8000/openapi.json # must NOT return JSON with "paths"
```

4. **Ask a real question in the browser.** A health check proves the process is
   alive; only a question proves retrieval, generation and citation all work
   together. Expect the first answer after a restart to be slow — a cold model
   took **118.6 s** on the reference hardware, against a warm median of 51.2 s.

If step 3 returns a JSON schema, `APP_ENV` did not reach the process — the most
likely cause is starting uvicorn without the environment variable set.
