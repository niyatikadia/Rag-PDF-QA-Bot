import { useEffect, useRef } from 'react'
import { X, ServerCrash, AlertCircle, AlertTriangle } from 'lucide-react'

/**
 * ErrorToast — F16 / F12 error surfacing.
 *
 * Accepts either a plain string or an error object shaped like an Axios
 * failure, so Day 7 can pass the real error straight through:
 *
 *   <ErrorToast error="Please select .pdf files only." />
 *   <ErrorToast error={{ status: 503, message: 'Ollama is not reachable' }} />
 *
 * Status 503 (Ollama down) and 400 (invalid question) get their own copy and
 * colour — a 503 is actionable by the user ("start Ollama"), a 400 is not the
 * same problem, and neither should read as a generic crash.
 *
 * Day 8: Escape dismisses the toast. The listener lives here rather than in each
 * caller so all three call sites (ChatInterface, DocumentsPage, FileUpload) get
 * it from one implementation. It ignores Escape raised inside a text field —
 * there, Escape belongs to ChatInterface's clear-the-input shortcut.
 */

function normalize(error, message) {
  const raw = error ?? message
  if (!raw) return null
  if (typeof raw === 'string') return { status: null, message: raw }
  return {
    status: raw.status ?? raw?.response?.status ?? null,
    message: raw.message ?? raw?.response?.data?.detail ?? 'Something went wrong.',
  }
}

const VARIANTS = {
  503: {
    Icon: ServerCrash,
    title: 'Ollama is not running',
    hint: 'Start it with "ollama serve" in a terminal, then send your question again.',
    box: 'bg-orange-50 border-orange-200',
    titleColor: 'text-orange-900',
    bodyColor: 'text-orange-800',
    iconColor: 'text-orange-600',
    close: 'text-orange-400 hover:text-orange-700',
  },
  400: {
    Icon: AlertTriangle,
    title: 'Check your question',
    hint: 'Type a question before sending. Questions are limited to 2000 characters.',
    box: 'bg-amber-50 border-amber-200',
    titleColor: 'text-amber-900',
    bodyColor: 'text-amber-800',
    iconColor: 'text-amber-600',
    close: 'text-amber-400 hover:text-amber-700',
  },
  default: {
    Icon: AlertCircle,
    title: 'Something went wrong',
    hint: null,
    box: 'bg-red-50 border-red-200',
    titleColor: 'text-red-900',
    bodyColor: 'text-red-800',
    iconColor: 'text-red-600',
    close: 'text-red-400 hover:text-red-700',
  },
}

/** True for elements where Escape means "clear this field", not "close the toast". */
function isTextEntry(el) {
  const tag = el?.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || el?.isContentEditable === true
}

export default function ErrorToast({ error, message, onDismiss }) {
  const normalized = normalize(error, message)
  const canDismiss = Boolean(onDismiss) && Boolean(normalized)

  // Escape to dismiss (Day 8).
  //
  // onDismiss is held in a ref so the listener subscribes once per toast rather
  // than on every render. Callers pass an inline arrow, so a render-keyed effect
  // would unsubscribe and resubscribe constantly — and when two toasts are on
  // screen, the first one's dismissal flushes a re-render that removes the
  // second one's listener *during* the same keydown dispatch, so the second
  // toast never sees the Escape. One press then dismissed only one toast. With a
  // stable listener, one press dismisses every toast on screen.
  const dismissRef = useRef(onDismiss)
  dismissRef.current = onDismiss

  useEffect(() => {
    if (!canDismiss) return undefined
    const onKeyDown = e => {
      if (e.key !== 'Escape' || isTextEntry(e.target)) return
      dismissRef.current?.()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [canDismiss])

  if (!normalized) return null

  const v = VARIANTS[normalized.status] ?? VARIANTS.default
  const { Icon } = v

  return (
    <div role="alert" className={`flex items-start gap-3 border rounded-lg px-4 py-3 ${v.box}`}>
      <Icon size={18} className={`flex-shrink-0 mt-0.5 ${v.iconColor}`} />
      <div className="flex-1 min-w-0">
        <p className={`text-sm font-semibold ${v.titleColor}`}>
          {v.title}
          {normalized.status && (
            <span className="ml-2 font-normal text-xs opacity-70">HTTP {normalized.status}</span>
          )}
        </p>
        <p className={`text-sm mt-0.5 break-words ${v.bodyColor}`}>{normalized.message}</p>
        {v.hint && (
          <p className={`text-xs mt-1.5 opacity-80 break-words ${v.bodyColor}`}>{v.hint}</p>
        )}
      </div>
      {onDismiss && (
        <button
          onClick={onDismiss}
          aria-label="Dismiss error (Esc)"
          title="Dismiss (Esc)"
          className={`focus-ring flex-shrink-0 rounded transition-colors ${v.close}`}
        >
          <X size={16} />
        </button>
      )}
    </div>
  )
}
