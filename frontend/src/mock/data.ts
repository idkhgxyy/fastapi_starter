import type { User, Document, Task, LLMStats, LLMCallLog, HealthStatus } from '@/types'

const NOW = new Date().toISOString()

function daysAgo(n: number): string {
  const d = new Date(Date.now() - n * 86400000)
  return d.toISOString()
}

const mockUser: User = {
  id: 1,
  username: 'DemoUser',
  email: 'demo@example.com',
  has_custom_llm_key: false,
}

const mockDocuments: Document[] = [
  { id: 1, filename: '快速上手指南.md', file_type: 'md', status: 'ready', chunks_count: 5, processing_task_id: null, error_message: null, created_at: daysAgo(2) },
  { id: 2, filename: '产品需求文档.pdf', file_type: 'pdf', status: 'ready', chunks_count: 12, processing_task_id: null, error_message: null, created_at: daysAgo(1) },
  { id: 3, filename: 'API 参考.txt', file_type: 'txt', status: 'processing', chunks_count: 0, processing_task_id: 'task-abc', error_message: null, created_at: NOW },
  { id: 4, filename: '设计规范.md', file_type: 'md', status: 'failed', chunks_count: 0, processing_task_id: null, error_message: '向量化失败：维度不匹配', created_at: daysAgo(3) },
]

const mockTasks: Task[] = [
  { id: 1, title: '完成前端登录页开发', description: '实现邮箱+密码登录表单，含表单校验和错误提示', status: 'completed', created_at: daysAgo(5), updated_at: daysAgo(2) },
  { id: 2, title: '对接 SSE 流式接口', description: '实现 fetch + ReadableStream 解析，支持打字机效果', status: 'in_progress', created_at: daysAgo(3), updated_at: daysAgo(1) },
  { id: 3, title: '搭建可观测性面板', description: '集成 Recharts 图表，展示 LLM 调用统计', status: 'in_progress', created_at: daysAgo(1), updated_at: NOW },
  { id: 4, title: '编写单元测试', description: '', status: 'pending', created_at: NOW, updated_at: NOW },
]

function generateDailyStats(days: number) {
  const result = []
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(Date.now() - i * 86400000)
    result.push({
      date: d.toISOString().slice(0, 10),
      calls: Math.floor(Math.random() * 50) + 5,
      tokens: Math.floor(Math.random() * 5000) + 500,
      cost_usd: parseFloat((Math.random() * 0.05 + 0.005).toFixed(4)),
      avg_latency_ms: Math.floor(Math.random() * 3000) + 500,
    })
  }
  return result
}

const mockStats: LLMStats = {
  total_calls: 234,
  successful_calls: 228,
  failed_calls: 6,
  total_tokens: 45678,
  total_cost_usd: 0.0523,
  avg_latency_ms: 2150,
  daily_stats: generateDailyStats(7),
  endpoint_stats: [
    { endpoint: '/api/v1/chat', calls: 145, tokens: 28900 },
    { endpoint: '/api/v1/rag/query', calls: 62, tokens: 12400 },
    { endpoint: '/api/v1/rag/query/stream', calls: 27, tokens: 4378 },
  ],
  per_user_stats: [
    { user_id: 1, calls: 234, tokens: 45678, cost_usd: 0.0523 },
  ],
}

const mockCallLogs: LLMCallLog[] = Array.from({ length: 20 }).map((_, i) => ({
  id: i + 1,
  endpoint: i % 3 === 0 ? '/api/v1/chat' : '/api/v1/rag/query',
  model_name: 'gpt-4o-mini',
  provider: 'openai',
  request_id: `req_${Math.random().toString(36).slice(2, 10)}`,
  prompt: `这是第 ${i + 1} 条模拟调用中的用户提问内容，用于前端展示。`,
  response: i % 5 === 0 ? null : `这是第 ${i + 1} 条模拟调用的 AI 回复内容。包含了详细的回答信息。`,
  tool_calls: i === 0 ? JSON.stringify([{ id: 'call_1', type: 'function', function: { name: 'get_current_weather', arguments: '{"location":"北京"}' } }]) : null,
  prompt_tokens: Math.floor(Math.random() * 200) + 30,
  completion_tokens: Math.floor(Math.random() * 400) + 50,
  total_tokens: 0,
  latency_ms: Math.floor(Math.random() * 4000) + 200,
  estimated_cost_usd: parseFloat((Math.random() * 0.002).toFixed(6)),
  status: i % 5 === 0 ? 'failed' : 'success',
  error_message: i % 5 === 0 ? 'Rate limit exceeded' : null,
  created_at: new Date(Date.now() - i * 60000).toISOString(),
})).map((log) => ({ ...log, total_tokens: log.prompt_tokens + log.completion_tokens }))

const mockHealth: HealthStatus = {
  status: 'ok',
  version: '0.1.0',
  dependencies: {
    database: { status: 'up' },
    redis: { status: 'up' },
    ollama: { status: 'up', models: ['qwen2.5:7b', 'nomic-embed-text:v1.5'] },
  },
}

export interface MockEntry {
  method: string
  path: string
  handler: (data?: unknown) => unknown
}

const MOCK_RESPONSES: MockEntry[] = [
  { method: 'POST', path: '/auth/login', handler: () => ({ access_token: 'mock-jwt-token.demo.xxx', token_type: 'bearer' }) },
  { method: 'POST', path: '/users/', handler: () => mockUser },
  { method: 'GET', path: '/users/me', handler: () => mockUser },
  { method: 'PUT', path: '/users/me/llm-config', handler: (data) => ({ ...mockUser, has_custom_llm_key: !!(data as Record<string, unknown>)?.api_key }) },
  { method: 'PUT', path: '/users/me/password', handler: () => ({ message: '密码修改成功' }) },
  { method: 'GET', path: '/chat/', handler: () => ({ reply: '这是 Mock 模式下的回复，用于前端独立开发调试。你可以继续体验对话流程。' }) },
  { method: 'GET', path: '/tasks/', handler: () => mockTasks },
  { method: 'POST', path: '/tasks/', handler: (data) => {
    const d = data as { title: string; description?: string }
    const task: Task = { id: Date.now(), title: d.title, description: d.description || null, status: 'pending', created_at: NOW, updated_at: NOW }
    return task
  }},
  { method: 'PUT', path: '/tasks/', handler: (data) => data },
  { method: 'DELETE', path: '/tasks/', handler: () => ({ message: '已删除' }) },
  { method: 'GET', path: '/rag/documents', handler: () => mockDocuments },
  { method: 'POST', path: '/rag/upload', handler: () => ({ ...mockDocuments[0], id: Date.now(), filename: '新建文档.md', status: 'queued', chunks_count: 0 }) },
  { method: 'DELETE', path: '/rag/documents/', handler: () => ({ message: '文档已删除' }) },
  { method: 'POST', path: '/rag/query', handler: () => ({
    query: 'mock query',
    answer: '这是 Mock 模式下知识库问答的模拟回答。在实际运行中，后端会基于 pgvector 检索相关文档块并调用 LLM 生成回答。',
    source_chunks: ['FastAPI 是一个现代、快速（高性能）的 Web 框架，用于构建 API。', '本项目使用 SQLAlchemy 作为 ORM，支持 PostgreSQL 数据库。', 'RAG 功能通过 pgvector 扩展实现向量相似度搜索。'],
  })},
  { method: 'GET', path: '/observability/llm-stats', handler: () => mockStats },
  { method: 'GET', path: '/observability/llm-calls', handler: () => mockCallLogs },
  { method: 'GET', path: '/health', handler: () => mockHealth },
]

function matchPath(pattern: string, actual: string): boolean {
  const patternParts = pattern.split('/')
  const actualParts = actual.split('/')
  if (patternParts.length !== actualParts.length) return false
  return patternParts.every((part, i) => part.startsWith('{') || part === actualParts[i])
}

export function getMockResponse(method: string, url: string, data?: unknown): { data: unknown } | null {
  for (const entry of MOCK_RESPONSES) {
    if (entry.method === method && matchPath(entry.path, url)) {
      return { data: entry.handler(data) }
    }
  }
  return null
}
