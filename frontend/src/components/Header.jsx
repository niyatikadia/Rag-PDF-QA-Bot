import { Link, useLocation } from 'react-router-dom'
import { FileText, MessageSquare } from 'lucide-react'

/**
 * Header — app title + primary navigation. Fixed height; App keeps it out of
 * the scrolling area so pages can own their own scroll.
 */
export default function Header() {
  const { pathname } = useLocation()

  // Nav padding tightens below sm: at 375px the title plus two px-4 buttons plus
  // px-6 gutters overflowed the header.
  const navClass = path =>
    `focus-ring flex items-center gap-1.5 px-2.5 sm:px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
      pathname === path
        ? 'bg-blue-600 text-white'
        : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
    }`

  return (
    <header className="flex-shrink-0 bg-white border-b border-gray-200 px-4 sm:px-6 py-3 flex items-center justify-between gap-2">
      {/* min-w-0 so the title, not the nav, is what yields when space runs out */}
      <div className="flex items-center gap-2 min-w-0">
        <FileText className="text-blue-600 flex-shrink-0" size={22} />
        <span className="font-semibold text-gray-900 truncate">PDF Q&amp;A Chatbot</span>
        <span className="hidden sm:inline flex-shrink-0 text-[10px] font-semibold uppercase tracking-wider text-gray-500 border border-gray-200 rounded px-1.5 py-0.5 ml-1">
          RAG
        </span>
      </div>
      <nav className="flex flex-shrink-0 items-center gap-1 sm:gap-2">
        <Link
          to="/chat"
          className={navClass('/chat')}
          aria-current={pathname === '/chat' ? 'page' : undefined}
        >
          <MessageSquare size={16} /> Chat
        </Link>
        <Link
          to="/documents"
          className={navClass('/documents')}
          aria-current={pathname === '/documents' ? 'page' : undefined}
        >
          <FileText size={16} /> Documents
        </Link>
      </nav>
    </header>
  )
}
