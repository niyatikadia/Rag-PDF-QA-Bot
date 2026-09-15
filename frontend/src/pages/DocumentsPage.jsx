import { useCallback, useEffect, useRef, useState } from 'react'
import FileUpload from '../components/FileUpload'
import DocumentList from '../components/DocumentList'
import ErrorToast from '../components/ErrorToast'
import LoadingIndicator from '../components/LoadingIndicator'
import { listDocuments, deleteDocument } from '../services/api'

/**
 * DocumentsPage — F14 upload + manage documents, F15 processing status.
 *
 * Day 7: the Day 6 MOCK_DOCUMENTS array is gone. The list is loaded from
 * GET /api/documents and kept live by polling.
 *
 * Polling rules (Day 7 requirement):
 *  - poll only while at least one document is "processing"; stop when none are.
 *    Ingestion is a FastAPI BackgroundTask, so "processing" is the only state
 *    that can change on its own — polling a settled list would be pure noise.
 *  - the interval is always cleared on unmount, and every setState is guarded
 *    by a mounted ref, so a poll in flight during a route change cannot warn.
 *  - a failed poll is swallowed: it must never wipe the list the user is
 *    looking at, and must never raise a toast, because a single dropped
 *    request during a 2.5 s cadence is not something the user can act on. Only
 *    a sustained outage (3 consecutive failures) surfaces, and then as a quiet
 *    inline line rather than a toast.
 */

const POLL_INTERVAL_MS = 2500
const POLL_FAILURES_BEFORE_NOTICE = 3

// Native extraction finishes in well under a second on these documents; OCR is
// ~1-3 s per page (spec §6.5). So a document still processing after this long
// is almost certainly in the OCR fallback. That is an inference from real
// observed state, and the copy is worded as such rather than asserting it.
const OCR_HINT_AFTER_MS = 4000

export default function DocumentsPage() {
  const [documents, setDocuments] = useState([])
  const [isInitialLoading, setIsInitialLoading] = useState(true)
  const [error, setError] = useState(null)
  const [pollDown, setPollDown] = useState(false)
  // Whether the first load actually succeeded. A failed load leaves `documents`
  // empty, which is indistinguishable from a genuinely empty library — and
  // rendering "No documents yet" then tells the user something untrue about
  // their own data (found Day 2). Same reasoning as the count below.
  const [initialLoadFailed, setInitialLoadFailed] = useState(false)
  const [ocrLikely, setOcrLikely] = useState(false)

  const mountedRef = useRef(true)
  const pollFailuresRef = useRef(0)
  const processingSinceRef = useRef(null)

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
    }
  }, [])

  /** Records how long the current processing batch has been running. */
  const trackProcessing = useCallback(docs => {
    const anyProcessing = docs.some(d => d.status === 'processing')
    if (!anyProcessing) {
      processingSinceRef.current = null
      setOcrLikely(false)
      return
    }
    if (processingSinceRef.current === null) processingSinceRef.current = Date.now()
    setOcrLikely(Date.now() - processingSinceRef.current >= OCR_HINT_AFTER_MS)
  }, [])

  /** Authoritative refetch. Rejects on failure so callers can decide. */
  const refresh = useCallback(async () => {
    const docs = await listDocuments()
    if (!mountedRef.current) return null
    setDocuments(docs)
    setInitialLoadFailed(false) // any successful load clears the unknown state
    trackProcessing(docs)
    return docs
  }, [trackProcessing])

  // ── Initial load ────────────────────────────────────────────────────────────
  useEffect(() => {
    refresh()
      .catch(err => {
        if (!mountedRef.current) return
        setInitialLoadFailed(true)
        setError({
          status: err?.response?.status ?? null,
          message:
            err?.response?.data?.detail ??
            'Could not load your documents. Check that the API server is running.',
        })
      })
      .finally(() => {
        if (mountedRef.current) setIsInitialLoading(false)
      })
  }, [refresh])

  // ── Status polling, only while something is processing ──────────────────────
  const hasProcessing = documents.some(d => d.status === 'processing')

  useEffect(() => {
    if (!hasProcessing) {
      pollFailuresRef.current = 0
      setPollDown(false)
      return undefined
    }

    const id = setInterval(async () => {
      try {
        await refresh()
        if (!mountedRef.current) return
        pollFailuresRef.current = 0
        setPollDown(false)
      } catch {
        // Deliberately swallowed — see the polling rules above. The list the
        // user is looking at is left exactly as it was.
        if (!mountedRef.current) return
        pollFailuresRef.current += 1
        if (pollFailuresRef.current >= POLL_FAILURES_BEFORE_NOTICE) setPollDown(true)
      }
    }, POLL_INTERVAL_MS)

    return () => clearInterval(id)
  }, [hasProcessing, refresh])

  // ── Upload ──────────────────────────────────────────────────────────────────
  // POST /api/documents/upload answers 202 with an UploadResponse, which has no
  // page/chunk/OCR counts — so refetch rather than pushing it in as a card.
  const handleUploadComplete = useCallback(() => {
    refresh().catch(() => {
      /* the poller picks the new document up */
    })
  }, [refresh])

  // ── Delete ──────────────────────────────────────────────────────────────────
  const handleDelete = useCallback(
    async documentId => {
      setDocuments(prev => prev.filter(d => d.document_id !== documentId))
      try {
        await deleteDocument(documentId)
      } catch (err) {
        if (!mountedRef.current) return
        setError({
          status: err?.response?.status ?? null,
          message: err?.response?.data?.detail ?? 'Could not delete that document.',
        })
        // Put the card back by reloading the backend's own truth.
        refresh().catch(() => {})
      }
    },
    [refresh],
  )

  // ── Derived UI state ────────────────────────────────────────────────────────
  const readyCount = documents.filter(d => d.status === 'ready').length
  const ocrCount = documents.reduce((sum, d) => sum + (d.ocr_pages_count || 0), 0)

  const processingDocs = documents.filter(d => d.status === 'processing')
  const ingestStatus =
    processingDocs.length === 0
      ? null
      : ocrLikely
        ? {
            variant: 'ocr',
            message: `Still processing ${processingDocs[0].filename} — running OCR on scanned pages…`,
          }
        : {
            variant: 'default',
            message:
              processingDocs.length === 1
                ? `Processing ${processingDocs[0].filename}…`
                : `Processing ${processingDocs.length} documents…`,
          }

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
        <div className="mb-6">
          <h1 className="text-xl font-semibold text-gray-900">Documents</h1>
          <p className="text-sm text-gray-500 mt-1">
            Upload PDFs to make them searchable. Scanned pages are recovered with OCR.
          </p>
        </div>

        {/* Page-level errors sit above the content, not below the list. Below
            the list they landed off-screen once there were enough documents to
            scroll — for an action the user took at the top of the page. */}
        {error && (
          <div className="mb-6">
            <ErrorToast error={error} onDismiss={() => setError(null)} />
          </div>
        )}

        <section className="mb-8">
          <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
            Upload PDFs
          </h2>
          <FileUpload onUploadComplete={handleUploadComplete} ingestStatus={ingestStatus} />
        </section>

        <section>
          <div className="flex items-baseline justify-between mb-3 gap-3">
            {/* No count until the first load resolves — "(0)" while still
                loading asserts an empty library that may not be empty. */}
            <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
              Uploaded documents
              {isInitialLoading || initialLoadFailed ? '' : ` (${documents.length})`}
            </h2>
            {documents.length > 0 && (
              <span className="text-xs text-gray-500">
                {readyCount} ready
                {ocrCount > 0 && ` · ${ocrCount} page${ocrCount === 1 ? '' : 's'} via OCR`}
              </span>
            )}
          </div>

          {isInitialLoading ? (
            <LoadingIndicator message="Loading your documents…" />
          ) : initialLoadFailed && documents.length === 0 ? (
            /* The list could not be loaded, so its contents are unknown — not
               empty. Saying "No documents yet" here would assert something
               false about the user's own data, and the error above already
               says what happened and what to do about it. */
            <div className="border border-dashed border-gray-300 rounded-xl py-12 px-6 text-center">
              <p className="text-sm font-semibold text-gray-700">
                Your documents could not be loaded
              </p>
              <p className="text-xs text-gray-500 mt-1">
                This is not the same as having none — the list is unavailable right now. Start the
                API server and reload.
              </p>
            </div>
          ) : (
            <DocumentList documents={documents} onDelete={handleDelete} />
          )}

          {pollDown && (
            <p className="text-xs text-gray-500 mt-3">
              Status updates are not getting through right now — showing the last known state.
              Retrying…
            </p>
          )}
        </section>
      </div>
    </div>
  )
}
