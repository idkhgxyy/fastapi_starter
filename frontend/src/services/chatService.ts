import api from './api'

export interface ChatRequest {
  message: string
  stream: boolean
}

export async function sendChatMessage(message: string): Promise<string> {
  const response = await api.post<{ reply: string }>('/chat/', {
    message,
    stream: false,
  })
  return response.data.reply
}

export async function* streamChatMessage(message: string): AsyncGenerator<{
  reasoning?: string
  content?: string
  error?: string
}> {
  const useMock = import.meta.env.VITE_USE_MOCK === 'true'
  if (useMock) {
    yield { content: '这是 Mock 模式下的流式回复。你可以继续体验对话流程，所有数据均为预设的演示数据。' }
    return
  }

  const token = localStorage.getItem('agent_token')
  const baseUrl = import.meta.env.VITE_API_BASE || '/api/v1'
  const url = `${baseUrl}/chat/`

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ message, stream: true }),
  })

  if (!response.ok) {
    let errorMsg = '请求失败'
    try {
      const err = await response.json()
      errorMsg = err.detail || errorMsg
    } catch {}
    yield { error: errorMsg }
    return
  }

  const reader = response.body?.getReader()
  if (!reader) {
    yield { error: '无法读取响应流' }
    return
  }

  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed || !trimmed.startsWith('data: ')) continue

        const data = trimmed.slice(6)
        if (data === '[DONE]') return

        try {
          const parsed = JSON.parse(data)
          yield parsed
        } catch {}
      }
    }
  } finally {
    reader.releaseLock()
  }
}
