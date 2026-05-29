import { useState, useEffect, useCallback } from 'react'
import type { HealthStatus } from '@/types'
import { getHealth } from '@/services/healthService'
import { IconRefresh, IconActivity } from '@/components/ui/Icons'

function StatusDot({ status }: { status: string }) {
  const color = status === 'up' ? 'bg-[var(--color-success)]' : status === 'down' ? 'bg-[var(--color-error)]' : 'bg-[var(--color-warning)]'
  return <span className={`w-3 h-3 rounded-full ${color} animate-pulse`} />
}

const serviceLabels: Record<string, string> = {
  database: 'Database',
  redis: 'Redis',
  ollama: 'Ollama',
}

export default function HealthPage() {
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const fetchHealth = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await getHealth()
      setHealth(data)
    } catch {
      setError('无法获取健康状态')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchHealth()
    const interval = setInterval(fetchHealth, 10000)
    return () => clearInterval(interval)
  }, [fetchHealth])

  const allUp = health?.dependencies && Object.values(health.dependencies).every((d) => d.status === 'up')

  return (
    <div className="min-h-screen bg-[var(--bg-primary)]">
      <header className="h-14 border-b border-[var(--border-primary)] bg-[var(--bg-secondary)] flex items-center px-6 gap-4">
        <h1 className="text-sm font-semibold text-[var(--text-primary)]">系统健康状态</h1>
        <button onClick={fetchHealth} disabled={loading} className="p-1.5 rounded text-[var(--text-tertiary)] hover:text-[var(--text-primary)] disabled:opacity-50 transition-colors">
          <IconRefresh />
        </button>
      </header>

      <div className="max-w-xl mx-auto p-6 space-y-6">
        {loading && !health ? (
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-24 rounded-xl bg-[var(--bg-tertiary)] animate-pulse" />
            ))}
          </div>
        ) : error ? (
          <div className="text-center py-16">
            <p className="text-sm text-[var(--color-error)]">{error}</p>
            <button onClick={fetchHealth} className="mt-3 text-xs text-brand-500 hover:text-brand-400 transition-colors">
              重试
            </button>
          </div>
        ) : health ? (
          <>
            <div className={`p-4 rounded-xl border ${
              allUp ? 'border-[var(--color-success)]/30 bg-[var(--color-success)]/5' : 'border-[var(--color-error)]/30 bg-[var(--color-error)]/5'
            }`}>
              <div className="flex items-center gap-3">
                <IconActivity className={allUp ? 'text-[var(--color-success)]' : 'text-[var(--color-warning)]'} />
                <div>
                  <p className="text-sm font-medium text-[var(--text-primary)]">
                    {allUp ? '所有服务正常运行' : '部分服务异常'}
                  </p>
                  <p className="text-xs text-[var(--text-tertiary)] mt-0.5">
                    版本 {health.version} · {allUp ? '✓' : '⚠'} 每 10 秒自动刷新
                  </p>
                </div>
              </div>
            </div>

            <div className="space-y-3">
              {Object.entries(health.dependencies).map(([key, dep]) => (
                <div key={key} className="p-4 rounded-xl border border-[var(--border-primary)]">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <StatusDot status={dep.status} />
                      <div>
                        <p className="text-sm font-medium text-[var(--text-primary)]">
                          {serviceLabels[key] || key}
                        </p>
                        <p className="text-xs text-[var(--text-tertiary)] mt-0.5">
                          {dep.status === 'up' ? '正常运行' : dep.error || '未知状态'}
                        </p>
                      </div>
                    </div>
                    <span className={`text-xs font-medium ${
                      dep.status === 'up' ? 'text-[var(--color-success)]' : 'text-[var(--color-error)]'
                    }`}>
                      {dep.status === 'up' ? 'UP' : 'DOWN'}
                    </span>
                  </div>
                  {key === 'ollama' && dep.status === 'up' && 'models' in dep && Array.isArray((dep as { models?: string[] }).models) && (
                    <div className="mt-3 pt-3 border-t border-[var(--border-primary)]">
                      <p className="text-xs text-[var(--text-tertiary)] mb-1">可用模型</p>
                      <div className="flex flex-wrap gap-1">
                        {(dep as { models?: string[] }).models?.map((m: string) => (
                          <span key={m} className="text-xs px-2 py-0.5 rounded-full bg-brand-500/10 text-brand-500">
                            {m}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </>
        ) : null}
      </div>
    </div>
  )
}
