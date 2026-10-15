import { useState, useCallback } from 'react'
import type { Message } from '@/types'
import { sendChatMessage, streamChatMessage } from '@/services/chatService'

function generateId() {
  return `msg_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`

}

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  // 同一次页面会话内共享一个 session_id，后端据此维持多轮上下文
  const [sessionId] = useState(() =>
    typeof crypto !== 'undefined' && crypto.randomUUID
      ? crypto.randomUUID()
      : `sess_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`
  )

  const sendMessage = useCallback(async (content: string) => {
    if (!content.trim() || isStreaming) return

    const userMessage: Message = {
      id: generateId(),
      role: 'user',
      content: content.trim(),
      timestamp: Date.now(),
    }

    const assistantMessage: Message = {
      id: generateId(),
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
    }

    setMessages((prev) => [...prev, userMessage, assistantMessage])
    setIsStreaming(true)

    try {
      // 优先使用非流式请求（支持 Tool Calling），失败后回退到流式
      try {
        const reply = await sendChatMessage(content.trim(), sessionId)
        if (reply) {
          setMessages((prev) => {
            const updated = [...prev]
            const last = updated[updated.length - 1]
            if (last?.id === assistantMessage.id) {
              updated[updated.length - 1] = { ...last, content: reply }
            }
            return updated
          })
          return
        }
      } catch {
        // 非流式请求失败，回退到流式
      }

      // 流式回退
      const generator = streamChatMessage(content.trim(), sessionId)
      let fullContent = ''
      let reasoningContent = ''
      let hasError = false

      for await (const chunk of generator) {
        if (chunk.error) {
          hasError = true
          setMessages((prev) => {
            const updated = [...prev]
            const last = updated[updated.length - 1]
            if (last?.id === assistantMessage.id) {
              updated[updated.length - 1] = { ...last, content: `错误：${chunk.error}` }
            }
            return updated
          })
          break
        }

        if (chunk.reasoning) {
          reasoningContent += chunk.reasoning
        }

        if (chunk.content) {
          fullContent += chunk.content
        }

        setMessages((prev) => {
          const updated = [...prev]
          const last = updated[updated.length - 1]
          if (last?.id === assistantMessage.id) {
            updated[updated.length - 1] = {
              ...last,
              content: fullContent,
              reasoning: reasoningContent || undefined,
            }
          }
          return updated
        })
      }

      if (hasError || !fullContent) {
        setMessages((prev) => {
          const updated = [...prev]
          const last = updated[updated.length - 1]
          if (last?.id === assistantMessage.id && !last.content) {
            updated[updated.length - 1] = {
              ...last,
              content: '请求失败，请重试',
            }
          }
          return updated
        })
      }
    } finally {
      setIsStreaming(false)
    }
  }, [isStreaming, sessionId])

  const clearMessages = useCallback(() => {
    setMessages([])
  }, [])

  return {
    messages,
    isStreaming,
    sendMessage,
    clearMessages,
  }
}
