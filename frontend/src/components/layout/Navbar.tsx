import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'
import { useTheme } from '@/contexts/ThemeContext'
import { IconSun, IconMoon, IconFile, IconUser, IconLogout, IconSettings, IconMenu } from '@/components/ui/Icons'

export default function Navbar({ onToggleSidebar }: { onToggleSidebar: () => void }) {
  const { user, logout } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const navigate = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  function handleLogout() {
    logout()
    navigate('/auth/login', { replace: true })
  }

  return (
    <nav className="h-16 shrink-0 border-b border-[var(--border-primary)]/80 bg-[var(--bg-secondary)]/80 backdrop-blur-xl flex items-center px-4 gap-3">
      <button
        onClick={onToggleSidebar}
        className="p-2.5 rounded-xl text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)] transition-colors"
        aria-label="打开侧栏"
      >
        <IconMenu />
      </button>

      <div className="flex items-center gap-2.5">
        <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-[var(--text-primary)] text-[var(--bg-primary)] shadow-sm">
          <span className="text-sm font-bold">F</span>
        </div>
        <span className="hidden text-sm font-semibold tracking-tight text-[var(--text-primary)] sm:block">
          Folio
        </span>
      </div>

      <div className="flex-1" />

      <button
        type="button"
        onClick={() => navigate('/knowledge')}
        className="hidden sm:inline-flex h-9 items-center gap-2 rounded-xl border border-[var(--border-primary)] bg-[var(--bg-primary)]/60 px-3 text-xs font-medium text-[var(--text-secondary)] transition hover:border-brand-500/30 hover:text-brand-600"
      >
        <IconFile />
        知识库
      </button>

      <div className="flex items-center gap-1">
        <button
          onClick={toggleTheme}
          className="p-2 rounded-lg text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)] transition-colors"
        >
          {theme === 'dark' ? <IconSun /> : <IconMoon />}
        </button>

        <div className="relative" ref={menuRef}>
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="flex items-center gap-2 p-1.5 rounded-lg hover:bg-[var(--bg-tertiary)] transition-colors"
          >
            <div className="w-7 h-7 rounded-full bg-brand-500/20 flex items-center justify-center">
              <IconUser className="text-brand-500" />
            </div>
            <span className="text-sm text-[var(--text-primary)] hidden sm:block max-w-[120px] truncate">
              {user?.username || '用户'}
            </span>
          </button>

          {menuOpen && (
            <div className="absolute right-0 top-full mt-1 w-48 rounded-xl border border-[var(--border-primary)] bg-[var(--bg-secondary)] shadow-lg py-1 z-50">
              <div className="px-3 py-2 border-b border-[var(--border-primary)]">
                <p className="text-sm font-medium text-[var(--text-primary)] truncate">
                  {user?.username || '用户'}
                </p>
                <p className="text-xs text-[var(--text-tertiary)] truncate">
                  {user?.email || ''}
                </p>
              </div>
              <button
                onClick={() => { setMenuOpen(false); navigate('/settings') }}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)] transition-colors"
              >
                <IconSettings />
                设置
              </button>
              <button
                onClick={handleLogout}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-[var(--color-error)] hover:bg-[var(--bg-tertiary)] transition-colors"
              >
                <IconLogout />
                退出登录
              </button>
            </div>
          )}
        </div>
      </div>
    </nav>
  )
}
