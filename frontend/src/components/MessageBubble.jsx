import { Sparkles, FileSearch, RotateCw } from 'lucide-react'
import CitationCard from './CitationCard'
import ErrorToast from './ErrorToast'

/**
 * MessageBubble — one turn of the F13 conversation history.
 *
 * role: "user" | "assistant"
 *
 * A "not found" answer arrives from the backend with citations: [] — in that
 * case the answer renders alone, with no empty "Sources" strip (Day 5 handoff).
 *
 * Day 8: a turn may instead be a FAILED turn (status: "failed"), which renders
 * the same ErrorToast — so the 503 / 400 / generic variants stay exactly as
 * distinct as they were — anchored under the question it belongs to, with Retry.
 * A failed turn also has no citations, so the not-found note is gated on it
 * explicitly; without that gate a 503 would claim "no matching passages found",
 * which is a different and wrong statement.
 */
export default function MessageBubble({
  role,
  content,
  citations = [],
  processingTimeMs,
  status,
  error,
  onRetry,
}) {
  const isUser = role === 'user'
  const isFailed = !isUser && status === 'failed'
  const hasCitations = !isUser && !isFailed && citations.length > 0
  const isNotFound = !isUser && !isFailed && citations.length === 0

  if (isFailed) {
    return (
      <div className="flex justify-start mb-5">
        <div className="max-w-[85%] sm:max-w-[75%] w-full flex flex-col gap-2 items-start">
          <ErrorToast error={error} />
          {onRetry && (
            <button
              onClick={onRetry}
              className="focus-ring inline-flex items-center gap-1.5 text-xs font-medium text-gray-600 hover:text-blue-700 hover:bg-gray-100 rounded-lg px-2.5 py-1.5 transition-colors"
            >
              <RotateCw size={13} /> Retry this question
            </button>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-5`}>
      <div
        className={`max-w-[85%] sm:max-w-[75%] flex flex-col gap-2 ${isUser ? 'items-end' : 'items-start'}`}
      >
        {/* min-w-0 is required alongside break-words: this is a flex item, and a
            flex item's default min-width:auto makes its min-content size the
            width of the longest unbreakable token, which overrides the parent's
            max-w and pushes a horizontal scrollbar into the message list.
            break-words alone does not shrink that intrinsic size. */}
        <div
          className={`min-w-0 max-w-full rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap break-words ${
            isUser
              ? 'bg-blue-600 text-white rounded-br-sm'
              : 'bg-white border border-gray-200 text-gray-800 rounded-bl-sm shadow-sm'
          }`}
        >
          {content}
        </div>

        {/* Sources — omitted entirely when the backend returned no citations */}
        {hasCitations && (
          <div className="flex flex-col gap-1.5 w-full">
            <div className="flex items-center gap-1.5">
              <Sparkles size={11} className="text-gray-500" />
              <span className="text-[10px] text-gray-500 font-semibold uppercase tracking-wider">
                {citations.length} source{citations.length > 1 ? 's' : ''}
              </span>
              {typeof processingTimeMs === 'number' && (
                /* gray-500, not gray-300 (Day 2 — contrast): gray-300 on white
                   measured 1.47:1, effectively invisible, and this is the only
                   place the user sees how long their answer took. */
                <span className="text-[10px] text-gray-500 ml-auto tabular-nums">
                  {(processingTimeMs / 1000).toFixed(1)}s
                </span>
              )}
            </div>
            {citations.map((cit, i) => (
              <CitationCard key={`${cit.filename}-${i}`} citation={cit} rank={i} />
            ))}
          </div>
        )}

        {/* "Not found" — explain the absence of sources rather than showing an empty strip */}
        {isNotFound && (
          <div className="flex items-center gap-1.5 text-[10px] text-gray-500">
            <FileSearch size={11} />
            <span>No matching passages found in your documents</span>
          </div>
        )}
      </div>
    </div>
  )
}
