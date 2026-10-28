import { useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Message } from '@/types'
import ToolCallCard from './ToolCallCard'
import { IconActivity, IconChat, IconSun, IconUser, IconWrench } from '@/components/ui/Icons'

interface MessageListProps {
  messages: Message[]
  isStreaming: boolean
  onQuickAsk?: (question: string) => void
}

export default function MessageList({ messages, isStreaming, onQuickAsk }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  if (messages.length === 0) {
    return <EmptyState onQuickAsk={onQuickAsk} />
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto max-w-3xl space-y-7 px-4 py-8">
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        {isStreaming && (
          <div className="inline-flex items-center gap-2 rounded-full border border-[var(--border-primary)] bg-[var(--bg-secondary)] px-3 py-1.5 text-xs text-[var(--text-tertiary)]">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand-500" />
            正在思考...
          </div>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}

function MessageBubble({ message }: { message: Message }) {
  if (message.role === 'user') {
    return (
      <div className="flex items-start justify-end gap-3">
        <div className="max-w-[78%] rounded-2xl rounded-br-md bg-brand-500 px-4 py-2.5 text-white shadow-sm">
          <p className="whitespace-pre-wrap text-sm leading-6">{message.content}</p>
        </div>
        <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-brand-500/20 bg-brand-500/10">
          <IconUser className="text-brand-600" />
        </div>
      </div>
    )
  }

  if (message.role === 'system') {
    return null
  }

  return (
    <div className="flex items-start gap-3">
      <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[var(--text-primary)] text-[var(--bg-primary)] shadow-sm">
        <span className="text-xs font-bold">F</span>
      </div>
      <div className="min-w-0 flex-1 space-y-3">
        {message.reasoning && <ReasoningBlock content={message.reasoning} />}
        {message.content && (
          <div className="rounded-2xl rounded-tl-md border border-[var(--border-primary)]/80 bg-[var(--bg-secondary)]/75 px-4 py-3.5 shadow-[var(--shadow-card)]">
            <div className="prose prose-sm max-w-none text-[var(--text-primary)]">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
            </div>
          </div>
        )}
        {message.tool_calls?.map((tc, i) => (
          <ToolCallCard key={i} toolCall={tc} />
        ))}
      </div>
    </div>
  )
}

function ReasoningBlock({ content }: { content: string }) {
  return (
    <div className="rounded-lg border border-yellow-500/20 bg-yellow-500/5 overflow-hidden">
      <details className="group">
        <summary className="flex items-center gap-2 px-3 py-2 text-xs font-medium text-yellow-600 dark:text-yellow-400 cursor-pointer hover:bg-yellow-500/5 transition-colors">
          <svg className="w-3.5 h-3.5 group-open:rotate-90 transition-transform" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="9 18 15 12 9 6" />
          </svg>
          思考过程
        </summary>
        <div className="px-3 pb-3 text-xs text-[var(--text-secondary)] leading-relaxed whitespace-pre-wrap">
          {content}
        </div>
      </details>
    </div>
  )
}

function EmptyState({ onQuickAsk }: { onQuickAsk?: (question: string) => void }) {
  const quickQuestions = [
    { label: '这个系统有哪些功能？', icon: IconChat },
    { label: '帮我算一下 123 × 456', icon: IconActivity },
    { label: '创建一个任务：学习 FastAPI', icon: IconWrench },
    { label: '今天北京天气怎么样？', icon: IconSun },
  ]

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto flex min-h-full max-w-3xl flex-col justify-center px-5 py-16">
        <div className="max-w-xl">
          <h2 className="text-2xl font-semibold tracking-tight text-[var(--text-primary)]">
            开始对话
          </h2>
          <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
            直接输入问题，或从下面选一个。
          </p>
        </div>

        <div className="mt-6 grid gap-3 sm:grid-cols-2">
          {quickQuestions.map((q) => {
            const Icon = q.icon
            return (
              <button
                key={q.label}
                onClick={() => onQuickAsk?.(q.label)}
                className="group flex items-center gap-3 rounded-2xl border border-[var(--border-primary)] bg-[var(--bg-secondary)]/75 p-4 text-left transition hover:border-brand-500/30 hover:shadow-[var(--shadow-card)]"
              >
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-brand-500/10 text-brand-600">
                  <Icon />
                </span>
                <span className="min-w-0 flex-1 text-sm font-medium text-[var(--text-primary)]">
                  {q.label}
                </span>
                <span className="text-sm text-[var(--text-tertiary)] transition-transform group-hover:translate-x-0.5">
                  →
                </span>
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}
