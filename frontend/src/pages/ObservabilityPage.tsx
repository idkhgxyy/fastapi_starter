import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { getLLMStats, listLLMCalls } from '@/services/observabilityService'
import type { LLMStats, LLMCallLog } from '@/types'
import StatsCards from '@/components/observability/StatsCards'
import TrendChart from '@/components/observability/TrendChart'
import EndpointChart from '@/components/observability/EndpointChart'
import LLMCallLogTable from '@/components/observability/LLMCallLogTable'
import { IconRefresh } from '@/components/ui/Icons'

export default function ObservabilityPage() {
  const navigate = useNavigate()
  const [stats, setStats] = useState<LLMStats | null>(null)
  const [logs, setLogs] = useState<LLMCallLog[]>([])
  const [statsLoading, setStatsLoading] = useState(true)
  const [logsLoading, setLogsLoading] = useState(true)
  const [days, setDays] = useState(7)

  const fetchData = useCallback(async () => {
    setStatsLoading(true)
    setLogsLoading(true)
    try {
      const [statsData, logsData] = await Promise.all([
        getLLMStats(days),
        listLLMCalls(0, 20),
      ])
      setStats(statsData)
      setLogs(logsData)
    } catch {} finally {
      setStatsLoading(false)
      setLogsLoading(false)
    }
  }, [days])

  useEffect(() => { fetchData() }, [fetchData])

  const DAY_OPTIONS = [7, 14, 30]

  return (
    <div className="min-h-screen bg-[var(--bg-primary)]">
      <header className="h-14 border-b border-[var(--border-primary)] bg-[var(--bg-secondary)] flex items-center px-6 gap-4">
        <button onClick={() => navigate('/chat')} className="text-sm text-[var(--text-tertiary)] hover:text-[var(--text-primary)] transition-colors">
          ← 返回
        </button>
        <h1 className="text-sm font-semibold text-[var(--text-primary)]">可观测性面板</h1>
        <div className="flex-1" />
        <div className="flex items-center gap-1 bg-[var(--bg-primary)] rounded-lg p-0.5 border border-[var(--border-primary)]">
          {DAY_OPTIONS.map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`px-2.5 py-1 text-xs font-medium rounded-md transition-colors ${
                days === d ? 'bg-brand-500 text-white' : 'text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]'
              }`}
            >
              {d}天
            </button>
          ))}
        </div>
        <button onClick={fetchData} className="p-1.5 rounded text-[var(--text-tertiary)] hover:text-[var(--text-primary)] transition-colors">
          <IconRefresh />
        </button>
      </header>

      <div className="max-w-5xl mx-auto p-6 space-y-6">
        {statsLoading && !stats ? (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-24 rounded-xl bg-[var(--bg-tertiary)] animate-pulse" />
            ))}
          </div>
        ) : stats ? (
          <>
            <StatsCards stats={stats} />

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
              <div className="lg:col-span-2">
                <TrendChart data={stats.daily_stats} dataKey="calls" label={`近 ${days} 天调用趋势`} color="#6366f1" />
              </div>
              <div>
                <TrendChart data={stats.daily_stats} dataKey="tokens" label="Token 趋势" color="#22c55e" />
              </div>
            </div>

            <EndpointChart data={stats.endpoint_stats} />

            <section>
              <h2 className="text-sm font-medium text-[var(--text-primary)] mb-3">LLM 调用日志</h2>
              <LLMCallLogTable logs={logs} loading={logsLoading} />
            </section>
          </>
        ) : null}
      </div>
    </div>
  )
}
