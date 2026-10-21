import api from './api'

export interface ConversationSummary {
  id: number
  title: string
  created_at: string
  updated_at: string
  message_count: number
}

export interface ConversationMessage {
  id: number
  role: 'user' | 'assistant' | 'system'
  content: string
  created_at: string
}

export interface ConversationDetail extends ConversationSummary {
  messages: ConversationMessage[]
}

export async function listConversations(): Promise<ConversationSummary[]> {
  const response = await api.get<ConversationSummary[]>('/conversations/')
  return response.data
}

export async function createConversation(title?: string): Promise<ConversationSummary> {
  const response = await api.post<ConversationSummary>('/conversations/', title ? { title } : {})
  return response.data
}

export async function getConversation(id: number): Promise<ConversationDetail> {
  const response = await api.get<ConversationDetail>(`/conversations/${id}`)
  return response.data
}

export async function deleteConversation(id: number): Promise<void> {
  await api.delete(`/conversations/${id}`)
}
