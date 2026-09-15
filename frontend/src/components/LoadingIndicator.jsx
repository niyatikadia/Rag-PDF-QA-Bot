import { useEffect, useState } from 'react'
import { Loader2, ScanLine } from 'lucide-react'

/**
 * LoadingIndicator — F15 processing-status feedback.
 *
 * variant:
 *   "default" — generic spinner + message (upload, delete, misc).
 *   "ocr"     — amber OCR state: "Running OCR on scanned pages…" (spec §F15).
 *   "chat"    — PATIENT answer-generation state. The first answer after Ollama
 *               starts can take ~4 minutes (Day 5 measured 63.6s warm), so this
 *               variant escalates its copy over time and shows an elapsed timer
 *               instead of looking hung.
 *
 * The escalation lives here (not in the caller) so Day 7 keeps it unchanged.
 */

// Escalating copy for the "chat" variant: [minimum elapsed seconds, message].
const CHAT_STAGES = [
  [0, 'Searching your documents…'],
  [4, 'Reading the most relevant passages…'],
  [12, 'Generating the answer…'],
  [30, 'Still working — the model is warming up.'],
  [75, 'This is the first answer since Ollama started; it can take a few minutes.'],
]

function formatElapsed(seconds) {
  if (seconds < 60) return `${seconds}s`
  return `${Math.floor(seconds / 60)}m ${String(seconds % 60).padStart(2, '0')}s`
}

export default function LoadingIndicator({ message, variant = 'default' }) {
  const isChat = variant === 'chat'
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    if (!isChat) return
    setElapsed(0)
    const id = setInterval(() => setElapsed(e => e + 1), 1000)
    return () => clearInterval(id)
  }, [isChat])

  // ── OCR variant ─────────────────────────────────────────────────────────────
  if (variant === 'ocr') {
    return (
      <div className="flex items-start gap-3 bg-amber-50 border border-amber-200 rounded-lg px-4 py-3">
        <ScanLine size={18} className="text-amber-600 flex-shrink-0 mt-0.5 animate-pulse" />
        <div className="min-w-0">
          <p className="text-sm font-medium text-amber-800">
            {message || 'Running OCR on scanned pages…'}
          </p>
          <p className="text-xs text-amber-700/80 mt-0.5">
            This page had no embedded text. OCR is slower than native extraction.
          </p>
        </div>
      </div>
    )
  }

  // ── Patient chat variant ────────────────────────────────────────────────────
  if (isChat) {
    const stage = [...CHAT_STAGES].reverse().find(([at]) => elapsed >= at)
    const showHint = elapsed >= 30

    return (
      <div className="flex justify-start mb-4">
        {/* max-w matches MessageBubble so the two stay aligned at every width */}
        <div className="max-w-[85%] sm:max-w-[75%] bg-white border border-gray-200 rounded-2xl rounded-bl-sm shadow-sm px-4 py-3">
          <div className="flex items-center gap-3">
            <Loader2 size={16} className="text-blue-600 flex-shrink-0 animate-spin" />
            <span className="text-sm text-gray-700">{message || stage[1]}</span>
            <span className="text-xs text-gray-500 tabular-nums ml-auto pl-3">
              {formatElapsed(elapsed)}
            </span>
          </div>
          {showHint && (
            <p className="text-xs text-gray-500 mt-2 pl-7">
              Answers are generated locally by Ollama — please keep this tab open.
            </p>
          )}
        </div>
      </div>
    )
  }

  // ── Default variant ─────────────────────────────────────────────────────────
  return (
    <div className="flex items-center gap-3 text-sm text-gray-600 py-2 px-3">
      <Loader2 size={16} className="text-blue-600 animate-spin flex-shrink-0" />
      <span>{message || 'Processing…'}</span>
    </div>
  )
}
