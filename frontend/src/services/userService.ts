import api from './api'
import type { User, LLMConfig } from '@/types'

export async function getCurrentUser(): Promise<User> {
  const response = await api.get<User>('/users/me')
  return response.data
}

export async function updateLLMConfig(config: LLMConfig): Promise<User> {
  const response = await api.put<User>('/users/me/llm-config', config)
  return response.data
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  await api.put('/users/me/password', {
    current_password: currentPassword,
    new_password: newPassword,
  })
}
