import { useState, useEffect, useRef, type ChangeEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import type { Document } from '@/types'
import { listDocuments, uploadDocument, deleteDocument } from '@/services/ragService'
import { IconFile, IconUpload, IconTrash, IconRefresh } from '@/components/ui/Icons'
import { statusLabels, statusColors } from '@/components/knowledge/constants'

export default function KnowledgePage() {
  const navigate = useNavigate()
  const [docs, setDocs] = useState<Document[]>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const [viewMode, setViewMode] = useState<'card' | 'table'>('card')
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

  return (
    <div className="min-h-screen bg-[var(--bg-primary)]">
      <header className="h-14 border-b border-[var(--border-primary)] bg-[var(--bg-secondary)] flex items-center px-6 gap-4">
        <button onClick={() => navigate('/chat')} className="text-sm text-[var(--text-tertiary)] hover:text-[var(--text-primary)] transition-colors">
          ← 返回
        </button>
        <h1 className="text-sm font-semibold text-[var(--text-primary)]">知识库管理</h1>
      </header>

      <div className="max-w-4xl mx-auto p-6 space-y-6">
        <div className="border-2 border-dashed border-[var(--border-primary)] rounded-xl p-8 text-center hover:border-brand-500/50 transition-colors">
          <input ref={fileRef} type="file" accept=".txt,.md,.pdf" onChange={handleUpload} className="hidden" />
          <button onClick={() => fileRef.current?.click()} disabled={uploading} className="disabled:opacity-50">
            <IconUpload className="mx-auto mb-3 text-[var(--text-tertiary)]" />
            <p className="text-sm text-[var(--text-tertiary)]">{uploading ? '上传中...' : '拖拽或点击上传文档'}</p>
            <p className="text-xs text-[var(--text-tertiary)] mt-1">支持 .txt .md .pdf 格式</p>
          </button>
        </div>

        {error && <p className="text-sm text-[var(--color-error)] bg-[var(--color-error)]/10 rounded-lg px-3 py-2">{error}</p>}

        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium text-[var(--text-primary)]">文档列表 ({docs.length})</h2>
          <div className="flex items-center gap-2">
            <button onClick={() => setViewMode(viewMode === 'card' ? 'table' : 'card')} className="text-xs text-[var(--text-tertiary)] hover:text-[var(--text-primary)] transition-colors">
              {viewMode === 'card' ? '表格视图' : '卡片视图'}
            </button>
            <button onClick={loadDocs} className="p-1.5 rounded text-[var(--text-tertiary)] hover:text-[var(--text-primary)] transition-colors">
              <IconRefresh />
            </button>
          </div>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-24 rounded-xl bg-[var(--bg-tertiary)] animate-pulse" />
            ))}
          </div>
        ) : docs.length === 0 ? (
          <div className="text-center py-16">
            <IconFile className="mx-auto mb-3 text-[var(--text-tertiary)]" />
            <p className="text-sm text-[var(--text-tertiary)]">暂无文档</p>
            <p className="text-xs text-[var(--text-tertiary)] mt-1">上传文档以开始构建知识库</p>
          </div>
        ) : viewMode === 'table' ? (
          <div className="rounded-xl border border-[var(--border-primary)] overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-[var(--bg-secondary)] text-[var(--text-tertiary)] text-xs uppercase tracking-wider">
                  <th className="text-left px-4 py-3 font-medium">文件名</th>
                  <th className="text-left px-4 py-3 font-medium">类型</th>
                  <th className="text-left px-4 py-3 font-medium">状态</th>
                  <th className="text-left px-4 py-3 font-medium">Chunks</th>
                  <th className="text-left px-4 py-3 font-medium">上传时间</th>
                  <th className="text-right px-4 py-3 font-medium">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-secondary)]">
                {docs.map((doc) => (
                  <tr key={doc.id} className="hover:bg-[var(--bg-secondary)] transition-colors">
                    <td className="px-4 py-3 text-[var(--text-primary)]">{doc.filename}</td>
                    <td className="px-4 py-3 text-[var(--text-secondary)]">{doc.file_type}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center gap-1.5 text-xs ${statusColors[doc.status] === 'bg-[var(--color-success)]' ? 'text-[var(--color-success)]' : 'text-[var(--text-tertiary)]'}`}>
                        <span className={`w-2 h-2 rounded-full ${statusColors[doc.status]}`} />
                        {statusLabels[doc.status] || doc.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-[var(--text-secondary)]">{doc.chunks_count}</td>
                    <td className="px-4 py-3 text-[var(--text-tertiary)] text-xs">
                      {new Date(doc.created_at).toLocaleString('zh-CN')}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button onClick={() => handleDelete(doc.id)} className="p-1.5 rounded text-[var(--text-tertiary)] hover:text-[var(--color-error)] transition-colors">
                        <IconTrash />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {docs.map((doc) => (
              <div key={doc.id} className="p-4 rounded-xl border border-[var(--border-primary)] hover:bg-[var(--bg-secondary)] transition-colors group">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-[var(--bg-tertiary)] flex items-center justify-center">
                      <IconFile className="text-[var(--text-tertiary)]" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-[var(--text-primary)]">{doc.filename}</p>
                      <p className="text-xs text-[var(--text-tertiary)]">{doc.file_type}</p>
                    </div>
                  </div>
                  <button onClick={() => handleDelete(doc.id)} className="p-1.5 rounded text-[var(--text-tertiary)] opacity-0 group-hover:opacity-100 hover:text-[var(--color-error)] transition-all">
                    <IconTrash />
                  </button>
                </div>
                <div className="flex items-center gap-3 mt-3 text-xs text-[var(--text-tertiary)]">
                  <span className={`inline-flex items-center gap-1`}>
                    <span className={`w-2 h-2 rounded-full ${statusColors[doc.status]}`} />
                    {statusLabels[doc.status] || doc.status}
                  </span>
                  {doc.status === 'ready' && <span>{doc.chunks_count} chunks</span>}
                  <span>{new Date(doc.created_at).toLocaleDateString('zh-CN')}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
