import { useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Message } from '@/types'
import ToolCallCard from './ToolCallCard'
import { IconUser } from '@/components/ui/Icons'

interface MessageListProps {
  messages: Message[]
  isStreaming: boolean
}

export default function MessageList({ messages, isStreaming }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  if (messages.length === 0) {
    return <EmptyState />
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-3xl mx-auto py-6 px-4 space-y-6">
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        {isStreaming && (
          <div className="flex items-center gap-2 text-sm text-[var(--text-tertiary)]">
            <span className="w-1.5 h-1.5 rounded-full bg-brand-500 animate-pulse" />
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
        <div className="max-w-[70%] bg-brand-500 text-white rounded-2xl rounded-br-md px-4 py-2.5">
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        </div>
        <div className="w-8 h-8 rounded-full bg-brand-500/20 flex items-center justify-center shrink-0 mt-1">
          <IconUser className="text-brand-500" />
        </div>
      </div>
    )
  }

  if (message.role === 'system') {
    return null
  }

  return (
    <div className="flex items-start gap-3">
      <div className="w-8 h-8 rounded-full bg-brand-500 flex items-center justify-center shrink-0 mt-1">
        <span className="text-white text-xs font-bold">A</span>
      </div>
      <div className="flex-1 min-w-0 space-y-3">
        {message.reasoning && (
          <ReasoningBlock content={message.reasoning} />
        )}
        {message.content && (
          <div className="prose prose-sm max-w-none text-[var(--text-primary)]">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content}
            </ReactMarkdown>
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

function EmptyState() {
  return (
    <div className="flex-1 flex items-center justify-center">
      <div className="text-center">
        <div className="w-16 h-16 rounded-2xl bg-brand-500/10 flex items-center justify-center mx-auto mb-4">
          <svg className="w-8 h-8 text-brand-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
        </div>
        <h2 className="text-lg font-semibold text-[var(--text-primary)] mb-1">
          开始对话
        </h2>
        <p className="text-sm text-[var(--text-tertiary)] max-w-sm">
          在下方输入消息与 AI 助手对话，或在侧边栏管理知识库与任务
        </p>
      </div>
    </div>
  )
}
