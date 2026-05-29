import { useState, useEffect, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import type { Task } from '@/types'
import { listTasks, createTask, updateTask, deleteTask } from '@/services/taskService'
import TaskStatusBadge from '@/components/tasks/TaskStatusBadge'
import { IconPlus, IconTrash, IconX } from '@/components/ui/Icons'

type FilterKey = 'all' | 'todo' | 'in_progress' | 'done'

const filterLabels: Record<FilterKey, string> = {
  all: '全部',
  todo: '待办',
  in_progress: '进行中',
  done: '已完成',
}

export default function TasksPage() {
  const navigate = useNavigate()
  const [tasks, setTasks] = useState<Task[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<FilterKey>('all')
  const [showForm, setShowForm] = useState(false)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function loadTasks() {
    try {
      const data = await listTasks()
      setTasks(data)
    } catch {} finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadTasks() }, [])

  const filteredTasks = filter === 'all' ? tasks : tasks.filter((t) => t.status === filter)

  async function handleCreate(e: FormEvent) {
    e.preventDefault()
    if (!title.trim() || submitting) return
    setSubmitting(true)
    try {
      await createTask(title.trim(), description.trim())
      setTitle('')
      setDescription('')
      setShowForm(false)
      await loadTasks()
    } finally {
      setSubmitting(false)
    }
  }

  async function handleToggleStatus(task: Task) {
    const nextStatus: Task['status'] = task.status === 'todo' ? 'in_progress' : task.status === 'in_progress' ? 'done' : 'todo'
    try {
      await updateTask(task.id, { status: nextStatus })
      await loadTasks()
    } catch {}
  }

  async function handleDelete(id: number) {
    try {
      await deleteTask(id)
      await loadTasks()
    } catch {}
  }

  return (
    <div className="min-h-screen bg-[var(--bg-primary)]">
      <header className="h-14 border-b border-[var(--border-primary)] bg-[var(--bg-secondary)] flex items-center px-6 gap-4">
        <button onClick={() => navigate('/chat')} className="text-sm text-[var(--text-tertiary)] hover:text-[var(--text-primary)] transition-colors">
          ← 返回
        </button>
        <h1 className="text-sm font-semibold text-[var(--text-primary)]">任务管理</h1>
      </header>

      <div className="max-w-3xl mx-auto p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex gap-1 bg-[var(--bg-secondary)] rounded-lg p-1 border border-[var(--border-primary)]">
            {(Object.entries(filterLabels) as [FilterKey, string][]).map(([key, label]) => (
              <button
                key={key}
                onClick={() => setFilter(key)}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                  filter === key ? 'bg-[var(--bg-primary)] text-[var(--text-primary)] shadow-sm' : 'text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]'
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          <button
            onClick={() => setShowForm(!showForm)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-brand-500 text-white text-sm font-medium hover:bg-brand-600 transition-colors"
          >
            <IconPlus />
            新建任务
          </button>
        </div>

        {showForm && (
          <form onSubmit={handleCreate} className="p-4 rounded-xl border border-[var(--border-primary)] bg-[var(--bg-secondary)] space-y-3">
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="任务标题"
              required
              className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition-colors"
            />
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="描述（可选）"
              rows={3}
              className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] resize-none focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition-colors"
            />
            <div className="flex gap-2">
              <button type="submit" disabled={!title.trim() || submitting} className="flex-1 py-2 rounded-lg bg-brand-500 text-white text-sm font-medium hover:bg-brand-600 disabled:opacity-50 transition-colors">
                {submitting ? '创建中...' : '创建'}
              </button>
              <button type="button" onClick={() => { setShowForm(false); setTitle(''); setDescription('') }} className="px-3 py-2 rounded-lg border border-[var(--border-primary)] text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors">
                <IconX />
              </button>
            </div>
          </form>
        )}

        {loading ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-24 rounded-xl bg-[var(--bg-tertiary)] animate-pulse" />
            ))}
          </div>
        ) : filteredTasks.length === 0 ? (
          <div className="text-center py-16">
            <p className="text-sm text-[var(--text-tertiary)]">{filter === 'all' ? '还没有任务' : `没有${filterLabels[filter]}状态的任务`}</p>
            {filter === 'all' && (
              <button onClick={() => setShowForm(true)} className="mt-2 text-xs text-brand-500 hover:text-brand-400 transition-colors">
                创建第一个任务
              </button>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            {filteredTasks.map((task) => (
              <div key={task.id} className="p-4 rounded-xl border border-[var(--border-primary)] hover:bg-[var(--bg-secondary)] transition-colors group">
                <div className="flex items-start justify-between gap-3">
                  <button onClick={() => handleToggleStatus(task)} className="flex-1 text-left">
                    <div className="flex items-center gap-2">
                      <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center shrink-0 transition-colors ${
                        task.status === 'done' ? 'border-[var(--color-success)] bg-[var(--color-success)]' : 'border-[var(--text-tertiary)]'
                      }`}>
                        {task.status === 'done' && (
                          <svg className="w-3 h-3 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                            <polyline points="20 6 9 17 4 12" />
                          </svg>
                        )}
                      </div>
                      <p className={`text-sm font-medium ${task.status === 'done' ? 'line-through text-[var(--text-tertiary)]' : 'text-[var(--text-primary)]'}`}>
                        {task.title}
                      </p>
                    </div>
                    {task.description && (
                      <p className="text-xs text-[var(--text-tertiary)] mt-2 ml-7">{task.description}</p>
                    )}
                    <div className="flex items-center gap-2 mt-2 ml-7">
                      <TaskStatusBadge status={task.status} />
                      <span className="text-xs text-[var(--text-tertiary)]">
                        {new Date(task.created_at).toLocaleString('zh-CN')}
                      </span>
                    </div>
                  </button>
                  <button onClick={() => handleDelete(task.id)} className="shrink-0 p-1.5 rounded text-[var(--text-tertiary)] opacity-0 group-hover:opacity-100 hover:text-[var(--color-error)] transition-all">
                    <IconTrash />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
