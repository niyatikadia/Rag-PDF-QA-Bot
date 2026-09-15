import { useState, useRef } from 'react'
import { Upload } from 'lucide-react'
import LoadingIndicator from './LoadingIndicator'
import ErrorToast from './ErrorToast'
import { uploadDocument } from '../services/api'

/**
 * FileUpload — F1/F15. Drag-and-drop + click-to-select PDF uploader.
 *
 * Day 7: uploadOne() calls the real POST /api/documents/upload. Validation,
 * drag state and the OCR status stage are unchanged from Day 6.
 *
 * Two things about that endpoint shape the component:
 *
 *  1. It answers **202 with an UploadResponse** — {document_id, filename,
 *     status, message} — not a DocumentInfo. There is no total_pages /
 *     total_chunks / ocr_pages_count yet, because ingestion has not run. So
 *     this component hands the raw UploadResponse up and the page refetches
 *     the list rather than pushing a half-populated card into it.
 *
 *  2. Ingestion (including OCR) runs in a FastAPI BackgroundTask *after* the
 *     202, so the upload call itself finishes long before OCR does. The OCR
 *     stage below is therefore driven by `ingestStatus`, which DocumentsPage
 *     computes from its real polled document statuses — this component no
 *     longer guesses "is it scanned?" from the filename.
 */

const MAX_BYTES = 20 * 1024 * 1024 // 20 MB, matches backend validation

export default function FileUpload({ onUploadComplete, ingestStatus = null }) {
  const [isDragging, setIsDragging] = useState(false)
  const [stage, setStage] = useState(null) // { message, variant } | null
  const [error, setError] = useState(null)
  const inputRef = useRef(null)

  /** Sends one file. Resolves with the 202 UploadResponse. */
  const uploadOne = async file => {
    setStage({ message: `Uploading ${file.name}…`, variant: 'default' })
    return uploadDocument(file)
  }

  const handleFiles = async fileList => {
    const files = [...fileList]
    if (files.length === 0) return

    const rejected = files.filter(f => !f.name.toLowerCase().endsWith('.pdf'))
    if (rejected.length > 0) {
      setError(`Only .pdf files are supported — rejected ${rejected.map(f => f.name).join(', ')}.`)
      return
    }

    const tooLarge = files.filter(f => f.size > MAX_BYTES)
    if (tooLarge.length > 0) {
      setError(
        `Each file must be 20 MB or smaller — ${tooLarge[0].name} is ${(tooLarge[0].size / 1024 / 1024).toFixed(1)} MB.`,
      )
      return
    }

    setError(null)
    for (const file of files) {
      try {
        const doc = await uploadOne(file)
        onUploadComplete?.(doc)
      } catch (err) {
        setError({
          status: err?.response?.status ?? null,
          message: err?.response?.data?.detail ?? `Failed to upload ${file.name}.`,
        })
        break
      }
    }
    setStage(null)
    if (inputRef.current) inputRef.current.value = ''
  }

  const isUploading = stage !== null

  return (
    <div className="space-y-3">
      <div
        role="button"
        tabIndex={0}
        aria-label="Upload PDFs — activate to browse, or drop files here"
        /* focus-ring applies in every state. Through Day 7 the only focus hint
           was a border colour in the idle branch, so the dropzone had no visible
           focus at all while dragging or uploading. */
        className={`focus-ring border-2 border-dashed rounded-xl p-6 sm:p-8 text-center transition-colors ${
          isUploading
            ? 'border-gray-200 bg-gray-50 cursor-wait opacity-70'
            : isDragging
              ? 'border-blue-500 bg-blue-50 cursor-pointer'
              : 'border-gray-300 hover:border-blue-400 hover:bg-gray-50 cursor-pointer'
        }`}
        onClick={() => !isUploading && inputRef.current?.click()}
        onKeyDown={e => {
          if (!isUploading && (e.key === 'Enter' || e.key === ' ')) {
            e.preventDefault()
            inputRef.current?.click()
          }
        }}
        onDragOver={e => {
          e.preventDefault()
          if (!isUploading) setIsDragging(true)
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={e => {
          e.preventDefault()
          setIsDragging(false)
          if (!isUploading) handleFiles(e.dataTransfer.files)
        }}
      >
        <Upload
          className={`mx-auto mb-2 ${isDragging ? 'text-blue-500' : 'text-gray-400'}`}
          size={28}
        />
        <p className="text-sm font-medium text-gray-700">
          {isDragging ? 'Drop to upload' : 'Drag & drop PDFs here'}
        </p>
        <p className="text-xs text-gray-500 mt-1">
          or click to browse · PDF only · max 20 MB per file
        </p>
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,.pdf"
          multiple
          className="hidden"
          onChange={e => handleFiles(e.target.files)}
        />
      </div>

      {(stage ?? ingestStatus) && (
        <LoadingIndicator
          message={(stage ?? ingestStatus).message}
          variant={(stage ?? ingestStatus).variant}
        />
      )}
      {error && <ErrorToast error={error} onDismiss={() => setError(null)} />}
    </div>
  )
}
