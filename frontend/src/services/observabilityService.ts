import api from './api'
import type { LLMStats, LLMCallLog } from '@/types'

export async function getLLMStats(days = 7): Promise<LLMStats> {
  const response = await api.get<LLMStats>('/observability/llm-stats', { params: { days } })
  return response.data
}

export async function listLLMCalls(skip = 0, limit = 20): Promise<LLMCallLog[]> {
  const response = await api.get<LLMCallLog[]>('/observability/llm-calls', {
    params: { skip, limit },
  })
  return response.data
}
