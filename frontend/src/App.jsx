import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Header from './components/Header'
import ChatPage from './pages/ChatPage'
import DocumentsPage from './pages/DocumentsPage'

/**
 * App — shell + routing.
 *
 * The shell is a fixed-height flex column so each page owns its own scrolling:
 * the chat keeps its input bar pinned, the documents page scrolls normally.
 */
export default function App() {
  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <div className="h-screen flex flex-col overflow-hidden">
        <Header />
        <main className="flex-1 min-h-0 overflow-hidden">
          <Routes>
            <Route path="/" element={<Navigate to="/chat" replace />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/documents" element={<DocumentsPage />} />
            <Route path="*" element={<Navigate to="/chat" replace />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
