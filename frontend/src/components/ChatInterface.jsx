import { useState, useRef, useEffect } from 'react'
import { Send, MessageSquare, Eraser } from 'lucide-react'
import MessageBubble from './MessageBubble'
import LoadingIndicator from './LoadingIndicator'
import ErrorToast from './ErrorToast'
import { useChat } from '../hooks/useChat'

/**
 * ChatInterface — F12 chat UI + F13 conversation history for the session.
 *
 * All chat state lives in useChat(); this component is presentation only, so
 * the Day 7 backend swap happens entirely inside the hook.
 */
export default function ChatInterface({ documentId = null }) {
  const { messages, isLoading, error, sendMessage, retryMessage, clearHistory, setError } =
    useChat()
  const [input, setInput] = useState('')
  const textareaRef = useRef(null)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  const handleSend = () => {
    if (isLoading) return
    sendMessage(input, documentId)
    if (input.trim()) {
      setInput('')
      if (textareaRef.current) textareaRef.current.style.height = 'auto'
    }
  }

  const handleKeyDown = e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
      return
    }
    // Escape clears the draft. It stops here so it does not also dismiss a
    // toast — ErrorToast owns Escape everywhere outside a text field.
    if (e.key === 'Escape' && input) {
      e.preventDefault()
      e.stopPropagation()
      setInput('')
      if (textareaRef.current) textareaRef.current.style.height = 'auto'
    }
  }

  // Grow the textarea with its content, up to the max-height cap.
  const handleChange = e => {
    setInput(e.target.value)
    e.target.style.height = 'auto'
    e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`
  }

  return (
    <div className="flex flex-col h-full">
      {/* Conversation toolbar — only once there is history to clear */}
      {messages.length > 0 && (
        <div className="flex items-center justify-between gap-3 px-4 sm:px-6 py-2 border-b border-gray-200 bg-white/60">
          <span className="text-xs text-gray-500 truncate">
            {messages.filter(m => m.role === 'user').length} question
            {messages.filter(m => m.role === 'user').length === 1 ? '' : 's'} this session
          </span>
          <button
            onClick={clearHistory}
            className="focus-ring flex-shrink-0 flex items-center gap-1.5 text-xs text-gray-500 hover:text-red-600 transition-colors px-2 py-1 rounded hover:bg-gray-100"
          >
            <Eraser size={13} /> Clear chat
          </button>
        </div>
      )}

      {/* Message list */}
      <div className="flex-1 min-h-0 overflow-y-auto px-4 sm:px-6 py-6">
        <div className="max-w-3xl mx-auto">
          {messages.length === 0 && !isLoading && (
            /* Empty state — same tokens as DocumentList's, so the two read as
               one family: rounded-2xl p-3.5 tile, 26px icon, text-sm semibold
               heading, text-xs body. Only the framing differs (this one is the
               page's hero and is vertically centred). */
            <div className="flex flex-col items-center justify-center h-full min-h-[50vh] text-center">
              <div className="bg-blue-50 rounded-2xl p-3.5 mb-3">
                <MessageSquare className="text-blue-500" size={26} />
              </div>
              <p className="text-sm font-semibold text-gray-700">Ask a question about your PDFs</p>
              <p className="text-xs text-gray-500 mt-1 max-w-sm">
                Answers are grounded in your uploaded documents and cite the file and page they came
                from. Upload PDFs on the Documents tab first.
              </p>
            </div>
          )}

          {messages.map((msg, i) => (
            <MessageBubble
              key={i}
              role={msg.role}
              content={msg.content}
              citations={msg.citations}
              processingTimeMs={msg.processingTimeMs}
              status={msg.status}
              error={msg.error}
              onRetry={msg.status === 'failed' ? () => retryMessage(i) : undefined}
            />
          ))}

          {isLoading && <LoadingIndicator variant="chat" />}

          {error && (
            <div className="mb-4">
              <ErrorToast error={error} onDismiss={() => setError(null)} />
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </div>

      {/* Input bar */}
      <div className="border-t border-gray-200 bg-white px-4 sm:px-6 py-4">
        <div className="max-w-3xl mx-auto">
          <div className="flex items-end gap-3 bg-gray-50 border border-gray-300 rounded-xl px-4 py-3 focus-within:border-blue-500 focus-within:ring-1 focus-within:ring-blue-500 transition-colors">
            <textarea
              ref={textareaRef}
              className="flex-1 bg-transparent resize-none text-sm text-gray-800 placeholder-gray-500 outline-none max-h-40 leading-relaxed"
              rows={1}
              maxLength={2000}
              placeholder="Ask a question about your uploaded PDFs…"
              value={input}
              onChange={handleChange}
              onKeyDown={handleKeyDown}
              disabled={isLoading}
            />
            <button
              onClick={handleSend}
              disabled={isLoading}
              aria-label="Send question"
              className="focus-ring flex-shrink-0 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed text-white rounded-lg p-2 transition-colors"
            >
              <Send size={16} />
            </button>
          </div>
          {/* Keyboard shortcuts, documented in the UI. The character limit is
              dropped below sm so the line does not wrap on a phone.

              gray-500, not gray-400 (Day 2 — contrast). At gray-400 this line
              measured 2.54:1 against WCAG AA's 4.5:1, which made the app's own
              keyboard-accessibility hint the least readable text on the page.
              gray-500 measures 4.83:1. */}
          <p className="text-xs text-gray-500 mt-1.5 text-center">
            <kbd className="font-sans font-medium">Enter</kbd> to send ·{' '}
            <kbd className="font-sans font-medium">Shift+Enter</kbd> for a new line ·{' '}
            <kbd className="font-sans font-medium">Esc</kbd> to clear
            <span className="hidden sm:inline"> · max 2000 characters</span>
          </p>
        </div>
      </div>
    </div>
  )
}
