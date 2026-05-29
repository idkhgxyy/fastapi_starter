import api from './api'
import type { HealthStatus } from '@/types'

export async function getHealth(): Promise<HealthStatus> {
  const response = await api.get<HealthStatus>('/health')
  return response.data
}
