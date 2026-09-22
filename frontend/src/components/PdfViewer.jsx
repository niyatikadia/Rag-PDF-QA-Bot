import { useEffect, useRef } from 'react'
import { X, ExternalLink, FileText } from 'lucide-react'
import { documentFileUrl } from '../services/api'

/**
 * PdfViewer — a modal that shows an uploaded PDF (Day 12).
 *
 * Added because the Documents page could list a PDF but never show one: the
 * only way to read an uploaded file was to open backend/data/uploads and match
 * a UUID filename back to a real name by hand.
 *
 * ── Why an iframe and not a PDF library ─────────────────────────────────────
 * Chrome, Edge and Firefox all ship a full PDF viewer — pages, zoom, search,
 * print, save — and an iframe pointing at a URL served as `application/pdf`
 * with `Content-Disposition: inline` hands the file straight to it. Bundling
 * pdf.js would add a megabyte of JavaScript and a worker to rebuild a worse
 * version of something already installed. The backend sets that content type
 * and disposition precisely so this works (see documents.get_document_file).
 *
 * The trade is that the viewer's chrome is the browser's, so it will not match
 * the app's styling and cannot be themed. For reading a source document that is
 * the right trade — and "Open in new tab" is there for anyone who wants the
 * browser's own full-window viewer instead.
 */
export default function PdfViewer({ document: doc, onClose }) {
  const closeRef = useRef(null)
  const previouslyFocusedRef = useRef(null)

  const fileUrl = doc ? documentFileUrl(doc.document_id, doc.filename) : null

  // Escape closes the viewer. Captured on window, because ErrorToast also
  // listens for Escape at the bubble phase — without stopPropagation a single
  // press would close this modal *and* dismiss a toast sitting behind it. The
  // topmost layer should consume the key.
  useEffect(() => {
    if (!doc) return undefined
    const onKeyDown = e => {
      if (e.key !== 'Escape') return
      e.stopPropagation()
      onClose?.()
    }
    window.addEventListener('keydown', onKeyDown, true)
    return () => window.removeEventListener('keydown', onKeyDown, true)
  }, [doc, onClose])

  // While the modal is open the page behind it must not scroll: without this,
  // spinning the wheel over the backdrop scrolls the document list underneath,
  // which reads as the dialog itself being broken.
  useEffect(() => {
    if (!doc) return undefined
    const previous = window.document.body.style.overflow
    window.document.body.style.overflow = 'hidden'
    return () => {
      window.document.body.style.overflow = previous
    }
  }, [doc])

  // Move focus into the dialog on open and hand it back on close, so the
  // keyboard does not stay parked on a card behind the backdrop.
  useEffect(() => {
    if (!doc) return undefined
    previouslyFocusedRef.current = window.document.activeElement
    closeRef.current?.focus()
    return () => {
      const target = previouslyFocusedRef.current
      if (target && typeof target.focus === 'function') target.focus()
    }
  }, [doc])

  if (!doc) return null

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col bg-gray-900/70 backdrop-blur-sm p-3 sm:p-6"
      // Clicking the backdrop closes; clicking the panel must not, so the panel
      // stops the click rather than the backdrop inspecting the event target.
      onClick={onClose}
      role="presentation"
    >
      <div
        className="flex flex-col flex-1 min-h-0 w-full max-w-5xl mx-auto bg-white rounded-xl shadow-2xl overflow-hidden"
        onClick={e => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={`Preview of ${doc.filename}`}
      >
        <header className="flex items-center gap-3 px-4 py-2.5 border-b border-gray-200 bg-gray-50">
          <FileText className="text-blue-500 flex-shrink-0" size={18} />
          {/* min-w-0 lets the long filename ellipse instead of shoving the
              buttons off the row — same reasoning as DocumentCard's title. */}
          <p className="flex-1 min-w-0 text-sm font-medium text-gray-800 truncate" title={doc.filename}>
            {doc.filename}
          </p>

          <a
            href={fileUrl}
            target="_blank"
            rel="noreferrer"
            className="focus-ring flex-shrink-0 inline-flex items-center gap-1.5 text-xs font-medium text-gray-600 hover:text-blue-700 hover:bg-blue-50 rounded-lg px-2 py-1.5 transition-colors"
            title="Open this PDF in a new browser tab"
          >
            <ExternalLink size={14} /> Open in new tab
          </a>

          <button
            ref={closeRef}
            onClick={onClose}
            className="focus-ring flex-shrink-0 text-gray-500 hover:text-gray-900 hover:bg-gray-200 rounded-lg transition-colors p-1.5"
            title="Close preview (Esc)"
            aria-label="Close preview"
          >
            <X size={18} />
          </button>
        </header>

        {/* bg-gray-100 so the gap around a portrait page reads as the viewer's
            own matte rather than a half-loaded panel. */}
        <div className="flex-1 min-h-0 bg-gray-100">
          <iframe
            key={doc.document_id}
            src={fileUrl}
            title={`${doc.filename} preview`}
            className="w-full h-full border-0"
          />
        </div>
      </div>
    </div>
  )
}
