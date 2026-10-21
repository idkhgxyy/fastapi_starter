import { useState, useCallback, useEffect } from 'react'
import type { Message } from '@/types'
import type { ConversationMessage, ConversationSummary } from '@/services/conversationService'
import {
  createConversation,
  deleteConversation as deleteConversationApi,
  getConversation,
  listConversations,
} from '@/services/conversationService'
import { sendChatMessage, streamChatMessage } from '@/services/chatService'

const LAST_CONVERSATION_KEY = 'agent_last_conversation'

function generateId() {
  return `msg_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
}

function toUiMessage(message: ConversationMessage): Message {
  return {
    id: `db_${message.id}`,
    role: message.role === 'assistant' ? 'assistant' : 'user',
    content: message.content,
    timestamp: Date.parse(message.created_at) || Date.now(),
  }
}

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [conversationId, setConversationId] = useState<number | null>(null)
  const [conversations, setConversations] = useState<ConversationSummary[]>([])
  const [loadingConversations, setLoadingConversations] = useState(true)
  const [conversationsError, setConversationsError] = useState('')

  const refreshConversations = useCallback(async () => {
    try {
      const data = await listConversations()
      setConversations(data)
      setConversationsError('')
      return data
    } catch {
      setConversationsError('会话列表加载失败')
      return []
    } finally {
      setLoadingConversations(false)
    }
  }, [])

  const selectConversation = useCallback(
    async (id: number) => {
      if (isStreaming) return
      try {
        const detail = await getConversation(id)
        setConversationId(id)
        setMessages(detail.messages.map(toUiMessage))
        localStorage.setItem(LAST_CONVERSATION_KEY, String(id))
      } catch {
        setConversationsError('会话加载失败')
        localStorage.removeItem(LAST_CONVERSATION_KEY)
      }
    },
    [isStreaming]
  )

  const newConversation = useCallback(() => {
    if (isStreaming) return
    setConversationId(null)
    setMessages([])
    localStorage.removeItem(LAST_CONVERSATION_KEY)
  }, [isStreaming])

  const removeConversation = useCallback(
    async (id: number) => {
      try {
        await deleteConversationApi(id)
      } catch {
        setConversationsError('删除会话失败')
        return
      }
      if (conversationId === id) {
        setConversationId(null)
        setMessages([])
        localStorage.removeItem(LAST_CONVERSATION_KEY)
      }
      await refreshConversations()
    },
    [conversationId, refreshConversations]
  )

  // 首屏：拉会话列表，并恢复上次打开的会话（刷新/断线不丢）
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      const data = await refreshConversations()
      if (cancelled) return
      const saved = Number(localStorage.getItem(LAST_CONVERSATION_KEY))
      if (!saved || !data.some((item) => item.id === saved)) {
        localStorage.removeItem(LAST_CONVERSATION_KEY)
        return
      }
      try {
        const detail = await getConversation(saved)
        if (cancelled) return
        setConversationId(saved)
        setMessages(detail.messages.map(toUiMessage))
      } catch {
        localStorage.removeItem(LAST_CONVERSATION_KEY)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [refreshConversations])

  const sendMessage = useCallback(
    async (content: string) => {
      if (!content.trim() || isStreaming) return

      // 没有会话就先建一个：只有真正发消息才会产生会话，避免一堆空会话
      let cid = conversationId
      if (cid === null) {
        try {
          const created = await createConversation()
          cid = created.id
          setConversationId(cid)
          localStorage.setItem(LAST_CONVERSATION_KEY, String(cid))
        } catch {
          // 建会话失败也允许继续聊：后端在没有 conversation_id 时会退回 Redis
          cid = null
        }
      }

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
          for await (const chunk of streamChatMessage(content.trim(), undefined, cid)) {
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
          const reply = await sendChatMessage(content.trim(), undefined, cid)
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
        // 标题与更新时间由后端在落库时更新，这里刷新列表
        void refreshConversations()
      }
    },
    [conversationId, isStreaming, refreshConversations]
  )

  return {
    messages,
    isStreaming,
    conversationId,
    conversations,
    loadingConversations,
    conversationsError,
    sendMessage,
    newConversation,
    selectConversation,
    removeConversation,
    refreshConversations,
  }
}
