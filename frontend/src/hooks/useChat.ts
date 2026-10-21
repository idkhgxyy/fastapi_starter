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

    const patchAssistant = (patch: Partial<Message>) => {
      setMessages((prev) => {
        const updated = [...prev]
        const last = updated[updated.length - 1]
        if (last?.id === assistantMessage.id) {
          updated[updated.length - 1] = { ...last, ...patch }
        }
        return updated
      })
    }

    try {
      // 优先流式：首 token 一两秒内出现，长回答不再干等整个生成过程。
      // 需要工具调用的请求由后端自动转交非流式工具链，前端无需区分。
      let fullContent = ''
      let reasoningContent = ''
      let streamError: string | null = null

      try {
        for await (const chunk of streamChatMessage(content.trim(), sessionId)) {
          if (chunk.error) {
            streamError = chunk.error
            break
          }
          if (chunk.reasoning) {
            reasoningContent += chunk.reasoning
          }
          if (chunk.content) {
            fullContent += chunk.content
          }
          patchAssistant({
            content: fullContent,
            reasoning: reasoningContent || undefined,
          })
        }
      } catch (err) {
        streamError = err instanceof Error ? err.message : '流式请求失败'
      }

      // 已经拿到部分内容就不再回退，避免把用户看到的答案覆盖掉
      if (fullContent) {
        if (streamError) {
          patchAssistant({ content: `${fullContent}\n\n（回答中断：${streamError}）` })
        }
        return
      }

      // 流式什么也没拿到（协议不兼容 / 工具链异常）→ 非流式兜底
      try {
        const reply = await sendChatMessage(content.trim(), sessionId)
        if (reply) {
          patchAssistant({ content: reply })
          return
        }
      } catch {
        // 两条链路都失败，落到下面的统一提示
      }

      patchAssistant({ content: `错误：${streamError ?? '请求失败，请重试'}` })
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
