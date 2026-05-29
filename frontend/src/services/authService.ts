import api from './api'
import type { User } from '@/types'

export interface LoginResponse {
  access_token: string
  token_type: string
}

export async function login(email: string, password: string): Promise<LoginResponse> {
  const formData = new FormData()
  formData.append('username', email)
  formData.append('password', password)
  const response = await api.post<LoginResponse>('/auth/login', formData, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  })
  return response.data
}

export async function register(username: string, email: string, password: string): Promise<User> {
  const response = await api.post<User>('/users/', { username, email, password })
  return response.data
}

export async function getCurrentUser(): Promise<User> {
  const response = await api.get<User>('/users/me')
  return response.data
}
