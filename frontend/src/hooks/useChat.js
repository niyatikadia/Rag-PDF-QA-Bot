/**
 * useChat.js — chat state (F13 conversation history) + ask-a-question flow.
 *
 * Day 7: wired to the real backend. POST /api/chat/ask returns
 * schemas.AskResponse — {answer, citations[], processing_time_ms} — and the
 * error path below is unchanged from Day 6 because the Day 6 mock rejected with
 * an Axios-shaped error on purpose.
 *
 * Status codes this hook has to survive (see routers/chat.py):
 *   200 — an answer, including the F11 "not found" answer with citations: [].
 *         That is a valid result, not an error.
 *   400 — empty question.
 *   503 — Ollama unreachable; ErrorToast turns this into "start Ollama".
 *
 * Day 8 — failed turns. Through Day 7 a failed request left the user's question
 * in the history with nothing under it and raised a floating toast, so after a
 * 503 the conversation looked broken, and retrying pushed the same question in
 * twice. A failure now becomes a real turn in the history
 * ({role:'assistant', status:'failed'}) carrying the error and the question that
 * produced it, so MessageBubble can render it under the question it belongs to
 * and offer Retry. The floating `error` is now only for the pre-flight
 * empty-question guard, which has no user bubble to attach to.
 */
import { useState, useCallback } from 'react'
import { askQuestion } from '../services/api'

export function useChat() {
  const [messages, setMessages] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)

  const sendMessage = useCallback(
    async (question, documentId = null) => {
      const trimmed = question.trim()
      if (isLoading) return

      // F12/F13 client-side guard — the backend also rejects this with a 400.
      if (!trimmed) {
        setError({ status: 400, message: 'Question cannot be empty.' })
        return
      }

      setError(null)
      setIsLoading(true)
      setMessages(prev => [...prev, { role: 'user', content: trimmed, citations: [] }])

      try {
        const response = await askQuestion(trimmed, documentId)

        setMessages(prev => [
          ...prev,
          {
            role: 'assistant',
            content: response.answer,
            citations: response.citations ?? [],
            processingTimeMs: response.processing_time_ms,
          },
        ])
      } catch (err) {
        // The failure becomes a turn in the history rather than a floating
        // toast, so the question never sits there answerless.
        setMessages(prev => [
          ...prev,
          {
            role: 'assistant',
            status: 'failed',
            question: trimmed,
            documentId,
            error: {
              status: err?.response?.status ?? null,
              message:
                err?.response?.data?.detail ??
                'Could not reach the backend. Check that the API server is running.',
            },
          },
        ])
      } finally {
        setIsLoading(false)
      }
    },
    [isLoading],
  )

  /**
   * Re-send the question behind a failed turn. Drops the failed turn *and* the
   * user bubble above it first, so a retry replaces the exchange instead of
   * appending a second copy of the same question (the Day 7 duplicate).
   */
  const retryMessage = useCallback(
    index => {
      if (isLoading) return
      const target = messages[index]
      if (!target || target.status !== 'failed') return

      const previous = messages[index - 1]
      const from = previous?.role === 'user' ? index - 1 : index
      setMessages(prev => prev.slice(0, from))
      sendMessage(target.question, target.documentId ?? null)
    },
    [isLoading, messages, sendMessage],
  )

  const clearHistory = useCallback(() => {
    setMessages([])
    setError(null)
  }, [])

  return { messages, isLoading, error, sendMessage, retryMessage, clearHistory, setError }
}
