import axios from 'axios'
import { getMockResponse } from '@/mock/data'

const useMock = import.meta.env.VITE_USE_MOCK === 'true'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
})

api.interceptors.request.use((config) => {
  if (useMock) {
    const method = (config.method || 'get').toUpperCase()
    const url = (config.url || '').split('?')[0]
    const mock = getMockResponse(method, url, config.data)
    if (mock) {
      config.adapter = () => {
        return Promise.resolve({
          data: mock.data,
          status: 200,
          statusText: 'OK',
          headers: {},
          config,
        })
      }
    }
    return config
  }
  const token = localStorage.getItem('agent_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const path = window.location.pathname
      if (path !== '/auth/login' && path !== '/auth/register') {
        localStorage.removeItem('agent_token')
        localStorage.removeItem('agent_user')
        window.location.href = '/auth/login'
      }
    }
    return Promise.reject(error)
  }
)

export default api
