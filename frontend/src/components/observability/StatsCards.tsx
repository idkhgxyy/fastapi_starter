import type { LLMStats } from '@/types'

function formatNumber(n: number): string {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`
  return n.toLocaleString()
}

const cards = [
  {
    key: 'total_calls' as const,
    label: '总调用次数',
    format: (s: LLMStats) => formatNumber(s.total_calls),
    sub: (s: LLMStats) => `${formatNumber(s.successful_calls)} 成功 / ${formatNumber(s.failed_calls)} 失败`,
  },
  {
    key: 'total_tokens' as const,
    label: '总 Token 量',
    format: (s: LLMStats) => formatNumber(s.total_tokens),
    sub: () => '',
  },
  {
    key: 'avg_latency_ms' as const,
    label: '平均耗时',
    format: (s: LLMStats) => `${(s.avg_latency_ms / 1000).toFixed(2)}s`,
    sub: () => '',
  },
  {
    key: 'total_cost_usd' as const,
    label: '总成本',
    format: (s: LLMStats) => `$${s.total_cost_usd.toFixed(4)}`,
    sub: () => '',
  },
]

export default function StatsCards({ stats }: { stats: LLMStats }) {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      {cards.map((card) => (
        <div key={card.key} className="p-4 rounded-xl border border-[var(--border-primary)] bg-[var(--bg-secondary)]">
          <p className="text-xs text-[var(--text-tertiary)] mb-1">{card.label}</p>
          <p className="text-2xl font-semibold text-[var(--text-primary)] font-mono tracking-tight">
            {card.format(stats)}
          </p>
          {card.sub(stats) && (
            <p className="text-xs text-[var(--text-tertiary)] mt-1">{card.sub(stats)}</p>
          )}
        </div>
      ))}
    </div>
  )
}
