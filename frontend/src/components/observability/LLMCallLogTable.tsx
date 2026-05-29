import { useState } from 'react'
import type { LLMCallLog } from '@/types'
import { IconX, IconChevronRight } from '@/components/ui/Icons'

interface Props {
  logs: LLMCallLog[]
  loading?: boolean
}

export default function LLMCallLogTable({ logs, loading }: Props) {
  const [selected, setSelected] = useState<LLMCallLog | null>(null)

  return (
    <>
      <div className="rounded-xl border border-[var(--border-primary)] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-[var(--bg-secondary)] text-[var(--text-tertiary)] text-xs uppercase tracking-wider">
                <th className="text-left px-4 py-3 font-medium">#</th>
                <th className="text-left px-4 py-3 font-medium">时间</th>
                <th className="text-left px-4 py-3 font-medium">端点</th>
                <th className="text-left px-4 py-3 font-medium">模型</th>
                <th className="text-right px-4 py-3 font-medium">Token</th>
                <th className="text-right px-4 py-3 font-medium">耗时</th>
                <th className="text-right px-4 py-3 font-medium">成本</th>
                <th className="text-center px-4 py-3 font-medium">状态</th>
                <th className="text-right px-4 py-3 font-medium"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-secondary)]">
              {loading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i}>
                    {Array.from({ length: 9 }).map((_, j) => (
                      <td key={j} className="px-4 py-3"><div className="h-4 rounded bg-[var(--bg-tertiary)] animate-pulse" /></td>
                    ))}
                  </tr>
                ))
              ) : logs.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-4 py-8 text-center text-sm text-[var(--text-tertiary)]">
                    暂无 LLM 调用记录
                  </td>
                </tr>
              ) : (
                logs.map((log, i) => (
                  <tr
                    key={log.id}
                    className="hover:bg-[var(--bg-secondary)] transition-colors cursor-pointer"
                    onClick={() => setSelected(log)}
                  >
                    <td className="px-4 py-3 text-[var(--text-tertiary)] text-xs font-mono">{i + 1}</td>
                    <td className="px-4 py-3 text-[var(--text-secondary)] text-xs font-mono whitespace-nowrap">
                      {new Date(log.created_at).toLocaleTimeString('zh-CN')}
                    </td>
                    <td className="px-4 py-3 text-[var(--text-primary)] font-mono text-xs">{log.endpoint}</td>
                    <td className="px-4 py-3 text-[var(--text-secondary)] text-xs">{log.model_name}</td>
                    <td className="px-4 py-3 text-right text-[var(--text-secondary)] font-mono text-xs">{log.total_tokens}</td>
                    <td className="px-4 py-3 text-right text-[var(--text-secondary)] font-mono text-xs">{(log.latency_ms / 1000).toFixed(1)}s</td>
                    <td className="px-4 py-3 text-right text-[var(--text-secondary)] font-mono text-xs">${log.estimated_cost_usd.toFixed(4)}</td>
                    <td className="px-4 py-3 text-center">
                      <span className={`inline-flex items-center gap-1 text-xs font-medium ${
                        log.status === 'success' ? 'text-[var(--color-success)]' : 'text-[var(--color-error)]'
                      }`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${log.status === 'success' ? 'bg-[var(--color-success)]' : 'bg-[var(--color-error)]'}`} />
                        {log.status === 'success' ? '成功' : '失败'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <IconChevronRight className="text-[var(--text-tertiary)]" />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {selected && (
        <CallDetailModal log={selected} onClose={() => setSelected(null)} />
      )}
    </>
  )
}

function CallDetailModal({ log, onClose }: { log: LLMCallLog; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="fixed inset-0 bg-black/40" onClick={onClose} />
      <div className="relative z-10 w-full max-w-2xl max-h-[85vh] overflow-y-auto rounded-xl border border-[var(--border-primary)] bg-[var(--bg-secondary)] shadow-xl">
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--border-primary)]">
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">调用详情 #{log.id}</h3>
          <button onClick={onClose} className="p-1 rounded text-[var(--text-tertiary)] hover:text-[var(--text-primary)] transition-colors">
            <IconX />
          </button>
        </div>

        <div className="p-5 space-y-4">
          <div className="grid grid-cols-2 gap-4 text-sm">
            {[
              ['端点', log.endpoint],
              ['模型', log.model_name],
              ['供应商', log.provider],
              ['状态', log.status],
              ['Token', `${log.prompt_tokens} prompt + ${log.completion_tokens} completion = ${log.total_tokens} total`],
              ['耗时', `${(log.latency_ms / 1000).toFixed(2)}s`],
              ['成本', `$${log.estimated_cost_usd.toFixed(6)}`],
              ['时间', new Date(log.created_at).toLocaleString('zh-CN')],
            ].map(([label, value]) => (
              <div key={label}>
                <p className="text-xs text-[var(--text-tertiary)] mb-0.5">{label}</p>
                <p className="text-sm text-[var(--text-primary)] font-mono">{value}</p>
              </div>
            ))}
          </div>

          {log.tool_calls && (
            <div>
              <p className="text-xs text-[var(--text-tertiary)] mb-1">工具调用</p>
              <pre className="text-xs text-[var(--text-secondary)] font-mono bg-[var(--bg-tertiary)] rounded-lg p-3 overflow-x-auto whitespace-pre-wrap max-h-40 overflow-y-auto">
                {(() => {
                  try { return JSON.stringify(JSON.parse(log.tool_calls), null, 2) }
                  catch { return log.tool_calls }
                })()}
              </pre>
            </div>
          )}

          <div>
            <p className="text-xs text-[var(--text-tertiary)] mb-1">Prompt</p>
            <pre className="text-xs text-[var(--text-secondary)] font-mono bg-[var(--bg-tertiary)] rounded-lg p-3 overflow-x-auto whitespace-pre-wrap max-h-40 overflow-y-auto">
              {log.prompt || '(空)'}
            </pre>
          </div>

          <div>
            <p className="text-xs text-[var(--text-tertiary)] mb-1">Response</p>
            <pre className="text-xs text-[var(--text-secondary)] font-mono bg-[var(--bg-tertiary)] rounded-lg p-3 overflow-x-auto whitespace-pre-wrap max-h-40 overflow-y-auto">
              {log.response || '(空)'}
            </pre>
          </div>

          {log.error_message && (
            <div>
              <p className="text-xs text-[var(--color-error)] mb-1">错误信息</p>
              <pre className="text-xs text-[var(--color-error)] font-mono bg-[var(--color-error)]/5 rounded-lg p-3 overflow-x-auto">
                {log.error_message}
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
