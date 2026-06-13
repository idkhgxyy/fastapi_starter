import { useState, useEffect, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'
import { login, getCurrentUser } from '@/services/authService'
import api from '@/services/api'

export default function LoginPage() {
  const navigate = useNavigate()
  const { login: authLogin } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [tokenInput, setTokenInput] = useState('')
  const [showTokenLogin, setShowTokenLogin] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    api.get('/auth/setup/status').then((r) => {
      if (!r.data.initialized) {
        navigate('/setup', { replace: true })
      }
    }).catch(() => {})
  }, [navigate])

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const { access_token } = await login(email, password)
      authLogin(access_token, { id: 0, username: '', email, full_name: null, is_active: true, is_superuser: false, has_custom_llm_key: false, llm_provider: null, llm_base_url: null, llm_model_name: null })
      const user = await getCurrentUser()
      authLogin(access_token, user)
      navigate('/chat', { replace: true })
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { status?: number; data?: { detail?: string } } }
        if (axiosErr.response?.status === 401) {
          setError('邮箱或密码错误')
        } else if (axiosErr.response?.data?.detail) {
          setError(axiosErr.response.data.detail)
        } else {
          setError('登录失败，请稍后重试')
        }
      } else {
        setError('连接服务器失败，请检查网络')
      }
    } finally {
      setLoading(false)
    }
  }

  function handleTokenLogin() {
    const trimmed = tokenInput.trim()
    if (!trimmed) return
    authLogin(trimmed, { id: 0, username: '', email: '', full_name: null, is_active: true, is_superuser: false, has_custom_llm_key: false, llm_provider: null, llm_base_url: null, llm_model_name: null })
    navigate('/chat', { replace: true })
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--bg-primary)] p-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-[var(--text-primary)] tracking-tight">
            FastAPI AI Agent
          </h1>
          <p className="text-sm text-[var(--text-tertiary)] mt-1">
            登录以继续使用
          </p>
        </div>

        <div className="rounded-xl border border-[var(--border-primary)] bg-[var(--bg-secondary)] p-6">
          <div className="flex mb-6 border-b border-[var(--border-primary)]">
            <Link
              to="/auth/login"
              className="flex-1 pb-3 text-sm font-medium text-center text-brand-500 border-b-2 border-brand-500"
            >
              登录
            </Link>
            <Link
              to="/auth/register"
              className="flex-1 pb-3 text-sm font-medium text-center text-[var(--text-tertiary)] hover:text-[var(--text-primary)] transition-colors"
            >
              注册
            </Link>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-[var(--text-secondary)] mb-1">
                邮箱
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
                className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500 transition-colors"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-[var(--text-secondary)] mb-1">
                密码
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500 transition-colors"
              />
            </div>

            {error && (
              <p className="text-sm text-[var(--color-error)] bg-[var(--color-error)]/10 rounded-lg px-3 py-2">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 rounded-lg bg-brand-500 text-white text-sm font-medium hover:bg-brand-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? '登录中...' : '登录'}
            </button>
          </form>

          <div className="mt-4">
            <button
              type="button"
              onClick={() => setShowTokenLogin(!showTokenLogin)}
              className="text-xs text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] transition-colors"
            >
              {showTokenLogin ? '收起' : '粘贴 Token 直接登录'}
            </button>

            {showTokenLogin && (
              <div className="mt-3 space-y-2">
                <input
                  type="text"
                  value={tokenInput}
                  onChange={(e) => setTokenInput(e.target.value)}
                  placeholder="粘贴 JWT Token..."
                  className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500 transition-colors"
                />
                <button
                  type="button"
                  onClick={handleTokenLogin}
                  disabled={!tokenInput.trim()}
                  className="w-full py-2 rounded-lg border border-brand-500/30 text-brand-500 text-sm font-medium hover:bg-brand-500/10 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  确认
                </button>
              </div>
            )}
          </div>
        </div>

        <p className="text-center mt-6 text-xs text-[var(--text-tertiary)]">
          FastAPI AI Agent v0.1.0
        </p>
      </div>
    </div>
  )
}
