import { Trash2, FileText, CheckCircle2, Clock, XCircle, ScanLine, Layers } from 'lucide-react'

/**
 * DocumentCard — F14 document management.
 *
 * Backend contract (schemas.DocumentInfo):
 *   { document_id, filename, upload_date, status, total_pages, total_chunks,
 *     ocr_pages_count, error_message }
 *
 * [v2] Page count reads "12 pages (3 via OCR)" when ocr_pages_count > 0, so it
 * is visible at a glance whether a document went through OCR (spec §7.2).
 */

// Foregrounds are the -700 shades, not -600 (changed Day 2 — contrast).
// Measured against their own tinted backgrounds rather than against white,
// which is what these pills actually sit on:
//   green-600 on green-50  3.15:1  FAIL     green-700  4.79:1  pass
//   red-600   on red-50    4.41:1  FAIL     red-700    5.91:1  pass
//   blue-600  on blue-50   4.75:1  pass     (left alone)
// WCAG AA requires 4.5:1 for text this size. These pills are the only thing
// that tells a user whether their document is usable, so they are exactly the
// wrong place to be unreadable.
const STATUS = {
  ready: { Icon: CheckCircle2, label: 'Ready', cls: 'text-green-700 bg-green-50 border-green-200' },
  processing: {
    Icon: Clock,
    label: 'Processing…',
    cls: 'text-blue-700 bg-blue-50 border-blue-200',
  },
  failed: { Icon: XCircle, label: 'Failed', cls: 'text-red-700 bg-red-50 border-red-200' },
}

function formatDate(value) {
  if (!value) return null
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return null
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** "12 pages (3 via OCR)" · "3 pages" · null when the count is unknown. */
function formatPages(totalPages, ocrPages) {
  if (!totalPages) return null
  const base = `${totalPages} page${totalPages === 1 ? '' : 's'}`
  return ocrPages > 0 ? `${base} (${ocrPages} via OCR)` : base
}

export default function DocumentCard({ document, onDelete }) {
  const {
    document_id,
    filename,
    upload_date,
    status,
    total_pages = 0,
    total_chunks = 0,
    ocr_pages_count = 0,
    error_message,
  } = document

  const meta = STATUS[status] ?? {
    Icon: FileText,
    label: status,
    cls: 'text-gray-600 bg-gray-50 border-gray-200',
  }
  const { Icon } = meta
  const isProcessing = status === 'processing'
  const pagesLabel = formatPages(total_pages, ocr_pages_count)
  const uploaded = formatDate(upload_date)

  // A document can finish as "ready" and still hold no chunks — the backend only
  // fails a document when *every* page yields nothing. Through Day 7 the chunk
  // count was simply hidden at 0, so such a card read as perfectly healthy while
  // being unsearchable. Say so instead.
  const isEmptyReady = status === 'ready' && total_chunks === 0

  return (
    <div className="flex items-start gap-3 bg-white border border-gray-200 rounded-xl px-4 py-3 shadow-sm hover:border-gray-300 transition-colors">
      <FileText className="text-blue-500 flex-shrink-0 mt-0.5" size={20} />

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          {/* min-w-0 is what makes `truncate` work here: truncate implies
              whitespace-nowrap, so without it this p's min-content width is the
              full filename and it refuses to shrink, pushing the status and OCR
              pills out of the row instead of ellipsing. */}
          <p className="min-w-0 text-sm font-medium text-gray-800 truncate" title={filename}>
            {filename}
          </p>
          <span
            className={`inline-flex items-center gap-1 border rounded-full px-2 py-px text-[10px] font-semibold ${meta.cls}`}
          >
            <Icon size={10} className={isProcessing ? 'animate-pulse' : ''} />
            {meta.label}
          </span>
          {ocr_pages_count > 0 && (
            <span
              title={`${ocr_pages_count} page${ocr_pages_count === 1 ? ' was' : 's were'} scanned and recovered with OCR.`}
              className="inline-flex items-center gap-1 bg-amber-50 border border-amber-200 text-amber-800 rounded-full px-2 py-px text-[10px] font-semibold"
            >
              <ScanLine size={10} /> OCR
            </span>
          )}
        </div>

        {/* [v2] "12 pages (3 via OCR)" */}
        <div className="flex items-center gap-2 mt-1 text-xs text-gray-500 flex-wrap">
          {pagesLabel && <span>{pagesLabel}</span>}
          {total_chunks > 0 && (
            <>
              {pagesLabel && <span className="text-gray-300">·</span>}
              <span className="inline-flex items-center gap-1">
                <Layers size={11} /> {total_chunks} chunk{total_chunks === 1 ? '' : 's'}
              </span>
            </>
          )}
          {isEmptyReady && (
            <>
              {pagesLabel && <span className="text-gray-300">·</span>}
              <span
                className="inline-flex items-center gap-1 font-medium text-amber-700"
                title="This document finished processing but produced no searchable chunks, so questions cannot match against it."
              >
                <Layers size={11} /> 0 chunks — not searchable
              </span>
            </>
          )}
          {uploaded && (
            <>
              {(pagesLabel || total_chunks > 0 || isEmptyReady) && (
                <span className="text-gray-300">·</span>
              )}
              <span>{uploaded}</span>
            </>
          )}
          {isProcessing && !pagesLabel && <span className="italic">Extracting text…</span>}
        </div>

        {status === 'failed' && error_message && (
          <p className="mt-1.5 text-xs text-red-700 bg-red-50 border border-red-200 rounded px-2 py-1 break-words">
            {error_message}
          </p>
        )}
      </div>

      {/* gray-500, not gray-400 (Day 2 — contrast): this is an interactive
          control's icon, which WCAG 1.4.11 holds to 3:1. gray-400 on white is
          2.54:1; gray-500 is 4.83:1. */}
      <button
        onClick={() => onDelete?.(document_id)}
        className="focus-ring flex-shrink-0 text-gray-500 hover:text-red-700 hover:bg-red-50 rounded-lg transition-colors p-1.5"
        title={`Delete ${filename}`}
        aria-label={`Delete ${filename}`}
      >
        <Trash2 size={16} />
      </button>
    </div>
  )
}
