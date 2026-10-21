import api from './api'

export type AgentTaskStatus = 'pending' | 'running' | 'succeeded' | 'failed'

export interface AgentTaskStep {
  seq: number
  name: string
  status: AgentTaskStatus
  summary: string | null
  prompt_tokens: number
  completion_tokens: number
  cost_cny: number
  started_at: string | null
  finished_at: string | null
}

export interface AgentTask {
  id: number
  title: string
  goal: string
  status: AgentTaskStatus
  output_type: string
  scope_document_ids: number[] | null
  error_message: string | null
  prompt_tokens: number
  completion_tokens: number
  cost_cny: number
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export interface AgentTaskDetail extends AgentTask {
  result_markdown: string | null
  steps: AgentTaskStep[]
}

export async function listAgentTasks(): Promise<AgentTask[]> {
  const response = await api.get<AgentTask[]>('/agent-tasks/')
  return response.data
}

export async function createAgentTask(
  goal: string,
  scopeMode: 'auto' | 'selected',
  documentIds: number[]
): Promise<AgentTask> {
  const response = await api.post<AgentTask>('/agent-tasks/', {
    goal,
    scope_mode: scopeMode,
    document_ids: documentIds,
  })
  return response.data
}

export async function getAgentTask(id: number): Promise<AgentTaskDetail> {
  const response = await api.get<AgentTaskDetail>(`/agent-tasks/${id}`)
  return response.data
}

export async function retryAgentTask(id: number): Promise<AgentTask> {
  const response = await api.post<AgentTask>(`/agent-tasks/${id}/retry`)
  return response.data
}

export async function deleteAgentTask(id: number): Promise<void> {
  await api.delete(`/agent-tasks/${id}`)
}

export async function downloadAgentTask(taskId: number): Promise<void> {
  const token = localStorage.getItem('agent_token')
  const baseUrl = import.meta.env.VITE_API_BASE || '/api/v1'
  const response = await fetch(`${baseUrl}/agent-tasks/${taskId}/export`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!response.ok) {
    throw new Error('导出失败')
  }
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `agent-task-${taskId}.md`
  link.click()
  URL.revokeObjectURL(url)
}
