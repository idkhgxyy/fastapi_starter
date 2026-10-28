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
    <div className="flex min-h-screen items-center justify-center bg-[var(--bg-primary)] px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-7 text-center">
          <span className="text-lg font-semibold tracking-tight text-[var(--text-primary)]">Folio</span>
        </div>

        <div className="card-surface rounded-2xl p-6 sm:p-7">
          <h1 className="text-xl font-semibold tracking-tight text-[var(--text-primary)]">登录</h1>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">使用邮箱和密码登录。</p>

          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            <div>
              <label htmlFor="email" className="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">
                邮箱
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
                className="h-11 w-full rounded-xl border border-[var(--border-primary)] bg-[var(--bg-primary)] px-3.5 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] transition focus:border-brand-500 focus:outline-none focus:ring-4 focus:ring-brand-500/10"
              />
            </div>

            <div>
              <label htmlFor="password" className="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">
                密码
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                className="h-11 w-full rounded-xl border border-[var(--border-primary)] bg-[var(--bg-primary)] px-3.5 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] transition focus:border-brand-500 focus:outline-none focus:ring-4 focus:ring-brand-500/10"
              />
            </div>

            {error && (
              <p className="rounded-xl border border-[var(--color-error)]/20 bg-[var(--color-error)]/10 px-3.5 py-2.5 text-sm text-[var(--color-error)]">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="h-11 w-full rounded-xl bg-[var(--text-primary)] text-sm font-semibold text-[var(--bg-primary)] transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? '登录中...' : '登录'}
            </button>
          </form>

          <div className="mt-5">
            <button
              type="button"
              onClick={() => setShowTokenLogin(!showTokenLogin)}
              className="text-xs text-[var(--text-tertiary)] transition-colors hover:text-[var(--text-primary)]"
            >
              {showTokenLogin ? '收起 Token 登录' : '使用 JWT Token 登录'}
            </button>

            {showTokenLogin && (
              <div className="mt-3 space-y-2">
                <input
                  type="text"
                  value={tokenInput}
                  onChange={(e) => setTokenInput(e.target.value)}
                  placeholder="粘贴 JWT Token..."
                  className="h-10 w-full rounded-xl border border-[var(--border-primary)] bg-[var(--bg-primary)] px-3 font-mono text-xs text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:border-brand-500 focus:outline-none focus:ring-4 focus:ring-brand-500/10"
                />
                <button
                  type="button"
                  onClick={handleTokenLogin}
                  disabled={!tokenInput.trim()}
                  className="h-10 w-full rounded-xl border border-brand-500/30 text-sm font-medium text-brand-600 transition hover:bg-brand-500/10 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  确认登录
                </button>
              </div>
            )}
          </div>

          <p className="mt-6 border-t border-[var(--border-secondary)] pt-4 text-center text-sm text-[var(--text-secondary)]">
            还没有账号？
            <Link to="/auth/register" className="ml-1 font-medium text-brand-600 hover:text-brand-700">
              创建一个
            </Link>
          </p>
        </div>

        <p className="mt-5 text-center text-xs text-[var(--text-tertiary)]">Folio · v0.1.0</p>
      </div>
    </div>
  )
}
