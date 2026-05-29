import api from './api'
import type { Task } from '@/types'

export async function listTasks(skip = 0, limit = 50): Promise<Task[]> {
  const response = await api.get<Task[]>('/tasks/', { params: { skip, limit } })
  return response.data
}

export async function createTask(title: string, description = ''): Promise<Task> {
  const response = await api.post<Task>('/tasks/', { title, description })
  return response.data
}

export async function updateTask(id: number, data: Partial<Pick<Task, 'title' | 'description' | 'status'>>): Promise<Task> {
  const response = await api.put<Task>(`/tasks/${id}`, data)
  return response.data
}

export async function deleteTask(id: number): Promise<void> {
  await api.delete(`/tasks/${id}`)
}
