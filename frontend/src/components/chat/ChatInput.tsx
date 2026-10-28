import { useState, useRef, type KeyboardEvent, type FormEvent } from 'react'
import { IconSend, IconStop } from '@/components/ui/Icons'

interface ChatInputProps {
  onSend: (message: string) => void
  disabled?: boolean
}

export default function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [input, setInput] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  function adjustHeight() {
    const el = textareaRef.current
    if (el) {
      el.style.height = 'auto'
      el.style.height = `${Math.min(el.scrollHeight, 8 * 24)}px`
    }
  }

  function handleSubmit(e?: FormEvent) {
    e?.preventDefault()
    const trimmed = input.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setInput('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="border-t border-[var(--border-primary)]/70 bg-[var(--bg-secondary)]/60 px-4 py-4 backdrop-blur-xl"
    >
      <div className="mx-auto max-w-3xl">
        <div className="flex items-end gap-2 rounded-2xl border border-[var(--border-primary)] bg-[var(--bg-primary)] p-2 shadow-[var(--shadow-card)] transition focus-within:border-brand-500/50 focus-within:ring-4 focus-within:ring-brand-500/10">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => {
              setInput(e.target.value)
              adjustHeight()
            }}
            onKeyDown={handleKeyDown}
            rows={1}
            placeholder="输入消息，按 Enter 发送..."
            disabled={disabled}
            className="max-h-32 flex-1 resize-none bg-transparent px-3 py-2 text-sm leading-6 text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!input.trim() || disabled}
            aria-label={disabled ? '停止生成' : '发送消息'}
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-500 text-white shadow-sm transition hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {disabled ? <IconStop /> : <IconSend />}
          </button>
        </div>
        <p className="mt-2 text-center text-xs text-[var(--text-tertiary)]">
          Shift+Enter 换行 · 答案由知识库内容生成，请核对来源
        </p>
      </div>
    </form>
  )
}
