import api from './api'
import type { Document } from '@/types'

export async function listDocuments(): Promise<Document[]> {
  const response = await api.get<Document[]>('/rag/documents')
  return response.data
}

export async function uploadDocument(file: File): Promise<Document> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await api.post<Document>('/rag/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return response.data
}

export async function deleteDocument(documentId: number): Promise<void> {
  await api.delete(`/rag/documents/${documentId}`)
}

export async function queryKnowledgeBase(query: string, topK = 3): Promise<{ answer: string; source_chunks: string[] }> {
  const response = await api.post<{ answer: string; source_chunks: string[] }>('/rag/query', {
    query,
    top_k: topK,
  })
  return response.data
}

export async function* streamQueryKnowledgeBase(
  query: string,
  topK = 3,
): AsyncGenerator<{ content?: string; source_chunks?: string[]; error?: string }> {
  const token = localStorage.getItem('agent_token')
  const baseUrl = import.meta.env.VITE_API_BASE || '/api/v1'
  const url = `${baseUrl}/rag/query/stream`

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ query, top_k: topK }),
  })

  if (!response.ok) {
    let errorMsg = '查询失败'
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
