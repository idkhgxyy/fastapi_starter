import { useState, type ReactNode } from 'react'
import Navbar from './Navbar'
import Sidebar from './Sidebar'
import { ChatProvider } from '@/contexts/ChatContext'

export default function ChatLayout({ children }: { children: ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <ChatProvider>
      <div className="h-screen flex flex-col bg-[var(--bg-primary)]">
        <Navbar onToggleSidebar={() => setSidebarOpen(!sidebarOpen)} />
        <div className="flex-1 flex min-h-0 relative">
          <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
          {children}
        </div>
      </div>
    </ChatProvider>
  )
}
