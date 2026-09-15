import { FileText, ScanLine } from 'lucide-react'

/**
 * CitationCard — F10 source/citation display.
 *
 * Backend contract (verified Day 5, schemas.Citation):
 *   { filename, pages: [int], relevance_score: float, extraction_method: "native"|"ocr" }
 *
 * Guarantees the backend already provides, which this component relies on:
 *   - one citation per file
 *   - `pages` is always a sorted list
 *   - citations arrive sorted by relevance_score descending  →  `rank` is just
 *     the array index, this component never re-sorts.
 *
 * relevance_score is deliberately labelled MATCH STRENGTH, not "confidence".
 * It is the similarity of the retrieved chunk to the question, not a measure of
 * how correct the answer is — Day 5 saw a correct broad answer score 0.2156.
 */

const MATCH_TOOLTIP =
  'Match strength is how closely this passage matched your question ' +
  '(vector similarity). It is not a measure of how correct the answer is — ' +
  'a correct answer to a broad question can still score low.'

export default function CitationCard({ citation, rank }) {
  const { filename, pages = [], relevance_score = 0, extraction_method } = citation
  const isOcr = extraction_method === 'ocr'
  const percent = Math.round(relevance_score * 100)

  return (
    <div className="bg-white border border-gray-200 rounded-lg px-3 py-2.5 shadow-sm">
      <div className="flex items-start gap-2">
        {typeof rank === 'number' && (
          /* gray-600, not gray-500 (Day 2 — contrast). This badge sits on
             bg-gray-100 rather than white, which costs it enough to land at
             4.39:1 — just under AA's 4.5:1. gray-600 on gray-100 is 7.0:1. */
          <span className="flex-shrink-0 mt-0.5 w-4 h-4 rounded bg-gray-100 text-gray-600 text-[10px] font-semibold flex items-center justify-center">
            {rank + 1}
          </span>
        )}

        <FileText size={14} className="flex-shrink-0 mt-0.5 text-blue-500" />

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 flex-wrap">
            {/* min-w-0 is what makes `truncate` work here: truncate implies
                whitespace-nowrap, so without it this span's min-content width is
                the full filename and it refuses to shrink, pushing the OCR badge
                out of the row instead of ellipsing. */}
            <span className="min-w-0 text-xs font-semibold text-gray-800 truncate" title={filename}>
              {filename}
            </span>

            {/* [v2] OCR badge — flags text recovered from a scanned page */}
            {isOcr && (
              <span
                title="This text was recovered from a scanned page using OCR, so it may contain recognition errors."
                className="inline-flex items-center gap-0.5 bg-amber-100 text-amber-800 border border-amber-300 rounded px-1.5 py-px text-[10px] font-semibold tracking-wide"
              >
                <ScanLine size={9} />
                OCR
              </span>
            )}
          </div>

          <p className="text-[11px] text-gray-500 mt-0.5">
            {pages.length === 1 ? 'Page' : 'Pages'} {pages.join(', ')}
          </p>
        </div>

        {/* Match strength */}
        <div className="flex-shrink-0 text-right w-20 sm:w-24" title={MATCH_TOOLTIP}>
          <p className="text-[10px] uppercase tracking-wider text-gray-500 font-semibold leading-none">
            Match strength
          </p>
          <div className="flex items-center gap-1.5 mt-1 justify-end">
            <span className="h-1 w-8 sm:w-12 bg-gray-100 rounded-full overflow-hidden">
              <span
                className="block h-full bg-blue-500 rounded-full"
                style={{ width: `${Math.max(percent, 2)}%` }}
              />
            </span>
            <span className="text-[11px] font-semibold text-gray-600 tabular-nums">{percent}%</span>
          </div>
        </div>
      </div>
    </div>
  )
}
