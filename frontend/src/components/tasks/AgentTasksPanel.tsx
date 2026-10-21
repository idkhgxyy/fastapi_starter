import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Document } from '@/types'
import { listDocuments } from '@/services/ragService'
import {
  createAgentTask,
  deleteAgentTask,
  downloadAgentTask,
  getAgentTask,
  listAgentTasks,
  retryAgentTask,
  type AgentTask,
  type AgentTaskDetail,
} from '@/services/agentTaskService'
import { IconPlus, IconRefresh, IconTrash, IconX } from '@/components/ui/Icons'

const STATUS_LABELS: Record<string, string> = {
  pending: '排队中',
  running: '生成中',
  succeeded: '已完成',
  failed: '失败',
}

const STATUS_DOTS: Record<string, string> = {
  pending: 'bg-yellow-500',
  running: 'bg-brand-500 animate-pulse',
  succeeded: 'bg-green-500',
  failed: 'bg-red-500',
}

const STEP_LABELS: Record<string, string> = {
  retrieve: '采集材料',
  outline: '生成大纲',
  write: '撰写小节',
  finalize: '汇总成果',
}

const POLL_INTERVAL_MS = 3000

function formatTime(value: string | null): string {
  if (!value) return ''
  const iso = value.endsWith('Z') ? value : `${value}Z`
  return new Date(iso).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export default function AgentTasksPanel() {
  const [tasks, setTasks] = useState<AgentTask[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [goal, setGoal] = useState('')
  const [scopeMode, setScopeMode] = useState<'auto' | 'selected'>('auto')
  const [documents, setDocuments] = useState<Document[]>([])
  const [selectedDocIds, setSelectedDocIds] = useState<number[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [detail, setDetail] = useState<AgentTaskDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const detailIdRef = useRef<number | null>(null)

  const loadTasks = useCallback(async () => {
    try {
      const data = await listAgentTasks()
      setTasks(data)
      setError('')
    } catch {
      setError('任务列表加载失败')
    } finally {
      setLoading(false)
    }
  }, [])

  const loadDetail = useCallback(async (id: number) => {
    detailIdRef.current = id
    setDetailLoading(true)
    try {
      const data = await getAgentTask(id)
      setDetail(data)
    } catch {
      setError('任务详情加载失败')
    } finally {
      setDetailLoading(false)
    }
  }, [])

  useEffect(() => {
    loadTasks()
  }, [loadTasks])

  const hasActive = tasks.some(
    (task) => task.status === 'pending' || task.status === 'running'
  )

  useEffect(() => {
    if (!hasActive) return
    const timer = window.setInterval(() => {
      void loadTasks()
      if (detailIdRef.current !== null) {
        void loadDetail(detailIdRef.current)
      }
    }, POLL_INTERVAL_MS)
    return () => window.clearInterval(timer)
  }, [hasActive, loadTasks, loadDetail])

  async function loadDocuments() {
    try {
      const data = await listDocuments()
      setDocuments(data.filter((doc) => doc.status === 'ready'))
    } catch {
      setError('文档列表加载失败')
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (goal.trim().length < 2 || submitting) return
    if (scopeMode === 'selected' && selectedDocIds.length === 0) {
      setError('请选择至少一篇文档，或切换为自动模式')
      return
    }
    setSubmitting(true)
    setError('')
    try {
      const task = await createAgentTask(
        goal.trim(),
        scopeMode,
        scopeMode === 'selected' ? selectedDocIds : []
      )
      setGoal('')
      setSelectedDocIds([])
      setShowForm(false)
      await loadTasks()
      await loadDetail(task.id)
    } catch (err) {
      const message = (err as { response?: { data?: { msg?: string; detail?: string } } })
        ?.response?.data
      setError(message?.msg || message?.detail || '任务创建失败')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleRetry(id: number) {
    try {
      await retryAgentTask(id)
      await loadTasks()
      await loadDetail(id)
    } catch {
      setError('重试失败')
    }
  }

  async function handleDelete(id: number) {
    if (!window.confirm('删除这个任务和它的成果？')) return
    try {
      await deleteAgentTask(id)
      if (detailIdRef.current === id) {
        detailIdRef.current = null
        setDetail(null)
      }
      await loadTasks()
    } catch {
      setError('删除失败')
    }
  }

  async function handleDownload(id: number) {
    try {
      await downloadAgentTask(id)
    } catch {
      setError('导出失败')
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-[var(--text-tertiary)] uppercase tracking-wider">
          目标成果
        </span>
        <div className="flex items-center gap-1">
          <button
            onClick={() => {
              setShowForm(!showForm)
              if (!showForm && documents.length === 0) void loadDocuments()
            }}
            title="新建目标"
            className="p-1 rounded text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] transition-colors"
          >
            <IconPlus />
          </button>
          <button
            onClick={() => {
              void loadTasks()
              if (detailIdRef.current !== null) void loadDetail(detailIdRef.current)
            }}
            title="刷新"
            className="p-1 rounded text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] transition-colors"
          >
            <IconRefresh />
          </button>
        </div>
      </div>

      {showForm && (
        <form
          onSubmit={handleSubmit}
          className="space-y-2 p-3 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)]"
        >
          <textarea
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            placeholder="描述你想达成的目标，例如：基于课设资料写一份选题分析报告"
            rows={3}
            className="w-full rounded-lg border border-[var(--border-primary)] bg-[var(--bg-secondary)] px-2.5 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
          />

          <div className="flex rounded-lg bg-[var(--bg-tertiary)] p-0.5 text-xs">
            {(['auto', 'selected'] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                onClick={() => {
                  setScopeMode(mode)
                  if (mode === 'selected' && documents.length === 0) void loadDocuments()
                }}
                className={`flex-1 py-1.5 rounded-md transition-colors ${
                  scopeMode === mode
                    ? 'bg-[var(--bg-primary)] text-[var(--text-primary)] shadow-sm'
                    : 'text-[var(--text-tertiary)]'
                }`}
              >
                {mode === 'auto' ? '自动用全部资料' : '指定文档'}
              </button>
            ))}
          </div>

          {scopeMode === 'selected' && (
            <div className="max-h-40 overflow-y-auto rounded-lg border border-[var(--border-primary)] p-2 space-y-1">
              {documents.length === 0 ? (
                <p className="text-xs text-[var(--text-tertiary)]">暂无已就绪文档</p>
              ) : (
                documents.map((doc) => (
                  <label
                    key={doc.id}
                    className="flex items-center gap-2 text-xs text-[var(--text-secondary)] cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={selectedDocIds.includes(doc.id)}
                      onChange={(e) =>
                        setSelectedDocIds((prev) =>
                          e.target.checked
                            ? [...prev, doc.id]
                            : prev.filter((id) => id !== doc.id)
                        )
                      }
                    />
                    <span className="truncate">{doc.filename}</span>
                  </label>
                ))
              )}
            </div>
          )}

          <button
            type="submit"
            disabled={submitting || goal.trim().length < 2}
            className="w-full rounded-lg bg-brand-500 py-2 text-sm font-medium text-white disabled:opacity-50 hover:bg-brand-600 transition-colors"
          >
            {submitting ? '提交中...' : '开始生成'}
          </button>
        </form>
      )}

      {error && (
        <p className="text-xs text-[var(--color-error)] bg-[var(--color-error)]/10 rounded-lg px-2 py-1.5">
          {error}
        </p>
      )}

      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-12 rounded-lg bg-[var(--bg-tertiary)] animate-pulse" />
          ))}
        </div>
      ) : tasks.length === 0 ? (
        <div className="text-center py-8">
          <p className="text-sm text-[var(--text-tertiary)]">还没有目标任务</p>
          <p className="text-xs text-[var(--text-tertiary)] mt-1">
            描述一个目标，让 Agent 基于资料产出成果
          </p>
        </div>
      ) : (
        <div className="space-y-1">
          {tasks.map((task) => (
            <div
              key={task.id}
              className="group flex items-center gap-2 rounded-lg hover:bg-[var(--bg-tertiary)] transition-colors"
            >
              <button
                onClick={() => loadDetail(task.id)}
                className="flex-1 min-w-0 text-left px-2.5 py-2"
              >
                <div className="flex items-center gap-2">
                  <span
                    className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                      STATUS_DOTS[task.status] || STATUS_DOTS.pending
                    }`}
                  />
                  <p className="truncate text-sm text-[var(--text-primary)]">{task.title}</p>
                </div>
                <p className="text-xs text-[var(--text-tertiary)] mt-0.5">
                  {STATUS_LABELS[task.status] || task.status} · ¥{task.cost_cny.toFixed(4)} ·{' '}
                  {formatTime(task.created_at)}
                </p>
              </button>
              <button
                onClick={() => handleDelete(task.id)}
                title="删除任务"
                className="shrink-0 p-1.5 mr-1 rounded text-[var(--text-tertiary)] opacity-0 group-hover:opacity-100 hover:text-[var(--color-error)] transition-all"
              >
                <IconTrash />
              </button>
            </div>
          ))}
        </div>
      )}

      {detailLoading && !detail && (
        <p className="text-xs text-[var(--text-tertiary)]">加载详情...</p>
      )}

      {detail && (
        <div
          className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4"
          onClick={() => {
            detailIdRef.current = null
            setDetail(null)
          }}
        >
          <div
            className="bg-[var(--bg-primary)] rounded-xl w-full max-w-3xl max-h-[85vh] overflow-y-auto p-5 space-y-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <h2 className="text-base font-semibold text-[var(--text-primary)]">
                  {detail.title}
                </h2>
                <p className="text-xs text-[var(--text-tertiary)] mt-1">
                  {STATUS_LABELS[detail.status] || detail.status} · ¥
                  {detail.cost_cny.toFixed(4)} ·{' '}
                  {detail.prompt_tokens + detail.completion_tokens} tokens
                </p>
              </div>
              <button
                onClick={() => {
                  detailIdRef.current = null
                  setDetail(null)
                }}
                className="p-1 text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"
              >
                <IconX />
              </button>
            </div>

            <div className="rounded-lg border border-[var(--border-primary)] p-3 space-y-2">
              {detail.steps.map((step) => (
                <div key={step.seq} className="flex items-start gap-2 text-xs">
                  <span
                    className={`mt-1 w-1.5 h-1.5 rounded-full shrink-0 ${
                      STATUS_DOTS[step.status] || STATUS_DOTS.pending
                    }`}
                  />
                  <div className="min-w-0">
                    <span className="text-[var(--text-secondary)]">
                      {STEP_LABELS[step.name] || step.name}
                    </span>
                    {step.summary && (
                      <p className="text-[var(--text-tertiary)] mt-0.5 break-words">
                        {step.summary}
                      </p>
                    )}
                  </div>
                </div>
              ))}
              {detail.steps.length === 0 && (
                <p className="text-xs text-[var(--text-tertiary)]">等待开始...</p>
              )}
            </div>

            {detail.error_message && (
              <p className="text-xs text-[var(--color-error)] bg-[var(--color-error)]/10 rounded-lg px-3 py-2">
                {detail.error_message}
              </p>
            )}

            {detail.result_markdown ? (
              <div className="prose prose-sm max-w-none text-[var(--text-primary)]">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {detail.result_markdown}
                </ReactMarkdown>
              </div>
            ) : (
              detail.status !== 'failed' && (
                <p className="text-xs text-[var(--text-tertiary)]">
                  成果生成中，页面会自动刷新...
                </p>
              )
            )}

            <div className="flex items-center gap-2 pt-1">
              {detail.result_markdown && (
                <button
                  onClick={() => handleDownload(detail.id)}
                  className="rounded-lg border border-[var(--border-primary)] px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
                >
                  下载 .md
                </button>
              )}
              {detail.status === 'failed' && (
                <button
                  onClick={() => handleRetry(detail.id)}
                  className="rounded-lg border border-[var(--border-primary)] px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
                >
                  重试
                </button>
              )}
              <button
                onClick={() => handleDelete(detail.id)}
                className="ml-auto text-xs text-[var(--text-tertiary)] hover:text-[var(--color-error)]"
              >
                删除
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
