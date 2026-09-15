import { FileSearch } from 'lucide-react'
import DocumentCard from './DocumentCard'

/**
 * DocumentList — F14. Renders uploaded documents, or an empty state.
 */
export default function DocumentList({ documents = [], onDelete }) {
  if (documents.length === 0) {
    return (
      /* Empty state — shares ChatInterface's tokens (rounded-2xl p-3.5 tile,
         26px icon, text-sm semibold heading, text-xs body) so the app's two
         empty states read as one family. */
      <div className="flex flex-col items-center justify-center text-center border border-dashed border-gray-300 rounded-xl py-12 px-6">
        <div className="bg-gray-100 rounded-2xl p-3.5 mb-3">
          <FileSearch className="text-gray-400" size={26} />
        </div>
        <p className="text-sm font-semibold text-gray-700">No documents yet</p>
        <p className="text-xs text-gray-500 mt-1 max-w-xs">
          Upload a PDF above to make it searchable. Scanned PDFs are run through OCR automatically.
        </p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2">
      {documents.map(doc => (
        <DocumentCard key={doc.document_id} document={doc} onDelete={onDelete} />
      ))}
    </div>
  )
}
