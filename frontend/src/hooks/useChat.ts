import { useState, useCallback } from 'react'
import type { Message } from '@/types'
import { sendChatMessage, streamChatMessage } from '@/services/chatService'

function generateId() {
  return `msg_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
}

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [isStreaming, setIsStreaming] = useState(false)

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
      const generator = streamChatMessage(content.trim())
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

      if (!hasError && !fullContent) {
        try {
          const reply = await sendChatMessage(content.trim())
          if (reply) {
            setMessages((prev) => {
              const updated = [...prev]
              const last = updated[updated.length - 1]
              if (last?.id === assistantMessage.id) {
                updated[updated.length - 1] = { ...last, content: reply }
              }
              return updated
            })
          }
        } catch (e) {
          setMessages((prev) => {
            const updated = [...prev]
            const last = updated[updated.length - 1]
            if (last?.id === assistantMessage.id) {
              updated[updated.length - 1] = {
                ...last,
                content: `请求失败：${e instanceof Error ? e.message : '未知错误'}`,
              }
            }
            return updated
          })
        }
      }
    } finally {
      setIsStreaming(false)
    }
  }, [isStreaming])

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
