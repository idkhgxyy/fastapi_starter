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
    <form onSubmit={handleSubmit} className="border-t border-[var(--border-primary)] p-4 bg-[var(--bg-secondary)]">
      <div className="max-w-3xl mx-auto">
        <div className="flex items-end gap-2">
          <div className="flex-1 relative">
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
              className="w-full max-h-32 resize-none rounded-xl border border-[var(--border-primary)] bg-[var(--bg-primary)] px-4 py-3 pr-12 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition-colors disabled:opacity-50"
            />
          </div>
          <button
            type="submit"
            disabled={!input.trim() || disabled}
            className="h-10 w-10 rounded-xl bg-brand-500 text-white flex items-center justify-center hover:bg-brand-600 disabled:opacity-40 disabled:cursor-not-allowed transition-all shrink-0"
          >
            {disabled ? <IconStop /> : <IconSend />}
          </button>
        </div>
        <p className="text-xs text-[var(--text-tertiary)] mt-2 text-center">
          Shift+Enter 换行 · AI 回复可能有误，请注意甄别
        </p>
      </div>
    </form>
  )
}
