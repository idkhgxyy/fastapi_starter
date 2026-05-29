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
