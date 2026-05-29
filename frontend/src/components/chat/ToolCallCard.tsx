import { useState } from 'react'
import type { ToolCall } from '@/types'
import { IconWrench, IconChevronRight } from '@/components/ui/Icons'

export default function ToolCallCard({ toolCall }: { toolCall: ToolCall }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="rounded-lg border border-[var(--border-primary)] bg-[var(--bg-tertiary)] overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
      >
        <IconWrench className="shrink-0" />
        <span className="font-medium">调用工具：{toolCall.name}</span>
        <IconChevronRight
          className={`ml-auto transition-transform ${expanded ? 'rotate-90' : ''}`}
        />
      </button>

      {expanded && (
        <div className="px-3 pb-3 space-y-2 border-t border-[var(--border-primary)] pt-2">
          <div>
            <p className="text-xs text-[var(--text-tertiary)] mb-1">参数</p>
            <pre className="text-xs text-[var(--text-secondary)] font-mono bg-[var(--bg-secondary)] rounded p-2 overflow-x-auto">
              {JSON.stringify(toolCall.arguments, null, 2)}
            </pre>
          </div>
          {toolCall.result && (
            <div>
              <p className="text-xs text-[var(--text-tertiary)] mb-1">结果</p>
              <pre className="text-xs text-[var(--text-secondary)] font-mono bg-[var(--bg-secondary)] rounded p-2 overflow-x-auto whitespace-pre-wrap">
                {toolCall.result}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
