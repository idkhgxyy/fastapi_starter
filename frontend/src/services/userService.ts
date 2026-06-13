import api from './api'
import type { User, LLMConfig } from '@/types'

export async function getCurrentUser(): Promise<User> {
  const response = await api.get<User>('/users/me')
  return response.data
}

export async function updateLLMConfig(config: LLMConfig): Promise<User> {
  const response = await api.put<User>('/users/me/llm-config', {
    llm_provider: config.provider,
    llm_base_url: config.base_url,
    llm_model_name: config.model_name,
    llm_api_key: config.api_key,
  })
  return response.data
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  await api.put('/users/me/password', {
    old_password: currentPassword,
    new_password: newPassword,
  })
}
