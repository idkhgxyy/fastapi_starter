import { useState, useEffect, useRef, type ChangeEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Document } from '@/types'
import {
  deleteDocument,
  listDocuments,
  queryKnowledgeBase,
  uploadDocument,
} from '@/services/ragService'
import { IconFile, IconRefresh, IconSend, IconTrash, IconUpload } from '@/components/ui/Icons'
import { statusLabels, statusColors } from '@/components/knowledge/constants'

export default function KnowledgePage() {
  const navigate = useNavigate()
  const [docs, setDocs] = useState<Document[]>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const [viewMode, setViewMode] = useState<'card' | 'table'>('card')
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState('')
  const [sourceChunks, setSourceChunks] = useState<string[]>([])
  const [asking, setAsking] = useState(false)
  const [askError, setAskError] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  async function loadDocs() {
    setError('')
    try {
      const data = await listDocuments()
      setDocs(data)
    } catch {
      setError('加载文档失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadDocs() }, [])

  async function handleUpload(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setError('')
    setUploading(true)
    try {
      await uploadDocument(file)
      await loadDocs()
    } catch {
      setError('上传失败，请重试')
    }
    if (fileRef.current) fileRef.current.value = ''
    setUploading(false)
  }

  async function handleDelete(id: number) {
    setError('')
    try {
      await deleteDocument(id)
      await loadDocs()
    } catch {
      setError('删除失败，请重试')
    }
  }

  async function handleAsk() {
    const trimmed = question.trim()
    if (!trimmed || asking) return
    setAsking(true)
    setAskError('')
    setAnswer('')
    setSourceChunks([])
    try {
      const result = await queryKnowledgeBase(trimmed, 3)
      setAnswer(result.answer)
      setSourceChunks(result.source_chunks || [])
    } catch {
      setAskError('提问失败，请检查后端服务后重试')
    } finally {
      setAsking(false)
    }
  }

  const readyCount = docs.filter((doc) => doc.status === 'ready').length
  const totalChunks = docs.reduce((sum, doc) => sum + doc.chunks_count, 0)

  return (
    <div className="min-h-screen bg-[var(--bg-primary)]">
      <header className="sticky top-0 z-20 border-b border-[var(--border-primary)]/80 bg-[var(--bg-secondary)]/80 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-6xl items-center gap-3 px-4 sm:px-6">
          <button
            onClick={() => navigate('/chat')}
            className="text-sm text-[var(--text-tertiary)] transition-colors hover:text-[var(--text-primary)]"
          >
            ← 返回
          </button>
          <span className="h-5 w-px bg-[var(--border-primary)]" />
          <h1 className="text-sm font-semibold text-[var(--text-primary)]">知识库</h1>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:py-10">
        <section className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h2 className="text-2xl font-semibold tracking-tight text-[var(--text-primary)] sm:text-3xl">
              文档与问答
            </h2>
            <p className="mt-2 max-w-xl text-sm leading-6 text-[var(--text-secondary)]">
              上传资料后，可以检索原文，也可以直接向知识库提问。
            </p>
          </div>
          <div className="grid grid-cols-3 gap-2 sm:gap-3">
            {[
              ['文档', docs.length],
              ['就绪', readyCount],
              ['片段', totalChunks],
            ].map(([label, value]) => (
              <div key={label} className="card-surface min-w-[86px] rounded-2xl px-4 py-3">
                <p className="text-[10px] uppercase tracking-[0.14em] text-[var(--text-tertiary)]">{label}</p>
                <p className="mt-1 font-mono text-xl text-[var(--text-primary)]">{value}</p>
              </div>
            ))}
          </div>
        </section>

        {error && (
          <p className="mt-5 rounded-xl border border-[var(--color-error)]/20 bg-[var(--color-error)]/8 px-3.5 py-2.5 text-sm text-[var(--color-error)]">
            {error}
          </p>
        )}

        <div className="mt-8 grid gap-5 lg:grid-cols-[1.15fr_0.85fr]">
          <section className="card-surface rounded-3xl p-5 sm:p-6">
            <h2 className="text-xl font-semibold tracking-tight text-[var(--text-primary)]">问知识库</h2>
            <p className="mt-1 text-sm text-[var(--text-tertiary)]">
              基于已就绪文档回答，并返回来源片段。
            </p>
            <div className="mt-5 flex flex-col gap-2 sm:flex-row">
              <input
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleAsk()}
                placeholder="问知识库，例如：这份文档的核心结论是什么？"
                className="h-11 flex-1 rounded-xl border border-[var(--border-primary)] bg-[var(--bg-primary)] px-3.5 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] transition focus:border-brand-500 focus:outline-none focus:ring-4 focus:ring-brand-500/10"
              />
              <button
                type="button"
                onClick={handleAsk}
                disabled={!question.trim() || asking}
                className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-brand-500 px-4 text-sm font-medium text-white transition hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <IconSend />
                {asking ? '回答中...' : '提问'}
              </button>
            </div>
            {askError && (
              <p className="mt-3 rounded-xl border border-[var(--color-error)]/20 bg-[var(--color-error)]/8 px-3.5 py-2.5 text-sm text-[var(--color-error)]">
                {askError}
              </p>
            )}
            {answer && (
              <div className="mt-4 rounded-2xl border border-[var(--border-primary)]/80 bg-[var(--bg-primary)]/60 p-4">
                <div className="prose prose-sm max-w-none text-[var(--text-primary)]">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{answer}</ReactMarkdown>
                </div>
              </div>
            )}
            {sourceChunks.length > 0 && (
              <details open className="mt-3 rounded-2xl border border-[var(--border-primary)]/80 bg-[var(--bg-primary)]/60">
                <summary className="cursor-pointer px-4 py-2.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]">
                  来源片段 ({sourceChunks.length})
                </summary>
                <div className="max-h-72 space-y-2 overflow-y-auto px-3 pb-3">
                  {sourceChunks.map((source, index) => (
                    <pre
                      key={index}
                      className="whitespace-pre-wrap break-words rounded-xl border border-[var(--border-secondary)] bg-[var(--bg-secondary)] p-3 font-mono text-[11px] leading-relaxed text-[var(--text-secondary)]"
                    >
                      {source}
                    </pre>
                  ))}
                </div>
              </details>
            )}
          </section>

          <div className="space-y-5">
            <section className="card-surface rounded-3xl p-5">
              <h2 className="text-xl font-semibold tracking-tight text-[var(--text-primary)]">上传文档</h2>
              <input
                ref={fileRef}
                type="file"
                accept=".txt,.md,.pdf"
                onChange={handleUpload}
                className="hidden"
              />
              <button
                onClick={() => fileRef.current?.click()}
                disabled={uploading}
                className="mt-4 w-full rounded-2xl border border-dashed border-[var(--border-primary)] bg-[var(--bg-primary)]/50 px-4 py-7 text-center transition hover:border-brand-500/50 hover:bg-brand-500/[0.03] disabled:opacity-50"
              >
                <span className="mx-auto flex h-11 w-11 items-center justify-center rounded-2xl bg-brand-500/10 text-brand-600">
                  <IconUpload />
                </span>
                <span className="mt-3 block text-sm font-medium text-[var(--text-primary)]">
                  {uploading ? '上传中...' : '点击上传文档'}
                </span>
                <span className="mt-1 block text-xs text-[var(--text-tertiary)]">
                  支持 .txt .md .pdf
                </span>
              </button>
              <p className="mt-3 text-xs leading-5 text-[var(--text-tertiary)]">
                上传后等待状态变为“就绪”，再提问。
              </p>
            </section>
          </div>
        </div>

        <section className="mt-8">
          <div className="mb-4 flex items-end justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold tracking-tight text-[var(--text-primary)]">
                文档列表 <span className="font-mono text-sm font-normal text-[var(--text-tertiary)]">({docs.length})</span>
              </h2>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setViewMode(viewMode === 'card' ? 'table' : 'card')}
                className="rounded-lg border border-[var(--border-primary)] bg-[var(--bg-secondary)] px-2.5 py-1.5 text-xs text-[var(--text-tertiary)] transition hover:text-[var(--text-primary)]"
              >
                {viewMode === 'card' ? '表格视图' : '卡片视图'}
              </button>
              <button
                onClick={loadDocs}
                className="rounded-lg border border-[var(--border-primary)] bg-[var(--bg-secondary)] p-2 text-[var(--text-tertiary)] transition hover:text-[var(--text-primary)]"
                aria-label="刷新文档列表"
              >
                <IconRefresh />
              </button>
            </div>
          </div>

          {loading ? (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="h-24 animate-pulse rounded-2xl bg-[var(--bg-tertiary)]" />
              ))}
            </div>
          ) : docs.length === 0 ? (
            <div className="card-surface rounded-3xl px-6 py-16 text-center">
              <IconFile className="mx-auto mb-3 text-[var(--text-tertiary)]" />
              <p className="text-sm font-medium text-[var(--text-primary)]">还没有文档</p>
              <p className="mt-1 text-xs text-[var(--text-tertiary)]">上传第一份资料，开始构建你的知识库。</p>
            </div>
          ) : viewMode === 'table' ? (
            <div className="card-surface overflow-x-auto rounded-2xl">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--border-secondary)] text-left text-[10px] uppercase tracking-[0.14em] text-[var(--text-tertiary)]">
                    <th className="px-4 py-3 font-semibold">文件名</th>
                    <th className="px-4 py-3 font-semibold">类型</th>
                    <th className="px-4 py-3 font-semibold">状态</th>
                    <th className="px-4 py-3 font-semibold">Chunks</th>
                    <th className="px-4 py-3 font-semibold">上传时间</th>
                    <th className="px-4 py-3 text-right font-semibold">操作</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border-secondary)]">
                  {docs.map((doc) => (
                    <tr key={doc.id} className="transition-colors hover:bg-[var(--bg-secondary)]">
                      <td className="px-4 py-3 font-medium text-[var(--text-primary)]">{doc.filename}</td>
                      <td className="px-4 py-3 text-[var(--text-secondary)]">{doc.file_type}</td>
                      <td className="px-4 py-3">
                        <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--border-primary)] bg-[var(--bg-primary)] px-2 py-1 text-[11px] text-[var(--text-secondary)]">
                          <span className={`h-1.5 w-1.5 rounded-full ${statusColors[doc.status]}`} />
                          {statusLabels[doc.status] || doc.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-[var(--text-secondary)]">{doc.chunks_count}</td>
                      <td className="px-4 py-3 text-xs text-[var(--text-tertiary)]">
                        {new Date(doc.created_at).toLocaleString('zh-CN')}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => handleDelete(doc.id)}
                          className="rounded-lg p-1.5 text-[var(--text-tertiary)] transition hover:bg-[var(--color-error)]/10 hover:text-[var(--color-error)]"
                          aria-label={`删除 ${doc.filename}`}
                        >
                          <IconTrash />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {docs.map((doc) => (
                <div
                  key={doc.id}
                  className="group card-surface rounded-2xl p-4 transition hover:-translate-y-0.5 hover:border-brand-500/25 hover:shadow-[var(--shadow-card)]"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex min-w-0 items-center gap-3">
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-500/10 text-brand-600">
                        <IconFile />
                      </div>
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-[var(--text-primary)]">{doc.filename}</p>
                        <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">{doc.file_type}</p>
                      </div>
                    </div>
                    <button
                      onClick={() => handleDelete(doc.id)}
                      className="rounded-lg p-1.5 text-[var(--text-tertiary)] opacity-0 transition-all hover:bg-[var(--color-error)]/10 hover:text-[var(--color-error)] group-hover:opacity-100"
                      aria-label={`删除 ${doc.filename}`}
                    >
                      <IconTrash />
                    </button>
                  </div>
                  <div className="mt-4 flex items-center gap-3 text-xs text-[var(--text-tertiary)]">
                    <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--border-primary)] bg-[var(--bg-primary)] px-2 py-1">
                      <span className={`h-1.5 w-1.5 rounded-full ${statusColors[doc.status]}`} />
                      {statusLabels[doc.status] || doc.status}
                    </span>
                    {doc.status === 'ready' && <span className="font-mono">{doc.chunks_count} chunks</span>}
                    <span>{new Date(doc.created_at).toLocaleDateString('zh-CN')}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  )
}
