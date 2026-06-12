import { useState, useEffect, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'
import { getCurrentUser, updateLLMConfig, changePassword } from '@/services/userService'
import type { HealthStatus } from '@/types'
import api from '@/services/api'

const PROVIDERS = [
  { value: '', label: '使用全局配置' },
  { value: 'openai', label: 'OpenAI' },
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'ollama', label: 'Ollama' },
  { value: 'custom', label: '自定义' },
]

export default function SettingsPage() {
  const navigate = useNavigate()
  const { user, setUser } = useAuth()

  const [provider, setProvider] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [modelName, setModelName] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [llmSaving, setLlmSaving] = useState(false)
  const [llmMessage, setLlmMessage] = useState('')

  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [pwSaving, setPwSaving] = useState(false)
  const [pwMessage, setPwMessage] = useState('')

  const [health, setHealth] = useState<HealthStatus | null>(null)

  useEffect(() => {
    getCurrentUser().then((u) => setUser(u)).catch(() => {})
    api.get<HealthStatus>('/health').then((r) => setHealth(r.data)).catch(() => {})
  }, [setUser])

  async function handleLLMConfig(e: FormEvent) {
    e.preventDefault()
    setLlmMessage('')
    setLlmSaving(true)
    try {
      const updated = await updateLLMConfig({
        provider: provider || undefined,
        base_url: baseUrl || undefined,
        model_name: modelName || undefined,
        api_key: apiKey || undefined,
      })
      setUser(updated)
      setApiKey('')
      setLlmMessage('LLM 配置已保存')
    } catch {
      setLlmMessage('保存失败，请重试')
    } finally {
      setLlmSaving(false)
    }
  }

  async function handlePassword(e: FormEvent) {
    e.preventDefault()
    setPwMessage('')
    if (newPassword !== confirmPassword) {
      setPwMessage('两次输入的新密码不一致')
      return
    }
    if (newPassword.length < 6) {
      setPwMessage('新密码至少 6 位')
      return
    }
    setPwSaving(true)
    try {
      await changePassword(currentPassword, newPassword)
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
      setPwMessage('密码修改成功')
    } catch {
      setPwMessage('修改失败，请检查旧密码是否正确')
    } finally {
      setPwSaving(false)
    }
  }

  return (
    <div className="min-h-screen bg-[var(--bg-primary)]">
      <header className="h-14 border-b border-[var(--border-primary)] bg-[var(--bg-secondary)] flex items-center px-6 gap-4">
        <button onClick={() => navigate('/chat')} className="text-sm text-[var(--text-tertiary)] hover:text-[var(--text-primary)] transition-colors">
          ← 返回
        </button>
        <h1 className="text-sm font-semibold text-[var(--text-primary)]">用户设置</h1>
      </header>

      <div className="max-w-xl mx-auto p-6 space-y-8">
        <section>
          <h2 className="text-sm font-semibold text-[var(--text-primary)] mb-3">系统状态</h2>
          <div className="grid grid-cols-3 gap-3">
            <StatusCard label="Database" status={health?.dependencies.database.status} />
            <StatusCard label="Redis" status={health?.dependencies.redis.status} />
            <StatusCard label="Ollama" status={health?.dependencies.ollama.status} />
          </div>
          {health?.dependencies.ollama.status !== 'up' && (
            <p className="mt-2 text-xs text-[var(--text-tertiary)]">
              Ollama 未运行 — RAG 文档向量化不可用。运行 <code className="px-1 py-0.5 rounded bg-[var(--bg-tertiary)] font-mono">make up-full</code> 启动完整服务。
            </p>
          )}
        </section>

        <hr className="border-[var(--border-primary)]" />

        <section>
          <h2 className="text-sm font-semibold text-[var(--text-primary)] mb-1">LLM 配置</h2>
          <p className="text-xs text-[var(--text-tertiary)] mb-4">
            配置个人 LLM Key 后，系统将优先使用你的配置，不再使用全局 Key
          </p>

          <form onSubmit={handleLLMConfig} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1">服务商</label>
              <select
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-sm text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition-colors"
              >
                {PROVIDERS.map((p) => (
                  <option key={p.value} value={p.value}>{p.label}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1">Base URL</label>
              <input
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder="https://api.openai.com/v1"
                className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition-colors"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1">模型名称</label>
              <input
                value={modelName}
                onChange={(e) => setModelName(e.target.value)}
                placeholder="gpt-4o-mini"
                className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition-colors"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1">
                API Key {user?.has_custom_llm_key ? <span className="text-[var(--color-success)]">(已配置)</span> : <span className="text-[var(--text-tertiary)]">(未配置)</span>}
              </label>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="sk-..."
                className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] font-mono focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition-colors"
              />
            </div>

            {llmMessage && (
              <p className={`text-sm ${llmMessage.includes('成功') ? 'text-[var(--color-success)]' : 'text-[var(--color-error)]'}`}>
                {llmMessage}
              </p>
            )}

            <button type="submit" disabled={llmSaving} className="px-4 py-2 rounded-lg bg-brand-500 text-white text-sm font-medium hover:bg-brand-600 disabled:opacity-50 transition-colors">
              {llmSaving ? '保存中...' : '保存配置'}
            </button>
          </form>
        </section>

        <hr className="border-[var(--border-primary)]" />

        <section>
          <h2 className="text-sm font-semibold text-[var(--text-primary)] mb-4">修改密码</h2>

          <form onSubmit={handlePassword} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1">旧密码</label>
              <input
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                required
                className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-sm text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition-colors"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1">新密码</label>
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                minLength={6}
                className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-sm text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition-colors"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1">确认新密码</label>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-sm text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition-colors"
              />
            </div>

            {pwMessage && (
              <p className={`text-sm ${pwMessage.includes('成功') ? 'text-[var(--color-success)]' : 'text-[var(--color-error)]'}`}>
                {pwMessage}
              </p>
            )}

            <button type="submit" disabled={pwSaving} className="px-4 py-2 rounded-lg bg-brand-500 text-white text-sm font-medium hover:bg-brand-600 disabled:opacity-50 transition-colors">
              {pwSaving ? '修改中...' : '修改密码'}
            </button>
          </form>
        </section>
      </div>
    </div>
  )
}

function StatusCard({ label, status }: { label: string; status?: string }) {
  const isUp = status === 'up'
  return (
    <div className="flex items-center gap-2 px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-secondary)]">
      <span className={`w-2 h-2 rounded-full ${isUp ? 'bg-emerald-500' : 'bg-red-400'}`} />
      <span className="text-sm text-[var(--text-secondary)]">{label}</span>
      <span className={`text-xs ml-auto ${isUp ? 'text-emerald-500' : 'text-red-400'}`}>
        {isUp ? 'UP' : 'DOWN'}
      </span>
    </div>
  )
}
