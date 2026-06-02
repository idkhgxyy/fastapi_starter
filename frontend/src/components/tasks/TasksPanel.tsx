import { useState, useEffect, type FormEvent } from 'react'
import type { Task } from '@/types'
import { listTasks, createTask, updateTask, deleteTask } from '@/services/taskService'
import TaskStatusBadge from './TaskStatusBadge'
import { IconPlus, IconTrash, IconX } from '@/components/ui/Icons'

export default function TasksPanel() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [loading, setLoading] = useState(true)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  async function loadTasks() {
    try {
      const data = await listTasks()
      setTasks(data)
    } catch {
      // silently fail
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadTasks()
  }, [])

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
    const nextStatus = task.status === 'pending' ? 'in_progress' : task.status === 'in_progress' ? 'completed' : 'pending'
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
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-[var(--text-tertiary)] uppercase tracking-wider">
          任务列表
        </span>
        <button
          onClick={() => setShowForm(!showForm)}
          className="p-1 rounded text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] transition-colors"
        >
          <IconPlus />
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="space-y-2 p-3 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)]">
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="任务标题"
            required
            className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-tertiary)] text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition-colors"
          />
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="描述（可选）"
            rows={2}
            className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-tertiary)] text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] resize-none focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition-colors"
          />
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={!title.trim() || submitting}
              className="flex-1 py-2 rounded-lg bg-brand-500 text-white text-sm font-medium hover:bg-brand-600 disabled:opacity-50 transition-colors"
            >
              {submitting ? '创建中...' : '创建'}
            </button>
            <button
              type="button"
              onClick={() => { setShowForm(false); setTitle(''); setDescription('') }}
              className="px-3 py-2 rounded-lg border border-[var(--border-primary)] text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
            >
              <IconX />
            </button>
          </div>
        </form>
      )}

      {loading ? (
        <div className="space-y-2">
          {[1, 2].map((i) => (
            <div key={i} className="h-20 rounded-lg bg-[var(--bg-tertiary)] animate-pulse" />
          ))}
        </div>
      ) : tasks.length === 0 ? (
        <div className="text-center py-8">
          <p className="text-sm text-[var(--text-tertiary)]">还没有任务</p>
          <button
            onClick={() => setShowForm(true)}
            className="mt-2 text-xs text-brand-500 hover:text-brand-400 transition-colors"
          >
            创建第一个任务
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          {tasks.map((task) => (
            <TaskCard
              key={task.id}
              task={task}
              onToggleStatus={() => handleToggleStatus(task)}
              onDelete={() => handleDelete(task.id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function TaskCard({ task, onToggleStatus, onDelete }: { task: Task; onToggleStatus: () => void; onDelete: () => void }) {
  return (
    <div className="p-3 rounded-lg border border-[var(--border-primary)] hover:bg-[var(--bg-tertiary)] transition-colors group">
      <div className="flex items-start justify-between gap-2">
        <button
          onClick={onToggleStatus}
          className="flex-1 text-left"
        >
          <p className={`text-sm font-medium ${task.status === 'completed' ? 'line-through text-[var(--text-tertiary)]' : 'text-[var(--text-primary)]'}`}>
            {task.title}
          </p>
          {task.description && (
            <p className="text-xs text-[var(--text-tertiary)] mt-1 line-clamp-2">{task.description}</p>
          )}
          <div className="flex items-center gap-2 mt-2">
            <TaskStatusBadge status={task.status} />
            <span className="text-xs text-[var(--text-tertiary)]">
              {new Date(task.created_at).toLocaleDateString('zh-CN')}
            </span>
          </div>
        </button>
        <button
          onClick={onDelete}
          className="shrink-0 p-1.5 rounded text-[var(--text-tertiary)] opacity-0 group-hover:opacity-100 hover:text-[var(--color-error)] transition-all"
        >
          <IconTrash />
        </button>
      </div>
    </div>
  )
}
