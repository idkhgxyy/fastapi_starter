import { useState, useEffect, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'
import { getCurrentUser } from '@/services/authService'
import api from '@/services/api'

interface SetupStatus {
  initialized: boolean
  llm_mock: boolean
  llm_provider: string
}

export default function SetupPage() {
  const navigate = useNavigate()
  const { login: authLogin } = useAuth()

  const [status, setStatus] = useState<SetupStatus | null>(null)
  const [loading, setLoading] = useState(true)

  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [llmApiKey, setLlmApiKey] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api.get<SetupStatus>('/auth/setup/status')
      .then((r) => {
        setStatus(r.data)
        if (r.data.initialized) {
          navigate('/auth/login', { replace: true })
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [navigate])

  async function handleSetup(e: FormEvent) {
    e.preventDefault()
    setError('')
    setSaving(true)
    try {
      const { access_token } = (await api.post('/auth/setup', {
        username,
        email,
        password,
        llm_api_key: llmApiKey || undefined,
      })).data
      const user = await getCurrentUser()
      authLogin(access_token, user)
      navigate('/chat', { replace: true })
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { data?: { detail?: string } } }
        setError(axiosErr.response?.data?.detail || '初始化失败，请重试')
      } else {
        setError('连接服务器失败')
      }
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--bg-primary)]">
        <div className="w-5 h-5 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (status?.initialized) return null

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--bg-primary)] p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="w-14 h-14 rounded-2xl bg-brand-500/10 flex items-center justify-center mx-auto mb-4">
            <svg className="w-7 h-7 text-brand-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2L2 7l10 5 10-5-10-5z" />
              <path d="M2 17l10 5 10-5" />
              <path d="M2 12l10 5 10-5" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] tracking-tight">
            欢迎使用 FastAPI Starter
          </h1>
          <p className="text-sm text-[var(--text-tertiary)] mt-1">
            创建管理员账号，开始使用
          </p>
        </div>

        <div className="rounded-xl border border-[var(--border-primary)] bg-[var(--bg-secondary)] p-6">
          <form onSubmit={handleSetup} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1">用户名</label>
              <input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="admin"
                required
                className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition-colors"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1">邮箱</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="admin@example.com"
                required
                className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition-colors"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1">密码</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="至少 6 位"
                required
                minLength={6}
                className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition-colors"
              />
            </div>

            <hr className="border-[var(--border-primary)]" />

            <div>
              <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1">
                LLM API Key <span className="text-[var(--text-tertiary)] font-normal">(可选，留空使用 Mock 模式)</span>
              </label>
              <input
                type="password"
                value={llmApiKey}
                onChange={(e) => setLlmApiKey(e.target.value)}
                placeholder="sk-..."
                className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition-colors"
              />
              <p className="mt-1 text-xs text-[var(--text-tertiary)]">
                {status?.llm_mock
                  ? '当前为 Mock 模式，填入 API Key 后将切换为真实 LLM 调用'
                  : `当前使用 ${status?.llm_provider} 全局配置`}
              </p>
            </div>

            {error && (
              <p className="text-sm text-[var(--color-error)] bg-[var(--color-error)]/10 rounded-lg px-3 py-2">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={saving}
              className="w-full py-2.5 rounded-lg bg-brand-500 text-white text-sm font-medium hover:bg-brand-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {saving ? '初始化中...' : '完成设置，开始使用'}
            </button>
          </form>
        </div>

        <p className="text-center mt-6 text-xs text-[var(--text-tertiary)]">
          FastAPI Starter — 开箱即用的 AI Agent 全栈模板
        </p>
      </div>
    </div>
  )
}
