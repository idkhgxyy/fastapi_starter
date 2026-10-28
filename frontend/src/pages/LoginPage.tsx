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
    <div className="relative min-h-screen overflow-hidden bg-[var(--bg-primary)]">
      <div className="pointer-events-none absolute -left-32 top-0 h-96 w-96 rounded-full bg-brand-500/15 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-40 right-0 h-[28rem] w-[28rem] rounded-full bg-[#c47b2c]/10 blur-3xl" />

      <div className="relative z-10 mx-auto flex min-h-screen max-w-6xl items-center px-4 py-10 sm:px-6 lg:px-8">
        <div className="grid w-full gap-12 lg:grid-cols-[1.05fr_0.95fr] lg:items-center">
          <section className="hidden lg:block">
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[var(--text-primary)] text-[var(--bg-primary)] shadow-lg shadow-black/10">
                <span className="text-lg font-bold">A</span>
              </div>
              <div>
                <p className="text-sm font-semibold tracking-tight">Agent</p>
                <p className="text-xs text-[var(--text-tertiary)]">Knowledge workspace</p>
              </div>
            </div>

            <p className="eyebrow mt-16">Private knowledge workspace</p>
            <h1 className="mt-4 max-w-xl font-display text-6xl leading-[0.95] tracking-tight text-[var(--text-primary)] xl:text-7xl">
              Your notes,
              <span className="block italic text-brand-500">on demand.</span>
            </h1>
            <p className="mt-6 max-w-md text-base leading-7 text-[var(--text-secondary)]">
              把散落的文档变成可检索、可引用、可追问的私人知识库。答案带来源，成本看得见。
            </p>

            <div className="mt-10 grid max-w-lg gap-3">
              {[
                ['01', '来源可追溯', '每个回答都能回看到命中的原文片段。'],
                ['02', '成本可控', '语义缓存与调用日志让每次问答都有账可查。'],
                ['03', '自我托管', 'FastAPI + pgvector，数据留在自己的服务器。'],
              ].map(([index, title, description]) => (
                <div key={index} className="flex gap-4 rounded-2xl border border-[var(--border-primary)]/70 bg-[var(--bg-secondary)]/60 p-4 backdrop-blur-sm">
                  <span className="font-mono text-xs text-brand-500">{index}</span>
                  <div>
                    <p className="text-sm font-semibold text-[var(--text-primary)]">{title}</p>
                    <p className="mt-1 text-xs leading-5 text-[var(--text-tertiary)]">{description}</p>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="mx-auto w-full max-w-md">
            <div className="mb-8 flex items-center gap-3 lg:hidden">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--text-primary)] text-[var(--bg-primary)]">
                <span className="font-bold">A</span>
              </div>
              <div>
                <p className="text-sm font-semibold">Agent</p>
                <p className="text-xs text-[var(--text-tertiary)]">Knowledge workspace</p>
              </div>
            </div>

            <div className="card-surface rounded-[28px] p-7 sm:p-8">
              <p className="eyebrow">Welcome back</p>
              <h2 className="mt-3 text-2xl font-semibold tracking-tight text-[var(--text-primary)]">
                登录你的工作台
              </h2>
              <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
                继续整理、检索和追问你的知识库。
              </p>

              <form onSubmit={handleSubmit} className="mt-8 space-y-5">
                <div>
                  <label htmlFor="email" className="mb-2 block text-xs font-semibold uppercase tracking-wider text-[var(--text-tertiary)]">
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
                  <label htmlFor="password" className="mb-2 block text-xs font-semibold uppercase tracking-wider text-[var(--text-tertiary)]">
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
                  <p className="rounded-xl border border-[var(--color-error)]/20 bg-[var(--color-error)]/8 px-3.5 py-2.5 text-sm text-[var(--color-error)]">
                    {error}
                  </p>
                )}

                <button
                  type="submit"
                  disabled={loading}
                  className="group flex h-11 w-full items-center justify-between rounded-xl bg-[var(--text-primary)] px-4 text-sm font-semibold text-[var(--bg-primary)] transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <span>{loading ? '登录中...' : '登录'}</span>
                  <span className="text-base transition-transform group-hover:translate-x-0.5">→</span>
                </button>
              </form>

              <div className="mt-6">
                <button
                  type="button"
                  onClick={() => setShowTokenLogin(!showTokenLogin)}
                  className="text-xs text-[var(--text-tertiary)] transition-colors hover:text-[var(--text-primary)]"
                >
                  {showTokenLogin ? '收起 Token 登录' : '使用 JWT Token 直接登录'}
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

              <p className="mt-7 border-t border-[var(--border-secondary)] pt-5 text-center text-sm text-[var(--text-secondary)]">
                还没有账号？
                <Link to="/auth/register" className="ml-1 font-medium text-brand-600 hover:text-brand-700">
                  创建一个
                </Link>
              </p>
            </div>

            <p className="mt-6 text-center text-xs tracking-wide text-[var(--text-tertiary)]">
              FastAPI AI Agent · v0.1.0
            </p>
          </section>
        </div>
      </div>
    </div>
  )
}
