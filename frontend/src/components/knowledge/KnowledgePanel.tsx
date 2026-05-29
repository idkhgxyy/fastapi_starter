import { useState, useEffect, useRef, type ChangeEvent } from 'react'
import type { Document } from '@/types'
import { listDocuments, uploadDocument, deleteDocument, queryKnowledgeBase } from '@/services/ragService'
import { IconFile, IconUpload, IconTrash, IconSearch, IconRefresh, IconX } from '@/components/ui/Icons'

const statusLabels: Record<string, string> = {
  queued: '排队中',
  processing: '处理中',
  ready: '就绪',
  failed: '失败',
}

const statusColors: Record<string, string> = {
  queued: 'bg-[var(--text-tertiary)]',
  processing: 'bg-brand-500',
  ready: 'bg-[var(--color-success)]',
  failed: 'bg-[var(--color-error)]',
}

export default function KnowledgePanel() {
  const [documents, setDocuments] = useState<Document[]>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [query, setQuery] = useState('')
  const [queryResult, setQueryResult] = useState<{ answer: string; source_chunks: string[] } | null>(null)
  const [querying, setQuerying] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  async function loadDocs() {
    try {
      const data = await listDocuments()
      setDocuments(data)
    } catch {
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadDocs()
  }, [])

  async function handleUpload(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      await uploadDocument(file)
      await loadDocs()
    } catch {}
    if (fileRef.current) fileRef.current.value = ''
    setUploading(false)
  }

  async function handleDelete(id: number) {
    try {
      await deleteDocument(id)
      await loadDocs()
    } catch {}
  }

  async function handleQuery() {
    if (!query.trim() || querying) return
    setQuerying(true)
    setQueryResult(null)
    try {
      const result = await queryKnowledgeBase(query.trim())
      setQueryResult(result)
    } catch {
    } finally {
      setQuerying(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="relative">
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
          className="w-full border-2 border-dashed border-[var(--border-primary)] rounded-xl p-6 text-center hover:border-brand-500/50 transition-colors cursor-pointer disabled:opacity-50"
        >
          <IconUpload className="mx-auto mb-2 text-[var(--text-tertiary)]" />
          <p className="text-sm text-[var(--text-tertiary)]">
            {uploading ? '上传中...' : '点击上传文档'}
          </p>
          <p className="text-xs text-[var(--text-tertiary)] mt-1">支持 .txt .md .pdf</p>
        </button>
      </div>

      <div>
        <div className="relative">
          <IconSearch className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)]" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleQuery()}
            placeholder="搜索知识库..."
            className="w-full h-9 pl-9 pr-3 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition-colors"
          />
        </div>

        {querying && (
          <div className="mt-2 text-xs text-[var(--text-tertiary)] flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-brand-500 animate-pulse" />
            正在查询...
          </div>
        )}

        {queryResult && (
          <div className="mt-2 p-3 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)]">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-[var(--text-tertiary)] uppercase">查询结果</span>
              <button onClick={() => setQueryResult(null)} className="text-[var(--text-tertiary)] hover:text-[var(--text-primary)]">
                <IconX />
              </button>
            </div>
            <p className="text-sm text-[var(--text-primary)] leading-relaxed">{queryResult.answer}</p>
            {queryResult.source_chunks.length > 0 && (
              <div className="mt-2 pt-2 border-t border-[var(--border-primary)]">
                <p className="text-xs text-[var(--text-tertiary)] mb-1">来源片段 ({queryResult.source_chunks.length})</p>
                {queryResult.source_chunks.map((chunk, i) => (
                  <p key={i} className="text-xs text-[var(--text-tertiary)] mt-1 line-clamp-2">
                    [{i + 1}] {chunk}
                  </p>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-[var(--text-tertiary)] uppercase tracking-wider">
            文档列表
          </span>
          <button
            onClick={loadDocs}
            className="p-1 rounded text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] transition-colors"
          >
            <IconRefresh />
          </button>
        </div>

        {loading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-14 rounded-lg bg-[var(--bg-tertiary)] animate-pulse" />
            ))}
          </div>
        ) : documents.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-sm text-[var(--text-tertiary)]">暂无文档</p>
            <p className="text-xs text-[var(--text-tertiary)] mt-1">上传文档以开始构建知识库</p>
          </div>
        ) : (
          <div className="space-y-1">
            {documents.map((doc) => (
              <div key={doc.id} className="flex items-center gap-3 p-2.5 rounded-lg hover:bg-[var(--bg-tertiary)] transition-colors group">
                <div className="w-8 h-8 rounded-lg bg-[var(--bg-tertiary)] flex items-center justify-center shrink-0">
                  <IconFile className="text-[var(--text-tertiary)]" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-[var(--text-primary)] truncate">{doc.filename}</p>
                  <p className="text-xs text-[var(--text-tertiary)]">
                    {statusLabels[doc.status] || doc.status}
                    {doc.status === 'ready' && ` · ${doc.chunks_count} chunks`}
                  </p>
                </div>
                <span className={`w-2 h-2 rounded-full shrink-0 ${statusColors[doc.status] || statusColors.queued}`} />
                <button
                  onClick={() => handleDelete(doc.id)}
                  className="shrink-0 p-1 rounded text-[var(--text-tertiary)] opacity-0 group-hover:opacity-100 hover:text-[var(--color-error)] transition-all"
                >
                  <IconTrash />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
