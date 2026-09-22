/**
 * api.js — Centralised Axios client for all backend API calls.
 *
 * Wired into the components on Day 7 (Phase 5 part 2).
 *
 * ── Timeouts ────────────────────────────────────────────────────────────────
 * The single 60 s instance timeout used through Day 6 was wrong for /chat/ask:
 * Day 5 measured a 63.6 s answer on a *warm* Ollama, and the first answer after
 * `ollama serve` starts can take several minutes while the model is loaded into
 * memory. At 60 s the browser would abort a request the backend went on to
 * answer successfully — the user would see a client-side timeout for a working
 * pipeline.
 *
 * So the timeout is per request, not global:
 *   - documents / health : short, because these are local SQLite + in-process
 *                          reads and a hang there is a real failure worth
 *                          surfacing quickly.
 *   - upload             : longer, it carries up to 20 MB. Note the endpoint
 *                          returns 202 as soon as the file is saved — ingestion
 *                          (including OCR) runs in a background task, so this
 *                          timeout does not need to cover processing.
 *   - chat/ask           : long, because it is blocked on local LLM generation.
 *
 * The /chat/ask timeout is deliberately set *longer* than the backend's own
 * OLLAMA_TIMEOUT_SECONDS (300 s, see backend/app/config.py). The backend clock
 * only starts once retrieval is done and it calls Ollama, so a backend request
 * that gives up takes slightly more than 300 s end to end. If the browser
 * aborted at exactly 300 s it would race the backend and usually win — and the
 * user would get a bare client-side abort ("Could not reach the backend")
 * instead of the backend's actionable 503 ("start Ollama / it can be slow while
 * the model loads"). Losing that race on purpose means the useful message wins.
 */
import axios from 'axios'

const BASE_URL = '/api' // proxied to http://localhost:8000 by Vite

const TIMEOUT_DEFAULT_MS = 30_000 // documents + health — local, fast
const TIMEOUT_UPLOAD_MS = 120_000 // 20 MB upload over the local proxy
const TIMEOUT_ASK_MS = 360_000 // > backend OLLAMA_TIMEOUT_SECONDS (300 s)

const client = axios.create({
  baseURL: BASE_URL,
  timeout: TIMEOUT_DEFAULT_MS,
})

// ── Documents ─────────────────────────────────────────────────────────────────

/**
 * POST /api/documents/upload → 202 UploadResponse
 * {document_id, filename, status, message} — NOT a DocumentInfo. It has no
 * page/chunk/OCR counts because processing has not run yet; callers should
 * refetch the list (or GET /api/documents/{id}) once processing completes.
 */
export async function uploadDocument(file) {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await client.post('/documents/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: TIMEOUT_UPLOAD_MS,
  })
  return data
}

export async function listDocuments() {
  const { data } = await client.get('/documents')
  return data
}

export async function getDocument(documentId) {
  const { data } = await client.get(`/documents/${documentId}`)
  return data
}

export async function deleteDocument(documentId) {
  const { data } = await client.delete(`/documents/${documentId}`)
  return data
}

/**
 * URL of the stored PDF itself — GET /api/documents/{id}/file (Day 12).
 *
 * Not an Axios call on purpose. The browser fetches this one itself, as the src
 * of an iframe or the href of a link, so what the caller needs is the address,
 * not the bytes: pulling 20 MB through Axios only to wrap it in a blob URL would
 * buy nothing and cost the whole file in memory.
 *
 * Relative, so it rides the same Vite proxy (and the same origin in production)
 * as every other call here.
 *
 * `filename` is appended as a trailing path segment and is ignored by the
 * backend — the document is found by its id. It is there because Chrome's PDF
 * viewer falls back to the last segment of the URL when a PDF carries no
 * `/Title` of its own, so without it such a file displayed as "file" in the
 * viewer's toolbar and print dialog. Omitted when unknown; the backend serves
 * the bare path too.
 */
export function documentFileUrl(documentId, filename) {
  const base = `${BASE_URL}/documents/${encodeURIComponent(documentId)}/file`
  return filename ? `${base}/${encodeURIComponent(filename)}` : base
}

// ── Chat ──────────────────────────────────────────────────────────────────────

export async function askQuestion(question, documentId = null) {
  const { data } = await client.post(
    '/chat/ask',
    { question, document_id: documentId },
    { timeout: TIMEOUT_ASK_MS },
  )
  return data
}

// ── Health ────────────────────────────────────────────────────────────────────

export async function getHealth() {
  const { data } = await client.get('/health')
  return data
}
